from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import streamlit as st

from booth_mode import (
    NO_SCHEDULE_MESSAGE,
    booth_service_labels,
    load_entry_values,
    mark_booth_exported,
    next_service_index,
    previous_service_index,
    update_booth_entry,
)
from export_settings import (
    EXPORT_LAYOUT_MODES,
    EXPORT_TARGET_NAMES,
    default_export_settings,
    export_filename_for_target,
    migrate_export_settings,
    render_for_export,
    resolve_export_target,
    resolve_multi_targets,
)
from font_settings import (
    AUTOMATIC_FONT_LABEL,
    get_effective_service_font,
    get_effective_speaker_font,
    get_effective_title_font,
    migrate_font_settings,
)
from layout_controls import (
    AREA_KEYS,
    MAX_TITLE_FONT_SIZE,
    clamp_box_to_canvas,
    nudge_font_size,
    nudge_skew_angle,
    update_layout_box,
)
from monark_schedule import (
    batch_export_candidates,
    entries_from_csv,
    entries_to_csv,
    entry_key,
    find_current_service_entry,
    get_monark_service_entries,
    mark_entry_exported,
)
from persistence import (
    SERVICE_LOG_PATH,
    SETTINGS_PATH,
    archive_service_log,
    can_replace_log,
    infer_log_year,
    load_service_log,
    load_settings,
    save_service_log,
    save_settings,
)
from presets import (
    ALIGNMENTS,
    DEFAULT_SERVICE_BOX,
    DEFAULT_SPEAKER_BOX,
    DEFAULT_TITLE_BOX,
    GENERATED_BACKGROUND_LABEL,
    list_presets,
    save_preset,
    settings_from_preset,
)
from title_renderer import (
    EXPORTS_DIR,
    TextBox,
    TitleImageOptions,
    default_font_path,
    ensure_project_dirs,
    list_custom_fonts,
    list_template_backgrounds,
)


DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
SERVICES = ["Morning", "Afternoon", "Evening"]


