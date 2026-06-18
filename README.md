# TitleMaker

A simple local Streamlit app for creating 1920x1080 Monark Springs camp meeting sermon livestream title images.

## Features

- Live preview in the browser
- PNG export to `exports/`
- Uppercases the day, service, title, and speaker automatically
- Wraps and shrinks long sermon titles to fit
- Selectable fonts from `fonts/`
- Separate fonts for service line, sermon title, and minister/speaker text
- Style presets saved as JSON in `presets/`
- Monark service line format with show/hide toggle
- Automatic Monark camp meeting schedule and live service log
- Booth Mode for large live-service controls
- Visual layout adjustment buttons for text regions
- Automatic local persistence for service logs and active settings
- Uses Barlow Condensed ExtraBold Italic as the preferred default when available
- Uses `fonts/BebasNeue-Regular.ttf` as a fallback when available
- Falls back to a system font if no custom font is available
- Generates a soft blue/gray church livestream background when no template is selected
- Supports custom template images from `templates/`

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
streamlit run app.py
```

## Fonts

TitleMaker scans the `fonts/` folder for `.ttf` and `.otf` files and shows them in the font dropdowns.

For the best match to the sample KEEP DRINKING style, use Barlow Condensed ExtraBold Italic. Place the font file in `fonts/`, for example:

```text
fonts/BarlowCondensed-ExtraBoldItalic.ttf
```

If Barlow Condensed ExtraBold Italic is present, TitleMaker selects it by default.

Bebas Neue is also supported as a fallback. Place it here:

```text
fonts/BebasNeue-Regular.ttf
```

If no custom font is present, TitleMaker will safely use the existing Bebas Neue/default fallback behavior and then an available system font.

## Separate Fonts Per Text Area

TitleMaker can use different fonts for each text area:

- `Service Line Font` controls the date/service line.
- `Sermon Title Font` controls the main title.
- `Minister / Speaker Font` controls the bottom speaker line.

By default, the sermon title and minister/speaker fonts match the Service Line font for backward compatibility. Uncheck `Sermon Title font matches Service Line font` or `Minister / Speaker font matches Service Line font` to choose a different font for that text area.

This is useful for keeping the classic Monark service-line look while experimenting with stronger sermon title emphasis.

## Service Line Format

TitleMaker renders the service line separately from the main sermon title. Use the `Show service line` checkbox in the sidebar to show or hide it.

Format:

```text
WEEKDAY SERVICE_CODE M-D-YY
```

Service codes:

- Morning -> AM
- Afternoon -> AFT
- Evening -> PM

Examples:

```text
SATURDAY PM 7-23-22
FRIDAY PM 7-22-22
FRIDAY AFT 7-22-22
```

## Monark Live Workflow

At Monark, the sermon title and preacher are often not known until the service is already underway. The schedule feature is designed as a live service log and quick-entry tool, not mainly as a pre-planning spreadsheet.

The Monark meeting starts on the last Friday of July and runs through the second Sunday, inclusive. TitleMaker generates 10 days of services with Morning, Afternoon, and Evening entries for each day, for 30 total service rows.

Use the sidebar section called `Monark Schedule Generator`:

1. Enter the year.
2. Click `Generate Monark Schedule`.
3. Use `Jump to Current Service` during camp to pick the most likely current service based on today's date and time.
4. In `Current Service`, type the sermon title and preacher as soon as they are known.
5. Preview updates immediately.
6. Click `Export Current Service` to save the image and mark that row exported.

The current service selector uses readable service-line options:

```text
FRIDAY AM 7-22-22
FRIDAY AFT 7-22-22
FRIDAY PM 7-22-22
```

Generated service lines look like:

```text
FRIDAY AM 7-25-26
SATURDAY AFT 7-26-26
SUNDAY PM 7-27-26
```

## Booth Mode

`Booth Mode` is the big live-use screen for the sound booth. It hides the spreadsheet-heavy workflow and focuses on the current service, title, speaker, preview, and export button.

Recommended live flow:

1. Generate the Monark schedule first.
2. Open `Booth Mode`.
3. Click `Jump to Current Service` to select the likely AM, AFT, or PM service based on the current date and time.
4. Type the sermon title and speaker as soon as they are known.
5. Watch the preview update immediately.
6. Click `Export Current Image`.
7. If a correction is needed, update the title or speaker and click `Re-export Current Image`.
8. Use `Service Log / Advanced` later for corrections, CSV backup, batch export, and history.

For best live use, open the app in a browser window and use fullscreen mode.

## Service Log

The `Service Log` table shows all 30 generated rows. Titles and speakers start blank. Use it to:

- Correct title or speaker text after the fact
- Add notes
- Check rows for later export
- See which services have already been exported
- Re-export a row when needed
- Download or import a CSV log for permanent history

Batch export uses only rows that are checked `Include` or already have a title or speaker. It does not force placeholder titles or speakers.

Exported filenames keep the existing safe structure and include sortable date/day/service components, for example:

```text
2026-07-24_FRIDAY_AM_SERVICE_TITLE.png
```

## Saved Data And Backups

TitleMaker automatically saves local working data in `data/`:

```text
data/service_log.json
data/settings.json
```

`data/service_log.json` stores the active Monark service log, including the year, generated rows, title, speaker, notes, include flag, exported status, and exported timestamp.

`data/settings.json` stores the active preset/style state, including selected preset, font, text color, background, service/title/speaker boxes, font sizes, auto-size settings, alignment, service-line visibility, layout guides, shadow, and skew settings.

When the app starts, it automatically restores these files if they exist. If a saved JSON file is missing or corrupted, TitleMaker shows a friendly warning and continues with safe defaults.

If you generate a schedule for a different year while a saved log is loaded, TitleMaker asks for confirmation before replacing it. Confirmed replacement archives the current log as:

```text
data/service_log_2026.json
data/service_log_2027.json
```

Manual backup controls are available in the sidebar:

- `Save Service Log Now`
- `Load Service Log`
- `Export Service Log CSV`
- `Import Service Log CSV`
- `Archive Current Log`

For a simple backup, keep a copy of `data/service_log.json` or export the Service Log CSV.

## Template Backgrounds

Add custom background images to `templates/`.

Supported formats:

- `.png`
- `.jpg`
- `.jpeg`
- `.webp`

Template images are resized and center-cropped to 1920x1080.

## Presets

Use the `Preset` dropdown in the sidebar to load common title styles.

Built-in presets:

- Monark Blue Gray
- Plain Black Text
- Bold Service Title

Presets are JSON files stored in `presets/`. A preset can include the font choice, auto-size or title font size, text color, background choice, title position, service line position, speaker line position, text alignment, shadow setting, and whether the service line is shown.

To save your own style, adjust the sidebar style settings, enter a name in `Save current settings as preset`, and click `Save Preset`.

Custom presets appear in the dropdown after they are saved.

## Visual Layout Adjustment

Use `Visual Layout Adjustments` in the sidebar while watching the preview.

1. Select `Service Line`, `Sermon Title`, or `Speaker`.
2. Use the arrow buttons to move the selected text box.
3. Use `Wider`, `Narrower`, `Taller`, and `Shorter` to resize the region.
4. Use `A+` and `A-` to adjust font size.
5. For the sermon title, use `Italic +` and `Italic -` or the numeric `Italic slant angle` control to customize the slant.
6. Turn on `Show layout guides` while adjusting. The selected region is highlighted more strongly.

Step-size controls let you nudge by small or large amounts for position, size, font size, and skew angle.

Exact numeric editing is still available under `Advanced numeric layout values`, including X, Y, width, height, font size, auto-size, alignment, line spacing, title max font size, and italic slant angle.

The sermon title can now auto-size up to `400` for short titles.

## Smoke Tests

Run the preset smoke tests:

```bash
python3 -B -m unittest discover -s tests
```

## Exported Files

Exported images are saved to `exports/` using this format:

```text
YYYY-MM-DD_DAY_SERVICE_TITLE.png
```

Example:

```text
2026-07-18_FRIDAY_AM_IS_GOD_REAL.png
```
