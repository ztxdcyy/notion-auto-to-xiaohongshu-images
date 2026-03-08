#!/usr/bin/env python3
# Run example:
# python3 html_to_image.py 121/备用安卓机的好去处😄.html
from __future__ import annotations

import argparse
import asyncio
import math
import re
from html import unescape
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageFilter
from playwright.async_api import async_playwright


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render HTML+CSS into fixed 1400x2400 mobile images."
    )
    parser.add_argument("html", type=Path, help="Input HTML file path")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (optional, default: images_<post_title>)",
    )
    parser.add_argument("--width", type=int, default=1400, help="Final page width")
    parser.add_argument("--height", type=int, default=2400, help="Final page height")
    parser.add_argument(
        "--supersample",
        type=float,
        default=4.0,
        help="Render DPR before downscaling. Higher is sharper but slower/larger.",
    )
    parser.add_argument(
        "--side-padding",
        type=int,
        default=56,
        help="Left/right page padding in CSS px",
    )
    parser.add_argument(
        "--top-padding",
        type=int,
        default=64,
        help="Top page padding in CSS px",
    )
    parser.add_argument(
        "--bottom-padding",
        type=int,
        default=72,
        help="Bottom page padding in CSS px",
    )
    parser.add_argument(
        "--wait-ms",
        type=int,
        default=800,
        help="Extra wait for fonts/images after network idle",
    )
    parser.add_argument(
        "--sharpen",
        type=int,
        default=120,
        help="Unsharp mask percent after downscale. 0 disables.",
    )
    parser.add_argument(
        "--cut-mode",
        choices=["smart", "hard"],
        default="smart",
        help="smart: search blank rows near target; hard: fixed-height cuts.",
    )
    parser.add_argument(
        "--search-range",
        type=int,
        default=220,
        help="Smart mode: search range (+/- css px) around target cut.",
    )
    parser.add_argument(
        "--white-threshold",
        type=int,
        default=245,
        help="Smart mode: grayscale threshold to treat a pixel as white.",
    )
    parser.add_argument(
        "--white-row-ratio",
        type=float,
        default=0.992,
        help="Smart mode: row white ratio threshold.",
    )
    parser.add_argument(
        "--min-segment-height",
        type=int,
        default=1500,
        help="Smart mode: minimal segment height in css px.",
    )
    parser.add_argument(
        "--slice-padding",
        type=int,
        default=80,
        help="Top/bottom white padding added to each output slice (px)",
    )
    return parser.parse_args()


def build_override_css(args: argparse.Namespace) -> str:
    return f"""
html, body {{
  margin: 0 !important;
  padding: 0 !important;
  background: #ffffff !important;
}}
@media only screen {{
  body {{
    max-width: none !important;
    margin: 0 auto !important;
  }}
}}
body {{
  width: {args.width}px !important;
  box-sizing: border-box !important;
  padding: {args.top_padding}px {args.side_padding}px {args.bottom_padding}px !important;
}}
article.page,
.page-body {{
  width: 100% !important;
  max-width: none !important;
}}
img {{
  max-width: 100% !important;
  height: auto !important;
}}
"""


def downscale_to_final(
    png_bytes: bytes, final_size: tuple[int, int], sharpen: int
) -> Image.Image:
    img = Image.open(BytesIO(png_bytes)).convert("RGB")
    out = img.resize(final_size, Image.Resampling.LANCZOS)
    if sharpen > 0:
        out = out.filter(
            ImageFilter.UnsharpMask(radius=1.1, percent=sharpen, threshold=3)
        )
    return out


def infer_post_title(html_path: Path) -> str:
    source = html_path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"<title[^>]*>(.*?)</title>", source, flags=re.IGNORECASE | re.DOTALL)
    if match:
        title = unescape(match.group(1)).strip()
    else:
        title = html_path.stem.strip()

    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r'[\\/:*?"<>|]+', "_", title)
    return title or html_path.stem


def _best_white_row(gray_roi: Image.Image, threshold: int, ratio: float, target_row: int) -> int | None:
    width, height = gray_roi.size
    if width <= 0 or height <= 0:
        return None

    data = gray_roi.tobytes()
    mv = memoryview(data)
    candidates: list[int] = []
    for row in range(height):
        start = row * width
        end = start + width
        row_mv = mv[start:end]
        white = 0
        for px in row_mv:
            if px >= threshold:
                white += 1
        if white / width >= ratio:
            candidates.append(row)

    if not candidates:
        return None
    return min(candidates, key=lambda r: abs(r - target_row))


async def find_smart_cut(
    page,
    args: argparse.Namespace,
    current_y: int,
    full_height: int,
    content_h: int,
) -> int:
    target = current_y + content_h
    lo = max(current_y + args.min_segment_height, target - args.search_range)
    hi = min(full_height, target + args.search_range)
    if hi - lo < 8:
        return min(full_height, target)

    clip_h = hi - lo
    strip_png = await page.screenshot(
        type="png",
        full_page=True,
        clip={"x": 0, "y": lo, "width": args.width, "height": clip_h},
    )
    strip = Image.open(BytesIO(strip_png)).convert("L")

    scan_pad_css = max(0, args.side_padding + 4)
    left = int(round(scan_pad_css * args.supersample))
    right = int(round((args.width - scan_pad_css) * args.supersample))
    left = max(0, min(left, strip.width - 1))
    right = max(left + 1, min(right, strip.width))
    roi = strip.crop((left, 0, right, strip.height))

    target_row = int(round((target - lo) * args.supersample))
    best_row = _best_white_row(
        gray_roi=roi,
        threshold=args.white_threshold,
        ratio=args.white_row_ratio,
        target_row=target_row,
    )
    if best_row is None:
        return min(full_height, target)

    cut = lo + int(round(best_row / args.supersample))
    cut = max(current_y + 1, min(cut, full_height))
    return cut


