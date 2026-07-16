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

- Font everywhere: **`fonts/BarlowCondensed-BoldItalic.ttf`**
- All text is **white** with **no shadow**
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

Use **Show bounding boxes** for preview guides only. Export stays clean.

## Export

- Size: 1920×1080 PNG
- Folder: `exports/`
- Name example: `2026-07-31_FRIDAY_AM_THE_TRUTH_THE_WHOLE_TRUTH.png`

## Tests

```bash
python3 -B -m unittest discover -s tests
```
