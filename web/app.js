const $ = (id) => document.getElementById(id);

const dom = {
  postTitle: $("postTitle"),
  sourceDropzone: $("sourceDropzone"),
  sourceFile: $("sourceFile"),
  btnPickSource: $("btnPickSource"),
  uploadProgressWrap: $("uploadProgressWrap"),
  uploadProgressFill: $("uploadProgressFill"),
  uploadProgressText: $("uploadProgressText"),
  sourceMeta: $("sourceMeta"),
  sizePreset: $("sizePreset"),
  ratioHint: $("ratioHint"),
  previewSupersample: $("previewSupersample"),
  exportSupersample: $("exportSupersample"),
  exportSharpen: $("exportSharpen"),
  themePreset: $("themePreset"),
  themeColor: $("themeColor"),
  cutMode: $("cutMode"),
  searchRange: $("searchRange"),
  minSegHeight: $("minSegHeight"),
  whiteThreshold: $("whiteThreshold"),
  whiteRowRatio: $("whiteRowRatio"),
  waitMs: $("waitMs"),
  globalStatus: $("globalStatus"),
  btnPreview: $("btnPreview"),
  btnExport: $("btnExport"),
  taskKind: $("taskKind"),
  taskState: $("taskState"),
  taskPages: $("taskPages"),
  taskOutput: $("taskOutput"),
  pages: $("pages"),
  previewMeta: $("previewMeta"),
};

let pollTimer = null;
let activeTaskId = null;
let activeSourceId = null;
let uploadingSource = false;

const sizePresetMap = {
  "1200x1600": [1200, 1600],
  "1440x2400": [1440, 2400],
};

const themePresetMap = {
  classic_blue: "#3d7eff",
  morandi_sage: "#8c9a8e",
  morandi_bluegray: "#7e8f9f",
  morandi_rose: "#b58f8a",
  morandi_khaki: "#b9a99a",
};

const uiFallbackDefaults = {
  size_preset: "1440x2400",
  width: 1440,
  height: 2400,
  side_padding: 56,
  top_padding: 64,
  bottom_padding: 72,
  slice_padding: 80,
  cut_mode: "smart",
  search_range: 220,
  min_segment_height: 1500,
  white_threshold: 245,
  white_row_ratio: 0.992,
  wait_ms: 800,
  preview_supersample: 1.2,
  export_supersample: 5.0,
  export_sharpen: 120,
  theme_color: "#3d7eff",
};

const inlineParamMetaFallback = {
  params: {
    cutMode: {
      label: "切分模式",
      help: "智能切分会优先在空白行附近落刀；硬切分按固定高度直接切。",
    },
    searchRange: {
      label: "搜索范围(px)",
      help: "智能切分在目标切点附近搜索空白行的范围。越大越容易找到自然断点，但更耗时。",
    },
    minSegHeight: {
      label: "最小分段高度(px)",
      help: "限制每段最小内容高度，避免切得过碎。",
    },
    whiteThreshold: {
      label: "空白阈值",
      help: "像素灰度阈值（0-255）。越高越严格地判定“白色”。",
    },
    whiteRowRatio: {
      label: "空白行比例",
      help: "一行中达到空白阈值像素的比例。越接近 1，越要求整行接近空白。",
    },
    waitMs: {
      label: "额外等待(ms)",
      help: "页面加载后额外等待时间，用于让字体和图片稳定渲染。",
    },
    previewSupersample: {
      label: "预览清晰度(倍率)",
      help: "预览阶段渲染倍率。越高预览越清晰，但速度更慢。",
    },
    exportSupersample: {
      label: "导出清晰度(倍率)",
      help: "正式导出渲染倍率。越高越清晰，也更耗时和资源。",
    },
    exportSharpen: {
      label: "导出锐化强度",
      help: "导出后锐化强度。0 表示不锐化。",
    },
    themePreset: {
      label: "主题色预设",
      help: "可选经典蓝与莫兰迪色系预设。选择后会自动同步到取色器。",
    },
    themeColor: {
      label: "主题色取色器",
      help: "支持手动选色。若颜色不在预设里，预设会自动切换为“自定义”。",
    },
    sizePreset: {
      label: "尺寸预设",
      help: "固定为两种模板：1200x1600（3:4 常规图文）与 1440x2400（满屏打开）。",
    },
  },
};

