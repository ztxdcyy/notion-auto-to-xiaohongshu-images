const $ = (id) => document.getElementById(id);

const dom = {
  htmlPath: $("htmlPath"),
  htmlDropzone: $("htmlDropzone"),
  btnPickHtml: $("btnPickHtml"),
  cssPath: $("cssPath"),
  sizePreset: $("sizePreset"),
  ratioHint: $("ratioHint"),
  width: $("width"),
  height: $("height"),
  sidePadding: $("sidePadding"),
  topPadding: $("topPadding"),
  bottomPadding: $("bottomPadding"),
  slicePadding: $("slicePadding"),
  cutMode: $("cutMode"),
  searchRange: $("searchRange"),
  minSegHeight: $("minSegHeight"),
  whiteThreshold: $("whiteThreshold"),
  whiteRowRatio: $("whiteRowRatio"),
  waitMs: $("waitMs"),
  previewSupersample: $("previewSupersample"),
  exportSupersample: $("exportSupersample"),
  exportSharpen: $("exportSharpen"),
  globalStatus: $("globalStatus"),
  btnPreview: $("btnPreview"),
  btnExport: $("btnExport"),
  btnOpenOutput: $("btnOpenOutput"),
  taskKind: $("taskKind"),
  taskState: $("taskState"),
  taskPages: $("taskPages"),
  taskOutput: $("taskOutput"),
  pages: $("pages"),
  previewMeta: $("previewMeta"),
};

let pollTimer = null;
let activeTaskId = null;
let latestExportTaskId = null;
const sizePresetMap = {
  "1200x1600": [1200, 1600],
  "1440x2400": [1440, 2400],
};

function setGlobalStatus(status, text) {
  dom.globalStatus.className = `status ${status}`;
  dom.globalStatus.textContent = text;
}

function syncPageAspect() {
  const w = Math.max(1, Number(dom.width.value) || 1);
  const h = Math.max(1, Number(dom.height.value) || 1);
  dom.pages.style.setProperty("--page-aspect", `${w} / ${h}`);
}

function disableActions(disabled) {
  dom.btnPreview.disabled = disabled;
  dom.btnExport.disabled = disabled;
}

async function loadParamMeta() {
  try {
    const resp = await fetch("/static/param_meta.json");
    if (!resp.ok) return;
    const meta = await resp.json();
    const params = meta?.params || {};

    document.querySelectorAll(".param-label[data-param-key]").forEach((label) => {
      const key = label.dataset.paramKey;
      const cfg = params[key];
      const titleEl = label.querySelector(".field-title");
      const helpDot = label.querySelector(".help-dot");
      if (!helpDot) return;

      // Default policy: no help => no question mark.
      helpDot.style.display = "none";
      helpDot.removeAttribute("data-tip");
      helpDot.removeAttribute("title");

      if (!cfg) return;

      if (titleEl && typeof cfg.label === "string" && cfg.label.trim()) {
        titleEl.textContent = cfg.label.trim();
      }

      const help = typeof cfg.help === "string" ? cfg.help.trim() : "";
      if (!help) {
        helpDot.style.display = "none";
      } else {
        helpDot.style.display = "inline-flex";
        helpDot.dataset.tip = help;
        helpDot.title = help;
      }
    });
  } catch {
    // ignore metadata load failure and keep inline labels as fallback
  }
}

function collectSettings() {
  return {
    size_preset: dom.sizePreset.value,
    width: Number(dom.width.value),
    height: Number(dom.height.value),
    side_padding: Number(dom.sidePadding.value),
    top_padding: Number(dom.topPadding.value),
    bottom_padding: Number(dom.bottomPadding.value),
    slice_padding: Number(dom.slicePadding.value),
    cut_mode: dom.cutMode.value,
    search_range: Number(dom.searchRange.value),
    min_segment_height: Number(dom.minSegHeight.value),
    white_threshold: Number(dom.whiteThreshold.value),
    white_row_ratio: Number(dom.whiteRowRatio.value),
    wait_ms: Number(dom.waitMs.value),
    preview_supersample: Number(dom.previewSupersample.value),
    export_supersample: Number(dom.exportSupersample.value),
    export_sharpen: Number(dom.exportSharpen.value),
  };
}

