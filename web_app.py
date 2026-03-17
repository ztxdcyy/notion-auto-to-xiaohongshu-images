#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import uuid
import webbrowser
import zipfile
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent
WEB_ROOT = PROJECT_ROOT / "web"
RUNS_ROOT = PROJECT_ROOT / ".web_runs"
SOURCES_ROOT = RUNS_ROOT / "sources"
RUNS_ROOT.mkdir(parents=True, exist_ok=True)
SOURCES_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Notion HTML to Mobile Images Web App")
app.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")
app.mount("/runs", StaticFiles(directory=RUNS_ROOT), name="runs")

SIZE_PRESETS: dict[str, tuple[int, int]] = {
    "1200x1600": (1200, 1600),
    "1440x2400": (1440, 2400),
}


class RenderSettings(BaseModel):
    size_preset: Literal["1200x1600", "1440x2400"] = "1440x2400"
    width: int = 1440
    height: int = 2400
    side_padding: int = 56
    top_padding: int = 64
    bottom_padding: int = 72
    slice_padding: int = 80
    cut_mode: Literal["smart", "hard"] = "smart"
    search_range: int = 220
    white_threshold: int = 245
    white_row_ratio: float = 0.992
    min_segment_height: int = 1500
    wait_ms: int = 800
    preview_supersample: float = 1.2
    preview_max_pages: int = 0
    export_supersample: float = 5.0
    export_sharpen: int = 120
    theme_color: str = "#3d7eff"


class RunRequest(BaseModel):
    source_id: str
    settings: RenderSettings = Field(default_factory=RenderSettings)


class TaskStartResponse(BaseModel):
    task_id: str


class UploadSourceResponse(BaseModel):
    source_id: str
    source_name: str
    html_title: str


TASKS: dict[str, dict] = {}
TASKS_LOCK = threading.Lock()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_task(kind: Literal["preview", "export"]) -> str:
    task_id = uuid.uuid4().hex[:12]
    with TASKS_LOCK:
        TASKS[task_id] = {
            "id": task_id,
            "kind": kind,
            "status": "queued",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "logs": [],
            "error": None,
            "result": None,
        }
    return task_id


def update_task(task_id: str, **patch: object) -> None:
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if not task:
            return
        task.update(patch)
        task["updated_at"] = now_iso()


def append_log(task_id: str, message: str) -> None:
    clean = message.rstrip("\n")
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if not task:
            return
        task["logs"].append(clean)
        if len(task["logs"]) > 600:
            task["logs"] = task["logs"][-600:]
        task["updated_at"] = now_iso()


def _meta_path(source_dir: Path) -> Path:
    return source_dir / "source_meta.json"


def _safe_filename(name: str, fallback: str) -> str:
    base = Path(name or "").name
    cleaned = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]", "_", base)
    return cleaned or fallback


def _save_upload(upload: UploadFile, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("wb") as f:
        upload.file.seek(0)
        shutil.copyfileobj(upload.file, f)


def _safe_extract_zip(zip_path: Path, dst_dir: Path) -> None:
    dst_dir = dst_dir.resolve()
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            target = (dst_dir / member.filename).resolve()
            if not str(target).startswith(str(dst_dir)):
                raise ValueError("zip contains unsafe path")
        zf.extractall(dst_dir)


def _pick_html_file(root: Path) -> Path:
    candidates = [
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".html", ".htm"}
    ]
    if not candidates:
        raise ValueError("No .html file found in uploaded source")
    candidates.sort(key=lambda p: (len(p.relative_to(root).parts), len(str(p.relative_to(root)))))
    return candidates[0]


def _extract_html_title(html_path: Path) -> str:
    try:
        text = html_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return html_path.stem
    m = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return html_path.stem
    title = re.sub(r"\s+", " ", unescape(m.group(1))).strip()
    return title or html_path.stem


def resolve_input_paths(req: RunRequest) -> tuple[Path, Path, str]:
    source_id = (req.source_id or "").strip()
    if not re.fullmatch(r"[0-9a-f]{12}", source_id):
        raise ValueError("Invalid source_id")

    source_dir = (SOURCES_ROOT / source_id).resolve()
    if not source_dir.exists():
        raise ValueError("source_id not found; please re-upload")

    meta_file = _meta_path(source_dir)
    if not meta_file.is_file():
        raise ValueError("source metadata missing; please re-upload")

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    html_rel = str(meta.get("html_rel", "")).strip()
    css_rel = str(meta.get("css_rel", "")).strip()
    if not html_rel or not css_rel:
        raise ValueError("source metadata incomplete")

    html_path = (source_dir / html_rel).resolve()
    css_path = (source_dir / css_rel).resolve()
    if not html_path.is_file():
        raise ValueError("HTML source missing; please re-upload")
    if not css_path.is_file():
        raise ValueError("CSS source missing; please re-upload")

    css_href = os.path.relpath(css_path, start=html_path.parent).replace(os.sep, "/")
    return html_path, css_path, css_href


