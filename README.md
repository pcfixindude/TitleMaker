# TitleMaker

A simple local Streamlit app for creating **1920×1080** Monark Springs livestream sermon title images.

## TitleMaker Simplified Workflow

1. Choose day / date / service.
2. Type the sermon title.
3. Type the speaker / minister.
4. Pick a background image.
5. Preview the title card.
6. Toggle **Show bounding boxes** to see the three text regions.
7. Adjust Service / Title / Speaker box X, Y, Width, Height if needed.
8. Export PNG.

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Text and layout

### Font Choices

Open the **Font Choices** expander to pick a font for each text section:

- Service line font
- Sermon title font
- Speaker / Minister font

Fonts are discovered from:

- the project `fonts/` folder (`.ttf` / `.otf`)
- installed system font folders (macOS / Windows / Linux)

Defaults:

- Service / speaker → `BarlowCondensed-Bold.ttf`
- Title → `BarlowCondensed-BoldItalic.ttf`

If a saved font is missing, the app falls back safely and keeps rendering.

All text is **white** with **no shadow**.
- Service line and speaker stay on **one line** and auto-shrink to fit their boxes
- Sermon title auto-fits inside the **title box**:
  - Short titles grow aggressively to fill the title area height
  - 1 line if it fits at a large size
  - otherwise wrap to **2 lines max**, then maximize font size for that wrap
- Manual line breaks in the title are kept when they are 2 lines or fewer

## Default bounding boxes (1920×1080)

| Region | X | Y | Width | Height |
| --- | ---: | ---: | ---: | ---: |
| Service Line | 280 | 95 | 1360 | 90 |
| Sermon Title | 30 | 195 | 1860 | 460 |
| Speaker / Minister | 280 | 665 | 1360 | 90 |

**Reset boxes to defaults** restores these values.

### Preview editor

Around the preview:

- **Select** Service line / Sermon title / Speaker
- **Up / Down** move the selected box (kept centered horizontally)
- **+ / −** scale the selected text font (box height adjusts to fit)
- **4 preset buttons** on the left load saved layouts
- **Save as Preset** stores the current boxes/fonts into a chosen slot (1–4)

Selected text is highlighted in the preview guides. Export stays clean (no guides).

## Export

- Size: 1920×1080 PNG
- Folder: `exports/`
- Name example: `2026-07-31_FRIDAY_AM_THE_TRUTH_THE_WHOLE_TRUTH.png`

## Tests

```bash
python3 -B -m unittest discover -s tests
```
