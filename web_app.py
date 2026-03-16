#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import threading
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent
WEB_ROOT = PROJECT_ROOT / "web"
RUNS_ROOT = PROJECT_ROOT / ".web_runs"
RUNS_ROOT.mkdir(parents=True, exist_ok=True)

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


class RunRequest(BaseModel):
    html_path: str
    css_path: str | None = None
    settings: RenderSettings = Field(default_factory=RenderSettings)


class TaskStartResponse(BaseModel):
    task_id: str


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


def resolve_input_paths(req: RunRequest) -> tuple[Path, Path, str]:
    html_raw = req.html_path.strip().strip('"').strip("'")
    html_path = Path(html_raw).expanduser().resolve()
    if not html_path.is_file():
        raise ValueError(f"HTML not found: {html_path}")

    css_path = (
        Path(req.css_path.strip().strip('"').strip("'")).expanduser().resolve()
        if req.css_path and req.css_path.strip()
        else (PROJECT_ROOT / "my.css").resolve()
    )
    if not css_path.is_file():
        raise ValueError(f"CSS not found: {css_path}")

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
        "--no-open-preview",
    ]


def list_page_urls(output_dir: Path) -> list[dict]:
    pages = sorted(output_dir.glob("page_*.png"))
    out: list[dict] = []
    for p in pages:
        rel = p.resolve().relative_to(RUNS_ROOT.resolve()).as_posix()
        out.append(
            {
                "name": p.name,
                "url": f"/runs/{rel}",
            }
        )
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


@app.get("/api/pick-html")
def api_pick_html() -> dict:
    # macOS: use native Finder dialog via AppleScript (more reliable than tkinter in worker threads).
    if sys.platform == "darwin":
        script = (
            'set f to choose file with prompt "选择 HTML 文件" '
            'of type {"html", "htm"}\n'
            "POSIX path of f"
        )
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            err = (proc.stderr or "").strip().lower()
            if "user canceled" in err:
                raise HTTPException(status_code=400, detail="no file selected")
            raise HTTPException(status_code=500, detail=f"picker failed: {proc.stderr.strip()}")
        path = (proc.stdout or "").strip()
        if not path:
            raise HTTPException(status_code=400, detail="no file selected")
        return {"path": str(Path(path).expanduser().resolve())}

    # Other platforms: fallback to tkinter.
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"tkinter unavailable: {exc}") from exc

    root = tk.Tk()
    root.withdraw()
    root.update()
    path = filedialog.askopenfilename(
        title="选择 HTML 文件",
        filetypes=[("HTML files", "*.html *.htm"), ("All files", "*.*")],
    )
    root.destroy()
    if not path:
        raise HTTPException(status_code=400, detail="no file selected")
    return {"path": str(Path(path).expanduser().resolve())}


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


@app.post("/api/open-output/{task_id}")
def api_open_output(task_id: str) -> dict:
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="task not found")
        result = task.get("result") or {}
        output_dir = str(result.get("output_dir", "")).strip()

    if not output_dir:
        raise HTTPException(status_code=400, detail="no output directory yet")
    path = Path(output_dir).expanduser().resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail="output directory not found")

    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    elif sys.platform.startswith("win"):
        subprocess.Popen(["explorer", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])

    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    if os.environ.get("WEBAPP_NO_OPEN") != "1":
        threading.Timer(0.9, lambda: webbrowser.open("http://127.0.0.1:8123")).start()
    uvicorn.run("web_app:app", host="127.0.0.1", port=8123, reload=True)
