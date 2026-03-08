#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./run_html_pipeline.sh 121/备用安卓机的好去处😄.html
#   ./run_html_pipeline.sh 121/备用安卓机的好去处😄.html /Users/tim/Downloads/my.css

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: $0 <html_path> [css_file_path]"
  exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
HTML_PATH="$1"
CSS_FILE="${2:-$SCRIPT_DIR/my.css}"

if [ ! -f "$HTML_PATH" ]; then
  echo "HTML not found: $HTML_PATH"
  exit 1
fi

if [ ! -f "$CSS_FILE" ]; then
  echo "CSS file not found: $CSS_FILE"
  exit 1
fi

# Compute css href relative to html folder (for <link href="...">).
CSS_HREF="$(python3 - <<'PY' "$HTML_PATH" "$CSS_FILE"
from pathlib import Path
import os
html = Path(__import__('sys').argv[1]).resolve()
css = Path(__import__('sys').argv[2]).resolve()
rel = os.path.relpath(css, start=html.parent).replace(os.sep, "/")
print(rel)
PY
)"

echo "[1/2] Insert CSS link: $CSS_HREF"
python3 "$SCRIPT_DIR/insert_css_into_html.py" "$HTML_PATH" --css-href "$CSS_HREF"

echo "[2/2] Render images"
python3 "$SCRIPT_DIR/html_to_image.py" "$HTML_PATH"

echo "Done."
