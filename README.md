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
  - 1 line if it fits
  - otherwise wrap to **2 lines max**, then shrink until it fits
- Manual line breaks in the title are kept when they are 2 lines or fewer

## Bounding boxes

The main page has visible controls for three regions:

| Region | Controls |
| --- | --- |
| Service Line Box | Service X / Y / Width / Height |
| Sermon Title Box | Title X / Y / Width / Height |
| Speaker / Minister Box | Speaker X / Y / Width / Height |

Default starting values (1920×1080, above the open Bible):

- Service: x=280, y=95, w=1360, h=90
- Title: x=180, y=180, w=1560, h=520
- Speaker: x=280, y=760, w=1360, h=90

Use **Show bounding boxes** to draw preview guides around those regions.  
**Export PNG** and **Download clean PNG** never include the guides.

**Reset boxes to defaults** restores the starting layout.

## Export

- Size: 1920×1080 PNG
- Folder: `exports/`
- Name example: `2026-07-31_FRIDAY_AM_THE_TRUTH_THE_WHOLE_TRUTH.png`

## Folders

- `fonts/` — BarlowCondensed-BoldItalic.ttf
- `templates/` — background images
- `exports/` — exported PNGs

## Tests

```bash
python3 -B -m unittest discover -s tests
```