def main() -> None:
    ensure_project_dirs()
    st.set_page_config(page_title="TitleMaker", layout="wide")
    st.title("TitleMaker")
    st.caption("Monark Springs live service title maker")

    today = date.today()
    _ensure_defaults(today)
    _restore_saved_session()

    template_paths = list_template_backgrounds()
    font_paths = list_custom_fonts()
    preferred_font_path = default_font_path(font_paths)
    presets = list_presets()
    preset_names = [preset["name"] for preset in presets]
    presets_by_name = {preset["name"]: preset for preset in presets}

    background_labels = [GENERATED_BACKGROUND_LABEL] + [
        path.name for path in template_paths
    ]
    font_labels = [AUTOMATIC_FONT_LABEL] + [path.name for path in font_paths]
    default_font_label = (
        font_paths[font_paths.index(preferred_font_path)].name
        if preferred_font_path
        else font_labels[0]
    )
    if st.session_state.get("restore_message"):
        st.info(st.session_state.restore_message)
        st.session_state.restore_message = ""
    if st.session_state.get("persistence_warning"):
        st.warning(st.session_state.persistence_warning)
        st.session_state.persistence_warning = ""

    with st.sidebar:
        st.header("Monark Schedule Generator")
        schedule_year = st.number_input(
            "Year",
            min_value=1900,
            max_value=2100,
            value=int(st.session_state.get("service_log_year", today.year)),
            step=1,
        )
        requested_year = int(schedule_year)
        if st.button("Generate Monark Schedule", use_container_width=True):
            current_year = st.session_state.get("service_log_year")
            if not can_replace_log(current_year, requested_year, confirmed=False):
                st.session_state.pending_schedule_year = requested_year
                st.warning(
                    f"A saved log for {current_year} is loaded. Confirm before replacing it with {requested_year}."
                )
            else:
                _replace_schedule(requested_year)
                st.success("Generated 30 service log rows.")

        pending_year = st.session_state.get("pending_schedule_year")
        if pending_year:
            if st.button(
                f"Confirm Replace With {pending_year} Schedule",
                use_container_width=True,
            ):
                if st.session_state.schedule_entries:
                    archive_service_log(
                        st.session_state.schedule_entries,
                        st.session_state.get("service_log_year"),
                    )
                _replace_schedule(int(pending_year))
                st.session_state.pending_schedule_year = None
                st.success(f"Replaced log with {pending_year} schedule.")

        uploaded_csv = st.file_uploader("Import Service Log CSV", type=["csv"])
        if uploaded_csv is not None:
            st.session_state.schedule_entries = entries_from_csv(
                uploaded_csv.getvalue().decode("utf-8")
            )
            st.session_state.service_log_year = infer_log_year(
                st.session_state.schedule_entries
            )
            _select_first_entry()
            st.success("Imported service log.")

        if st.session_state.schedule_entries:
            if st.button("Save Service Log Now", use_container_width=True):
                _save_service_log_now()
                st.success("Service log saved.")

            if st.button("Load Service Log", use_container_width=True):
                if _load_saved_service_log():
                    st.success(
                        f"Loaded saved service log for {st.session_state.service_log_year}."
                    )
                else:
                    st.warning("No valid saved service log was found.")

            if st.button("Archive Current Log", use_container_width=True):
                archive_path = archive_service_log(
                    st.session_state.schedule_entries,
                    st.session_state.get("service_log_year"),
                )
                st.success(f"Archived to {archive_path}")

            st.download_button(
                "Export Service Log CSV",
                data=entries_to_csv(st.session_state.schedule_entries),
                file_name=f"monark_service_log_{schedule_year}.csv",
                mime="text/csv",
                use_container_width=True,
            )

            if st.button("Jump to Current Service", use_container_width=True):
                current = find_current_service_entry(st.session_state.schedule_entries)
                if current:
                    _load_entry(current)
                    st.success(f"Selected {current['service_line']}")
                else:
                    st.info("Today is not in the generated Monark schedule.")

        st.divider()
        st.header("Style")

        selected_preset_name = st.selectbox("Preset", preset_names, key="preset_name")
        if st.session_state.get("loaded_preset_name") != selected_preset_name:
            _apply_preset_to_session(
                presets_by_name[selected_preset_name],
                font_labels,
                background_labels,
                default_font_label,
            )
            st.session_state.loaded_preset_name = selected_preset_name

        _ensure_valid_choice("background_label", background_labels)
        _ensure_valid_choice("service_font", font_labels)
        _ensure_valid_choice("title_font", font_labels)
        _ensure_valid_choice("speaker_font", font_labels)
        _prepare_font_widget_defaults(font_labels)

        background_label = st.selectbox(
            "Background",
            background_labels,
            index=_choice_index(background_labels, st.session_state.background_label),
            key="background_label",
        )
        service_font = st.selectbox(
            "Service Line Font",
            font_labels,
            index=_choice_index(font_labels, st.session_state.service_font_widget),
            key="service_font_widget",
        )
        title_font_matches_service_font = st.checkbox(
            "Sermon Title font matches Service Line font",
            key="title_font_matches_service_font_widget",
        )
        if title_font_matches_service_font:
            title_font = service_font
            st.caption(f"Sermon Title Font: {title_font}")
        else:
            title_font = st.selectbox(
                "Sermon Title Font",
                font_labels,
                index=_choice_index(font_labels, st.session_state.title_font_widget),
                key="title_font_widget",
            )
        speaker_font_matches_service_font = st.checkbox(
            "Minister / Speaker font matches Service Line font",
            key="speaker_font_matches_service_font_widget",
        )
        if speaker_font_matches_service_font:
            speaker_font = service_font
            st.caption(f"Minister / Speaker Font: {speaker_font}")
        else:
            speaker_font = st.selectbox(
                "Minister / Speaker Font",
                font_labels,
                index=_choice_index(font_labels, st.session_state.speaker_font_widget),
                key="speaker_font_widget",
            )
        _sync_font_settings_from_widgets(
            service_font,
            title_font,
            speaker_font,
            title_font_matches_service_font,
            speaker_font_matches_service_font,
        )
        effective_font_settings = _current_font_settings()
        effective_service_font = get_effective_service_font(effective_font_settings)
        effective_title_font = get_effective_title_font(effective_font_settings)
        effective_speaker_font = get_effective_speaker_font(effective_font_settings)
        with st.expander("Booth font status", expanded=False):
            st.write(f"Service font: {effective_service_font}")
            st.write(f"Title font: {effective_title_font}")
            st.write(f"Speaker font: {effective_speaker_font}")
        text_color = st.color_picker("Text color", key="text_color")
        show_service_line = st.checkbox("Show service line", key="show_service_line")
        shadow_enabled = st.checkbox("Shadow", key="shadow_enabled")
        skew_enabled = st.checkbox("Skew title", key="skew_enabled")
        show_layout_guides = st.checkbox("Show layout guides", key="show_layout_guides")

        st.divider()
        st.header("Export Settings")
        selected_export_target = st.selectbox(
            "Export Target",
            EXPORT_TARGET_NAMES,
            index=_choice_index(EXPORT_TARGET_NAMES, st.session_state.selected_export_target),
            key="selected_export_target",
        )
        allow_builtin_edit = st.checkbox(
            "Allow editing built-in export size",
            key="allow_builtin_export_size_edit",
            disabled=selected_export_target == "Custom",
        )
        custom_or_editable = selected_export_target == "Custom" or allow_builtin_edit
        st.number_input(
            "Width",
            min_value=1,
            max_value=10000,
            key="custom_export_width",
            disabled=not custom_or_editable,
        )
        st.number_input(
            "Height",
            min_value=1,
            max_value=10000,
            key="custom_export_height",
            disabled=not custom_or_editable,
        )
        st.text_input(
            "Filename suffix",
            key="custom_export_suffix",
            disabled=selected_export_target != "Custom",
        )
        st.selectbox(
            "Export layout mode",
            EXPORT_LAYOUT_MODES,
            index=_choice_index(EXPORT_LAYOUT_MODES, st.session_state.export_layout_mode),
            key="export_layout_mode",
        )
        st.checkbox("Export multiple targets", key="export_multiple_targets")
        if st.session_state.export_multiple_targets:
            st.multiselect(
                "Targets to export",
                EXPORT_TARGET_NAMES,
                default=st.session_state.multi_target_selection,
                key="multi_target_selection",
            )
        current_export_target = resolve_export_target(_current_export_settings())
        st.caption(
            f"Export Target: {current_export_target.name} — {current_export_target.width}x{current_export_target.height}"
        )

        st.subheader("Visual Layout Adjustments")
        _visual_layout_controls()

        with st.expander("Advanced numeric layout values"):
            _box_controls("Service line", "service_box")
            _box_controls("Main title", "title_box", allow_line_spacing=True)
            _box_controls("Speaker", "speaker_box")

        preset_save_name = st.text_input(
            "Save current settings as preset",
            placeholder="Live Camp Style",
            key="preset_save_name",
        )
        if st.button("Save Preset", use_container_width=True):
            if preset_save_name.strip():
                save_preset(preset_save_name, _current_preset_settings())
                st.success(f"Saved preset: {preset_save_name.strip()}")
                st.rerun()
            else:
                st.warning("Enter a preset name first.")

    booth_tab, log_tab = st.tabs(["Booth Mode", "Service Log / Advanced"])

    with booth_tab:
        st.markdown("### Booth Mode")
        st.caption(
            "For best live use, open this page in a browser window and use fullscreen mode."
        )

        if not st.session_state.schedule_entries:
            st.info(NO_SCHEDULE_MESSAGE)
            booth_year = st.number_input(
                "Schedule year",
                min_value=1900,
                max_value=2100,
                value=today.year,
                step=1,
                key="booth_schedule_year",
            )
            if st.button("Generate Schedule", type="primary", use_container_width=True):
                _replace_schedule(int(booth_year))
                st.rerun()
        else:
            entries = st.session_state.schedule_entries
            if _selected_entry() is None:
                _select_first_entry()

            top_left, top_right = st.columns([1.2, 0.8], gap="large")
            with top_left:
                labels = booth_service_labels(entries)
                selected_label = st.selectbox(
                    "Current service",
                    labels,
                    index=_selected_entry_index(),
                    key="booth_selected_entry_label",
                )
                selected_entry = entries[_choice_index(labels, selected_label)]
                if entry_key(selected_entry) != st.session_state.selected_entry_key:
                    _load_entry(selected_entry)
                    st.rerun()

            with top_right:
                if st.button(
                    "Jump to Current Service",
                    type="secondary",
                    use_container_width=True,
                ):
                    current = find_current_service_entry(entries)
                    if current:
                        _load_entry(current)
                        st.success(f"Selected {current['service_line']}")
                        st.rerun()
                    else:
                        st.info("Today is not in the generated Monark schedule.")

            selected_entry = _selected_entry() or entries[0]
            left, right = st.columns([0.95, 1.35], gap="large")
            with left:
                st.subheader(selected_entry["service_line"])
                if selected_entry.get("exported"):
                    st.success("This service has already been exported.")
                else:
                    st.warning("Not exported yet.")

                sermon_title = st.text_area(
                    "Sermon title",
                    height=180,
                    key="sermon_title",
                    placeholder="Type title here...",
                )
                speaker_name = st.text_input(
                    "Preacher / speaker",
                    key="speaker_name",
                    placeholder="Type speaker here...",
                )
                with st.expander("Notes"):
                    notes = st.text_area("Notes", height=80, key="service_notes")

                st.session_state.schedule_entries = update_booth_entry(
                    st.session_state.schedule_entries,
                    st.session_state.selected_entry_key,
                    sermon_title,
                    speaker_name,
                    notes,
                )
                _save_service_log_now()

                nav_left, nav_right = st.columns(2)
                with nav_left:
                    if st.button("Previous Service", use_container_width=True):
                        _persist_current_booth_inputs()
                        current_index = _selected_entry_index()
                        previous_index = previous_service_index(current_index)
                        if previous_index == current_index:
                            st.info("Already at the first service.")
                        else:
                            _load_entry(entries[previous_index])
                            st.rerun()
                with nav_right:
                    if st.button("Next Service", use_container_width=True):
                        _persist_current_booth_inputs()
                        current_index = _selected_entry_index()
                        next_index = next_service_index(current_index, len(entries))
                        if next_index == current_index:
                            st.info("Already at the last service.")
                        else:
                            _load_entry(entries[next_index])
                            st.rerun()

                options = _options_from_entry(
                    selected_entry,
                    sermon_title,
                    speaker_name,
                    text_color,
                    background_label,
                    background_labels,
                    template_paths,
                    effective_service_font,
                    effective_title_font,
                    effective_speaker_font,
                    font_labels,
                    font_paths,
                    show_service_line,
                    shadow_enabled,
                    skew_enabled,
                    show_layout_guides,
                    st.session_state.selected_layout_area,
                )
                export_settings = _current_export_settings()
                current_export_target = resolve_export_target(export_settings)
                preview_image = render_for_export(
                    options,
                    current_export_target,
                    st.session_state.export_layout_mode,
                )
                output_name = export_filename_for_target(options, current_export_target)

                export_label = (
                    "Re-export Current Image"
                    if selected_entry.get("exported")
                    else "Export Current Image"
                )
                if st.button(export_label, type="primary", use_container_width=True):
                    if not sermon_title.strip() or not speaker_name.strip():
                        st.warning(
                            "Title or speaker is blank. Confirm below to export anyway."
                        )
                        st.session_state.confirm_blank_export = True
                    else:
                        _export_current(options)

                if st.session_state.get("confirm_blank_export"):
                    if st.button("Confirm Blank Export", use_container_width=True):
                        _export_current(options)
                        st.session_state.confirm_blank_export = False

                if st.session_state.export_multiple_targets:
                    if st.button(
                        "Export Current Image to Selected Targets",
                        use_container_width=True,
                    ):
                        paths = _export_current_multi(options)
                        st.success(f"Saved {len(paths)} files.")

                if st.session_state.get("last_export_path"):
                    st.success(f"Saved to {st.session_state.last_export_path}")

                st.download_button(
                    "Download Preview PNG",
                    data=_image_to_png_bytes(preview_image),
                    file_name=output_name,
                    mime="image/png",
                    use_container_width=True,
                )

            with right:
                st.subheader("Preview")
                st.image(preview_image, use_container_width=True)
                st.caption(
                    f"Export Target: {current_export_target.name} — {current_export_target.width}x{current_export_target.height}"
                )
                with st.expander("Status Panel", expanded=True):
                    st.write(f"Selected service line: {selected_entry['service_line']}")
                    st.write(
                        f"Exported: {'Yes' if selected_entry.get('exported') else 'No'}"
                    )
                    st.write(f"Exported At: {selected_entry.get('exported_at') or '-'}")
                    st.write(f"Title present: {'Yes' if sermon_title.strip() else 'No'}")
                    st.write(
                        f"Speaker present: {'Yes' if speaker_name.strip() else 'No'}"
                    )
                    st.write(
                        f"Current preset: {st.session_state.get('preset_name', '-')}"
                    )
                    st.write(f"Output folder: {EXPORTS_DIR}")

    with log_tab:
        st.header("Service Log")
        if not st.session_state.schedule_entries:
            st.info(NO_SCHEDULE_MESSAGE)
        else:
            edited_rows = st.data_editor(
                _service_log_rows(st.session_state.schedule_entries),
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                column_config={
                    "Key": st.column_config.TextColumn(disabled=True),
                    "Include": st.column_config.CheckboxColumn(),
                    "Exported": st.column_config.CheckboxColumn(disabled=True),
                },
            )
            st.session_state.schedule_entries = _merge_edited_rows(
                st.session_state.schedule_entries, edited_rows
            )
            _save_service_log_now()

            batch_candidates = batch_export_candidates(st.session_state.schedule_entries)
            if st.button(
                f"Export Included / Filled Rows ({len(batch_candidates)})",
                use_container_width=True,
            ):
                exported = _export_batch(
                    batch_candidates,
                    text_color,
                    background_label,
                    background_labels,
                    template_paths,
                    effective_service_font,
                    effective_title_font,
                    effective_speaker_font,
                    font_labels,
                    font_paths,
                    show_service_line,
                    shadow_enabled,
                    skew_enabled,
                )
                st.success(f"Exported {exported} images to {EXPORTS_DIR}")

    _save_settings_now()