def run_command_stream(task_id: str, cmd: list[str]) -> list[str]:
    append_log(task_id, f"$ {shlex.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    lines: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        lines.append(line.rstrip("\n"))
        append_log(task_id, line.rstrip("\n"))
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f"Command failed with code {code}")
    return lines


def build_common_render_args(settings: RenderSettings) -> list[str]:
    theme_color = settings.theme_color.strip() if isinstance(settings.theme_color, str) else ""
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", theme_color):
        theme_color = "#3d7eff"

    width, height = SIZE_PRESETS.get(settings.size_preset, SIZE_PRESETS["1440x2400"])
    return [
        "--width",
        str(width),
        "--height",
        str(height),
        "--side-padding",
        str(settings.side_padding),
        "--top-padding",
        str(settings.top_padding),
        "--bottom-padding",
        str(settings.bottom_padding),
        "--slice-padding",
        str(settings.slice_padding),
        "--cut-mode",
        settings.cut_mode,
        "--search-range",
        str(settings.search_range),
        "--white-threshold",
        str(settings.white_threshold),
        "--white-row-ratio",
        str(settings.white_row_ratio),
        "--min-segment-height",
        str(settings.min_segment_height),
        "--wait-ms",
        str(settings.wait_ms),
        "--theme-color",
        theme_color.lower(),
    ]


def list_page_urls(output_dir: Path) -> list[dict]:
    pages = sorted(output_dir.glob("page_*.png"))
    out: list[dict] = []
    for p in pages:
        rel = p.resolve().relative_to(RUNS_ROOT.resolve()).as_posix()
        out.append({"name": p.name, "url": f"/runs/{rel}"})
    return out


def parse_export_result(lines: list[str]) -> tuple[int, Path | None]:
    page_count = 0
    output_dir: Path | None = None
    pattern = re.compile(r"Done\. Exported (\d+) image\(s\) to (.+)$")
    for line in lines:
        m = pattern.search(line)
        if m:
            page_count = int(m.group(1))
            output_dir = Path(m.group(2).strip())
    return page_count, output_dir


def run_preview_task(task_id: str, req: RunRequest) -> None:
    try:
        update_task(task_id, status="running")
        html_path, _css_path, css_href = resolve_input_paths(req)
        settings = req.settings
        py = sys.executable

        preview_dir = RUNS_ROOT / "preview_current"
        preview_dir.mkdir(parents=True, exist_ok=True)
        for old in preview_dir.glob("page_*.png"):
            old.unlink()

        run_command_stream(
            task_id,
            [
                py,
                str(PROJECT_ROOT / "insert_css_into_html.py"),
                str(html_path),
                "--css-href",
                css_href,
            ],
        )

        render_cmd = [
            py,
            str(PROJECT_ROOT / "html_to_image.py"),
            str(html_path),
            "--output-dir",
            str(preview_dir),
            "--supersample",
            str(settings.preview_supersample),
            "--sharpen",
            "0",
            *build_common_render_args(settings),
        ]
        if settings.preview_max_pages > 0:
            render_cmd.extend(["--max-pages", str(settings.preview_max_pages)])
        run_command_stream(task_id, render_cmd)

        pages = list_page_urls(preview_dir)
        update_task(
            task_id,
            status="success",
            result={
                "output_dir": str(preview_dir),
                "page_count": len(pages),
                "pages": pages,
            },
        )
    except Exception as exc:
        update_task(task_id, status="error", error=str(exc))


def run_export_task(task_id: str, req: RunRequest) -> None:
    try:
        update_task(task_id, status="running")
        html_path, _css_path, css_href = resolve_input_paths(req)
        settings = req.settings
        py = sys.executable

        run_command_stream(
            task_id,
            [
                py,
                str(PROJECT_ROOT / "insert_css_into_html.py"),
                str(html_path),
                "--css-href",
                css_href,
            ],
        )

        lines = run_command_stream(
            task_id,
            [
                py,
                str(PROJECT_ROOT / "html_to_image.py"),
                str(html_path),
                "--supersample",
                str(settings.export_supersample),
                "--sharpen",
                str(settings.export_sharpen),
                *build_common_render_args(settings),
            ],
        )
        page_count, output_dir = parse_export_result(lines)
        if output_dir and output_dir.exists():
            real_count = len(list(output_dir.glob("page_*.png")))
            if real_count > 0:
                page_count = real_count
        update_task(
            task_id,
            status="success",
            result={
                "output_dir": str(output_dir) if output_dir else "",
                "page_count": page_count,
            },
        )
    except Exception as exc:
        update_task(task_id, status="error", error=str(exc))