function setGlobalStatus(status, text) {
  dom.globalStatus.className = `status ${status}`;
  dom.globalStatus.textContent = text;
}

function getPresetSize() {
  return sizePresetMap[dom.sizePreset.value] || sizePresetMap["1440x2400"];
}

function normalizeHexColor(value) {
  const raw = String(value || "").trim();
  if (/^#[0-9a-fA-F]{6}$/.test(raw)) return raw.toLowerCase();
  return uiFallbackDefaults.theme_color;
}

function detectThemePreset(color) {
  const normalized = normalizeHexColor(color);
  for (const [preset, hex] of Object.entries(themePresetMap)) {
    if (hex.toLowerCase() === normalized) {
      return preset;
    }
  }
  return "custom";
}

function syncThemePresetFromColor() {
  if (!dom.themePreset || !dom.themeColor) return;
  dom.themePreset.value = detectThemePreset(dom.themeColor.value);
}

function syncPageAspect() {
  const [w, h] = getPresetSize();
  dom.pages.style.setProperty("--page-aspect", `${w} / ${h}`);
}

function disableActions(disabled) {
  dom.btnPreview.disabled = disabled;
  dom.btnExport.disabled = disabled;
}

function setUploadProgress(percent) {
  const val = Math.max(0, Math.min(100, Math.round(percent)));
  dom.uploadProgressWrap.classList.remove("hidden");
  dom.uploadProgressWrap.setAttribute("aria-hidden", "false");
  dom.uploadProgressFill.style.width = `${val}%`;
  dom.uploadProgressText.textContent = `${val}%`;
}

function setUploadingUI(isUploading) {
  uploadingSource = isUploading;
  dom.btnPickSource.disabled = isUploading;
  dom.sourceDropzone.classList.toggle("is-uploading", isUploading);
  dom.sourceDropzone.setAttribute("aria-busy", isUploading ? "true" : "false");
}

function showError(err) {
  const msg = String(err || "Error");
  setGlobalStatus("error", msg.length > 60 ? `${msg.slice(0, 57)}...` : msg);
}

async function loadParamMeta() {
  const applyMeta = (meta) => {
    const params = meta?.params || {};
    document.querySelectorAll(".param-label[data-param-key]").forEach((label) => {
      const key = label.dataset.paramKey;
      const cfg = params[key];
      const titleEl = label.querySelector(".field-title");
      const helpDot = label.querySelector(".help-dot");
      if (!helpDot) return;

      helpDot.style.display = "none";
      helpDot.removeAttribute("data-tip");
      helpDot.removeAttribute("title");

      if (!cfg) return;
      if (titleEl && typeof cfg.label === "string" && cfg.label.trim()) {
        titleEl.textContent = cfg.label.trim();
      }

      const help = typeof cfg.help === "string" ? cfg.help.trim() : "";
      if (!help) return;
      helpDot.style.display = "inline-flex";
      helpDot.dataset.tip = help;
      helpDot.title = help;
    });
  };

  try {
    const resp = await fetch("/static/param_meta.json", { cache: "no-store" });
    if (!resp.ok) {
      applyMeta(inlineParamMetaFallback);
      return;
    }
    const meta = await resp.json();
    applyMeta({ ...inlineParamMetaFallback, ...meta, params: { ...inlineParamMetaFallback.params, ...(meta?.params || {}) } });
  } catch {
    applyMeta(inlineParamMetaFallback);
  }
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
  const [width, height] = getPresetSize();
  dom.ratioHint.textContent = `当前尺寸：${width} x ${height}`;
  syncPageAspect();
}

function setDefaults(d) {
  const preset = d.size_preset || detectSizePreset(Number(d.width) || 0, Number(d.height) || 0);
  dom.sizePreset.value = sizePresetMap[preset] ? preset : "1440x2400";
  if (dom.previewSupersample) dom.previewSupersample.value = d.preview_supersample ?? uiFallbackDefaults.preview_supersample;
  if (dom.exportSupersample) dom.exportSupersample.value = d.export_supersample ?? uiFallbackDefaults.export_supersample;
  if (dom.exportSharpen) dom.exportSharpen.value = d.export_sharpen ?? uiFallbackDefaults.export_sharpen;
  if (dom.cutMode) dom.cutMode.value = d.cut_mode ?? uiFallbackDefaults.cut_mode;
  if (dom.searchRange) dom.searchRange.value = d.search_range ?? uiFallbackDefaults.search_range;
  if (dom.minSegHeight) dom.minSegHeight.value = d.min_segment_height ?? uiFallbackDefaults.min_segment_height;
  if (dom.whiteThreshold) dom.whiteThreshold.value = d.white_threshold ?? uiFallbackDefaults.white_threshold;
  if (dom.whiteRowRatio) dom.whiteRowRatio.value = d.white_row_ratio ?? uiFallbackDefaults.white_row_ratio;
  if (dom.waitMs) dom.waitMs.value = d.wait_ms ?? uiFallbackDefaults.wait_ms;
  if (dom.themeColor) dom.themeColor.value = normalizeHexColor(d.theme_color ?? uiFallbackDefaults.theme_color);
  if (dom.themePreset) dom.themePreset.value = detectThemePreset(dom.themeColor ? dom.themeColor.value : uiFallbackDefaults.theme_color);
  applySizePreset();
}

function collectSettings() {
  const [width, height] = getPresetSize();
  const settings = { ...uiFallbackDefaults };
  if (dom.previewSupersample) settings.preview_supersample = Number(dom.previewSupersample.value) || uiFallbackDefaults.preview_supersample;
  if (dom.exportSupersample) settings.export_supersample = Number(dom.exportSupersample.value) || uiFallbackDefaults.export_supersample;
  if (dom.exportSharpen) settings.export_sharpen = Number(dom.exportSharpen.value) || uiFallbackDefaults.export_sharpen;
  if (dom.cutMode && (dom.cutMode.value === "smart" || dom.cutMode.value === "hard")) settings.cut_mode = dom.cutMode.value;
  if (dom.searchRange) settings.search_range = Number(dom.searchRange.value) || uiFallbackDefaults.search_range;
  if (dom.minSegHeight) settings.min_segment_height = Number(dom.minSegHeight.value) || uiFallbackDefaults.min_segment_height;
  if (dom.whiteThreshold) settings.white_threshold = Number(dom.whiteThreshold.value) || uiFallbackDefaults.white_threshold;
  if (dom.whiteRowRatio) settings.white_row_ratio = Number(dom.whiteRowRatio.value) || uiFallbackDefaults.white_row_ratio;
  if (dom.waitMs) settings.wait_ms = Number(dom.waitMs.value) || uiFallbackDefaults.wait_ms;
  if (dom.themeColor) settings.theme_color = normalizeHexColor(dom.themeColor.value);
  return {
    ...settings,
    size_preset: dom.sizePreset.value,
    width,
    height,
  };
}

function collectPayload() {
  return {
    source_id: activeSourceId,
    settings: collectSettings(),
  };
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

function uploadSourceWithProgress(file) {
  return new Promise((resolve, reject) => {
    const fd = new FormData();
    fd.append("source_file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload-source");
    xhr.responseType = "json";

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      setUploadProgress((event.loaded / event.total) * 100);
    };

    xhr.onerror = () => reject(new Error("上传失败：网络异常"));
    xhr.onabort = () => reject(new Error("上传已取消"));
    xhr.onload = () => {
      const data = xhr.response;
      if (xhr.status >= 200 && xhr.status < 300 && data) {
        setUploadProgress(100);
        resolve(data);
        return;
      }
      const detail = data && typeof data.detail === "string" ? data.detail : `HTTP ${xhr.status}`;
      reject(new Error(detail));
    };

    xhr.send(fd);
  });
}

function isAllowedSourceFile(file) {
  if (!file) return false;
  const name = (file.name || "").toLowerCase();
  return name.endsWith(".zip") || name.endsWith(".html") || name.endsWith(".htm");
}

async function uploadSource(file) {
  if (uploadingSource) return;
  if (!isAllowedSourceFile(file)) {
    throw new Error("仅支持 .zip / .html / .htm");
  }

  setUploadingUI(true);
  setUploadProgress(0);
  setGlobalStatus("running", "uploading source");
  dom.sourceMeta.textContent = "上传中";

  try {
    const data = await uploadSourceWithProgress(file);
    activeSourceId = data.source_id;
    dom.sourceMeta.textContent = "上传完成";
    dom.postTitle.textContent = data.html_title || "未命名帖子";
    setGlobalStatus("success", "source ready");
  } finally {
    setUploadingUI(false);
    dom.sourceFile.value = "";
  }
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
    if (!payload.source_id) {
      throw new Error("请先上传并解析源文件");
    }

    disableActions(true);
    setGlobalStatus("running", `${kind} starting`);

    const endpoint = kind === "preview" ? "/api/preview" : "/api/export";
    const data = await api(endpoint, "POST", payload);
    activeTaskId = data.task_id;
    await pollTask(activeTaskId);
  } catch (err) {
    disableActions(false);
    showError(err.message || String(err));
  }
}