def _image_to_png_bytes(image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _ensure_defaults(today: date) -> None:
    st.session_state.setdefault("schedule_entries", [])
    st.session_state.setdefault("service_log_year", today.year)
    st.session_state.setdefault("pending_schedule_year", None)
    st.session_state.setdefault("selected_entry_key", "")
    st.session_state.setdefault("sermon_title", "")
    st.session_state.setdefault("speaker_name", "")
    st.session_state.setdefault("service_notes", "")
    st.session_state.setdefault("background_label", GENERATED_BACKGROUND_LABEL)
    st.session_state.setdefault("font_label", AUTOMATIC_FONT_LABEL)
    st.session_state.setdefault("service_font", st.session_state.font_label)
    st.session_state.setdefault("title_font", st.session_state.font_label)
    st.session_state.setdefault("speaker_font", st.session_state.font_label)
    st.session_state.setdefault("title_font_matches_service_font", True)
    st.session_state.setdefault("speaker_font_matches_service_font", True)
    st.session_state.setdefault("text_color", "#FFFFFF")
    st.session_state.setdefault("show_service_line", True)
    st.session_state.setdefault("shadow_enabled", True)
    st.session_state.setdefault("skew_enabled", True)
    st.session_state.setdefault("show_layout_guides", False)
    st.session_state.setdefault("service_box", DEFAULT_SERVICE_BOX.copy())
    st.session_state.setdefault("title_box", DEFAULT_TITLE_BOX.copy())
    st.session_state.setdefault("speaker_box", DEFAULT_SPEAKER_BOX.copy())
    st.session_state.setdefault("selected_layout_area", "Sermon Title")
    st.session_state.setdefault("position_step", 5)
    st.session_state.setdefault("size_step", 10)
    st.session_state.setdefault("font_step", 5)
    st.session_state.setdefault("skew_step", 2.0)
    for key, value in default_export_settings().items():
        st.session_state.setdefault(key, value)


def _restore_saved_session() -> None:
    if st.session_state.get("persistence_loaded"):
        return

    settings = load_settings()
    if settings:
        export_settings = migrate_export_settings(settings)
        for key, value in export_settings.items():
            st.session_state[key] = value
        font_settings = migrate_font_settings(settings)
        st.session_state.service_font = font_settings["service_font"]
        st.session_state.title_font = font_settings["title_font"]
        st.session_state.speaker_font = font_settings["speaker_font"]
        st.session_state.title_font_matches_service_font = font_settings[
            "title_font_matches_service_font"
        ]
        st.session_state.speaker_font_matches_service_font = font_settings[
            "speaker_font_matches_service_font"
        ]
        st.session_state.font_label = font_settings["service_font"]
        _set_pending_font_widget_defaults()
        for key in (
            "preset_name",
            "loaded_preset_name",
            "text_color",
            "background_label",
            "service_box",
            "title_box",
            "speaker_box",
            "show_service_line",
            "show_layout_guides",
            "selected_layout_area",
            "shadow_enabled",
            "skew_enabled",
        ):
            if key in settings:
                if key == "service_box":
                    st.session_state[key] = _merge_box_defaults(
                        settings[key], DEFAULT_SERVICE_BOX
                    )
                elif key == "title_box":
                    st.session_state[key] = _merge_box_defaults(
                        settings[key], DEFAULT_TITLE_BOX
                    )
                elif key == "speaker_box":
                    st.session_state[key] = _merge_box_defaults(
                        settings[key], DEFAULT_SPEAKER_BOX
                    )
                else:
                    st.session_state[key] = settings[key]
    elif SETTINGS_PATH.exists():
        st.session_state.persistence_warning = (
            "Saved settings could not be read, so defaults were used."
        )

    if _load_saved_service_log():
        st.session_state.restore_message = (
            f"Loaded saved service log for {st.session_state.service_log_year}."
        )
    elif SERVICE_LOG_PATH.exists():
        st.session_state.persistence_warning = (
            "Saved service log could not be read, so a fresh log can be generated."
        )

    st.session_state.persistence_loaded = True


def _replace_schedule(year: int) -> None:
    st.session_state.schedule_entries = get_monark_service_entries(year)
    st.session_state.service_log_year = year
    _select_first_entry()
    _save_service_log_now()


def _load_saved_service_log() -> bool:
    loaded = load_service_log()
    if not loaded:
        return False
    st.session_state.schedule_entries = loaded["rows"]
    st.session_state.service_log_year = loaded["year"]
    _select_first_entry()
    return True


def _save_service_log_now() -> None:
    if st.session_state.schedule_entries:
        save_service_log(
            st.session_state.schedule_entries,
            st.session_state.get("service_log_year"),
        )


def _save_settings_now() -> None:
    save_settings(
        {
            "selected_preset": st.session_state.get("preset_name", ""),
            "preset_name": st.session_state.get("preset_name", ""),
            "loaded_preset_name": st.session_state.get("loaded_preset_name", ""),
            "font_label": st.session_state.font_label,
            "service_font": st.session_state.service_font,
            "title_font": st.session_state.title_font,
            "speaker_font": st.session_state.speaker_font,
            "title_font_matches_service_font": st.session_state.title_font_matches_service_font,
            "speaker_font_matches_service_font": st.session_state.speaker_font_matches_service_font,
            "text_color": st.session_state.text_color,
            "background_label": st.session_state.background_label,
            "service_box": st.session_state.service_box,
            "title_box": st.session_state.title_box,
            "speaker_box": st.session_state.speaker_box,
            "show_service_line": st.session_state.show_service_line,
            "show_layout_guides": st.session_state.show_layout_guides,
            "selected_layout_area": st.session_state.selected_layout_area,
            "shadow_enabled": st.session_state.shadow_enabled,
            "skew_enabled": st.session_state.skew_enabled,
            **_current_export_settings(),
        }
    )


def _box_controls(label: str, key: str, allow_line_spacing: bool = False) -> None:
    box = st.session_state[key]
    st.markdown(f"**{label}**")
    cols = st.columns(2)
    box["x"] = cols[0].number_input(f"{label} X", 0, 1920, int(box["x"]))
    box["y"] = cols[1].number_input(f"{label} Y", 0, 1080, int(box["y"]))
    cols = st.columns(2)
    box["width"] = cols[0].number_input(
        f"{label} Width", 50, 1920, int(box["width"])
    )
    box["height"] = cols[1].number_input(
        f"{label} Height", 30, 1080, int(box["height"])
    )
    box["alignment"] = st.selectbox(
        f"{label} Alignment",
        ALIGNMENTS,
        index=_choice_index(ALIGNMENTS, box["alignment"]),
    )
    box["auto_size"] = st.checkbox(f"{label} Auto-size", value=bool(box["auto_size"]))
    max_font_size = MAX_TITLE_FONT_SIZE if key == "title_box" else 260
    box["font_size"] = st.slider(
        f"{label} Font size",
        min_value=8,
        max_value=max_font_size,
        value=int(box["font_size"]),
        disabled=box["auto_size"],
    )
    if key == "title_box":
        box["max_font_size"] = st.slider(
            f"{label} Max font size",
            min_value=8,
            max_value=MAX_TITLE_FONT_SIZE,
            value=int(box.get("max_font_size", MAX_TITLE_FONT_SIZE)),
        )
        box["skew_angle"] = st.slider(
            "Italic slant angle",
            min_value=-25.0,
            max_value=25.0,
            value=float(box.get("skew_angle", 0.0)),
            step=0.5,
        )
    if allow_line_spacing:
        box["line_spacing"] = st.slider(
            f"{label} Line spacing",
            min_value=0.5,
            max_value=2.0,
            value=float(box["line_spacing"]),
            step=0.05,
        )
    st.session_state[key] = clamp_box_to_canvas(box)


def _visual_layout_controls() -> None:
    selected_area = st.selectbox(
        "Text area to adjust",
        list(AREA_KEYS.keys()),
        index=_choice_index(list(AREA_KEYS.keys()), st.session_state.selected_layout_area),
        key="selected_layout_area",
    )
    steps = st.columns(4)
    position_step = steps[0].select_slider(
        "Position step",
        options=[1, 5, 10, 25, 50],
        value=st.session_state.position_step,
        key="position_step",
    )
    size_step = steps[1].select_slider(
        "Size step",
        options=[1, 5, 10, 25, 50],
        value=st.session_state.size_step,
        key="size_step",
    )
    font_step = steps[2].select_slider(
        "Font step",
        options=[1, 2, 5, 10, 25],
        value=st.session_state.font_step,
        key="font_step",
    )
    skew_step = steps[3].select_slider(
        "Skew step",
        options=[0.5, 1.0, 2.0, 5.0],
        value=st.session_state.skew_step,
        key="skew_step",
    )

    st.caption("Position")
    row = st.columns([1, 1, 1])
    row[1].button("Up", on_click=_nudge_box, args=(selected_area, 0, -position_step, 0, 0), use_container_width=True)
    row = st.columns([1, 1, 1])
    row[0].button("Left", on_click=_nudge_box, args=(selected_area, -position_step, 0, 0, 0), use_container_width=True)
    row[1].markdown("<div style='text-align:center'>Move</div>", unsafe_allow_html=True)
    row[2].button("Right", on_click=_nudge_box, args=(selected_area, position_step, 0, 0, 0), use_container_width=True)
    row = st.columns([1, 1, 1])
    row[1].button("Down", on_click=_nudge_box, args=(selected_area, 0, position_step, 0, 0), use_container_width=True)

    st.caption("Size")
    row = st.columns(4)
    row[0].button("Wider", on_click=_nudge_box, args=(selected_area, 0, 0, size_step, 0), use_container_width=True)
    row[1].button("Narrower", on_click=_nudge_box, args=(selected_area, 0, 0, -size_step, 0), use_container_width=True)
    row[2].button("Taller", on_click=_nudge_box, args=(selected_area, 0, 0, 0, size_step), use_container_width=True)
    row[3].button("Shorter", on_click=_nudge_box, args=(selected_area, 0, 0, 0, -size_step), use_container_width=True)

    st.caption("Font")
    row = st.columns(2 if selected_area != "Sermon Title" else 4)
    row[0].button("A+", on_click=_nudge_font, args=(selected_area, font_step), use_container_width=True)
    row[1].button("A-", on_click=_nudge_font, args=(selected_area, -font_step), use_container_width=True)
    if selected_area == "Sermon Title":
        row[2].button("Italic +", on_click=_nudge_skew, args=(selected_area, skew_step), use_container_width=True)
        row[3].button("Italic -", on_click=_nudge_skew, args=(selected_area, -skew_step), use_container_width=True)


def _layout_settings() -> dict:
    return {
        "service_box": st.session_state.service_box,
        "title_box": st.session_state.title_box,
        "speaker_box": st.session_state.speaker_box,
    }


def _apply_layout_settings(settings: dict) -> None:
    st.session_state.service_box = settings["service_box"]
    st.session_state.title_box = settings["title_box"]
    st.session_state.speaker_box = settings["speaker_box"]


def _nudge_box(area_name: str, dx: int, dy: int, dw: int, dh: int) -> None:
    settings = update_layout_box(_layout_settings(), area_name, dx=dx, dy=dy, dw=dw, dh=dh)
    _apply_layout_settings(settings)


def _nudge_font(area_name: str, delta: int) -> None:
    settings = nudge_font_size(_layout_settings(), area_name, delta)
    _apply_layout_settings(settings)


def _nudge_skew(area_name: str, delta: float) -> None:
    settings = nudge_skew_angle(_layout_settings(), area_name, delta)
    _apply_layout_settings(settings)


def _merge_box_defaults(box: dict, defaults: dict) -> dict:
    merged = defaults.copy()
    if isinstance(box, dict):
        merged.update(box)
    return merged


def _prepare_font_widget_defaults(font_labels: list[str]) -> None:
    pending = st.session_state.pop("pending_font_widget_defaults", None)
    if isinstance(pending, dict):
        for key, value in pending.items():
            st.session_state[key] = value

    defaults = {
        "service_font_widget": st.session_state.service_font,
        "title_font_widget": st.session_state.title_font,
        "speaker_font_widget": st.session_state.speaker_font,
        "title_font_matches_service_font_widget": st.session_state.title_font_matches_service_font,
        "speaker_font_matches_service_font_widget": st.session_state.speaker_font_matches_service_font,
    }
    for key, value in defaults.items():
        if key.endswith("_font_widget") and value not in font_labels:
            value = font_labels[0]
        st.session_state.setdefault(key, value)


def _sync_font_settings_from_widgets(
    service_font: str,
    title_font: str,
    speaker_font: str,
    title_matches: bool,
    speaker_matches: bool,
) -> None:
    st.session_state.font_label = service_font
    st.session_state.service_font = service_font
    st.session_state.title_font = title_font
    st.session_state.speaker_font = speaker_font
    st.session_state.title_font_matches_service_font = title_matches
    st.session_state.speaker_font_matches_service_font = speaker_matches


def _set_pending_font_widget_defaults() -> None:
    st.session_state.pending_font_widget_defaults = {
        "service_font_widget": st.session_state.service_font,
        "title_font_widget": st.session_state.title_font,
        "speaker_font_widget": st.session_state.speaker_font,
        "title_font_matches_service_font_widget": st.session_state.title_font_matches_service_font,
        "speaker_font_matches_service_font_widget": st.session_state.speaker_font_matches_service_font,
    }


def _select_first_entry() -> None:
    entries = st.session_state.get("schedule_entries", [])
    if entries:
        _load_entry(entries[0])


def _selected_entry() -> dict | None:
    for entry in st.session_state.schedule_entries:
        if entry_key(entry) == st.session_state.selected_entry_key:
            return entry
    return None


def _selected_entry_index() -> int:
    for index, entry in enumerate(st.session_state.schedule_entries):
        if entry_key(entry) == st.session_state.selected_entry_key:
            return index
    return 0


def _load_entry(entry: dict) -> None:
    values = load_entry_values(entry)
    st.session_state.selected_entry_key = values["selected_key"]
    st.session_state.selected_entry_label = _entry_label(entry)
    st.session_state.sermon_title = values["title"]
    st.session_state.speaker_name = values["speaker"]
    st.session_state.service_notes = values["notes"]


def _update_selected_notes(notes: str) -> None:
    for entry in st.session_state.schedule_entries:
        if entry_key(entry) == st.session_state.selected_entry_key:
            entry["notes"] = notes
            break


def _persist_current_booth_inputs() -> None:
    st.session_state.schedule_entries = update_booth_entry(
        st.session_state.schedule_entries,
        st.session_state.selected_entry_key,
        st.session_state.get("sermon_title", ""),
        st.session_state.get("speaker_name", ""),
        st.session_state.get("service_notes", ""),
    )
    _save_service_log_now()


def _entry_label(entry: dict) -> str:
    return entry["service_line"]


def _service_log_rows(entries: list[dict]) -> list[dict]:
    return [
        {
            "Key": entry_key(entry),
            "Include": bool(entry.get("include")),
            "Date": entry["date"].isoformat(),
            "Weekday": entry["weekday"],
            "Service Name": entry["service"],
            "Service Code": entry["service_code"],
            "Service Line": entry["service_line"],
            "Title": entry.get("title", ""),
            "Speaker": entry.get("speaker", ""),
            "Notes": entry.get("notes", ""),
            "Exported": bool(entry.get("exported")),
            "Exported At": entry.get("exported_at", ""),
        }
        for entry in entries
    ]


def _merge_edited_rows(entries: list[dict], rows: list[dict]) -> list[dict]:
    if hasattr(rows, "to_dict"):
        rows = rows.to_dict("records")
    rows_by_key = {row["Key"]: row for row in rows}
    for entry in entries:
        row = rows_by_key.get(entry_key(entry))
        if not row:
            continue
        entry["include"] = bool(row["Include"])
        entry["title"] = row["Title"] or ""
        entry["speaker"] = row["Speaker"] or ""
        entry["notes"] = row["Notes"] or ""
    return entries


def _options_from_entry(
    entry: dict,
    title: str,
    speaker: str,
    text_color: str,
    background_label: str,
    background_labels: list[str],
    template_paths: list[Path],
    service_font: str,
    title_font: str,
    speaker_font: str,
    font_labels: list[str],
    font_paths: list[Path],
    show_service_line: bool,
    shadow_enabled: bool,
    skew_enabled: bool,
    show_layout_guides: bool,
    selected_layout_area: str | None = None,
) -> TitleImageOptions:
    return TitleImageOptions(
        day=entry["weekday"],
        service=entry["service"],
        service_date=entry["date"],
        sermon_title=title,
        speaker_name=speaker,
        text_color=text_color,
        background_path=_selected_background(background_label, background_labels, template_paths),
        service_font_path=_selected_font(service_font, font_labels, font_paths),
        title_font_path=_selected_font(title_font, font_labels, font_paths),
        speaker_font_path=_selected_font(speaker_font, font_labels, font_paths),
        service_line_box=_text_box(st.session_state.service_box),
        title_box=_text_box(st.session_state.title_box),
        speaker_box=_text_box(st.session_state.speaker_box),
        shadow_enabled=shadow_enabled,
        show_service_line=show_service_line,
        skew_enabled=skew_enabled,
        show_layout_guides=show_layout_guides,
        selected_layout_area=selected_layout_area,
    )


def _export_current(options: TitleImageOptions) -> None:
    target = resolve_export_target(_current_export_settings())
    output_path = EXPORTS_DIR / export_filename_for_target(options, target)
    render_for_export(options, target, st.session_state.export_layout_mode).save(
        output_path, "PNG"
    )
    st.session_state.schedule_entries = mark_booth_exported(
        st.session_state.schedule_entries,
        st.session_state.selected_entry_key,
        datetime.now(),
    )
    st.session_state.last_export_path = str(output_path)
    _save_service_log_now()
    st.success(f"Saved to {output_path}")


def _export_current_multi(options: TitleImageOptions) -> list[Path]:
    output_paths = []
    for target in resolve_multi_targets(_current_export_settings()):
        output_path = EXPORTS_DIR / export_filename_for_target(options, target)
        render_for_export(options, target, st.session_state.export_layout_mode).save(
            output_path, "PNG"
        )
        output_paths.append(output_path)
    if output_paths:
        st.session_state.schedule_entries = mark_booth_exported(
            st.session_state.schedule_entries,
            st.session_state.selected_entry_key,
            datetime.now(),
        )
        st.session_state.last_export_path = ", ".join(str(path) for path in output_paths)
        _save_service_log_now()
    return output_paths


def _export_batch(
    entries: list[dict],
    text_color: str,
    background_label: str,
    background_labels: list[str],
    template_paths: list[Path],
    service_font: str,
    title_font: str,
    speaker_font: str,
    font_labels: list[str],
    font_paths: list[Path],
    show_service_line: bool,
    shadow_enabled: bool,
    skew_enabled: bool,
) -> int:
    exported = 0
    target = resolve_export_target(_current_export_settings())
    for entry in entries:
        options = _options_from_entry(
            entry,
            entry.get("title", ""),
            entry.get("speaker", ""),
            text_color,
            background_label,
            background_labels,
            template_paths,
            service_font,
            title_font,
            speaker_font,
            font_labels,
            font_paths,
            show_service_line,
            shadow_enabled,
            skew_enabled,
            False,
            None,
        )
        output_path = EXPORTS_DIR / export_filename_for_target(options, target)
        render_for_export(options, target, st.session_state.export_layout_mode).save(
            output_path, "PNG"
        )
        st.session_state.schedule_entries = mark_entry_exported(
            st.session_state.schedule_entries, entry_key(entry), datetime.now()
        )
        exported += 1
    return exported


def _current_preset_settings() -> dict:
    return {
        "font_choice": st.session_state.font_label,
        **_current_font_settings(),
        **_current_export_settings(),
        "text_color": st.session_state.text_color,
        "background_choice": st.session_state.background_label,
        "service_line_box": st.session_state.service_box,
        "title_box": st.session_state.title_box,
        "speaker_box": st.session_state.speaker_box,
        "show_service_line": st.session_state.show_service_line,
        "show_layout_guides": st.session_state.show_layout_guides,
        "selected_layout_area": st.session_state.selected_layout_area,
        "shadow_enabled": st.session_state.shadow_enabled,
        "skew_enabled": st.session_state.skew_enabled,
    }


def _apply_preset_to_session(
    preset: dict,
    font_labels: list[str],
    background_labels: list[str],
    default_font_label: str,
) -> None:
    settings = settings_from_preset(preset)
    font_settings = migrate_font_settings(settings)
    export_settings = migrate_export_settings(settings)
    font_label = font_settings["service_font"]
    background_label = settings["background_choice"]
    st.session_state.font_label = (
        font_label
        if font_label in font_labels
        else default_font_label
        if default_font_label in font_labels
        else font_labels[0]
    )
    st.session_state.service_font = st.session_state.font_label
    st.session_state.title_font = (
        font_settings["title_font"]
        if font_settings["title_font"] in font_labels
        else st.session_state.font_label
    )
    st.session_state.speaker_font = (
        font_settings["speaker_font"]
        if font_settings["speaker_font"] in font_labels
        else st.session_state.font_label
    )
    st.session_state.title_font_matches_service_font = font_settings[
        "title_font_matches_service_font"
    ]
    st.session_state.speaker_font_matches_service_font = font_settings[
        "speaker_font_matches_service_font"
    ]
    _set_pending_font_widget_defaults()
    st.session_state.background_label = (
        background_label if background_label in background_labels else background_labels[0]
    )
    st.session_state.text_color = settings["text_color"]
    st.session_state.service_box = settings["service_line_box"].copy()
    st.session_state.title_box = settings["title_box"].copy()
    st.session_state.speaker_box = settings["speaker_box"].copy()
    st.session_state.show_service_line = settings["show_service_line"]
    st.session_state.show_layout_guides = settings["show_layout_guides"]
    st.session_state.selected_layout_area = settings["selected_layout_area"]
    st.session_state.shadow_enabled = settings["shadow_enabled"]
    st.session_state.skew_enabled = settings["skew_enabled"]
    for key, value in export_settings.items():
        st.session_state[key] = value


def _current_font_settings() -> dict:
    return {
        "service_font": st.session_state.service_font,
        "title_font": st.session_state.title_font,
        "speaker_font": st.session_state.speaker_font,
        "title_font_matches_service_font": st.session_state.title_font_matches_service_font,
        "speaker_font_matches_service_font": st.session_state.speaker_font_matches_service_font,
    }


def _current_export_settings() -> dict:
    return migrate_export_settings(
        {
            "selected_export_target": st.session_state.selected_export_target,
            "custom_export_width": st.session_state.custom_export_width,
            "custom_export_height": st.session_state.custom_export_height,
            "custom_export_suffix": st.session_state.custom_export_suffix,
            "allow_builtin_export_size_edit": st.session_state.allow_builtin_export_size_edit,
            "export_layout_mode": st.session_state.export_layout_mode,
            "export_multiple_targets": st.session_state.export_multiple_targets,
            "multi_target_selection": st.session_state.multi_target_selection,
        }
    )


def _text_box(box: dict) -> TextBox:
    return TextBox(
        x=int(box["x"]),
        y=int(box["y"]),
        width=int(box["width"]),
        height=int(box["height"]),
        alignment=box["alignment"],
        auto_size=bool(box["auto_size"]),
        font_size=int(box["font_size"]),
        max_font_size=int(box.get("max_font_size", MAX_TITLE_FONT_SIZE)),
        line_spacing=float(box["line_spacing"]),
        skew_angle=float(box.get("skew_angle", 0.0)),
    )


def _selected_background(
    background_label: str,
    background_labels: list[str],
    template_paths: list[Path],
) -> Path | None:
    if background_label == background_labels[0]:
        return None
    return template_paths[background_labels.index(background_label) - 1]


def _selected_font(
    font_label: str,
    font_labels: list[str],
    font_paths: list[Path],
) -> Path | None:
    if font_label == font_labels[0] or font_label not in font_labels:
        return None
    return font_paths[font_labels.index(font_label) - 1]


def _ensure_valid_choice(key: str, choices: list[str]) -> None:
    if st.session_state.get(key) not in choices:
        st.session_state[key] = choices[0]


def _choice_index(choices: list[str], value: str) -> int:
    try:
        return choices.index(value)
    except ValueError:
        return 0


if __name__ == "__main__":
    main()
