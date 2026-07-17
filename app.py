from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from io import BytesIO
from pathlib import Path

import streamlit as st

from font_discovery import (
    FontChoice,
    default_font_id_for_role,
    discover_fonts,
    resolve_selected_font,
)
from monark_schedule import find_current_service_entry, get_monark_service_entries
from simple_presets import (
    PRESET_SLOTS,
    load_preset,
    preset_slot_labels,
    save_preset,
)
from title_renderer import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    DEFAULT_SERVICE_BOX,
    DEFAULT_SPEAKER_BOX,
    DEFAULT_TITLE_BOX,
    EXPORTS_DIR,
    LAYOUT_DEFAULTS_VERSION,
    MAX_TITLE_FONT_SIZE,
    PROJECT_ROOT,
    TitleImageOptions,
    ensure_project_dirs,
    export_filename,
    list_template_backgrounds,
    normalize_selected_area,
    render_title_image,
    service_code,
    text_box_from_dict,
)


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
FONT_SELECT_KEYS = {
    "service": "simple_service_font_select",
    "title": "simple_title_font_select",
    "speaker": "simple_speaker_font_select",
}


@st.cache_data(show_spinner=False)
def _font_catalog() -> list[FontChoice]:
    return discover_fonts()


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
        service_date = simple_date if isinstance(simple_date, date) else date.today()
        day = service_date.strftime("%A")
        st.markdown(f"**Day:** {day}")
        st.caption("Day is calculated from the selected date.")
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
                    st.session_state.simple_service_select = current["service"]
                    st.success(f"Selected {current['service_line']}")
                    st.rerun()
                else:
                    st.info("Today is not in the generated Monark schedule.")

        st.subheader("Title")
        sermon_title = st.text_area(
            "Sermon title",
            height=120,
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
            help="Preview guides only. Normal export stays clean.",
        )

        catalog = _font_catalog()
        font_ids = [choice.font_id for choice in catalog]
        labels_by_id = {choice.font_id: choice.label for choice in catalog}
        with st.expander("Font Choices", expanded=False):
            st.caption(
                "Fonts from the project fonts/ folder and installed system fonts."
            )
            for role, label in (
                ("service", "Service Line Font"),
                ("title", "Sermon Title Font"),
                ("speaker", "Speaker / Minister Font"),
            ):
                key = FONT_SELECT_KEYS[role]
                if st.session_state.get(key) not in font_ids and font_ids:
                    fallback = default_font_id_for_role(role)
                    st.session_state[key] = (
                        fallback if fallback in font_ids else font_ids[0]
                    )
                    st.warning(
                        f"{label}: saved font missing — using "
                        f"{labels_by_id.get(st.session_state[key], 'default')}."
                    )
                st.selectbox(
                    label,
                    options=font_ids,
                    format_func=lambda font_id, mapping=labels_by_id: mapping.get(
                        font_id, font_id
                    ),
                    key=key,
                )

        with st.expander("Bounding box numbers", expanded=False):
            if st.button("Reset boxes to defaults", width="stretch"):
                _reset_box_defaults()
                st.rerun()
            _box_controls("Service Line Box", "service", "Service")
            _box_controls("Sermon Title Box", "title", "Title")
            _box_controls("Speaker / Minister Box", "speaker", "Speaker")

        selected_fonts = _selected_font_paths(catalog)
        _persist_font_settings()

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
            "service_font_path": selected_fonts["service"],
            "title_font_path": selected_fonts["title"],
            "speaker_font_path": selected_fonts["speaker"],
        }

        export_options = _build_options(
            **st.session_state.simple_render_inputs,
            selected_area=None,
        )
        export_options = replace(
            export_options, show_bounding_boxes=False, selected_layout_area=None
        )
        if st.button("Export PNG", type="primary", width="stretch"):
            output_path = EXPORTS_DIR / export_filename(export_options)
            render_title_image(export_options).save(output_path, "PNG")
            st.session_state.simple_last_export = str(output_path)
            st.success(f"Saved to {output_path}")

        if st.session_state.get("simple_last_export"):
            st.caption(f"Last export: {st.session_state.simple_last_export}")

        st.caption(
            "Fonts: service/speaker "
            f"{(selected_fonts['service'] or Path('fallback')).name}; "
            f"title {(selected_fonts['title'] or Path('fallback')).name}; "
            "white text; no shadow; export 1920×1080"
        )

    with right:
        st.subheader("Preview")
        message = st.session_state.pop("simple_preset_message", "")
        if message:
            st.info(message)
        _render_preview_workspace(export_options)


