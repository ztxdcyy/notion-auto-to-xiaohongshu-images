# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - 2026-03-17

### Added

- Cloud-friendly source upload workflow:
  - Added `POST /api/upload-source` (accepts `.zip` or `.html`, optional `.css`).
  - Added server-side `source_id` lifecycle and source metadata persistence under `.web_runs/sources/`.
- Frontend upload UX enhancements:
  - Large drag-and-drop upload zone.
  - Click-to-select upload entry.
  - Visual upload progress bar with percentage.
- Runtime fallback for parameter tooltip metadata in frontend:
  - Added inline fallback metadata for key params.
  - Added `cache: "no-store"` fetch policy for `/static/param_meta.json`.
- Added dependency `python-multipart` for FastAPI multipart upload handling.

### Changed

- Request model for preview/export switched from local path mode to upload mode:
  - `RunRequest` now uses `source_id` instead of `html_path/css_path`.
- Frontend information architecture updates:
  - Top-left main title now reflects uploaded HTML `<title>`.
  - Upload block renamed and simplified.
  - Primary theme color switched to Hermes-like orange.
  - Merged quality controls (preview/export supersample + sharpen) into `导出图片选项`.
  - Restored `切分策略选项` as a collapsible module.
- Frontend payload construction now includes visible quality/splitting controls while keeping safe defaults.
- Startup behavior tuned for local + cloud:
  - `PORT` and `WEBAPP_HOST` respected in `web_app.py` main entry.
  - Browser auto-open only triggers for local host modes.
- Visual style system refresh for exported images:
  - Main title scale increased significantly for cover-like reading effect.
  - `<hr>` divider switched from gradient to solid theme color.
  - Core accents in `my.css` now derive from CSS variable `--theme-color`.
- Added configurable theme color in `导出图片选项`:
  - Preset palette includes classic blue and Morandi options.
  - Added color picker for custom accent selection.
  - Theme color now flows from Web UI -> backend settings -> `html_to_image.py`.

### Removed

- Removed local absolute-path dependent Web UI flow:
  - Removed `HTML 路径` / `CSS 路径` inputs from frontend.
  - Removed `/api/pick-html` endpoint (Finder/tkinter picker).
  - Removed `/api/open-output/{task_id}` endpoint (local file manager opener).
- Removed legacy local packaging pipeline entry scripts that diverged from current Web App workflow:
  - `run_html_pipeline.py`
  - `run_html_pipeline.sh`
  - `run_html_pipeline.bat`
- Removed legacy CLI-only live preview branch in `html_to_image.py`:
  - Removed generation/opening of `preview_live.html`.
  - Removed `--no-open-preview` CLI argument.

### Fixed

- Tooltip regression in split-strategy parameters:
  - Ensured question-mark tooltip visibility even when static JSON loading fails.
- Empty UI default value issues:
  - Added/retained frontend fallback defaults to avoid blank parameter inputs.
- Todo duplicate checkbox rendering:
  - Hidden Notion built-in `.checkbox` and retained single custom checkbox style in `my.css`.
- Backward compatibility for mixed old/new workers:
  - Re-accepted legacy `--no-open-preview` arg as no-op in `html_to_image.py` to avoid `Command failed with code 2`.

## [1.2.1] - 2026-03-16

### Changed

- Web size presets are now fixed to two templates only:
  - `1200x1600` (3:4)
  - `1440x2400` (full-screen open style)
- Removed ratio-based/custom height calculation flow in frontend:
  - no `custom`
  - no computed height from ratio
  - width/height are now preset-driven and read-only in UI.
- Backend now enforces preset-driven output size when building `html_to_image.py` args
  (does not rely on user-entered width/height).

## [1.2.0] - 2026-03-16

### Added

- Introduced a local `Web App` flow for macOS-first usage:
  - Added `web_app.py` (FastAPI backend) with preview/export task APIs.
  - Added `web/` frontend UI:
    - left parameter panel
    - center full-document preview (PDF-like vertical browsing)
    - right task status + logs
- Added preview/export task lifecycle APIs:
  - `POST /api/preview`
  - `POST /api/export`
  - `GET /api/task/{task_id}`
  - `POST /api/open-output/{task_id}`
- Added web dependencies to `requirements.txt`: `fastapi`, `uvicorn[standard]`.

### Changed

- `html_to_image.py` now supports:
  - `--max-pages` (advanced fallback switch, default full document)
  - `--no-open-preview` (for backend-driven runs without browser pop-up)
- Web UI now includes export ratio presets:
  - `3:4`
  - `9:16`
  - `custom` (manual width/height)
  - preview card aspect ratio follows selected output ratio.
- Updated README with Web App startup instructions and architecture notes.

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
