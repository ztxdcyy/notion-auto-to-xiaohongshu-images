#!/usr/bin/env python3
"""Cross-platform pipeline runner for HTML -> mobile images.

Usage:
  python run_html_pipeline.py <html_path> [css_file_path]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inject CSS into HTML and render mobile images."
    )
    parser.add_argument("html_path", type=Path, help="Path to source HTML file")
    parser.add_argument(
        "css_file_path",
        nargs="?",
        type=Path,
        default=None,
        help="Optional CSS file path (default: <project>/my.css)",
    )
    return parser.parse_args()


def run_step(cmd: list[str]) -> None:
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    html_path = args.html_path.expanduser().resolve()
    css_file = (
        args.css_file_path.expanduser().resolve()
        if args.css_file_path is not None
        else (script_dir / "my.css").resolve()
    )

    if not html_path.is_file():
        print(f"HTML not found: {html_path}")
        return 1
    if not css_file.is_file():
        print(f"CSS file not found: {css_file}")
        return 1

    css_href = os.path.relpath(css_file, start=html_path.parent).replace(os.sep, "/")
    py = sys.executable

    print(f"[1/2] Insert CSS link: {css_href}", flush=True)
    run_step(
        [
            py,
            str(script_dir / "insert_css_into_html.py"),
            str(html_path),
            "--css-href",
            css_href,
        ]
    )

    print("[2/2] Render images", flush=True)
    run_step([py, str(script_dir / "html_to_image.py"), str(html_path)])
    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