function collectPayload() {
  return {
    html_path: dom.htmlPath.value.trim(),
    css_path: dom.cssPath.value.trim() || null,
    settings: collectSettings(),
  };
}

function setDefaults(d) {
  dom.sizePreset.value = d.size_preset || detectSizePreset(Number(d.width) || 0, Number(d.height) || 0);
  dom.width.value = d.width;
  dom.height.value = d.height;
  dom.sidePadding.value = d.side_padding;
  dom.topPadding.value = d.top_padding;
  dom.bottomPadding.value = d.bottom_padding;
  dom.slicePadding.value = d.slice_padding;
  dom.cutMode.value = d.cut_mode;
  dom.searchRange.value = d.search_range;
  dom.minSegHeight.value = d.min_segment_height;
  dom.whiteThreshold.value = d.white_threshold;
  dom.whiteRowRatio.value = d.white_row_ratio;
  dom.waitMs.value = d.wait_ms;
  dom.previewSupersample.value = d.preview_supersample;
  dom.exportSupersample.value = d.export_supersample;
  dom.exportSharpen.value = d.export_sharpen;
  applySizePreset();
}

function detectSizePreset(width, height) {
  for (const [name, pair] of Object.entries(sizePresetMap)) {
    if (width === pair[0] && height === pair[1]) {
      return name;
    }
  }
  return "1440x2400";
}

function applySizePreset() {
  const preset = dom.sizePreset.value;
  const [width, height] = sizePresetMap[preset] || sizePresetMap["1440x2400"];
  dom.width.value = width;
  dom.height.value = height;
  dom.width.disabled = true;
  dom.height.disabled = true;
  dom.ratioHint.textContent = `已应用固定尺寸：${width} x ${height}`;
  syncPageAspect();
}

function showError(err) {
  const msg = String(err || "Error");
  setGlobalStatus("error", msg.length > 48 ? `${msg.slice(0, 45)}...` : msg);
}

