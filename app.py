from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import replace
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

import streamlit as st

from font_config import (
    FontConfig,
    default_font_config_for_role,
    font_config_from_dict,
)
from font_discovery import (
    FontChoice,
    default_font_id_for_role,
    discover_fonts,
    filter_fonts,
    get_font_display_name,
)
from font_preview import safely_render_font_sample, sample_text_for_role
from monark_schedule import (
    adjacent_entry,
    entry_key,
    find_current_service_entry,
    get_service_entry_by_row_id,
    get_third_friday_of_july,
    mark_service_exported,
    service_log_schedule_warning,
    service_option_label,
    update_entry_text,
)
from service_log import (
    apply_display_edits,
    archive_service_log,
    entries_to_display_rows,
    export_service_log_csv,
    generate_service_log,
    import_service_log_csv,
    load_service_log,
    save_service_log,
)
from simple_presets import (
    PRESET_SLOTS,
    delete_default_settings,
    get_factory_default_settings,
    load_default_settings,
    load_preset_slot,
    normalize_preset_settings,
    preset_slot_labels,
    save_default_settings,
    save_preset_slot,
)
from title_renderer import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    DEFAULT_SERVICE_BOX,
    DEFAULT_SPEAKER_BOX,
    DEFAULT_TITLE_BOX,
    DEFAULT_TITLE_LINE_SPACING_PX,
    LAYOUT_DEFAULTS_VERSION,
    MAX_TITLE_FONT_SIZE,
    PROJECT_ROOT,
    TITLE_LINE_SPACING_PX_MAX,
    TITLE_LINE_SPACING_PX_MIN,
    TitleImageOptions,
    clamp_title_line_spacing,
    ensure_project_dirs,
    export_filename,
    format_short_youtube_title,
    format_youtube_title,
    list_template_backgrounds,
    normalize_selected_area,
    normalize_service_code,
    render_title_image,
    resolve_export_dir,
    text_box_from_dict,
)
from workflow_links import WHATSAPP_WEB_URL, YOUTUBE_PLAYLIST_URL

EXPORT_LOCATION_OPTIONS = ("Downloads folder", "App exports folder")


SERVICES = ["Morning", "Afternoon", "Evening"]
SERVICE_LABELS = {"Morning": "AM", "Afternoon": "AFT", "Evening": "PM"}
GENERATED_BACKGROUND = "Generated blue/gray background"

AREA_KEYS = ("service", "title", "speaker")
AREA_LABELS = {
    "service": "Service line",
    "title": "Sermon title",
    "speaker": "Speaker / Minister",
}
BOX_DEFAULTS = {
    "service": DEFAULT_SERVICE_BOX,
    "title": DEFAULT_TITLE_BOX,
    "speaker": DEFAULT_SPEAKER_BOX,
}
DEFAULT_FONT_SIZES = {
    "service": 86,
    "title": MAX_TITLE_FONT_SIZE,
    "speaker": 80,
}
NUDGE_Y = 10
FONT_STEP = 12
MIN_FONT = 24
MAX_FONT = 700
FONT_SETTINGS_PATH = PROJECT_ROOT / "data" / "simple_font_settings.json"
FONT_CONFIG_STATE_KEYS = {
    "service": "simple_service_font_config",
    "title": "simple_title_font_config",
    "speaker": "simple_speaker_font_config",
}
FONT_SECTION_LABELS = {
    "service": "Service Line",
    "title": "Sermon Title",
    "speaker": "Minister / Speaker",
}
FONT_PREVIEW_LIMIT = 25
ADVANCED_TEXT_STYLING_LABEL = "Advanced Text Styling"


@st.cache_data(show_spinner=False)
def _font_catalog() -> list[FontChoice]:
    return discover_fonts()


def main() -> None:
    ensure_project_dirs()
    st.set_page_config(page_title="TitleMaker", layout="wide")
    st.title("TitleMaker")
    st.caption("Simple Monark Springs livestream title maker")

    _ensure_simple_defaults()
    # Only this helper may assign to widget-owned input keys (before widgets render).
    _apply_pending_input_values_before_widgets()

    templates = list_template_backgrounds()
    background_labels = [GENERATED_BACKGROUND] + [path.name for path in templates]
    if "simple_background_select" not in st.session_state:
        st.session_state.simple_background_select = GENERATED_BACKGROUND
    # Keep a selected background that still exists after templates change.
    if st.session_state.simple_background_select not in background_labels:
        st.session_state.simple_background_select = (
            templates[0].name if templates else GENERATED_BACKGROUND
        )

    warning = st.session_state.pop("simple_settings_warning", "")
    if warning:
        st.warning(warning)
    log_warning = st.session_state.pop("service_log_warning", "")
    if log_warning:
        st.warning(log_warning)

    left, right = st.columns([0.95, 1.25], gap="large")

    with left:
        st.subheader("Service")
        entries = list(st.session_state.get("service_log_entries") or [])
        has_log = bool(entries)

        if has_log:
            _render_current_service_controls(entries)
        else:
            st.info("Generate a Monark Service Log to track all services.")

        simple_date = st.date_input("Date", key="simple_date_input")
        widget_service_date = (
            simple_date if isinstance(simple_date, date) else date.today()
        )
        widget_service = st.selectbox(
            "Service",
            SERVICES,
            format_func=lambda name: f"{SERVICE_LABELS[name]} ({name})",
            key="simple_service_select",
        )

        # Selected log row_id is the only source of truth for date/service/line.
        selected_entry = _active_service_log_entry(entries if has_log else [])
        if selected_entry is not None:
            service_date = selected_entry["date"]
            if not isinstance(service_date, date):
                service_date = date.fromisoformat(str(service_date))
            day = str(selected_entry.get("weekday") or service_date.strftime("%A"))
            service = str(selected_entry.get("service") or widget_service)
            service_line = str(
                selected_entry.get("service_line")
                or f"{day.upper()} {normalize_service_code(service)} "
                f"{service_date.month}-{service_date.day}-{service_date.strftime('%y')}"
            )
        else:
            service_date = widget_service_date
            day = service_date.strftime("%A")
            service = widget_service
            service_line = (
                f"{day.upper()} {normalize_service_code(service)} "
                f"{service_date.month}-{service_date.day}-{service_date.strftime('%y')}"
            )

        st.markdown(f"**Day:** {day}")
        st.caption("Day is calculated from the selected service log row (or date).")

        st.subheader("Title")
        sermon_title = st.text_area(
            "Sermon title",
            height=120,
            key="simple_title_input",
            placeholder="Type title here...",
        )
        st.slider(
            "Title line spacing",
            min_value=TITLE_LINE_SPACING_PX_MIN,
            max_value=TITLE_LINE_SPACING_PX_MAX,
            step=1,
            key="simple_title_line_spacing",
            help=(
                "Use negative values to tighten the gap between two title lines. "
                "Only applies when the sermon title wraps to 2 lines."
            ),
        )
        st.caption("Use negative values to tighten the gap between two title lines.")
        speaker = st.text_input(
            "Speaker / Minister",
            key="simple_speaker_input",
            placeholder="Type speaker here...",
        )

        # Keep the selected service-log row in sync with live title inputs.
        _sync_selected_service_from_inputs(sermon_title, speaker)

        st.subheader("Background")
        background_label = st.selectbox(
            "Background image",
            background_labels,
            key="simple_background_select",
        )

        show_boxes = st.checkbox(
            "Show bounding boxes",
            key="simple_show_boxes",
            help="Preview guides only. Normal export stays clean.",
        )

        catalog = _font_catalog()
        _render_font_settings_panel(catalog)
        _persist_font_settings()

        with st.expander("Bounding box numbers", expanded=False):
            if st.button("Reset boxes to defaults", width="stretch"):
                _reset_box_defaults()
                st.rerun()
            _box_controls("Service Line Box", "service", "Service")
            _box_controls("Sermon Title Box", "title", "Title")
            _box_controls("Speaker / Minister Box", "speaker", "Speaker")

        font_configs = _current_font_configs()
        st.session_state.simple_render_inputs = {
            "day": day,
            "service": service,
            "service_date": service_date,
            "sermon_title": sermon_title,
            "speaker": speaker,
            "background_label": background_label,
            "background_labels": background_labels,
            "templates": templates,
            "show_boxes": show_boxes,
            "service_font_config": font_configs["service"],
            "title_font_config": font_configs["title"],
            "speaker_font_config": font_configs["speaker"],
            "title_line_spacing": clamp_title_line_spacing(
                st.session_state.get(
                    "simple_title_line_spacing", DEFAULT_TITLE_LINE_SPACING_PX
                )
            ),
        }

        export_options = _build_options(
            **st.session_state.simple_render_inputs,
            selected_area=None,
        )
        export_options = replace(
            export_options, show_bounding_boxes=False, selected_layout_area=None
        )

        selected_id = _get_selected_service_row_id()
        st.caption(f"Selected log row: {selected_id or '(none — manual mode)'}")
        st.caption(f"Service line: {service_line}")

        youtube_title = format_youtube_title(service_line, sermon_title, speaker)
        short_youtube_title = format_short_youtube_title(day, sermon_title, speaker)
        st.text_input(
            "YouTube Video Title",
            value=youtube_title,
            disabled=True,
            help="SERVICE LINE | SERMON TITLE | SPEAKER — select and copy",
        )
        st.caption(f"Short YouTube title: {short_youtube_title}")

        st.selectbox(
            "Export location",
            EXPORT_LOCATION_OPTIONS,
            key="simple_export_location",
            help="Default is your Downloads folder when it exists.",
        )

        if st.button("Export PNG", type="primary", width="stretch"):
            export_dir = resolve_export_dir(
                st.session_state.get("simple_export_location", "Downloads folder")
            )
            export_dir.mkdir(parents=True, exist_ok=True)
            output_path = export_dir / export_filename(export_options)
            render_title_image(export_options).save(output_path, "PNG")
            st.session_state.simple_last_export = str(output_path)
            _mark_selected_service_exported(output_path)
            st.success(f"Saved to:\n{output_path}")

        if st.session_state.get("simple_last_export"):
            st.caption(f"Last export: {st.session_state.simple_last_export}")
            _render_post_export_helpers(st.session_state.simple_last_export)

        _render_youtube_tools()

        st.caption(
            "Fonts configured per section · white by default · "
            "effects off unless enabled · export 1920×1080"
        )

    with right:
        st.subheader("Preview")
        message = st.session_state.pop("simple_preset_message", "")
        if message:
            st.info(message)
        log_message = st.session_state.pop("service_log_message", "")
        if log_message:
            st.info(log_message)
        _render_preview_workspace(export_options)

    _render_service_log_section()


