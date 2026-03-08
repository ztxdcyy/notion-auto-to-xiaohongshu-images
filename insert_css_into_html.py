#!/usr/bin/env python3
# Run example:
# python3 insert_css_into_html.py 121/备用安卓机的好去处😄.html
from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Insert CSS link into HTML head.")
    parser.add_argument("html_path", type=Path, help="Path to target HTML file")
    parser.add_argument(
        "--css-href",
        default="../my.css",
        help='CSS href to insert (default: "../my.css")',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    html = args.html_path.expanduser().resolve()
    if not html.is_file():
        print(f"HTML not found: {html}")
        return 1

    s = html.read_text(encoding="utf-8", errors="ignore")
    link = f'<link rel="stylesheet" href="{args.css_href}"/>'

    if link in s:
        print("Already has the exact css link")
        return 0
    if ".css" in s and "<link" in s and args.css_href in s:
        print("Already has css link")
        return 0
    if "</head>" not in s:
        print("Cannot find </head> in HTML")
        return 1

    s = s.replace("</head>", f"{link}</head>", 1)
    html.write_text(s, encoding="utf-8")
    print("Inserted:", link)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