async function api(path, method = "GET", body = null) {
  const resp = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : null,
  });
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`;
    try {
      const data = await resp.json();
      msg = data.detail || msg;
    } catch {
      // ignore
    }
    throw new Error(msg);
  }
  return resp.json();
}

function renderPages(pages) {
  dom.pages.innerHTML = "";
  if (!pages || pages.length === 0) {
    dom.previewMeta.textContent = "预览为空";
    return;
  }
  dom.previewMeta.textContent = `共 ${pages.length} 页（全文预览）`;

  for (const page of pages) {
    const card = document.createElement("article");
    card.className = "page-card";
    const title = document.createElement("h4");
    title.textContent = page.name;
    const frame = document.createElement("div");
    frame.className = "page-frame";
    const img = document.createElement("img");
    img.loading = "lazy";
    img.alt = page.name;
    img.src = `${page.url}?v=${Date.now()}`;
    img.addEventListener("load", () => {
      frame.style.animation = "none";
      frame.style.background = "#fff";
    });
    frame.appendChild(img);
    card.appendChild(title);
    card.appendChild(frame);
    dom.pages.appendChild(card);
  }
}

function updateTaskInfo(task) {
  dom.taskKind.textContent = task.kind || "-";
  dom.taskState.textContent = task.status || "-";
  const pageCount = task.result?.page_count ?? "-";
  dom.taskPages.textContent = String(pageCount);
  dom.taskOutput.textContent = task.result?.output_dir || "-";
}

async function pollTask(taskId) {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }

  pollTimer = setInterval(async () => {
    try {
      const task = await api(`/api/task/${taskId}`);
      updateTaskInfo(task);
      if (task.status === "running" || task.status === "queued") {
        setGlobalStatus("running", `${task.kind} running`);
        return;
      }
      clearInterval(pollTimer);
      pollTimer = null;
      disableActions(false);

      if (task.status === "success") {
        setGlobalStatus("success", `${task.kind} done`);
        if (task.kind === "preview") {
          renderPages(task.result?.pages || []);
        }
        if (task.kind === "export") {
          latestExportTaskId = task.id;
        }
      } else {
        setGlobalStatus("error", `${task.kind} failed`);
        showError(task.error || "unknown error");
      }
    } catch (err) {
      clearInterval(pollTimer);
      pollTimer = null;
      disableActions(false);
      showError(err.message || String(err));
    }
  }, 800);
}

async function startTask(kind) {
  try {
    const payload = collectPayload();
    if (!payload.html_path) {
      throw new Error("请先填写 HTML 路径");
    }

    disableActions(true);
    setGlobalStatus("running", `${kind} starting`);

    const endpoint = kind === "preview" ? "/api/preview" : "/api/export";
    const data = await api(endpoint, "POST", payload);
    activeTaskId = data.task_id;
    if (kind === "export") {
      latestExportTaskId = data.task_id;
    }
    await pollTask(activeTaskId);
  } catch (err) {
    disableActions(false);
    showError(err.message || String(err));
  }
}

async function openOutputDir() {
  try {
    if (!latestExportTaskId) {
      throw new Error("请先执行一次高清导出");
    }
    await api(`/api/open-output/${latestExportTaskId}`, "POST");
  } catch (err) {
    showError(err.message || String(err));
  }
}

async function bootstrap() {
  try {
    setGlobalStatus("idle", "Loading");
    const data = await api("/api/config");
    setDefaults(data.defaults);
    setGlobalStatus("idle", "Idle");
  } catch (err) {
    showError(err.message || String(err));
  }
}

async function pickHtmlByDialog() {
  try {
    const data = await api("/api/pick-html");
    if (data.path) {
      dom.htmlPath.value = data.path;
      setGlobalStatus("idle", "HTML selected");
    }
  } catch (err) {
    showError(err.message || String(err));
  }
}

function pathFromUri(uri) {
  if (!uri) return "";
  const clean = uri.split("\n")[0].trim();
  if (!clean) return "";
  if (clean.startsWith("file://")) {
    const u = new URL(clean);
    const path = decodeURIComponent(u.pathname);
    if (/^\/[A-Za-z]:\//.test(path)) {
      return path.slice(1);
    }
    return path;
  }
  return "";
}

function tryResolveDroppedPath(event) {
  const dt = event.dataTransfer;
  if (!dt) return "";

  const uriList = dt.getData("text/uri-list");
  const fromUri = pathFromUri(uriList);
  if (fromUri) return fromUri;

  const plain = dt.getData("text/plain")?.trim() || "";
  if (plain.endsWith(".html") || plain.endsWith(".htm")) return plain;

  const first = dt.files && dt.files[0];
  if (first && typeof first.path === "string" && first.path) {
    return first.path;
  }
  return "";
}

function bindDropzone() {
  const dz = dom.htmlDropzone;
  if (!dz) return;

  const onEnter = (ev) => {
    ev.preventDefault();
    dz.classList.add("dragover");
  };
  const onLeave = () => dz.classList.remove("dragover");
  const onOver = (ev) => ev.preventDefault();
  const onDrop = (ev) => {
    ev.preventDefault();
    dz.classList.remove("dragover");
    const path = tryResolveDroppedPath(ev);
    if (!path) {
      showError("无法从拖拽中读取文件路径，请使用“选择 HTML 文件”。");
      return;
    }
    dom.htmlPath.value = path;
    setGlobalStatus("idle", "HTML dropped");
  };

  dz.addEventListener("dragenter", onEnter);
  dz.addEventListener("dragover", onOver);
  dz.addEventListener("dragleave", onLeave);
  dz.addEventListener("drop", onDrop);
}

dom.btnPreview.addEventListener("click", () => startTask("preview"));
dom.btnExport.addEventListener("click", () => startTask("export"));
dom.btnOpenOutput.addEventListener("click", openOutputDir);
dom.btnPickHtml.addEventListener("click", pickHtmlByDialog);
dom.sizePreset.addEventListener("change", applySizePreset);

bootstrap();
loadParamMeta();
bindDropzone();
