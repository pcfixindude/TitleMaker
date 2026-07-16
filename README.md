# TitleMaker

A simple local Streamlit app for creating **1920×1080** Monark Springs livestream sermon title images.

## TitleMaker Simplified Workflow

1. Choose day / date / service.
2. Type the sermon title.
3. Type the speaker / minister.
4. Pick a background image.
5. Preview the title card.
6. Toggle **Show bounding boxes** if you need layout guides.
7. Move the title up or down if needed.
8. Export PNG.

That is the whole live workflow.

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the local Streamlit URL in a browser. For booth use, fullscreen the window.

## What it does

- One page, left controls / right preview
- Service line format: `FRIDAY AM 7-31-26` (no leading zeroes on the date)
- Uses **`fonts/BarlowCondensed-BoldItalic.ttf`** for service line, title, and speaker
- Title auto-fits in the space between the service line and speaker
- Short titles grow large (up to font size **400**)
- Long titles wrap to **2 lines max**, then shrink to fit
- Manual line breaks in the title are preserved (capped at 2 lines)
- Normal export is a clean **1920×1080 PNG** (bounding boxes are preview-only)
- Files save under `exports/` as:
  `YYYY-MM-DD_SERVICE_TITLE.png`
  Example: `2026-07-31_FRIDAY_AM_THE_TRUTH_THE_WHOLE_TRUTH.png`

## Main controls

| Control | Purpose |
| --- | --- |
| Date / Day / Service | Builds the top service line |
| Sermon title | Main title text (uppercase when rendered) |
| Speaker / Minister | Bottom line |
| Background image | Image from `templates/`, or a generated blue/gray fallback |
| Show bounding boxes | Preview guides for service / title / speaker regions |
| Move Title Up / Down / Reset | Nudge title vertical position |
| Title vertical offset slider | Fine adjust (−150…+150) |
| Export PNG | Save to `exports/` |

Optional (collapsed): **Jump to current Monark service** using the generated Monark schedule. Manual day/service/date always works without it.

## Layout defaults (1920×1080)

- Service line box: x=120, y=130, w=1680, h=110
- Speaker box: x=120, y=740, w=1680, h=120
- Title box: full width with 120px side padding, vertically between service and speaker with 35px gaps, plus an optional vertical offset

## Folders

- `fonts/` — put `BarlowCondensed-BoldItalic.ttf` here
- `templates/` — background images
- `exports/` — exported PNGs
- `data/` — optional local persistence used by leftover helper modules
- `presets/` — unused by the simplified app (legacy)

## What was removed from the main UI

The live page no longer exposes:

- Font dropdowns / per-area fonts / match-font checkboxes
- Style presets save/load UI
- Skew controls
- Complex visual layout / nudge / interactive preview editors
- Multi-target export controls
- Spreadsheet / service-log as the primary workflow
- Booth Mode advanced pages that conflicted with Streamlit state

Legacy helper modules may still exist in the repo for reference, but they are not part of the simplified main app flow.

## Tests

```bash
python3 -B -m unittest discover -s tests
```
