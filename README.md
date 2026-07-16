# TitleMaker

A simple local Streamlit app for creating 1920x1080 Monark Springs camp meeting sermon livestream title images.

## Main Booth Workflow

Booth Mode is the default live screen. For normal services:

1. Generate the Monark schedule (sidebar or empty-state button).
2. Click **Jump to Current Service**.
3. Type the sermon title.
4. Type the speaker / minister.
5. Preview updates automatically.
6. Click **Export Current Image** (or **Re-export Current Image** if already exported).

Everything else lives under **Advanced** expanders (collapsed by default).

For best live use, open the app in a browser window and use fullscreen mode.

## Features

- Booth-first live workflow
- Large preview and export / re-export
- Previous / Next through all services (including blank rows)
- Automatic title fitting that uses the space between service and speaker lines
- Separate fonts per text area (Advanced)
- Style presets with save / load / delete (Advanced)
- Export targets including multi-target export (Advanced)
- Service log, CSV import/export, and batch export (Advanced)
- Visual layout adjustments and numeric box controls (Advanced)
- Automatic local persistence for service logs and settings

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Automatic Title Fitting

The sermon title is the hard part. By default:

- **Auto title area between service and speaker** is ON.
- Service and speaker lines stay centered in their fixed boxes.
- The title fills the remaining vertical space (with padding).
- Titles stay centered horizontally and vertically in that area.
- Short titles render large (up to font size **400**).
- Longer titles wrap to 2, 3, or more lines and shrink as needed.
- Manual line breaks (`Enter`) are preserved.
- Titles do not overflow into the service or speaker lines.

Turn off auto title area under **Advanced: Layout** to set the title box Y/height manually.

## Advanced: Service Log / Batch Tools

- Full 30-row service log table
- CSV import / export
- Load / archive saved logs
- Batch export of included or filled rows

## Advanced: Style Presets

- Load a preset
- Save the current style as a named preset
- Background, text color, shadow, skew, and service-line visibility

### Deleting presets

User-created presets can be deleted under **Advanced: Style Presets**:

1. Choose the user preset.
2. Check the confirmation box.
3. Click **Delete Preset**.

Built-in presets (`Monark Blue Gray`, `Plain Black Text`, `Bold Service Title`) are protected and cannot be deleted from the UI. If the active preset is deleted, TitleMaker falls back to **Monark Blue Gray**. Deleting a user preset removes its JSON file from `presets/`.

## Advanced: Fonts

Font selection is Advanced-only:

- Service Line Font
- Sermon Title Font (optional match to service font)
- Minister / Speaker Font (optional match to service font)

TitleMaker scans `fonts/` for `.ttf` / `.otf` files. Barlow Condensed ExtraBold Italic is preferred when present; Bebas Neue and system fonts are fallbacks.

## Advanced: Layout

- Layout guides
- Auto title area + padding from service / speaker
- Visual nudge controls (position, size, font, skew)
- Numeric X/Y/width/height, alignment, auto-size, line spacing

## Advanced: Export Targets

- Stream / YouTube / Facebook / Vimeo / Custom sizes
- Export layout mode (scale / fill-crop / stretch)
- Multi-target export

## Service Line Format

```text
WEEKDAY SERVICE_CODE M-D-YY
```

Examples: `FRIDAY PM 7-22-22`, `SATURDAY AFT 7-26-26`

## Saved Data

```text
data/service_log.json
data/settings.json
```

Settings include fonts, boxes, auto title area, padding, export targets, and the active preset.

## Smoke Tests

```bash
python3 -B -m unittest discover -s tests
```

## Exported Files

```text
exports/YYYY-MM-DD_DAY_SERVICE_TITLE_target.png
```
