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

### Font Settings

Open the **Font Settings** expander. Each text section has its own configuration:

- Service line
- Sermon title
- Minister / Speaker

Click **Configure** beside a section to open a font dialog:

- Choose a font from the project `fonts/` folder or installed system fonts
- Set text color (white by default)
- Optionally enable fancy effects: artificial bold, italic/skew, underline, shadow, outline, letter spacing

Defaults:

- Service / speaker → `BarlowCondensed-Bold.ttf` (non-italic font file)
- Title → `BarlowCondensed-BoldItalic.ttf` (italic comes from the font file itself)
- **Use font file default style only** is on — no artificial bold, skew, underline, shadow, outline, or letter spacing unless you turn them on

If a saved font is missing, the app falls back safely and keeps rendering.

Preset buttons save and restore each section’s full font config (font file + effects), not just the path.

- Service line and speaker stay on **one line** and auto-shrink to fit their boxes
- Sermon title auto-fits inside the **title box**:
  - Short titles grow aggressively to fill the title area height
  - 1 line if it fits at a large size
  - otherwise wrap to **2 lines max**, then maximize font size for that wrap
- Manual line breaks in the title are kept when they are 2 lines or fewer
- Fitting accounts for enabled effects (outline, skew, spacing, etc.) so text stays inside its box

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
- **Save as Preset** stores the current boxes, font configs (including effects), and related layout into a chosen slot (1–4)

Selected text is highlighted in the preview guides. Export stays clean (no guides).

## Export

- Size: 1920×1080 PNG
- Folder: `exports/`
- Name example: `2026-07-31_FRIDAY_AM_THE_TRUTH_THE_WHOLE_TRUTH.png`

## Tests

```bash
python3 -B -m unittest discover -s tests
```