def _get_selected_service_row_id(*, prefer_widget: bool = True) -> str | None:
    """Return the active service-log row_id (source of truth for log updates)."""
    if prefer_widget:
        current_select = st.session_state.get("service_log_current_select")
        if current_select:
            st.session_state.selected_service_row_id = current_select
            # Keep legacy key in sync for older session state.
            st.session_state.service_log_selected_row_id = current_select
            return str(current_select)
    selected = st.session_state.get("selected_service_row_id") or st.session_state.get(
        "service_log_selected_row_id"
    )
    return str(selected) if selected else None


def _set_selected_service_row_id(
    row_id_value: str | None, *, sync_widget: bool = True
) -> None:
    st.session_state.selected_service_row_id = row_id_value
    st.session_state.service_log_selected_row_id = row_id_value
    # Only assign the selectbox key before that widget is created on this run.
    if sync_widget and row_id_value:
        st.session_state.service_log_current_select = row_id_value


def _active_service_log_entry(entries: list) -> dict | None:
    selected_id = _get_selected_service_row_id()
    return get_service_entry_by_row_id(entries, selected_id)


def _render_current_service_controls(entries: list) -> None:
    row_ids = [entry_key(entry) for entry in entries]
    label_to_row_id = {
        service_option_label(entry): entry_key(entry) for entry in entries
    }
    labels = {entry_key(entry): service_option_label(entry) for entry in entries}
    selected = _get_selected_service_row_id()
    if selected not in row_ids and row_ids:
        selected = row_ids[0]
        _set_selected_service_row_id(selected)
        _stage_service_row_reload(selected)
        st.rerun()
    # Align selectbox source-of-truth before the widget is created.
    if st.session_state.get("service_log_current_select") not in row_ids:
        st.session_state.service_log_current_select = selected

    st.selectbox(
        "Current Service",
        options=row_ids,
        format_func=lambda rid, mapping=labels: mapping.get(rid, rid),
        key="service_log_current_select",
        on_change=_on_current_service_changed,
    )
    # Internal value is row_id; map from label dict only if needed (never partial match).
    chosen = st.session_state.get("service_log_current_select")
    if chosen not in row_ids and chosen in label_to_row_id:
        chosen = label_to_row_id[chosen]
    # Widget already owns service_log_current_select — sync row_id keys only.
    _set_selected_service_row_id(chosen, sync_widget=False)

    nav = st.columns(3)
    nav[0].button(
        "Previous Service",
        key="service_log_prev",
        width="stretch",
        on_click=_move_service,
        args=(-1,),
    )
    nav[1].button(
        "Next Service",
        key="service_log_next",
        width="stretch",
        on_click=_move_service,
        args=(1,),
    )
    nav[2].button(
        "Jump to Current Service",
        key="service_log_jump",
        width="stretch",
        on_click=_jump_to_current_service,
        help="Select today’s AM/AFT/PM from service start times (10:00 / 2:00 / 7:30).",
    )
    st.button(
        "Suggest Current Service",
        key="service_log_suggest",
        width="stretch",
        on_click=_jump_to_current_service,
        help="Same as Jump — uses local time and Monark service start times.",
    )


def _on_current_service_changed() -> None:
    # Do not prefer the widget here — it already holds the new value.
    previous = _get_selected_service_row_id(prefer_widget=False)
    new_id = st.session_state.get("service_log_current_select")
    if previous and new_id and previous != new_id:
        _commit_inputs_to_row(previous)
    _set_selected_service_row_id(new_id)
    _stage_service_row_reload(new_id)


def _move_service(step: int) -> None:
    entries = list(st.session_state.get("service_log_entries") or [])
    current = _get_selected_service_row_id()
    _commit_inputs_to_row(current)
    nxt = adjacent_entry(entries, current, step=step)
    if not nxt:
        st.session_state.service_log_message = (
            "Already at the first service." if step < 0 else "Already at the last service."
        )
        return
    new_id = entry_key(nxt)
    _set_selected_service_row_id(new_id)
    _stage_service_row_reload(new_id)


def _jump_to_current_service() -> None:
    entries = list(st.session_state.get("service_log_entries") or [])
    _commit_inputs_to_row(_get_selected_service_row_id())
    current = find_current_service_entry(entries)
    if not current:
        st.session_state.service_log_message = (
            "Today is outside the generated Monark schedule."
        )
        return
    new_id = entry_key(current)
    _set_selected_service_row_id(new_id)
    _stage_service_row_reload(new_id)
    st.session_state.service_log_message = (
        f"Suggested service: {current['service_line']} based on current time."
    )