def _render_preview_workspace(export_options: TitleImageOptions) -> None:
    preset_col, preview_col, nudge_col = st.columns([0.55, 2.4, 0.45], gap="small")

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
        st.button(
            "Save as Preset",
            key="simple_preset_save",
            width="stretch",
            on_click=_save_selected_preset_slot,
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
    st.session_state.setdefault("simple_show_boxes", True)
    st.session_state.setdefault("simple_last_export", "")
    st.session_state.setdefault("simple_selected_area", "title")
    st.session_state.setdefault("simple_preset_save_slot", 1)
    saved_fonts = _load_font_settings()
    for role, key in FONT_SELECT_KEYS.items():
        st.session_state.setdefault(
            key,
            saved_fonts.get(f"{role}_font_path") or default_font_id_for_role(role),
        )
    if st.session_state.get("simple_layout_version") != LAYOUT_DEFAULTS_VERSION:
        _reset_box_defaults()
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
    for prefix, defaults in BOX_DEFAULTS.items():
        st.session_state[f"simple_{prefix}_x"] = defaults["x"]
        st.session_state[f"simple_{prefix}_y"] = defaults["y"]
        st.session_state[f"simple_{prefix}_width"] = defaults["width"]
        st.session_state[f"simple_{prefix}_height"] = defaults["height"]
        st.session_state[f"simple_{prefix}_font_size"] = DEFAULT_FONT_SIZES[prefix]
        st.session_state[f"simple_{prefix}_auto_size"] = True


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


def _current_preset_payload(name: str) -> dict:
    return {
        "name": name,
        "service": _read_box("service"),
        "title": _read_box("title"),
        "speaker": _read_box("speaker"),
        "service_font_path": st.session_state.get(
            FONT_SELECT_KEYS["service"], default_font_id_for_role("service")
        ),
        "title_font_path": st.session_state.get(
            FONT_SELECT_KEYS["title"], default_font_id_for_role("title")
        ),
        "speaker_font_path": st.session_state.get(
            FONT_SELECT_KEYS["speaker"], default_font_id_for_role("speaker")
        ),
    }


def _apply_preset_slot(slot: int) -> None:
    preset = load_preset(slot)
    if not preset:
        st.session_state.simple_preset_message = f"Slot {slot} is empty. Save a preset first."
        return
    for prefix in AREA_KEYS:
        box = preset[prefix]
        st.session_state[f"simple_{prefix}_x"] = int(box["x"])
        st.session_state[f"simple_{prefix}_y"] = int(box["y"])
        st.session_state[f"simple_{prefix}_width"] = int(box["width"])
        st.session_state[f"simple_{prefix}_height"] = int(box["height"])
        st.session_state[f"simple_{prefix}_font_size"] = int(
            box.get("font_size", DEFAULT_FONT_SIZES[prefix])
        )
        st.session_state[f"simple_{prefix}_auto_size"] = bool(box.get("auto_size", True))
    st.session_state[FONT_SELECT_KEYS["service"]] = str(
        preset.get("service_font_path") or default_font_id_for_role("service")
    )
    st.session_state[FONT_SELECT_KEYS["title"]] = str(
        preset.get("title_font_path") or default_font_id_for_role("title")
    )
    st.session_state[FONT_SELECT_KEYS["speaker"]] = str(
        preset.get("speaker_font_path") or default_font_id_for_role("speaker")
    )
    st.session_state.simple_preset_message = f"Loaded preset slot {slot}."


def _save_selected_preset_slot() -> None:
    slot = int(st.session_state.get("simple_preset_save_slot") or 1)
    save_preset(slot, _current_preset_payload(f"Preset {slot}"))
    st.session_state.simple_preset_message = f"Saved to slot {slot}."


def _selected_font_paths(catalog: list[FontChoice]) -> dict[str, Path | None]:
    return {
        "service": resolve_selected_font(
            st.session_state.get(FONT_SELECT_KEYS["service"]),
            role="service",
            catalog=catalog,
        ),
        "title": resolve_selected_font(
            st.session_state.get(FONT_SELECT_KEYS["title"]),
            role="title",
            catalog=catalog,
        ),
        "speaker": resolve_selected_font(
            st.session_state.get(FONT_SELECT_KEYS["speaker"]),
            role="speaker",
            catalog=catalog,
        ),
    }


def _load_font_settings() -> dict[str, str]:
    if not FONT_SETTINGS_PATH.exists():
        return {}
    try:
        payload = json.loads(FONT_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        key: str(payload[key])
        for key in (
            "service_font_path",
            "title_font_path",
            "speaker_font_path",
        )
        if payload.get(key)
    }


def _persist_font_settings() -> None:
    FONT_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "service_font_path": st.session_state.get(
            FONT_SELECT_KEYS["service"], default_font_id_for_role("service")
        ),
        "title_font_path": st.session_state.get(
            FONT_SELECT_KEYS["title"], default_font_id_for_role("title")
        ),
        "speaker_font_path": st.session_state.get(
            FONT_SELECT_KEYS["speaker"], default_font_id_for_role("speaker")
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
    service_font_path: Path | None = None,
    title_font_path: Path | None = None,
    speaker_font_path: Path | None = None,
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
        selected_layout_area=normalize_selected_area(selected_area),
        shadow_enabled=False,
        text_color="#FFFFFF",
        service_font_path=service_font_path,
        title_font_path=title_font_path,
        speaker_font_path=speaker_font_path,
        service_line_box=text_box_from_dict(_read_box("service")),
        title_box=text_box_from_dict(_read_box("title")),
        speaker_box=text_box_from_dict(_read_box("speaker")),
    )


def _image_to_png_bytes(image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


if __name__ == "__main__":
    main()