function bindSourceDropzone() {
  const dz = dom.sourceDropzone;
  if (!dz) return;

  const openPicker = () => {
    if (!uploadingSource) {
      dom.sourceFile.click();
    }
  };

  dz.addEventListener("click", (ev) => {
    if (ev.target === dom.btnPickSource) return;
    openPicker();
  });
  dz.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      openPicker();
    }
  });

  dom.btnPickSource.addEventListener("click", openPicker);

  dz.addEventListener("dragenter", (ev) => {
    ev.preventDefault();
    dz.classList.add("dragover");
  });
  dz.addEventListener("dragover", (ev) => {
    ev.preventDefault();
    dz.classList.add("dragover");
  });
  dz.addEventListener("dragleave", () => dz.classList.remove("dragover"));
  dz.addEventListener("drop", async (ev) => {
    ev.preventDefault();
    dz.classList.remove("dragover");
    const file = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
    if (!file) return;
    activeSourceId = null;
    try {
      await uploadSource(file);
    } catch (err) {
      dom.sourceMeta.textContent = "上传失败";
      showError(err.message || String(err));
    }
  });

  dom.sourceFile.addEventListener("change", async () => {
    const file = dom.sourceFile.files && dom.sourceFile.files[0];
    if (!file) return;
    activeSourceId = null;
    try {
      await uploadSource(file);
    } catch (err) {
      dom.sourceMeta.textContent = "上传失败";
      showError(err.message || String(err));
    }
  });
}

async function bootstrap() {
  try {
    setGlobalStatus("idle", "Loading");
    setDefaults(uiFallbackDefaults);
    const data = await api("/api/config");
    setDefaults(data.defaults);
    setGlobalStatus("idle", "Idle");
  } catch {
    setDefaults(uiFallbackDefaults);
    setGlobalStatus("idle", "Idle");
  }
}

dom.btnPreview.addEventListener("click", () => startTask("preview"));
dom.btnExport.addEventListener("click", () => startTask("export"));
dom.sizePreset.addEventListener("change", applySizePreset);
if (dom.themePreset) {
  dom.themePreset.addEventListener("change", () => {
    if (!dom.themeColor) return;
    const hex = themePresetMap[dom.themePreset.value];
    if (hex) {
      dom.themeColor.value = hex;
    }
  });
}
if (dom.themeColor) {
  dom.themeColor.addEventListener("input", () => {
    dom.themeColor.value = normalizeHexColor(dom.themeColor.value);
    syncThemePresetFromColor();
  });
}

bootstrap();
loadParamMeta();
bindSourceDropzone();