def _commit_inputs_to_row(row_id_value: str | None) -> None:
    if not row_id_value:
        return
    entries = list(st.session_state.get("service_log_entries") or [])
    if not entries:
        return
    if get_service_entry_by_row_id(entries, row_id_value) is None:
        return
    update_entry_text(
        entries,
        row_id_value,
        str(st.session_state.get("simple_title_input") or ""),
        str(st.session_state.get("simple_speaker_input") or ""),
    )
    st.session_state.service_log_entries = entries
    save_service_log(
        entries, year=int(st.session_state.get("service_log_year") or date.today().year)
    )


def _stage_service_row_reload(row_id_value: str | None) -> None:
    """
    Stage selected-row values for the next pre-widget apply step.

    Do not assign to widget-owned keys here (simple_title_input, etc.).
    """
    entries = list(st.session_state.get("service_log_entries") or [])
    entry = get_service_entry_by_row_id(entries, row_id_value)
    if not entry:
        return
    st.session_state.pending_service_row_id = row_id_value
    st.session_state.pending_title_input = str(entry.get("title") or "")
    st.session_state.pending_speaker_input = str(entry.get("speaker") or "")
    st.session_state.pending_notes_input = str(entry.get("notes") or "")
    st.session_state.pending_date_input = entry["date"]
    st.session_state.pending_service_input = entry["service"]
    st.session_state.pending_current_service_select = row_id_value
    st.session_state.needs_input_reload = True


def _apply_pending_input_values_before_widgets() -> None:
    """
    Apply staged service-row values to widget keys.

    This is the ONLY helper that may assign to widget-owned keys such as
    simple_title_input / simple_speaker_input / simple_date_input /
    simple_service_select / service_log_current_select.
    """
    # Support legacy pending dict used by spreadsheet/CSV paths.
    legacy = st.session_state.pop("_service_log_pending_input_sync", None)
    if isinstance(legacy, dict):
        st.session_state.pending_title_input = legacy.get("title") or ""
        st.session_state.pending_speaker_input = legacy.get("speaker") or ""
        st.session_state.pending_notes_input = legacy.get("notes") or ""
        if legacy.get("date") is not None:
            st.session_state.pending_date_input = legacy["date"]
        if legacy.get("service"):
            st.session_state.pending_service_input = legacy["service"]
        st.session_state.needs_input_reload = True

    if not st.session_state.pop("needs_input_reload", False):
        return

    if "pending_title_input" in st.session_state:
        st.session_state.simple_title_input = st.session_state.pop("pending_title_input")
    if "pending_speaker_input" in st.session_state:
        st.session_state.simple_speaker_input = st.session_state.pop(
            "pending_speaker_input"
        )
    if "pending_notes_input" in st.session_state:
        # Notes live on the spreadsheet; keep pending for future widget if added.
        st.session_state.pop("pending_notes_input", None)
    if "pending_date_input" in st.session_state:
        st.session_state.simple_date_input = st.session_state.pop("pending_date_input")
    if "pending_service_input" in st.session_state:
        st.session_state.simple_service_select = st.session_state.pop(
            "pending_service_input"
        )
    if "pending_current_service_select" in st.session_state:
        st.session_state.service_log_current_select = st.session_state.pop(
            "pending_current_service_select"
        )
    if "pending_service_row_id" in st.session_state:
        pending_id = st.session_state.pop("pending_service_row_id")
        st.session_state.selected_service_row_id = pending_id
        st.session_state.service_log_selected_row_id = pending_id


def _sync_selected_service_from_inputs(title: str, speaker: str) -> None:
    row_id_value = _get_selected_service_row_id()
    entries = list(st.session_state.get("service_log_entries") or [])
    if not row_id_value or not entries:
        return
    entry = get_service_entry_by_row_id(entries, row_id_value)
    if not entry:
        return
    if entry.get("title") == title and entry.get("speaker") == speaker:
        return
    update_entry_text(entries, row_id_value, title, speaker)
    st.session_state.service_log_entries = entries
    save_service_log(
        entries, year=int(st.session_state.get("service_log_year") or date.today().year)
    )


def _render_post_export_helpers(export_path_str: str) -> None:
    st.subheader("Post to WhatsApp")
    path = Path(export_path_str)
    st.code(str(path), language=None)
    st.caption(
        "Open the Monark Audio/Video Booth WhatsApp group, then drag this image "
        "from Downloads into the chat."
    )
    cols = st.columns(2)
    with cols[0]:
        if st.button("Reveal Image in Finder", key="reveal_export_finder", width="stretch"):
            if path.is_file() and platform.system() == "Darwin":
                try:
                    subprocess.run(["open", "-R", str(path)], check=False)
                    st.session_state.service_log_message = f"Revealed in Finder: {path}"
                except Exception as exc:
                    st.warning(f"Could not reveal in Finder: {exc}")
            elif path.is_file():
                st.info(f"Image saved at:\n{path}")
            else:
                st.warning("Exported image file was not found on disk.")
    with cols[1]:
        st.link_button("Open WhatsApp Web", WHATSAPP_WEB_URL, width="stretch")


def _render_youtube_tools() -> None:
    st.subheader("YouTube Tools")
    st.link_button(
        "Open YouTube Studio Playlist",
        YOUTUBE_PLAYLIST_URL,
        width="stretch",
    )


def _mark_selected_service_exported(output_path: Path) -> None:
    row_id_value = _get_selected_service_row_id()
    entries = list(st.session_state.get("service_log_entries") or [])
    if not row_id_value or not entries:
        st.info(
            "No service log row selected; exported image but did not update service log."
        )
        return
    selected_entry = get_service_entry_by_row_id(entries, row_id_value)
    if selected_entry is None:
        st.warning(
            f"No service log row matches `{row_id_value}`; "
            "exported image but did not update service log."
        )
        return
    updated = mark_service_exported(
        entries,
        row_id_value,
        exported_file=str(output_path),
        exported_at=datetime.now(),
    )
    if not updated:
        st.warning(
            f"Could not mark `{row_id_value}` exported; "
            "no fallback row was updated."
        )
        return
    st.session_state.service_log_entries = entries
    save_service_log(
        entries, year=int(st.session_state.get("service_log_year") or date.today().year)
    )


