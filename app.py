from __future__ import annotations

from dataclasses import replace
from datetime import date
from io import BytesIO
from pathlib import Path

import streamlit as st

from monark_schedule import find_current_service_entry, get_monark_service_entries
from title_renderer import (
    BARLOW_BOLD_ITALIC,
    EXPORTS_DIR,
    TITLE_VERTICAL_GAP,
    TitleImageOptions,
    compute_title_box,
    default_font_path,
    ensure_project_dirs,
    export_filename,
    list_template_backgrounds,
    render_title_image,
    service_code,
)


DAYS = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]
SERVICES = ["Morning", "Afternoon", "Evening"]
SERVICE_LABELS = {"Morning": "AM", "Afternoon": "AFT", "Evening": "PM"}
GENERATED_BACKGROUND = "Generated blue/gray background"
OFFSET_STEP = 10
OFFSET_MIN = -150
OFFSET_MAX = 150


def main() -> None:
    ensure_project_dirs()
    st.set_page_config(page_title="TitleMaker", layout="wide")
    st.title("TitleMaker")
    st.caption("Simple Monark Springs livestream title maker")

    _ensure_simple_defaults()

    templates = list_template_backgrounds()
    background_labels = [GENERATED_BACKGROUND] + [path.name for path in templates]
    if "simple_background_select" not in st.session_state:
        st.session_state.simple_background_select = (
            templates[0].name if templates else GENERATED_BACKGROUND
        )

    left, right = st.columns([0.95, 1.25], gap="large")

    with left:
        st.subheader("Service")
        simple_date = st.date_input("Date", key="simple_date_input")
        day = st.selectbox("Day", DAYS, key="simple_day_select")
        service = st.selectbox(
            "Service",
            SERVICES,
            format_func=lambda name: f"{SERVICE_LABELS[name]} ({name})",
            key="simple_service_select",
        )

        with st.expander("Optional Monark schedule helpers", expanded=False):
            year = st.number_input(
                "Schedule year",
                min_value=1900,
                max_value=2100,
                value=date.today().year,
                step=1,
                key="simple_schedule_year",
            )
            if st.button("Jump to current Monark service", width="stretch"):
                entries = get_monark_service_entries(int(year))
                current = find_current_service_entry(entries)
                if current:
                    st.session_state.simple_date_input = current["date"]
                    st.session_state.simple_day_select = current["weekday"]
                    st.session_state.simple_service_select = current["service"]
                    st.success(f"Selected {current['service_line']}")
                    st.rerun()
                else:
                    st.info("Today is not in the generated Monark schedule.")

        st.subheader("Title")
        sermon_title = st.text_area(
            "Sermon title",
            height=140,
            key="simple_title_input",
            placeholder="Type title here...",
        )
        speaker = st.text_input(
            "Speaker / Minister",
            key="simple_speaker_input",
            placeholder="Type speaker here...",
        )

        st.subheader("Background")
        background_label = st.selectbox(
            "Background image",
            background_labels,
            key="simple_background_select",
        )

        show_boxes = st.checkbox(
            "Show bounding boxes",
            key="simple_show_boxes",
        )

        st.subheader("Title position")
        offset = int(st.session_state.simple_title_offset)
        move_cols = st.columns(3)
        if move_cols[0].button("Move Title Up", width="stretch"):
            st.session_state.simple_title_offset = max(OFFSET_MIN, offset - OFFSET_STEP)
            st.rerun()
        if move_cols[1].button("Move Title Down", width="stretch"):
            st.session_state.simple_title_offset = min(OFFSET_MAX, offset + OFFSET_STEP)
            st.rerun()
        if move_cols[2].button("Reset Title Position", width="stretch"):
            st.session_state.simple_title_offset = 0
            st.rerun()

        st.slider(
            "Title vertical offset",
            min_value=OFFSET_MIN,
            max_value=OFFSET_MAX,
            key="simple_title_offset",
            help="Moves the title box up (-) or down (+) between the service and speaker lines.",
        )

        options = _build_options(
            day=day,
            service=service,
            service_date=simple_date if isinstance(simple_date, date) else date.today(),
            sermon_title=sermon_title,
            speaker=speaker,
            background_label=background_label,
            background_labels=background_labels,
            templates=templates,
            show_boxes=show_boxes,
            title_offset=int(st.session_state.simple_title_offset),
        )

        export_options = replace(options, show_bounding_boxes=False)
        if st.button("Export PNG", type="primary", width="stretch"):
            output_path = EXPORTS_DIR / export_filename(export_options)
            render_title_image(export_options).save(output_path, "PNG")
            st.session_state.simple_last_export = str(output_path)
            st.success(f"Saved to {output_path}")

        if st.session_state.get("simple_last_export"):
            st.caption(f"Last export: {st.session_state.simple_last_export}")

        font_path = default_font_path()
        st.caption(
            f"Font: {font_path.name if font_path else 'system fallback'} · "
            f"Export size: 1920×1080 · Title gap: {TITLE_VERTICAL_GAP}px"
        )

    with right:
        st.subheader("Preview")
        preview = render_title_image(options)
        st.image(preview, width="stretch")
        st.download_button(
            "Download clean PNG",
            data=_image_to_png_bytes(render_title_image(export_options)),
            file_name=export_filename(export_options),
            mime="image/png",
            width="stretch",
        )
        title_box = compute_title_box(int(st.session_state.simple_title_offset))
        st.caption(
            f"Service: {options.day.upper()} {service_code(options.service)} · "
            f"Title box y={title_box['y']} h={title_box['height']}"
        )


def _ensure_simple_defaults() -> None:
    today = date.today()
    st.session_state.setdefault("simple_date_input", today)
    st.session_state.setdefault("simple_day_select", today.strftime("%A"))
    st.session_state.setdefault("simple_service_select", "Evening")
    st.session_state.setdefault("simple_title_input", "")
    st.session_state.setdefault("simple_speaker_input", "")
    # Background default is set in main() once templates are known.
    st.session_state.setdefault("simple_show_boxes", False)
    st.session_state.setdefault("simple_title_offset", 0)
    st.session_state.setdefault("simple_last_export", "")
    # Preferred font path exists for diagnostics only.
    st.session_state.setdefault(
        "simple_font_path",
        str(BARLOW_BOLD_ITALIC if BARLOW_BOLD_ITALIC.exists() else ""),
    )


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
    title_offset: int,
) -> TitleImageOptions:
    background_path = None
    if background_label != GENERATED_BACKGROUND and background_label in background_labels:
        index = background_labels.index(background_label) - 1
        if 0 <= index < len(templates):
            background_path = templates[index]

    return TitleImageOptions(
        day=day,
        service=service,
        service_date=service_date,
        sermon_title=sermon_title,
        speaker_name=speaker,
        background_path=background_path,
        show_bounding_boxes=show_boxes,
        title_vertical_offset=title_offset,
    )


def _image_to_png_bytes(image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


if __name__ == "__main__":
    main()
