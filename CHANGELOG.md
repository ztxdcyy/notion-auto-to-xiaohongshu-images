# Changelog

All notable changes to this project will be documented in this file.

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