@app.get("/")
def home() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")


@app.get("/api/config")
def api_config() -> dict:
    defaults = RenderSettings()
    width, height = SIZE_PRESETS.get(defaults.size_preset, SIZE_PRESETS["1440x2400"])
    defaults.width = width
    defaults.height = height
    as_dict = defaults.model_dump() if hasattr(defaults, "model_dump") else defaults.dict()
    return {"defaults": as_dict}


@app.post("/api/upload-source", response_model=UploadSourceResponse)
async def api_upload_source(
    source_file: UploadFile = File(...),
    css_file: UploadFile | None = File(None),
) -> UploadSourceResponse:
    source_name = source_file.filename or "source"
    ext = Path(source_name).suffix.lower()
    if ext not in {".zip", ".html", ".htm"}:
        raise HTTPException(status_code=400, detail="source_file must be .zip or .html")

    css_ext = Path(css_file.filename or "").suffix.lower() if css_file else ""
    if css_file and css_ext != ".css":
        raise HTTPException(status_code=400, detail="css_file must be .css")

    source_id = uuid.uuid4().hex[:12]
    source_dir = SOURCES_ROOT / source_id
    payload_dir = source_dir / "payload"

    try:
        payload_dir.mkdir(parents=True, exist_ok=True)

        if ext == ".zip":
            zip_path = payload_dir / "source.zip"
            _save_upload(source_file, zip_path)
            _safe_extract_zip(zip_path, payload_dir)
            zip_path.unlink(missing_ok=True)
            try:
                html_path = _pick_html_file(payload_dir)
            except ValueError:
                # Some users upload a wrapper zip that contains exactly one inner zip.
                nested_zips = [p for p in payload_dir.rglob("*.zip") if p.is_file()]
                if len(nested_zips) != 1:
                    raise
                inner_zip = nested_zips[0]
                inner_extract_dir = inner_zip.with_suffix("")
                inner_extract_dir.mkdir(parents=True, exist_ok=True)
                _safe_extract_zip(inner_zip, inner_extract_dir)
                inner_zip.unlink(missing_ok=True)
                html_path = _pick_html_file(payload_dir)
        else:
            html_name = _safe_filename(source_name, "post.html")
            html_path = payload_dir / html_name
            _save_upload(source_file, html_path)

        if css_file:
            css_name = _safe_filename(css_file.filename or "custom.css", "custom.css")
            css_path = source_dir / css_name
            _save_upload(css_file, css_path)
        else:
            css_path = source_dir / "my.css"
            shutil.copy2(PROJECT_ROOT / "my.css", css_path)

        title = _extract_html_title(html_path)
        meta = {
            "source_name": source_name,
            "html_title": title,
            "html_rel": html_path.resolve().relative_to(source_dir.resolve()).as_posix(),
            "css_rel": css_path.resolve().relative_to(source_dir.resolve()).as_posix(),
        }
        _meta_path(source_dir).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return UploadSourceResponse(
            source_id=source_id,
            source_name=source_name,
            html_title=title,
        )
    except HTTPException:
        shutil.rmtree(source_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(source_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"upload failed: {exc}") from exc


@app.post("/api/preview", response_model=TaskStartResponse)
def api_preview(req: RunRequest) -> TaskStartResponse:
    try:
        resolve_input_paths(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    task_id = create_task("preview")
    threading.Thread(target=run_preview_task, args=(task_id, req), daemon=True).start()
    return TaskStartResponse(task_id=task_id)


@app.get("/api/preview/pages")
def api_preview_pages() -> dict:
    preview_dir = RUNS_ROOT / "preview_current"
    if not preview_dir.exists():
        return {"page_count": 0, "pages": []}
    pages = list_page_urls(preview_dir)
    return {"page_count": len(pages), "pages": pages}


@app.post("/api/export", response_model=TaskStartResponse)
def api_export(req: RunRequest) -> TaskStartResponse:
    try:
        resolve_input_paths(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    task_id = create_task("export")
    threading.Thread(target=run_export_task, args=(task_id, req), daemon=True).start()
    return TaskStartResponse(task_id=task_id)


@app.get("/api/task/{task_id}")
def api_task(task_id: str) -> dict:
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="task not found")
        return task


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8123"))
    host = os.environ.get("WEBAPP_HOST", "0.0.0.0")
    if os.environ.get("WEBAPP_NO_OPEN") != "1" and host in {"127.0.0.1", "localhost"}:
        threading.Timer(0.9, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    uvicorn.run("web_app:app", host=host, port=port, reload=False)