def _render_service_log_section() -> None:
    st.divider()
    with st.expander("Service Log", expanded=True):
        st.caption(
            "Monark meeting starts on the third Friday of July and runs "
            "10 days through Sunday night (30 services: AM / AFT / PM each day)."
        )
        year = st.number_input(
            "Service log year",
            min_value=1900,
            max_value=2100,
            step=1,
            key="service_log_year",
        )
        expected_start = get_third_friday_of_july(int(year))
        expected_end = expected_start + timedelta(days=9)
        st.caption(
            f"{int(year)} meeting: {expected_start.strftime('%A %m-%d-%y')} → "
            f"{expected_end.strftime('%A %m-%d-%y')} "
            f"({expected_start.isoformat()} … {expected_end.isoformat()})"
        )
        existing = list(st.session_state.get("service_log_entries") or [])
        schedule_warning = service_log_schedule_warning(existing, year=int(year))
        if schedule_warning:
            st.warning(schedule_warning)

        gen_cols = st.columns([1.4, 1])
        with gen_cols[0]:
            if existing:
                st.checkbox(
                    "Replace existing service log when generating",
                    key="service_log_confirm_replace",
                    help=(
                        "Required before regenerating. The current log is archived "
                        "first, then replaced with the third-Friday 10-day schedule."
                    ),
                )
            st.button(
                "Generate Monark Service Log",
                width="stretch",
                on_click=_generate_service_log_clicked,
                key="service_log_generate",
            )
            if existing:
                st.button(
                    "Regenerate Monark Service Log",
                    width="stretch",
                    on_click=_generate_service_log_clicked,
                    key="service_log_regenerate",
                    help=(
                        "Archives the current log (after confirm checkbox) and "
                        "rebuilds dates from the third Friday of July."
                    ),
                )
        with gen_cols[1]:
            st.caption(f"{len(existing)} service rows loaded")

        entries = list(st.session_state.get("service_log_entries") or [])
        if not entries:
            st.info(
                "Generate a Monark Service Log to track all services "
                "(third Friday of July, 10 days, 30 rows)."
            )
            _render_service_log_csv_controls([])
            return

        display_rows = entries_to_display_rows(entries)
        try:
            import pandas as pd

            frame = pd.DataFrame(display_rows)
            column_config = {
                "Date": st.column_config.TextColumn("Date", disabled=True),
                "Weekday": st.column_config.TextColumn("Weekday", disabled=True),
                "Service": st.column_config.TextColumn("Service", disabled=True),
                "Service Line": st.column_config.TextColumn(
                    "Service Line", disabled=True
                ),
                "Sermon Title": st.column_config.TextColumn("Sermon Title"),
                "Minister / Speaker": st.column_config.TextColumn(
                    "Minister / Speaker"
                ),
                "Notes": st.column_config.TextColumn("Notes"),
                "Exported": st.column_config.CheckboxColumn("Exported", disabled=True),
                "Exported At": st.column_config.TextColumn(
                    "Exported At", disabled=True
                ),
                "Exported File": st.column_config.TextColumn(
                    "Exported File", disabled=True
                ),
                "Include": st.column_config.CheckboxColumn("Include"),
                "_row_id": None,
            }
            edited = st.data_editor(
                frame,
                hide_index=True,
                width="stretch",
                num_rows="fixed",
                column_config=column_config,
                column_order=[
                    "Date",
                    "Weekday",
                    "Service",
                    "Service Line",
                    "Sermon Title",
                    "Minister / Speaker",
                    "Notes",
                    "Exported",
                    "Exported At",
                    "Exported File",
                    "Include",
                ],
                key="service_log_data_editor",
            )
            edited_rows = edited.to_dict(orient="records")
        except Exception:
            # Fallback without pandas-specific config.
            edited_rows = st.data_editor(
                display_rows,
                hide_index=True,
                width="stretch",
                num_rows="fixed",
                key="service_log_data_editor_fallback",
            )

        updated = apply_display_edits(entries, edited_rows)
        before = [
            (
                entry_key(entry),
                entry.get("title"),
                entry.get("speaker"),
                entry.get("notes"),
                bool(entry.get("include")),
            )
            for entry in entries
        ]
        after = [
            (
                entry_key(entry),
                entry.get("title"),
                entry.get("speaker"),
                entry.get("notes"),
                bool(entry.get("include")),
            )
            for entry in updated
        ]
        if after != before:
            st.session_state.service_log_entries = updated
            save_service_log(updated, year=int(year))
            selected = _get_selected_service_row_id()
            selected_entry = get_service_entry_by_row_id(updated, selected)
            if selected_entry is not None:
                _stage_service_row_reload(selected)
                st.rerun()

        _render_service_log_csv_controls(updated)


