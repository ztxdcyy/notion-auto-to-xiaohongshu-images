# Changelog

All notable changes to this project will be documented in this file.

## [1.1.1] - 2026-03-10

### Added

- Windows-compatible pipeline launcher:
  - Added `run_html_pipeline.bat` for `cmd` usage.
  - Added `run_html_pipeline.py` as cross-platform pipeline core.

### Changed

- Refactored `run_html_pipeline.sh` into a thin launcher that delegates to
  `run_html_pipeline.py` (same behavior on macOS/Linux, easier parity with Windows).
- Updated README usage examples and project structure to include `.bat` + `.py`
  pipeline entrypoints.

## [1.1.0] - 2026-03-10

### Changed

- Live preview file location moved from export output folders to project root:
  - `preview_live.html` is now generated next to `html_to_image.py`.
  - Preview page now loads slices via absolute `file://` URI of the current output directory.
- Export startup behavior:
  - Browser auto-opens project preview page as soon as export begins.
  - Old `preview_live.html` in output folders is removed to avoid confusion.
- Default render quality:
  - CLI default `--supersample` increased from `4.0` to `5.0`.
  - `argparse` help now shows parameter defaults directly.
- Visual theme:
  - Reverted `my.css` base background from Morandi palette back to white (`#ffffff`).

## [1.0.1] - 2026-03-09

### Fixed

- Resolved smart-cut vs slice-padding conflict in `html_to_image.py`.
  - Root cause:
    - Cut-step should follow `content_h = height - 2*slice_padding`.
    - Canvas/output height should remain `height`.
    - When these two were mixed, next-slice top spacing could look inconsistent.
  - Debugged and fixed flow:
    - Added/confirmed `--slice-padding` and content-height based stepping.
    - Ensured `find_smart_cut` targets `current_y + content_h`.
    - Kept screenshot pasted into white canvas with Y offset `pad * supersample`.
    - Tightened smart-cut search window upper bound to `target` (removed ineffective upper-half search).
    - Added validation: `min_segment_height <= content_h`.
    - Removed unused `math` import.
  - Verification:
    - Re-ran full pipeline and confirmed fixed-size output (`1400x2400`) and stable slice spacing.

## [1.0.0] - 2026-03-09

### Added

- Initial project scaffold for Notion HTML to mobile image conversion.
- `html_to_image.py`:
  - Fixed-size image output (`1400x2400` by default).
  - Supersampling + downscale for sharper text.
  - Smart cut mode (blank-row-aware) and hard cut mode.
  - Slice-level vertical padding via `--slice-padding`.
  - Auto output folder naming: `images_<post_title>`.
- `insert_css_into_html.py`:
  - Idempotent CSS link injection into HTML head.
  - CLI arguments for target HTML and CSS href.
- `run_html_pipeline.sh`:
  - One-command pipeline to inject CSS and render images.
  - Automatic relative CSS path resolution.
- `my.css` baseline style template.
- Documentation:
  - Full pipeline README from Notion export to final images.
  - Usage examples and parameter reference.
