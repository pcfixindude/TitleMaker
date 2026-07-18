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

Font configuration is **inline** so the preview stays visible while you edit.

Open the **Font Settings** expander, then choose which section to configure:

- Service Line
- Sermon Title
- Minister / Speaker

Changes update the preview live (no Apply step).

- Search/filter fonts and browse sample previews rendered in each typeface
- Select a font from the dropdown or a preview row
- **Basic Appearance:** text color and “Use font file default style only”
- **Advanced Text Styling:** optional artificial bold, italic/skew, underline, letter spacing
- **Shadow** and **Outline** are separate sections and off by default

Defaults:

- Service / speaker → `BarlowCondensed-Bold.ttf` (non-italic font file)
- Title → `BarlowCondensed-BoldItalic.ttf` (italic comes from the font file itself)
- **Use font file default style only** is on — Advanced Text Styling, Shadow, and Outline stay off unless you enable them

If a saved font is missing, the app falls back safely and keeps rendering.

Preset buttons save and restore each section’s full font config (font file + all styling options).

- Service line and speaker stay on **one line** and auto-shrink to fit their boxes
- Sermon title auto-fits inside the **title box**:
  - Short titles grow aggressively to fill the title area height
  - 1 line if it fits at a large size
  - otherwise wrap to **2 lines max**, then maximize font size for that wrap
- Manual line breaks in the title are kept when they are 2 lines or fewer
- Fitting accounts for enabled effects (outline, skew, spacing, etc.) so text stays inside its box

### Title line spacing

When a sermon title wraps to two lines, adjust **Title line spacing** (under the sermon title field). Negative values tighten the two lines; positive values spread them apart. Default is `0`. This setting is saved with simple presets.

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
- **Save Current Settings as Default** stores startup settings
- **Reset to Factory Defaults** restores built-in defaults (presets are kept)

Selected text is highlighted in the preview guides. Export stays clean (no guides).

## Saving Presets and Defaults

- Preset buttons are saved permanently to `data/simple_presets.json`
- **Save Current Settings as Default** writes startup settings to `data/default_settings.json`
- TitleMaker loads saved defaults automatically on startup (or factory defaults if that file is missing/invalid)
- **Reset to Factory Defaults** restores built-in boxes/fonts/effects without deleting presets
- **Delete Saved Default Settings** removes `data/default_settings.json` so the next fresh start uses factory defaults
- Presets and defaults save boxes, fonts and font options, background, title line spacing, bounding-box visibility, and text effects
- JSON files are written atomically (temp file, then replace) to avoid corruption

## Service Log Spreadsheet

Track every Monark service in an editable spreadsheet:

1. Open **Service Log** and choose a year.
2. Click **Generate Monark Service Log** (30 rows: 10 days × AM/AFT/PM).
   The log starts on the **third Friday of July** and runs through the second Sunday (10 days).
3. Choose **Current Service**, then type the sermon title and minister/speaker.
4. Use **Previous Service** / **Next Service** to move through every row (including blanks).
5. **Jump to Current Service** / **Suggest Current Service** selects today’s row from local time and service start times:
   - AM 10:00
   - AFT 2:00
   - PM 7:30  
   (Before 10:00 AM, Morning is suggested.)
6. **Export PNG** marks the selected `row_id` as exported and stores the full file path/time.
7. Edit or correct rows in the Service Log table.
8. **Export Service Log CSV** / **Import Service Log CSV** for backups or external edits.

The service log is saved separately from style presets in `data/service_log.json`.

## Export

- Size: 1920×1080 PNG
- Default folder: your **Downloads** folder (falls back to `exports/` if Downloads is missing)
- Optional setting: **Export location** → Downloads folder or App exports folder
- Name example: `2026-07-17_FRIDAY_AM_THE_TRUTH_THE_WHOLE_TRUTH.png`

## WhatsApp posting

TitleMaker does not post into WhatsApp automatically. After export:

1. Confirm the saved image path (usually in Downloads).
2. Use **Reveal Image in Finder** (macOS) or open Downloads manually.
3. Click **Open WhatsApp Web** and open the **Monark Audio/Video Booth** group.
4. Drag the exported image from Downloads into the chat.

## YouTube tools

- **Open YouTube Studio Playlist** opens the Monark playlist in YouTube Studio.
- **YouTube Video Title** is generated live as:  
  `SERVICE LINE | SERMON TITLE | SPEAKER`  
  Example: `FRIDAY AFT 7-18-26 | IS GOD REAL? | BRO. MARTY CLEVENGER`  
  A short weekday-only variant is shown underneath for convenience.

## Tests

```bash
python3 -B -m unittest discover -s tests
```