async def export_pages(args: argparse.Namespace) -> tuple[Path, int]:
    html_path = args.html.expanduser().resolve()
    if not html_path.is_file():
        raise FileNotFoundError(f"HTML not found: {html_path}")

    if args.output_dir is None:
        out_dir = html_path.parent / f"images_{infer_post_title(html_path)}"
    else:
        out_dir = (
            args.output_dir
            if args.output_dir.is_absolute()
            else html_path.parent / args.output_dir
        )
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    for old in out_dir.glob("page_*.png"):
        old.unlink()

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=args.supersample,
        )

        await page.goto(f"file://{html_path}", wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle")
        await page.evaluate(
            """(css) => {
                const style = document.createElement('style');
                style.id = '__codex_override_css__';
                style.textContent = css;
                document.head.appendChild(style);
            }""",
            build_override_css(args),
        )
        await page.evaluate("document.fonts && document.fonts.ready")
        await page.wait_for_timeout(args.wait_ms)

        full_height = await page.evaluate(
            """
            () => Math.max(
              document.documentElement.scrollHeight,
              document.body.scrollHeight,
              document.documentElement.offsetHeight,
              document.body.offsetHeight
            )
            """
        )
        full_height = int(full_height)
        pad = args.slice_padding
        content_h = args.height - 2 * pad

        idx = 0
        y = 0
        while y < full_height:
            remaining = full_height - y
            if remaining <= content_h:
                cut = full_height
            elif args.cut_mode == "hard":
                cut = min(full_height, y + content_h)
            else:
                cut = await find_smart_cut(
                    page=page,
                    args=args,
                    current_y=y,
                    full_height=full_height,
                    content_h=content_h,
                )
                if cut <= y:
                    cut = min(full_height, y + content_h)
                if cut - y < args.min_segment_height and remaining > content_h:
                    cut = min(full_height, y + content_h)

            # Keep each slice content inside the center content box.
            cut = min(cut, y + content_h)

            clip_h = max(1, cut - y)

            shot = await page.screenshot(
                type="png",
                full_page=True,
                clip={"x": 0, "y": y, "width": args.width, "height": clip_h},
            )

            canvas = Image.new(
                "RGB",
                (
                    int(round(args.width * args.supersample)),
                    int(round(args.height * args.supersample)),
                ),
                (255, 255, 255),
            )
            seg = Image.open(BytesIO(shot)).convert("RGB")
            canvas.paste(seg, (0, int(round(pad * args.supersample))))
            buf = BytesIO()
            canvas.save(buf, format="PNG")
            shot = buf.getvalue()

            final_img = downscale_to_final(
                shot,
                final_size=(args.width, args.height),
                sharpen=args.sharpen,
            )
            final_img.save(out_dir / f"page_{idx + 1:03d}.png", "PNG")
            idx += 1
            y = cut

        await browser.close()

    return out_dir, idx


def main() -> int:
    args = parse_args()
    if args.width <= 0 or args.height <= 0:
        print("width/height must be > 0")
        return 1
    if args.supersample <= 0:
        print("supersample must be > 0")
        return 1
    if min(args.side_padding, args.top_padding, args.bottom_padding) < 0:
        print("padding values must be >= 0")
        return 1
    if args.wait_ms < 0:
        print("wait-ms must be >= 0")
        return 1
    if args.sharpen < 0:
        print("sharpen must be >= 0")
        return 1
    if args.search_range < 0:
        print("search-range must be >= 0")
        return 1
    if args.white_threshold < 0 or args.white_threshold > 255:
        print("white-threshold must be in [0,255]")
        return 1
    if args.white_row_ratio < 0 or args.white_row_ratio > 1:
        print("white-row-ratio must be in [0,1]")
        return 1
    if args.min_segment_height <= 0:
        print("min-segment-height must be > 0")
        return 1
    if args.slice_padding < 0:
        print("slice-padding must be >= 0")
        return 1
    if args.slice_padding * 2 >= args.height:
        print("slice-padding is too large for current height")
        return 1

    out_dir, page_count = asyncio.run(export_pages(args))
    print(f"Done. Exported {page_count} image(s) to {out_dir}")
    print(
        "Final size per image: "
        f"{args.width}x{args.height} (fixed), supersample={args.supersample}"
    )
    print(
        "Applied page paddings: "
        f"left/right={args.side_padding}, top={args.top_padding}, bottom={args.bottom_padding}"
    )
    print(
        f"Slice padding: top/bottom={args.slice_padding}, "
        f"content_height={args.height - 2 * args.slice_padding}"
    )
    print(
        f"Cut mode: {args.cut_mode}, search_range={args.search_range}, "
        f"white_threshold={args.white_threshold}, white_row_ratio={args.white_row_ratio}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
