from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
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
FONT_CONFIG_STATE_KEYS = {
    "service": "simple_service_font_config",
    "title": "simple_title_font_config",
    "speaker": "simple_speaker_font_config",
}
FONT_DIALOG_TITLES = {
    "service": "Configure Service Line Font",
    "title": "Configure Sermon Title Font",
    "speaker": "Configure Minister / Speaker Font",
}
FONT_SECTION_LABELS = {
    "service": "Service Line",
    "title": "Sermon Title",
    "speaker": "Minister / Speaker",
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
        _render_font_settings_panel(catalog)
        _maybe_open_font_dialog(catalog)
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
            "Fonts configured per section · white by default · "
            "effects off unless enabled · export 1920×1080"
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
    for role, key in FONT_CONFIG_STATE_KEYS.items():
        if key not in st.session_state:
            raw = saved_fonts.get(f"{role}_font_config")
            if raw is None and saved_fonts.get(f"{role}_font_path"):
                raw = saved_fonts[f"{role}_font_path"]
            st.session_state[key] = font_config_from_dict(raw, role=role).to_dict()
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
    configs = _current_font_configs()
    return {
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
        st.session_state[FONT_CONFIG_STATE_KEYS[prefix]] = font_config_from_dict(
            preset.get(f"{prefix}_font_config") or preset.get(f"{prefix}_font_path"),
            role=prefix,
        ).to_dict()
    if preset.get("background_label"):
        st.session_state.simple_background_select = str(preset["background_label"])
    st.session_state.simple_preset_message = f"Loaded preset slot {slot}."


def _save_selected_preset_slot() -> None:
    slot = int(st.session_state.get("simple_preset_save_slot") or 1)
    save_preset(slot, _current_preset_payload(f"Preset {slot}"))
    st.session_state.simple_preset_message = f"Saved to slot {slot}."


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
    return Path(cfg.font_path).name or cfg.font_path


def _render_font_settings_panel(catalog: list[FontChoice]) -> None:
    with st.expander("Font Settings", expanded=False):
        st.caption(
            "Each section has its own font file and optional fancy effects. "
            "Defaults use the font file as-is (no artificial effects)."
        )
        for role in AREA_KEYS:
            cfg = font_config_from_dict(
                st.session_state.get(FONT_CONFIG_STATE_KEYS[role]), role=role
            )
            st.markdown(f"**{FONT_SECTION_LABELS[role]}**")
            st.caption(
                f"{_font_display_name(cfg, catalog)} · {cfg.effects_summary()}"
            )
            cols = st.columns([1.4, 1])
            if cols[0].button(
                f"Configure {FONT_SECTION_LABELS[role]} Font",
                key=f"open_{role}_font_dialog",
                width="stretch",
            ):
                _seed_font_dialog_widgets(role, cfg, catalog)
                st.session_state.simple_font_dialog_role = role
                st.rerun()
            if cols[1].button(
                "Reset",
                key=f"reset_{role}_font_inline",
                width="stretch",
                help=f"Reset {FONT_SECTION_LABELS[role]} font to default",
            ):
                st.session_state[FONT_CONFIG_STATE_KEYS[role]] = (
                    default_font_config_for_role(role).to_dict()
                )
                st.rerun()
        if st.button(
            "Reset All Font Settings to Defaults",
            key="reset_all_font_settings",
            width="stretch",
        ):
            for role in AREA_KEYS:
                st.session_state[FONT_CONFIG_STATE_KEYS[role]] = (
                    default_font_config_for_role(role).to_dict()
                )
            st.rerun()


def _maybe_open_font_dialog(catalog: list[FontChoice]) -> None:
    role = st.session_state.get("simple_font_dialog_role")
    if role not in AREA_KEYS:
        return
    if hasattr(st, "dialog"):
        _FONT_DIALOGS[role](catalog)
    else:
        with st.expander(FONT_DIALOG_TITLES[role], expanded=True):
            _font_config_dialog_body(role, catalog)


def _seed_font_dialog_widgets(
    role: str, cfg: FontConfig, catalog: list[FontChoice]
) -> None:
    """Set dialog widget keys before widgets are created (safe for Streamlit)."""
    font_ids = [choice.font_id for choice in catalog]
    font_id = cfg.font_path
    if font_id not in font_ids:
        fallback = default_font_id_for_role(role)
        font_id = fallback if fallback in font_ids else (font_ids[0] if font_ids else font_id)
    st.session_state[f"{role}_font_dialog_font_select"] = font_id
    st.session_state[f"{role}_font_dialog_search"] = ""
    st.session_state[f"{role}_font_dialog_text_color"] = cfg.text_color or "#FFFFFF"
    st.session_state[f"{role}_font_dialog_default_style"] = bool(
        cfg.use_font_file_default_style_only
    )
    st.session_state[f"{role}_font_dialog_artificial_bold"] = bool(cfg.artificial_bold)
    st.session_state[f"{role}_font_dialog_artificial_italic"] = bool(cfg.artificial_italic)
    st.session_state[f"{role}_font_dialog_skew_angle"] = float(cfg.skew_angle)
    st.session_state[f"{role}_font_dialog_underline"] = bool(cfg.underline)
    st.session_state[f"{role}_font_dialog_letter_spacing"] = float(cfg.letter_spacing)
    st.session_state[f"{role}_font_shadow_enabled"] = bool(cfg.shadow_enabled)
    st.session_state[f"{role}_font_shadow_color"] = cfg.shadow_color or "#000000"
    st.session_state[f"{role}_font_shadow_offset_x"] = int(cfg.shadow_offset_x)
    st.session_state[f"{role}_font_shadow_offset_y"] = int(cfg.shadow_offset_y)
    st.session_state[f"{role}_font_outline_enabled"] = bool(cfg.outline_enabled)
    st.session_state[f"{role}_font_outline_color"] = cfg.outline_color or "#000000"
    st.session_state[f"{role}_font_outline_width"] = int(cfg.outline_width)


def _read_font_dialog_config(role: str) -> FontConfig:
    return FontConfig(
        font_path=str(
            st.session_state.get(f"{role}_font_dialog_font_select")
            or default_font_id_for_role(role)
        ),
        text_color=str(
            st.session_state.get(f"{role}_font_dialog_text_color") or "#FFFFFF"
        ),
        use_font_file_default_style_only=bool(
            st.session_state.get(f"{role}_font_dialog_default_style", True)
        ),
        artificial_bold=bool(
            st.session_state.get(f"{role}_font_dialog_artificial_bold", False)
        ),
        artificial_italic=bool(
            st.session_state.get(f"{role}_font_dialog_artificial_italic", False)
        ),
        skew_angle=float(st.session_state.get(f"{role}_font_dialog_skew_angle") or 0),
        underline=bool(st.session_state.get(f"{role}_font_dialog_underline", False)),
        letter_spacing=float(
            st.session_state.get(f"{role}_font_dialog_letter_spacing") or 0
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


def _font_config_dialog_body(role: str, catalog: list[FontChoice]) -> None:
    if st.session_state.pop(f"{role}_font_dialog_needs_seed", False):
        _seed_font_dialog_widgets(
            role,
            font_config_from_dict(
                st.session_state.get(FONT_CONFIG_STATE_KEYS[role]), role=role
            ),
            catalog,
        )
    labels_by_id = {choice.font_id: choice.label for choice in catalog}
    search = st.text_input(
        "Search fonts",
        key=f"{role}_font_dialog_search",
        placeholder="Filter by name…",
    )
    query = (search or "").strip().lower()
    font_ids = [
        choice.font_id
        for choice in catalog
        if not query or query in choice.label.lower() or query in choice.font_id.lower()
    ]
    if not font_ids and catalog:
        font_ids = [choice.font_id for choice in catalog]
    current = st.session_state.get(f"{role}_font_dialog_font_select")
    if current not in font_ids and font_ids:
        st.session_state[f"{role}_font_dialog_font_select"] = font_ids[0]

    st.selectbox(
        "Font",
        options=font_ids,
        format_func=lambda font_id, mapping=labels_by_id: mapping.get(font_id, font_id),
        key=f"{role}_font_dialog_font_select",
    )
    st.color_picker("Text color", key=f"{role}_font_dialog_text_color")
    default_only = st.checkbox(
        "Use font file default style only",
        key=f"{role}_font_dialog_default_style",
        help="When checked, fancy effects are ignored and the font file is used as-is.",
    )

    st.markdown("**Fancy options**")
    fancy = st.container()
    with fancy:
        st.checkbox(
            "Artificial bold",
            key=f"{role}_font_dialog_artificial_bold",
            disabled=default_only,
        )
        st.checkbox(
            "Artificial italic",
            key=f"{role}_font_dialog_artificial_italic",
            disabled=default_only,
        )
        st.slider(
            "Skew / slant angle",
            min_value=-25.0,
            max_value=25.0,
            step=0.5,
            key=f"{role}_font_dialog_skew_angle",
            disabled=default_only,
            help="Positive slants right; negative slants left.",
        )
        st.checkbox(
            "Underline",
            key=f"{role}_font_dialog_underline",
            disabled=default_only,
        )
        st.slider(
            "Letter spacing",
            min_value=-10.0,
            max_value=50.0,
            step=0.5,
            key=f"{role}_font_dialog_letter_spacing",
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
        c1, c2 = st.columns(2)
        c1.number_input(
            "Shadow X",
            min_value=-40,
            max_value=40,
            step=1,
            key=f"{role}_font_shadow_offset_x",
            disabled=default_only,
        )
        c2.number_input(
            "Shadow Y",
            min_value=-40,
            max_value=40,
            step=1,
            key=f"{role}_font_shadow_offset_y",
            disabled=default_only,
        )

        st.markdown("**Outline / stroke**")
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

    b1, b2, b3 = st.columns(3)
    if b1.button("Apply", key=f"{role}_font_dialog_apply", type="primary", width="stretch"):
        st.session_state[FONT_CONFIG_STATE_KEYS[role]] = _read_font_dialog_config(
            role
        ).to_dict()
        st.session_state.simple_font_dialog_role = None
        st.rerun()
    if b2.button("Cancel", key=f"{role}_font_dialog_cancel", width="stretch"):
        st.session_state.simple_font_dialog_role = None
        st.rerun()
    if b3.button(
        "Reset this section to default",
        key=f"{role}_font_dialog_reset",
        width="stretch",
    ):
        st.session_state[FONT_CONFIG_STATE_KEYS[role]] = default_font_config_for_role(
            role
        ).to_dict()
        st.session_state[f"{role}_font_dialog_needs_seed"] = True
        st.rerun()


if hasattr(st, "dialog"):

    @st.dialog("Configure Service Line Font", width="large")
    def _service_font_dialog(catalog: list[FontChoice]) -> None:
        _font_config_dialog_body("service", catalog)

    @st.dialog("Configure Sermon Title Font", width="large")
    def _title_font_dialog(catalog: list[FontChoice]) -> None:
        _font_config_dialog_body("title", catalog)

    @st.dialog("Configure Minister / Speaker Font", width="large")
    def _speaker_font_dialog(catalog: list[FontChoice]) -> None:
        _font_config_dialog_body("speaker", catalog)

    _FONT_DIALOGS = {
        "service": _service_font_dialog,
        "title": _title_font_dialog,
        "speaker": _speaker_font_dialog,
    }

else:

    def _fallback_font_dialog(catalog: list[FontChoice], *, role: str) -> None:
        _font_config_dialog_body(role, catalog)

    _FONT_DIALOGS = {
        "service": lambda catalog: _fallback_font_dialog(catalog, role="service"),
        "title": lambda catalog: _fallback_font_dialog(catalog, role="title"),
        "speaker": lambda catalog: _fallback_font_dialog(catalog, role="speaker"),
    }


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
        service_font_config=service_font_config,
        title_font_config=title_font_config,
        speaker_font_config=speaker_font_config,
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