def _render_service_log_csv_controls(entries: list) -> None:
    c1, c2 = st.columns(2)
    csv_text = export_service_log_csv(entries) if entries else ""
    c1.download_button(
        "Export Service Log CSV",
        data=csv_text or "row_id\n",
        file_name="service_log.csv",
        mime="text/csv",
        width="stretch",
        disabled=not bool(entries),
    )
    uploaded = c2.file_uploader(
        "Import Service Log CSV",
        type=["csv"],
        key="service_log_csv_upload",
    )
    if uploaded is not None:
        try:
            text = uploaded.getvalue().decode("utf-8-sig")
            imported = import_service_log_csv(text)
            st.session_state.service_log_entries = imported
            save_service_log(
                imported,
                year=int(st.session_state.get("service_log_year") or date.today().year),
            )
            if imported:
                first_id = entry_key(imported[0])
                _set_selected_service_row_id(first_id)
                _stage_service_row_reload(first_id)
            st.session_state.service_log_message = (
                f"Imported {len(imported)} service log rows."
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Could not import CSV: {exc}")


def _generate_service_log_clicked() -> None:
    year = int(st.session_state.get("service_log_year") or date.today().year)
    _generate_service_log(year)


def _generate_service_log(year: int) -> None:
    existing = list(st.session_state.get("service_log_entries") or [])
    if existing and not st.session_state.get("service_log_confirm_replace"):
        st.session_state.service_log_message = (
            "Check “Replace existing service log when generating” before replacing. "
            "This archives the old log, then builds the third-Friday 10-day schedule."
        )
        return
    start = get_third_friday_of_july(year)
    end = start + timedelta(days=9)
    summary = (
        f"Generated Monark service log for {year}: "
        f"{start.isoformat()} (Friday) through {end.isoformat()} (Sunday), "
        "10 days / 30 services."
    )
    if existing:
        archive_path = archive_service_log(existing, year=year)
        if archive_path:
            st.session_state.service_log_message = (
                f"Previous log archived to {archive_path.name}. {summary}"
            )
        else:
            st.session_state.service_log_message = summary
    else:
        st.session_state.service_log_message = summary
    generated = generate_service_log(year)
    st.session_state.service_log_entries = generated
    save_service_log(generated, year=year)
    if generated:
        first_id = entry_key(generated[0])
        _set_selected_service_row_id(first_id)
        # Stage only — applied next run by _apply_pending_input_values_before_widgets.
        _stage_service_row_reload(first_id)
    st.session_state.service_log_confirm_replace = False


def _apply_pending_service_log_input_sync() -> None:
    """Backward-compatible alias. """
    _apply_pending_input_values_before_widgets()


def _render_preview_workspace(export_options: TitleImageOptions) -> None:
    preset_col, preview_col, nudge_col = st.columns([0.7, 2.25, 0.45], gap="small")

    with preset_col:
        st.caption("Presets")
        labels = preset_slot_labels()
        for slot in PRESET_SLOTS:
            st.button(
                labels[slot],
                key=f"simple_preset_load_{slot}",
                width="stretch",
                on_click=_apply_preset_slot,
                args=(slot,),
            )
        st.divider()
        st.selectbox(
            "Save slot",
            list(PRESET_SLOTS),
            format_func=lambda slot: f"Slot {slot}",
            key="simple_preset_save_slot",
            label_visibility="collapsed",
        )
        st.text_input(
            "Preset name",
            key="simple_preset_name",
            placeholder="Optional name",
        )
        st.button(
            "Save as Preset",
            key="simple_preset_save",
            width="stretch",
            on_click=_save_selected_preset_slot,
        )
        st.divider()
        st.button(
            "Save Current Settings as Default",
            key="simple_save_default_settings",
            width="stretch",
            on_click=_save_current_as_default,
        )
        st.button(
            "Reset to Factory Defaults",
            key="simple_reset_factory_defaults",
            width="stretch",
            on_click=_reset_to_factory_defaults,
        )
        st.button(
            "Delete Saved Default Settings",
            key="simple_delete_default_settings",
            width="stretch",
            on_click=_delete_saved_default_settings,
        )

    with preview_col:
        if hasattr(st, "segmented_control"):
            selected = st.segmented_control(
                "Selected text",
                options=list(AREA_KEYS),
                format_func=lambda key: AREA_LABELS[key],
                key="simple_selected_area",
                help="Choose which text the arrow and size buttons control.",
            )
        else:
            selected = st.radio(
                "Selected text",
                options=list(AREA_KEYS),
                format_func=lambda key: AREA_LABELS[key],
                key="simple_selected_area",
                horizontal=True,
                help="Choose which text the arrow and size buttons control.",
            )
        area = selected or st.session_state.get("simple_selected_area") or "title"
        inputs = dict(st.session_state.simple_render_inputs)
        # Respect the Show bounding boxes checkbox; selected area only highlights when on.
        options = _build_options(**inputs, selected_area=area)
        preview = render_title_image(options)
        st.image(preview, width="stretch")
        st.download_button(
            "Download clean PNG",
            data=_image_to_png_bytes(render_title_image(export_options)),
            file_name=export_filename(export_options),
            mime="image/png",
            width="stretch",
        )
        st.caption(
            f"Selected: {AREA_LABELS.get(area, area)} · "
            f"y={st.session_state[f'simple_{area}_y']} · "
            f"font={st.session_state[f'simple_{area}_font_size']}"
            f"{'' if st.session_state[f'simple_{area}_auto_size'] else ' (manual)'}"
        )

    with nudge_col:
        st.caption("Edit")
        st.button(
            ":material/keyboard_arrow_up:",
            key="simple_nudge_up",
            width="stretch",
            on_click=_nudge_selected_y,
            args=(-NUDGE_Y,),
        )
        st.button(
            ":material/keyboard_arrow_down:",
            key="simple_nudge_down",
            width="stretch",
            on_click=_nudge_selected_y,
            args=(NUDGE_Y,),
        )
        st.divider()
        st.button(
            ":material/add:",
            key="simple_font_plus",
            width="stretch",
            on_click=_scale_selected_font,
            args=(FONT_STEP,),
        )
        st.button(
            ":material/remove:",
            key="simple_font_minus",
            width="stretch",
            on_click=_scale_selected_font,
            args=(-FONT_STEP,),
        )


def _box_controls(heading: str, prefix: str, label: str) -> None:
    st.markdown(f"**{heading}**")
    row1 = st.columns(2)
    row2 = st.columns(2)
    row1[0].number_input(
        f"{label} X",
        min_value=0,
        max_value=CANVAS_WIDTH,
        step=5,
        key=f"simple_{prefix}_x",
    )
    row1[1].number_input(
        f"{label} Y",
        min_value=0,
        max_value=CANVAS_HEIGHT,
        step=5,
        key=f"simple_{prefix}_y",
    )
    row2[0].number_input(
        f"{label} Width",
        min_value=40,
        max_value=CANVAS_WIDTH,
        step=10,
        key=f"simple_{prefix}_width",
    )
    row2[1].number_input(
        f"{label} Height",
        min_value=20,
        max_value=CANVAS_HEIGHT,
        step=5,
        key=f"simple_{prefix}_height",
    )


def _ensure_simple_defaults() -> None:
    today = date.today()
    st.session_state.setdefault("simple_date_input", today)
    st.session_state.setdefault("simple_service_select", "Evening")
    st.session_state.setdefault("simple_title_input", "")
    st.session_state.setdefault("simple_speaker_input", "")
    st.session_state.setdefault("simple_last_export", "")
    st.session_state.setdefault("simple_export_location", "Downloads folder")
    st.session_state.setdefault("simple_selected_area", "title")
    st.session_state.setdefault("simple_preset_save_slot", 1)
    st.session_state.setdefault("simple_preset_name", "")
    st.session_state.setdefault("font_editor_selected_section", "title")
    st.session_state.setdefault("service_log_year", date.today().year)
    st.session_state.setdefault("selected_service_row_id", None)
    st.session_state.setdefault("service_log_selected_row_id", None)
    st.session_state.setdefault("service_log_confirm_replace", False)
    # Migrate legacy session key once.
    if (
        st.session_state.get("selected_service_row_id") is None
        and st.session_state.get("service_log_selected_row_id")
    ):
        st.session_state.selected_service_row_id = (
            st.session_state.service_log_selected_row_id
        )

    if "service_log_entries" not in st.session_state:
        loaded_log, log_warning = load_service_log()
        st.session_state.service_log_entries = loaded_log
        if log_warning:
            st.session_state.service_log_warning = log_warning
        if loaded_log:
            selected = _get_selected_service_row_id(prefer_widget=False) or entry_key(
                loaded_log[0]
            )
            _set_selected_service_row_id(selected)
            if not st.session_state.get("service_log_inputs_seeded"):
                _stage_service_row_reload(selected)
                st.session_state.service_log_inputs_seeded = True
                # Pending values are applied immediately below via
                # _apply_pending_input_values_before_widgets() in main().

    if not st.session_state.get("simple_startup_settings_applied"):
        saved_defaults, warning = load_default_settings()
        if warning:
            st.session_state.simple_settings_warning = warning
        if saved_defaults is not None:
            _apply_settings_dict(saved_defaults, reset_background_if_missing=False)
        else:
            # Prefer last session font file if present; otherwise factory.
            factory = get_factory_default_settings()
            legacy = _load_font_settings()
            if legacy:
                for role in AREA_KEYS:
                    raw = legacy.get(f"{role}_font_config") or legacy.get(
                        f"{role}_font_path"
                    )
                    if raw is not None:
                        factory[f"{role}_font_config"] = font_config_from_dict(
                            raw, role=role
                        ).to_dict()
                if "title_line_spacing" in legacy:
                    factory["title_line_spacing"] = clamp_title_line_spacing(
                        legacy["title_line_spacing"]
                    )
            _apply_settings_dict(factory, reset_background_if_missing=True)
        st.session_state.simple_startup_settings_applied = True
        st.session_state.simple_layout_version = LAYOUT_DEFAULTS_VERSION
        return

    st.session_state.setdefault("simple_show_boxes", True)
    st.session_state.setdefault(
        "simple_title_line_spacing", DEFAULT_TITLE_LINE_SPACING_PX
    )
    for role, key in FONT_CONFIG_STATE_KEYS.items():
        if key not in st.session_state:
            st.session_state[key] = default_font_config_for_role(role).to_dict()
    if st.session_state.get("simple_layout_version") != LAYOUT_DEFAULTS_VERSION:
        # Keep user-saved startup defaults; only migrate when none are saved.
        saved_defaults, _ = load_default_settings()
        if saved_defaults is None:
            _apply_settings_dict(
                get_factory_default_settings(), reset_background_if_missing=False
            )
        st.session_state.simple_layout_version = LAYOUT_DEFAULTS_VERSION
    else:
        for prefix, defaults in BOX_DEFAULTS.items():
            st.session_state.setdefault(f"simple_{prefix}_x", defaults["x"])
            st.session_state.setdefault(f"simple_{prefix}_y", defaults["y"])
            st.session_state.setdefault(f"simple_{prefix}_width", defaults["width"])
            st.session_state.setdefault(f"simple_{prefix}_height", defaults["height"])
            st.session_state.setdefault(
                f"simple_{prefix}_font_size", DEFAULT_FONT_SIZES[prefix]
            )
            st.session_state.setdefault(f"simple_{prefix}_auto_size", True)


def _reset_box_defaults() -> None:
    factory = get_factory_default_settings()
    for prefix in AREA_KEYS:
        box = factory[prefix]
        st.session_state[f"simple_{prefix}_x"] = int(box["x"])
        st.session_state[f"simple_{prefix}_y"] = int(box["y"])
        st.session_state[f"simple_{prefix}_width"] = int(box["width"])
        st.session_state[f"simple_{prefix}_height"] = int(box["height"])
        st.session_state[f"simple_{prefix}_font_size"] = int(
            box.get("font_size", DEFAULT_FONT_SIZES[prefix])
        )
        st.session_state[f"simple_{prefix}_auto_size"] = bool(box.get("auto_size", True))
    st.session_state.simple_title_line_spacing = DEFAULT_TITLE_LINE_SPACING_PX


def _read_box(prefix: str) -> dict:
    return {
        "x": int(st.session_state[f"simple_{prefix}_x"]),
        "y": int(st.session_state[f"simple_{prefix}_y"]),
        "width": int(st.session_state[f"simple_{prefix}_width"]),
        "height": int(st.session_state[f"simple_{prefix}_height"]),
        "font_size": int(st.session_state[f"simple_{prefix}_font_size"]),
        "auto_size": bool(st.session_state[f"simple_{prefix}_auto_size"]),
    }


def _center_box_x(prefix: str) -> None:
    width = int(st.session_state[f"simple_{prefix}_width"])
    st.session_state[f"simple_{prefix}_x"] = max(0, (CANVAS_WIDTH - width) // 2)


def _nudge_selected_y(delta: int) -> None:
    area = st.session_state.get("simple_selected_area") or "title"
    height = int(st.session_state[f"simple_{area}_height"])
    y = int(st.session_state[f"simple_{area}_y"]) + delta
    y = max(0, min(CANVAS_HEIGHT - height, y))
    st.session_state[f"simple_{area}_y"] = y
    _center_box_x(area)


def _scale_selected_font(delta: int) -> None:
    area = st.session_state.get("simple_selected_area") or "title"
    size = int(st.session_state[f"simple_{area}_font_size"]) + delta
    size = max(MIN_FONT, min(MAX_FONT, size))
    st.session_state[f"simple_{area}_font_size"] = size
    st.session_state[f"simple_{area}_auto_size"] = False

    # Grow/shrink the box height so larger fonts have room, keep vertical center.
    old_h = int(st.session_state[f"simple_{area}_height"])
    center_y = int(st.session_state[f"simple_{area}_y"]) + old_h // 2
    if area == "title":
        new_h = max(old_h if delta < 0 else old_h, int(size * 1.05))
        if delta < 0:
            new_h = max(80, min(old_h, int(size * 1.15)))
        else:
            new_h = max(old_h, int(size * 1.05))
    else:
        new_h = max(40, int(size * 1.15))
    new_h = min(CANVAS_HEIGHT, new_h)
    new_y = max(0, min(CANVAS_HEIGHT - new_h, center_y - new_h // 2))
    st.session_state[f"simple_{area}_height"] = new_h
    st.session_state[f"simple_{area}_y"] = new_y
    _center_box_x(area)


def _current_settings_payload(name: str) -> dict:
    configs = _current_font_configs()
    return normalize_preset_settings(
        {
            "name": name,
            "service": _read_box("service"),
            "title": _read_box("title"),
            "speaker": _read_box("speaker"),
            "service_font_config": configs["service"].to_dict(),
            "title_font_config": configs["title"].to_dict(),
            "speaker_font_config": configs["speaker"].to_dict(),
            "service_font_path": configs["service"].font_path,
            "title_font_path": configs["title"].font_path,
            "speaker_font_path": configs["speaker"].font_path,
            "background_label": st.session_state.get("simple_background_select"),
            "title_line_spacing": clamp_title_line_spacing(
                st.session_state.get(
                    "simple_title_line_spacing", DEFAULT_TITLE_LINE_SPACING_PX
                )
            ),
            "show_bounding_boxes": bool(
                st.session_state.get("simple_show_boxes", True)
            ),
        }
    )


def _apply_settings_dict(
    settings: dict,
    *,
    reset_background_if_missing: bool = False,
) -> None:
    """Apply normalized settings into session state before widgets render."""
    preset = normalize_preset_settings(settings)
    for prefix in AREA_KEYS:
        box = preset[prefix]
        st.session_state[f"simple_{prefix}_x"] = int(box["x"])
        st.session_state[f"simple_{prefix}_y"] = int(box["y"])
        st.session_state[f"simple_{prefix}_width"] = int(box["width"])
        st.session_state[f"simple_{prefix}_height"] = int(box["height"])
        st.session_state[f"simple_{prefix}_font_size"] = int(
            box.get("font_size", DEFAULT_FONT_SIZES[prefix])
        )
        st.session_state[f"simple_{prefix}_auto_size"] = bool(
            box.get("auto_size", True)
        )
        cfg = font_config_from_dict(
            preset.get(f"{prefix}_font_config") or preset.get(f"{prefix}_font_path"),
            role=prefix,
        )
        st.session_state[FONT_CONFIG_STATE_KEYS[prefix]] = cfg.to_dict()
        st.session_state[f"{prefix}_font_editor_needs_seed"] = True
    st.session_state.simple_title_line_spacing = clamp_title_line_spacing(
        preset.get("title_line_spacing", DEFAULT_TITLE_LINE_SPACING_PX)
    )
    st.session_state.simple_show_boxes = bool(preset.get("show_bounding_boxes", True))
    background = preset.get("background_label")
    if background:
        st.session_state.simple_background_select = str(background)
    elif reset_background_if_missing:
        st.session_state.simple_background_select = GENERATED_BACKGROUND


def _apply_preset_slot(slot: int) -> None:
    preset = load_preset_slot(slot)
    if not preset:
        st.session_state.simple_preset_message = (
            f"Slot {slot} is empty. Save a preset first."
        )
        return
    _apply_settings_dict(preset, reset_background_if_missing=False)
    st.session_state.simple_preset_message = "Preset loaded."


def _save_selected_preset_slot() -> None:
    slot = int(st.session_state.get("simple_preset_save_slot") or 1)
    custom_name = str(st.session_state.get("simple_preset_name") or "").strip()
    name = custom_name or f"Preset {slot}"
    save_preset_slot(slot, _current_settings_payload(name), name=name)
    st.session_state.simple_preset_message = f"Preset {slot} saved."


def _save_current_as_default() -> None:
    save_default_settings(_current_settings_payload("Startup Default"))
    st.session_state.simple_preset_message = (
        "Current settings saved as startup default."
    )


def _reset_to_factory_defaults() -> None:
    _apply_settings_dict(
        get_factory_default_settings(), reset_background_if_missing=True
    )
    st.session_state.simple_preset_message = "Factory defaults restored."


def _delete_saved_default_settings() -> None:
    if delete_default_settings():
        st.session_state.simple_preset_message = (
            "Saved default settings deleted. Restart uses factory defaults "
            "unless you save new defaults."
        )
    else:
        st.session_state.simple_preset_message = "No saved default settings file found."


def _current_font_configs() -> dict[str, FontConfig]:
    return {
        role: font_config_from_dict(
            st.session_state.get(FONT_CONFIG_STATE_KEYS[role]), role=role
        )
        for role in AREA_KEYS
    }


def _font_display_name(cfg: FontConfig, catalog: list[FontChoice]) -> str:
    by_id = {choice.font_id: choice.label for choice in catalog}
    if cfg.font_path in by_id:
        return by_id[cfg.font_path]
    return get_font_display_name(cfg.font_path)


def _render_font_settings_panel(catalog: list[FontChoice]) -> None:
    """Inline font editor — keeps the right-column preview visible for live updates."""
    with st.expander("Font Settings", expanded=False):
        st.caption(
            "Edit fonts beside the preview. Changes update live. "
            "Defaults use the font file as-is (no artificial effects)."
        )
        # Summaries for all sections
        for role in AREA_KEYS:
            cfg = font_config_from_dict(
                st.session_state.get(FONT_CONFIG_STATE_KEYS[role]), role=role
            )
            st.caption(
                f"**{FONT_SECTION_LABELS[role]}:** "
                f"{_font_display_name(cfg, catalog)} · {cfg.effects_summary()}"
            )

        if hasattr(st, "segmented_control"):
            selected = st.segmented_control(
                "Section to configure",
                options=list(AREA_KEYS),
                format_func=lambda key: FONT_SECTION_LABELS[key],
                key="font_editor_selected_section",
            )
        else:
            selected = st.radio(
                "Section to configure",
                options=list(AREA_KEYS),
                format_func=lambda key: FONT_SECTION_LABELS[key],
                key="font_editor_selected_section",
                horizontal=True,
            )
        role = selected or st.session_state.get("font_editor_selected_section") or "title"
        if role not in AREA_KEYS:
            role = "title"

        prev = st.session_state.get("_font_editor_prev_section")
        needs_seed = bool(st.session_state.pop(f"{role}_font_editor_needs_seed", False))
        if prev != role or needs_seed:
            _seed_font_editor_widgets(
                role,
                font_config_from_dict(
                    st.session_state.get(FONT_CONFIG_STATE_KEYS[role]), role=role
                ),
                catalog,
            )
            st.session_state._font_editor_prev_section = role

        _render_section_font_editor(role, catalog)

        # Live sync: widget values become the active config for this section.
        st.session_state[FONT_CONFIG_STATE_KEYS[role]] = _read_font_editor_config(
            role
        ).to_dict()

        actions = st.columns(2)
        if actions[0].button(
            "Reset this section to default",
            key=f"reset_{role}_font_section",
            width="stretch",
        ):
            st.session_state[FONT_CONFIG_STATE_KEYS[role]] = default_font_config_for_role(
                role
            ).to_dict()
            st.session_state[f"{role}_font_editor_needs_seed"] = True
            st.rerun()
        if actions[1].button(
            "Reset All Font Settings to Defaults",
            key="reset_all_font_settings",
            width="stretch",
        ):
            for area in AREA_KEYS:
                st.session_state[FONT_CONFIG_STATE_KEYS[area]] = (
                    default_font_config_for_role(area).to_dict()
                )
                st.session_state[f"{area}_font_editor_needs_seed"] = True
            st.rerun()


def _seed_font_editor_widgets(
    role: str, cfg: FontConfig, catalog: list[FontChoice]
) -> None:
    """Set editor widget keys before widgets are created (safe for Streamlit)."""
    font_ids = [choice.font_id for choice in catalog]
    font_id = cfg.font_path
    if font_id not in font_ids:
        fallback = default_font_id_for_role(role)
        font_id = fallback if fallback in font_ids else (font_ids[0] if font_ids else font_id)
    st.session_state[f"{role}_font_picker_select"] = font_id
    st.session_state["font_editor_search"] = st.session_state.get("font_editor_search", "")
    st.session_state[f"{role}_font_text_color"] = cfg.text_color or "#FFFFFF"
    st.session_state[f"{role}_font_default_style"] = bool(
        cfg.use_font_file_default_style_only
    )
    st.session_state[f"{role}_advanced_text_styling_artificial_bold"] = bool(
        cfg.artificial_bold
    )
    st.session_state[f"{role}_advanced_text_styling_artificial_italic"] = bool(
        cfg.artificial_italic
    )
    st.session_state[f"{role}_advanced_text_styling_skew_angle"] = float(cfg.skew_angle)
    st.session_state[f"{role}_advanced_text_styling_underline"] = bool(cfg.underline)
    st.session_state[f"{role}_advanced_text_styling_letter_spacing"] = float(
        cfg.letter_spacing
    )
    st.session_state[f"{role}_font_shadow_enabled"] = bool(cfg.shadow_enabled)
    st.session_state[f"{role}_font_shadow_color"] = cfg.shadow_color or "#000000"
    st.session_state[f"{role}_font_shadow_offset_x"] = int(cfg.shadow_offset_x)
    st.session_state[f"{role}_font_shadow_offset_y"] = int(cfg.shadow_offset_y)
    st.session_state[f"{role}_font_outline_enabled"] = bool(cfg.outline_enabled)
    st.session_state[f"{role}_font_outline_color"] = cfg.outline_color or "#000000"
    st.session_state[f"{role}_font_outline_width"] = int(cfg.outline_width)


def _read_font_editor_config(role: str) -> FontConfig:
    return FontConfig(
        font_path=str(
            st.session_state.get(f"{role}_font_picker_select")
            or default_font_id_for_role(role)
        ),
        text_color=str(st.session_state.get(f"{role}_font_text_color") or "#FFFFFF"),
        use_font_file_default_style_only=bool(
            st.session_state.get(f"{role}_font_default_style", True)
        ),
        artificial_bold=bool(
            st.session_state.get(f"{role}_advanced_text_styling_artificial_bold", False)
        ),
        artificial_italic=bool(
            st.session_state.get(f"{role}_advanced_text_styling_artificial_italic", False)
        ),
        skew_angle=float(
            st.session_state.get(f"{role}_advanced_text_styling_skew_angle") or 0
        ),
        underline=bool(
            st.session_state.get(f"{role}_advanced_text_styling_underline", False)
        ),
        letter_spacing=float(
            st.session_state.get(f"{role}_advanced_text_styling_letter_spacing") or 0
        ),
        shadow_enabled=bool(st.session_state.get(f"{role}_font_shadow_enabled", False)),
        shadow_color=str(st.session_state.get(f"{role}_font_shadow_color") or "#000000"),
        shadow_offset_x=int(st.session_state.get(f"{role}_font_shadow_offset_x") or 0),
        shadow_offset_y=int(st.session_state.get(f"{role}_font_shadow_offset_y") or 0),
        outline_enabled=bool(st.session_state.get(f"{role}_font_outline_enabled", False)),
        outline_color=str(
            st.session_state.get(f"{role}_font_outline_color") or "#000000"
        ),
        outline_width=int(st.session_state.get(f"{role}_font_outline_width") or 0),
    )


def _render_section_font_editor(role: str, catalog: list[FontChoice]) -> None:
    st.markdown(f"### {FONT_SECTION_LABELS[role]} font")

    st.markdown("**Font**")
    st.text_input(
        "Search fonts",
        key="font_editor_search",
        placeholder="Filter by name…",
    )
    matches = filter_fonts(
        catalog,
        st.session_state.get("font_editor_search"),
        limit=FONT_PREVIEW_LIMIT,
    )
    labels_by_id = {choice.font_id: choice.label for choice in catalog}
    font_ids = [choice.font_id for choice in matches] or [
        choice.font_id for choice in catalog[:FONT_PREVIEW_LIMIT]
    ]
    current = st.session_state.get(f"{role}_font_picker_select")
    # Keep the active selection available even if filtered out of the short list.
    if current and current not in font_ids:
        font_ids = [current] + font_ids
    if current not in font_ids and font_ids:
        # Only adjust before the selectbox is created.
        st.session_state[f"{role}_font_picker_select"] = font_ids[0]

    st.selectbox(
        "Font",
        options=font_ids,
        format_func=lambda font_id, mapping=labels_by_id: mapping.get(font_id, font_id),
        key=f"{role}_font_picker_select",
    )

    selected_id = st.session_state.get(f"{role}_font_picker_select")
    selected_choice = next(
        (choice for choice in catalog if choice.font_id == selected_id), None
    )
    sample = sample_text_for_role(role)
    if selected_choice is not None:
        st.caption("Selected font sample")
        st.image(
            _cached_font_sample_image(
                str(selected_choice.path),
                sample,
                selected_choice.path.stat().st_mtime
                if selected_choice.path.exists()
                else 0.0,
            ),
            width="stretch",
        )

    st.caption(
        f"Showing first {len(matches)} match"
        f"{'es' if len(matches) != 1 else ''} "
        f"(project fonts listed first)"
    )
    _render_font_picker_rows(role, matches, sample)

    st.markdown("**Basic Appearance**")
    st.color_picker("Text color", key=f"{role}_font_text_color")
    default_only = st.checkbox(
        "Use font file default style only",
        key=f"{role}_font_default_style",
        help=(
            "When checked, Advanced Text Styling, Shadow, and Outline are ignored "
            "and the font file is used as-is."
        ),
    )

    st.markdown(f"**{ADVANCED_TEXT_STYLING_LABEL}**")
    st.checkbox(
        "Artificial bold",
        key=f"{role}_advanced_text_styling_artificial_bold",
        disabled=default_only,
    )
    st.checkbox(
        "Artificial italic",
        key=f"{role}_advanced_text_styling_artificial_italic",
        disabled=default_only,
    )
    st.slider(
        "Skew / slant angle",
        min_value=-25.0,
        max_value=25.0,
        step=0.5,
        key=f"{role}_advanced_text_styling_skew_angle",
        disabled=default_only,
        help="Positive slants right; negative slants left.",
    )
    st.checkbox(
        "Underline",
        key=f"{role}_advanced_text_styling_underline",
        disabled=default_only,
    )
    st.slider(
        "Letter spacing",
        min_value=-10.0,
        max_value=50.0,
        step=0.5,
        key=f"{role}_advanced_text_styling_letter_spacing",
        disabled=default_only,
    )

    st.markdown("**Shadow**")
    st.checkbox(
        "Enable shadow",
        key=f"{role}_font_shadow_enabled",
        disabled=default_only,
    )
    st.color_picker(
        "Shadow color",
        key=f"{role}_font_shadow_color",
        disabled=default_only,
    )
    shadow_cols = st.columns(2)
    shadow_cols[0].number_input(
        "Shadow X offset",
        min_value=-40,
        max_value=40,
        step=1,
        key=f"{role}_font_shadow_offset_x",
        disabled=default_only,
    )
    shadow_cols[1].number_input(
        "Shadow Y offset",
        min_value=-40,
        max_value=40,
        step=1,
        key=f"{role}_font_shadow_offset_y",
        disabled=default_only,
    )

    st.markdown("**Outline**")
    st.checkbox(
        "Enable outline",
        key=f"{role}_font_outline_enabled",
        disabled=default_only,
    )
    st.color_picker(
        "Outline color",
        key=f"{role}_font_outline_color",
        disabled=default_only,
    )
    st.slider(
        "Outline width",
        min_value=0,
        max_value=20,
        step=1,
        key=f"{role}_font_outline_width",
        disabled=default_only,
    )


def _render_font_picker_rows(
    role: str, matches: list[FontChoice], sample: str
) -> None:
    if not matches:
        st.info("No fonts match this search.")
        return
    for index, choice in enumerate(matches):
        row = st.columns([3.2, 0.9])
        with row[0]:
            st.caption(choice.label)
            mtime = choice.path.stat().st_mtime if choice.path.exists() else 0.0
            st.image(
                _cached_font_sample_image(str(choice.path), sample, mtime),
                width="stretch",
            )
        safe_name = choice.path.name.replace(" ", "_")
        row[1].button(
            "Select",
            key=f"{role}_font_picker_select_btn_{index}_{safe_name}",
            width="stretch",
            on_click=_select_font_for_role,
            args=(role, choice.font_id),
        )


def _select_font_for_role(role: str, font_id: str) -> None:
    """Callback: update picker selection before the next widget render."""
    st.session_state[f"{role}_font_picker_select"] = font_id
    cfg = font_config_from_dict(
        st.session_state.get(FONT_CONFIG_STATE_KEYS[role]), role=role
    )
    cfg.font_path = font_id
    st.session_state[FONT_CONFIG_STATE_KEYS[role]] = cfg.to_dict()


@st.cache_data(show_spinner=False)
def _cached_font_sample_image(path_str: str, sample: str, mtime: float) -> bytes:
    from io import BytesIO

    image = safely_render_font_sample(path_str, sample)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    _ = mtime  # invalidate cache when the font file changes
    return buffer.getvalue()


def _load_font_settings() -> dict:
    if not FONT_SETTINGS_PATH.exists():
        return {}
    try:
        payload = json.loads(FONT_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _persist_font_settings() -> None:
    FONT_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    configs = _current_font_configs()
    payload = {
        "service_font_config": configs["service"].to_dict(),
        "title_font_config": configs["title"].to_dict(),
        "speaker_font_config": configs["speaker"].to_dict(),
        "service_font_path": configs["service"].font_path,
        "title_font_path": configs["title"].font_path,
        "speaker_font_path": configs["speaker"].font_path,
        "title_line_spacing": clamp_title_line_spacing(
            st.session_state.get(
                "simple_title_line_spacing", DEFAULT_TITLE_LINE_SPACING_PX
            )
        ),
    }
    FONT_SETTINGS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _build_options(
    *,
    day: str,
    service: str,
    service_date: date,
    sermon_title: str,
    speaker: str,
    background_label: str,
    background_labels: list[str],
    templates: list[Path],
    show_boxes: bool,
    selected_area: str | None,
    service_font_config: FontConfig | None = None,
    title_font_config: FontConfig | None = None,
    speaker_font_config: FontConfig | None = None,
    service_font_path: Path | None = None,
    title_font_path: Path | None = None,
    speaker_font_path: Path | None = None,
    title_line_spacing: int = DEFAULT_TITLE_LINE_SPACING_PX,
) -> TitleImageOptions:
    background_path = None
    if background_label != GENERATED_BACKGROUND and background_label in background_labels:
        index = background_labels.index(background_label) - 1
        if 0 <= index < len(templates):
            background_path = templates[index]

    spacing = clamp_title_line_spacing(title_line_spacing)
    return TitleImageOptions(
        day=day,
        service=service,
        service_date=service_date,
        sermon_title=sermon_title,
        speaker_name=speaker,
        background_path=background_path,
        show_bounding_boxes=show_boxes,
        selected_layout_area=normalize_selected_area(selected_area),
        shadow_enabled=False,
        text_color="#FFFFFF",
        title_line_spacing=spacing,
        service_font_config=service_font_config,
        title_font_config=title_font_config,
        speaker_font_config=speaker_font_config,
        service_font_path=service_font_path,
        title_font_path=title_font_path,
        speaker_font_path=speaker_font_path,
        service_line_box=text_box_from_dict(_read_box("service")),
        title_box=text_box_from_dict(_read_box("title"), line_gap_adjust=spacing),
        speaker_box=text_box_from_dict(_read_box("speaker")),
    )


def _image_to_png_bytes(image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


if __name__ == "__main__":
    main()
