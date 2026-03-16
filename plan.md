# Web App Plan (macOS First) - Updated 2026-03-16

## 1. Product Direction (Locked)

- Product form: `Web App` (not packaged local app).
- Target users: non-technical users, minimal command-line usage.
- Core flow: Notion export HTML -> preview in browser -> high-quality export.

## 2. Core Experience (Locked)

- Input: `HTML + CSS`.
- Output: mobile-readable images.
- Two-stage workflow:
  1. `Preview`: full-document preview, fast low-cost render.
  2. `Export`: full-document high-quality render.
- Preview and export must share the same pagination logic.

## 3. Decision Notes (Locked)

- Preview must be full-document; not "first N pages only" as default behavior.
- `max-pages` is only an advanced fallback/debug switch.
- Ratio presets must be first-class in UI: `3:4`, `9:16`, `custom`.
- Preview container should be fixed shell + inner scroll.

## 4. Current Implementation Status

## 4.1 Backend (`web_app.py`) - Completed

- Added API endpoints:
  - `POST /api/preview`
  - `GET /api/preview/pages`
  - `POST /api/export`
  - `GET /api/task/{task_id}`
  - `POST /api/open-output/{task_id}`
  - `GET /api/pick-html`
- Preview/export task execution is async (threaded) with status + logs in memory.
- macOS file picker now uses native Finder dialog via `osascript` (more stable than tkinter in this app context).

## 4.2 Render Engine (`html_to_image.py`) - Completed

- Added `--no-open-preview` for backend-driven runs.
- Added `--max-pages` as advanced fallback switch.
- Retained same pagination/cut logic for both preview and export workflows.

## 4.3 Frontend (`web/`) - Completed

- Three-column UI:
  - left: parameter panel
  - center: full-document preview
  - right: task summary/actions
- Ratio preset UI:
  - `3:4` / `9:16` / `custom`
  - preset auto-computes `height` from `width`
  - preview frame aspect ratio follows selected output ratio
- Preview shell behavior:
  - fixed outer shell
  - inner vertical scroll
- File import UX:
  - drag-and-drop HTML into dropzone
  - click button to open Finder and select HTML
- Log panel hidden from UI; only concise task notes/status shown.

## 5. UX Rules (Do Not Regress)

- Keep the center preview panel fixed; avoid page-level vertical jumpiness on desktop.
- Keep preview cards centered in the preview viewport.
- Do not reintroduce verbose log panel unless explicitly requested.
- Preserve low-friction import:
  - drag-drop first
  - native file picker as fallback/primary for non-technical users.

## 6. Milestones

1. `M1` Basic web app skeleton and API connection - Completed.
2. `M2` Full-document preview experience - Completed (base version).
3. `M3` Export workflow robustness - In progress.
4. `M4` UX polish + onboarding copy - Pending.

## 7. Next Work Items (Priority)

1. Improve task progress visibility (lightweight progress model instead of only status text).
2. Add preset bundles for beginners (e.g., "小红书 3:4", "手机长图 9:16").
3. Add preview caching/versioning to avoid stale-image confusion after parameter changes.
4. Add stronger validation and inline error hints for path/parameter issues.
5. Add one-click "open recent html" history for repeat workflows.

## 8. Done Criteria

- Non-technical user can finish one full run from HTML selection to final export inside web UI.
- Preview reflects full-document pagination and is visually aligned with export behavior.
- Ratio presets (`3:4`, `9:16`) work end-to-end in both preview and export.
- Export result remains stable and reproducible.

## 9. Anti-Drift Checklist (Before Every Change)

- Is this still a `Web App` first flow?
- Is preview still full-document (not sample-only)?
- Is pagination logic still shared between preview/export?
- Did we keep the center preview shell fixed with inner scrolling?
- Did we avoid exposing unnecessary complexity to beginner users?

