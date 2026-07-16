from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import streamlit as st

from booth_mode import (
    NO_SCHEDULE_MESSAGE,
    build_booth_service_label,
    booth_service_labels,
    load_entry_values,
    mark_booth_exported,
    next_service_index,
    previous_service_index,
    switch_service,
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
    DEFAULT_TITLE_SIDE_PADDING,
    DEFAULT_TITLE_VERTICAL_GAP,
    clamp_box_to_canvas,
    get_effective_layout_boxes,
    nudge_font_size,
    nudge_skew_angle,
    resolve_auto_title_layout_settings,
    update_layout_box,
)
from layout_interaction import (
    apply_layout_event,
    auto_fit_title_box,
    boxes_for_overlay,
    center_box_horizontally,
    center_title_vertically_in_available_space,
    normalize_area_name,
)
from interactive_preview import render_interactive_preview
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
    default_preset_name,
    delete_preset,
    is_builtin_preset,
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
    _consume_pending_layout_event()

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
        st.header("Schedule")
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

        if st.session_state.schedule_entries:
            if st.button("Save Service Log Now", use_container_width=True):
                _save_service_log_now()
                st.success("Service log saved.")

        st.caption("Fonts, layout, presets, and batch tools are under Advanced below.")

    _ensure_valid_choice("background_label", background_labels)
    _ensure_valid_choice("service_font", font_labels)
    _ensure_valid_choice("title_font", font_labels)
    _ensure_valid_choice("speaker_font", font_labels)
    _prepare_font_widget_defaults(font_labels)
    _sync_font_settings_from_session()
    effective_font_settings = _current_font_settings()
    effective_service_font = get_effective_service_font(effective_font_settings)
    effective_title_font = get_effective_title_font(effective_font_settings)
    effective_speaker_font = get_effective_speaker_font(effective_font_settings)
    background_label = st.session_state.background_label
    text_color = st.session_state.text_color
    show_service_line = st.session_state.show_service_line
    shadow_enabled = st.session_state.shadow_enabled
    skew_enabled = st.session_state.skew_enabled
    show_layout_guides = st.session_state.show_layout_guides

    st.markdown("### Booth Mode")
    st.caption(
        "Pick the service, type the title and speaker, preview, then export. "
        "Open Advanced only when you need style or batch tools."
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

        labels = booth_service_labels(entries)
        _prepare_booth_selector_widget(labels)
        selected_label = st.selectbox(
            "Current service",
            labels,
            index=_selected_entry_index(),
            key="booth_selected_entry_label",
        )
        selected_entry = entries[_choice_index(labels, selected_label)]
        if entry_key(selected_entry) != st.session_state.selected_entry_key:
            _switch_to_entry_index(_choice_index(labels, selected_label))
            st.rerun()

        nav_cols = st.columns([1, 1, 1.2])
        with nav_cols[0]:
            if st.button("Previous Service", use_container_width=True):
                _persist_current_booth_inputs()
                current_index = _selected_entry_index()
                previous_index = previous_service_index(current_index)
                if previous_index == current_index:
                    st.info("Already at the first service.")
                else:
                    _switch_to_entry_index(previous_index)
                    st.rerun()
        with nav_cols[1]:
            if st.button("Next Service", use_container_width=True):
                _persist_current_booth_inputs()
                current_index = _selected_entry_index()
                next_index = next_service_index(current_index, len(entries))
                if next_index == current_index:
                    st.info("Already at the last service.")
                else:
                    _switch_to_entry_index(next_index)
                    st.rerun()
        with nav_cols[2]:
            if st.button("Jump to Current Service", use_container_width=True):
                current = find_current_service_entry(entries)
                if current:
                    _switch_to_entry_index(_entry_index_for_key(entry_key(current)))
                    st.success(f"Selected {current['service_line']}")
                    st.rerun()
                else:
                    st.info("Today is not in the generated Monark schedule.")

        selected_entry = _selected_entry() or entries[0]
        _prepare_booth_input_widgets(selected_entry)
        left, right = st.columns([0.95, 1.35], gap="large")
        with left:
            st.subheader(selected_entry["service_line"])
            if selected_entry.get("exported"):
                st.success("Exported")
            else:
                st.warning("Not exported yet")

            sermon_title = st.text_area(
                "Sermon title",
                height=180,
                key="booth_sermon_title_widget",
                placeholder="Type title here...",
            )
            speaker_name = st.text_input(
                "Speaker / Minister",
                key="booth_speaker_widget",
                placeholder="Type speaker here...",
            )
            with st.expander("Notes", expanded=False):
                notes = st.text_area("Notes", height=80, key="booth_notes_widget")

            st.session_state.schedule_entries = update_booth_entry(
                st.session_state.schedule_entries,
                st.session_state.selected_entry_key,
                sermon_title,
                speaker_name,
                notes,
            )
            _save_service_log_now()

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
                # Guides are drawn by the interactive overlay when enabled.
                show_layout_guides
                and not st.session_state.get("interactive_preview_layout_editor", False),
                st.session_state.selected_layout_area,
            )
            export_settings = _current_export_settings()
            current_export_target = resolve_export_target(export_settings)
            preview_image = render_for_export(
                options,
                current_export_target,
                st.session_state.export_layout_mode,
            )
            # Clean export options (guides only when explicitly enabled for debug export).
            export_options = _options_from_entry(
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
            output_name = export_filename_for_target(export_options, current_export_target)

            export_label = (
                "Re-export Current Image"
                if selected_entry.get("exported")
                else "Export Current Image"
            )
            if st.button(export_label, type="primary", width="stretch"):
                if not sermon_title.strip() or not speaker_name.strip():
                    st.warning(
                        "Title or speaker is blank. Confirm below to export anyway."
                    )
                    st.session_state.confirm_blank_export = True
                else:
                    _export_current(export_options)

            if st.session_state.get("confirm_blank_export"):
                if st.button("Confirm Blank Export", width="stretch"):
                    _export_current(export_options)
                    st.session_state.confirm_blank_export = False

            if st.session_state.get("last_export_path"):
                st.caption(f"Last saved: {st.session_state.last_export_path}")

            st.download_button(
                "Download Preview PNG",
                data=_image_to_png_bytes(preview_image),
                file_name=output_name,
                mime="image/png",
                width="stretch",
            )

        with right:
            st.subheader("Preview")
            _render_booth_preview(
                preview_image,
                current_export_target,
            )

    st.divider()
    st.markdown("### Advanced")
    st.caption("Collapsed by default. Open only when you need batch tools, styles, fonts, or layout.")

    with st.expander("Advanced: Service Log / Batch Tools", expanded=False):
        _render_advanced_service_log(
            schedule_year,
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

    with st.expander("Advanced: Style Presets", expanded=False):
        _render_advanced_style_presets(
            presets,
            presets_by_name,
            preset_names,
            font_labels,
            background_labels,
            default_font_label,
        )

    with st.expander("Advanced: Fonts", expanded=False):
        _render_advanced_fonts(font_labels)

    with st.expander("Advanced: Layout", expanded=False):
        _render_advanced_layout()

    with st.expander("Advanced: Export Targets", expanded=False):
        _render_advanced_export_targets()
        if st.session_state.schedule_entries and st.session_state.export_multiple_targets:
            selected_entry = _selected_entry()
            if selected_entry:
                options = _options_from_entry(
                    selected_entry,
                    selected_entry.get("title", ""),
                    selected_entry.get("speaker", ""),
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
                    False,
                    None,
                )
                if st.button(
                    "Export Current Image to Selected Targets",
                    use_container_width=True,
                ):
                    paths = _export_current_multi(options)
                    st.success(f"Saved {len(paths)} files.")

    _save_settings_now()


def _sync_font_settings_from_session() -> None:
    """Keep stored font settings available when Advanced Fonts is closed."""
    st.session_state.font_label = st.session_state.service_font


def _render_advanced_service_log(
    schedule_year: int,
    text_color: str,
    background_label: str,
    background_labels: list[str],
    template_paths: list[Path],
    effective_service_font: str,
    effective_title_font: str,
    effective_speaker_font: str,
    font_labels: list[str],
    font_paths: list[Path],
    show_service_line: bool,
    shadow_enabled: bool,
    skew_enabled: bool,
) -> None:
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

    if not st.session_state.schedule_entries:
        st.info(NO_SCHEDULE_MESSAGE)
        return

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
        f"Batch Export Included / Filled Rows ({len(batch_candidates)})",
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


def _render_advanced_style_presets(
    presets: list[dict],
    presets_by_name: dict[str, dict],
    preset_names: list[str],
    font_labels: list[str],
    background_labels: list[str],
    default_font_label: str,
) -> None:
    selected_preset_name = st.selectbox("Preset", preset_names, key="preset_name")
    if st.session_state.get("loaded_preset_name") != selected_preset_name:
        _apply_preset_to_session(
            presets_by_name[selected_preset_name],
            font_labels,
            background_labels,
            default_font_label,
        )
        st.session_state.loaded_preset_name = selected_preset_name

    st.selectbox(
        "Background",
        background_labels,
        index=_choice_index(background_labels, st.session_state.background_label),
        key="background_label",
    )
    st.color_picker("Text color", key="text_color")
    st.checkbox("Show service line", key="show_service_line")
    st.checkbox("Shadow", key="shadow_enabled")
    st.checkbox("Skew title", key="skew_enabled")

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

    st.markdown("**Delete preset**")
    deletable = [name for name in preset_names if not is_builtin_preset(name)]
    if not deletable:
        st.caption("No user-created presets to delete. Built-in presets are protected.")
    else:
        delete_name = st.selectbox(
            "User preset to delete",
            deletable,
            key="preset_delete_name",
        )
        confirm_delete = st.checkbox(
            f"Confirm delete “{delete_name}”",
            key="confirm_preset_delete",
        )
        if st.button("Delete Preset", use_container_width=True):
            if not confirm_delete:
                st.warning("Check the confirmation box before deleting.")
            else:
                result = delete_preset(delete_name)
                if result.get("deleted"):
                    if st.session_state.get("preset_name") == delete_name:
                        fallback = result.get("fallback_name") or default_preset_name()
                        st.session_state.preset_name = fallback
                        st.session_state.loaded_preset_name = ""
                        if fallback in presets_by_name:
                            _apply_preset_to_session(
                                presets_by_name[fallback],
                                font_labels,
                                background_labels,
                                default_font_label,
                            )
                            st.session_state.loaded_preset_name = fallback
                    st.success(f"Deleted preset: {delete_name}")
                    st.rerun()
                else:
                    st.error(f"Could not delete preset ({result.get('reason')}).")


def _render_advanced_fonts(font_labels: list[str]) -> None:
    _prepare_font_widget_defaults(font_labels)
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
    effective = _current_font_settings()
    st.write(f"Service font: {get_effective_service_font(effective)}")
    st.write(f"Title font: {get_effective_title_font(effective)}")
    st.write(f"Speaker font: {get_effective_speaker_font(effective)}")


def _render_advanced_layout() -> None:
    st.checkbox("Show layout guides", key="show_layout_guides")
    st.checkbox(
        "Interactive preview layout editor",
        key="interactive_preview_layout_editor",
        help=(
            "Click the title guide, then use arrow keys to move it. "
            "Press + or - to resize the title font. "
            "Double-click the title guide to auto-fit the title area between "
            "the service line and speaker."
        ),
    )
    st.caption(
        "Click the title guide, then use arrow keys to move it. Press + or - to "
        "resize the title font. Double-click the title guide to auto-fit the "
        "title area between the service line and speaker. "
        "Use Preview Layout Controls under the preview for reliable buttons."
    )

    st.markdown("#### Title Auto Layout")
    st.caption(
        "When enabled, the sermon title region automatically fills the space "
        "between the service line and speaker line with equal spacing above and below."
    )
    st.checkbox(
        "Auto-size title box between service and speaker",
        key="auto_title_box_between_service_and_speaker",
    )
    pad_cols = st.columns(2)
    pad_cols[0].number_input(
        "Title side padding",
        min_value=0,
        max_value=800,
        key="title_side_padding",
        help="Equal left/right padding. At 1920px width, 120 gives a 1680px-wide title box.",
    )
    pad_cols[1].number_input(
        "Title vertical gap",
        min_value=0,
        max_value=400,
        key="title_vertical_gap",
        help="Equal gap above and below the title box between service and speaker.",
    )

    # Keep legacy keys synchronized for persistence/migration.
    st.session_state.auto_title_area = bool(
        st.session_state.auto_title_box_between_service_and_speaker
    )
    st.session_state.title_top_padding = int(st.session_state.title_vertical_gap)
    st.session_state.title_bottom_padding = int(st.session_state.title_vertical_gap)

    effective = get_effective_layout_boxes(
        {
            "service_box": st.session_state.service_box,
            "title_box": st.session_state.title_box,
            "speaker_box": st.session_state.speaker_box,
            "auto_title_box_between_service_and_speaker": st.session_state.auto_title_box_between_service_and_speaker,
            "title_side_padding": st.session_state.title_side_padding,
            "title_vertical_gap": st.session_state.title_vertical_gap,
        }
    )
    if effective.get("warning"):
        st.warning(effective["warning"])
    elif st.session_state.auto_title_box_between_service_and_speaker:
        box = effective["title_box"]
        st.caption(
            f"Effective title box: x={box['x']}, y={box['y']}, "
            f"width={box['width']}, height={box['height']}"
        )

    st.subheader("Visual Layout Adjustments")
    _visual_layout_controls(
        disable_title_geometry=bool(
            st.session_state.auto_title_box_between_service_and_speaker
        )
    )

    with st.expander("Advanced numeric layout values", expanded=False):
        _box_controls("Service line", "service_box")
        auto_title = bool(st.session_state.auto_title_box_between_service_and_speaker)
        if auto_title:
            st.info(
                "Auto title box is on. Title X/Y/width/height are calculated. "
                "Turn it off to edit the title box manually."
            )
        _box_controls(
            "Main title",
            "title_box",
            allow_line_spacing=True,
            disable_geometry=auto_title,
        )
        _box_controls("Speaker", "speaker_box")


def _render_booth_preview(preview_image, current_export_target) -> None:
    interactive = bool(st.session_state.get("interactive_preview_layout_editor", False))
    show_guides = bool(st.session_state.get("show_layout_guides", False))

    if interactive:
        effective = get_effective_layout_boxes(_current_layout_settings())
        overlay_settings = {
            "service_box": effective["service_box"],
            "title_box": effective["title_box"],
            "speaker_box": effective["speaker_box"],
        }
        result = render_interactive_preview(
            preview_image,
            boxes_for_overlay(overlay_settings),
            st.session_state.get("selected_layout_area", "Sermon Title"),
            position_step=int(st.session_state.get("position_step", 5)),
            font_step=int(st.session_state.get("font_step", 5)),
            key="booth_interactive_preview",
            on_layout_event=lambda: _stage_layout_event_from_component(
                "booth_interactive_preview"
            ),
        )
        _ = result  # Component mount result; events are applied via pending_layout_event.
        st.caption(
            f"Selected layout area: {st.session_state.get('selected_layout_area', 'Sermon Title')}"
        )
        st.caption(
            "Controls: Arrow keys move, + / - resize font, double-click auto-fits title box."
        )
    else:
        st.image(preview_image, width="stretch")

    st.caption(
        f"{current_export_target.name} — {current_export_target.width}x{current_export_target.height}"
    )
    if st.session_state.get("layout_autofit_message"):
        st.success(st.session_state.layout_autofit_message)
        st.session_state.layout_autofit_message = ""

    controls_expanded = interactive or show_guides
    with st.expander("Preview Layout Controls", expanded=controls_expanded):
        _render_preview_layout_controls()


def _render_preview_layout_controls() -> None:
    st.caption(
        "Reliable buttons for moving and resizing the selected text area. "
        "Works even when keyboard focus is not in the interactive preview."
    )
    _sync_preview_area_selector()
    area = st.selectbox(
        "Adjust area",
        ["Service Line", "Sermon Title", "Speaker"],
        key="preview_adjust_area",
        on_change=_on_preview_area_change,
    )
    area = normalize_area_name(area)

    step_cols = st.columns(3)
    position_step = step_cols[0].select_slider(
        "Move step",
        options=[1, 5, 10, 25, 50],
        key="position_step",
    )
    size_step = step_cols[1].select_slider(
        "Size step",
        options=[1, 5, 10, 25, 50],
        key="size_step",
    )
    font_step = step_cols[2].select_slider(
        "Font step",
        options=[1, 2, 5, 10, 25],
        key="font_step",
    )

    st.caption("Move")
    row = st.columns([1, 1, 1])
    row[1].button(
        "↑",
        key="preview_move_up",
        on_click=_preview_nudge,
        args=(area, 0, -int(position_step), 0, 0),
        width="stretch",
    )
    row = st.columns([1, 1, 1])
    row[0].button(
        "←",
        key="preview_move_left",
        on_click=_preview_nudge,
        args=(area, -int(position_step), 0, 0, 0),
        width="stretch",
    )
    row[1].markdown(
        "<div style='text-align:center;padding-top:0.4rem'>Move</div>",
        unsafe_allow_html=True,
    )
    row[2].button(
        "→",
        key="preview_move_right",
        on_click=_preview_nudge,
        args=(area, int(position_step), 0, 0, 0),
        width="stretch",
    )
    row = st.columns([1, 1, 1])
    row[1].button(
        "↓",
        key="preview_move_down",
        on_click=_preview_nudge,
        args=(area, 0, int(position_step), 0, 0),
        width="stretch",
    )

    st.caption("Size")
    size_row = st.columns(4)
    size_row[0].button(
        "Wider",
        key="preview_wider",
        on_click=_preview_nudge,
        args=(area, 0, 0, int(size_step), 0),
        width="stretch",
    )
    size_row[1].button(
        "Narrower",
        key="preview_narrower",
        on_click=_preview_nudge,
        args=(area, 0, 0, -int(size_step), 0),
        width="stretch",
    )
    size_row[2].button(
        "Taller",
        key="preview_taller",
        on_click=_preview_nudge,
        args=(area, 0, 0, 0, int(size_step)),
        width="stretch",
    )
    size_row[3].button(
        "Shorter",
        key="preview_shorter",
        on_click=_preview_nudge,
        args=(area, 0, 0, 0, -int(size_step)),
        width="stretch",
    )

    st.caption("Font")
    font_row = st.columns(2)
    font_row[0].button(
        "A−",
        key="preview_font_minus",
        on_click=_preview_font,
        args=(area, -int(font_step)),
        width="stretch",
    )
    font_row[1].button(
        "A+",
        key="preview_font_plus",
        on_click=_preview_font,
        args=(area, int(font_step)),
        width="stretch",
    )

    center_row = st.columns(2)
    center_row[0].button(
        "Center Horizontally",
        key="preview_center_h",
        on_click=_preview_center_h,
        args=(area,),
        width="stretch",
    )
    center_row[1].button(
        "Center Vertically in Available Space",
        key="preview_center_v",
        on_click=_preview_center_v,
        width="stretch",
    )

    if st.button(
        "Auto-fit Title Between Service and Speaker",
        key="preview_autofit_title",
        type="primary",
        width="stretch",
    ):
        _apply_layout_dict(auto_fit_title_box(_current_layout_settings()))
        st.session_state.selected_layout_area = "Sermon Title"
        st.session_state.preview_adjust_area = "Sermon Title"
        st.session_state.layout_autofit_message = (
            "Title box auto-fit between service line and speaker."
        )
        st.rerun()


def _current_layout_settings() -> dict:
    return {
        "service_box": st.session_state.service_box,
        "title_box": st.session_state.title_box,
        "speaker_box": st.session_state.speaker_box,
        "selected_layout_area": st.session_state.get("selected_layout_area", "Sermon Title"),
        "auto_title_box_between_service_and_speaker": st.session_state.get(
            "auto_title_box_between_service_and_speaker", False
        ),
        "auto_title_area": st.session_state.get("auto_title_area", False),
        "title_side_padding": st.session_state.get(
            "title_side_padding", DEFAULT_TITLE_SIDE_PADDING
        ),
        "title_vertical_gap": st.session_state.get(
            "title_vertical_gap", DEFAULT_TITLE_VERTICAL_GAP
        ),
    }


def _apply_layout_dict(settings: dict) -> None:
    st.session_state.service_box = settings["service_box"]
    st.session_state.title_box = settings["title_box"]
    st.session_state.speaker_box = settings["speaker_box"]
    if "selected_layout_area" in settings:
        st.session_state.selected_layout_area = settings["selected_layout_area"]
    if "auto_title_box_between_service_and_speaker" in settings:
        st.session_state.auto_title_box_between_service_and_speaker = settings[
            "auto_title_box_between_service_and_speaker"
        ]
        st.session_state.auto_title_area = settings[
            "auto_title_box_between_service_and_speaker"
        ]


def _sync_preview_area_selector() -> None:
    if st.session_state.get("_layout_selection_from_event"):
        st.session_state.preview_adjust_area = st.session_state.selected_layout_area
        st.session_state._layout_selection_from_event = False
    st.session_state.setdefault(
        "preview_adjust_area",
        st.session_state.get("selected_layout_area", "Sermon Title"),
    )


def _on_preview_area_change() -> None:
    st.session_state.selected_layout_area = normalize_area_name(
        st.session_state.preview_adjust_area
    )


def _on_advanced_area_change() -> None:
    st.session_state.selected_layout_area = normalize_area_name(
        st.session_state.advanced_layout_area
    )


def _preview_nudge(area: str, dx: int, dy: int, dw: int, dh: int) -> None:
    settings = update_layout_box(
        _current_layout_settings(), area, dx=dx, dy=dy, dw=dw, dh=dh
    )
    if area == "Sermon Title" and (dx or dy or dw or dh):
        settings["auto_title_box_between_service_and_speaker"] = False
        settings["auto_title_area"] = False
    settings["selected_layout_area"] = area
    _apply_layout_dict(settings)


def _preview_font(area: str, delta: int) -> None:
    settings = apply_layout_event(
        _current_layout_settings(),
        {"event": "font", "area": area, "font_delta": delta},
        font_step=abs(delta) or 5,
    )["settings"]
    _apply_layout_dict(settings)


def _preview_center_h(area: str) -> None:
    settings = center_box_horizontally(_current_layout_settings(), area)
    if area == "Sermon Title":
        settings["auto_title_box_between_service_and_speaker"] = False
        settings["auto_title_area"] = False
    settings["selected_layout_area"] = area
    _apply_layout_dict(settings)


def _preview_center_v() -> None:
    settings = center_title_vertically_in_available_space(_current_layout_settings())
    settings["auto_title_box_between_service_and_speaker"] = False
    settings["auto_title_area"] = False
    settings["selected_layout_area"] = "Sermon Title"
    _apply_layout_dict(settings)


def _stage_layout_event_from_component(component_key: str) -> None:
    state = st.session_state.get(component_key) or {}
    event = state.get("layout_event")
    if isinstance(event, dict):
        st.session_state.pending_layout_event = event


def _consume_pending_layout_event() -> None:
    event = st.session_state.pop("pending_layout_event", None)
    if not isinstance(event, dict):
        return
    result = apply_layout_event(
        _current_layout_settings(),
        event,
        position_step=int(st.session_state.get("position_step", 5)),
        font_step=int(st.session_state.get("font_step", 5)),
        size_step=int(st.session_state.get("size_step", 10)),
    )
    _apply_layout_dict(result["settings"])
    st.session_state.selected_layout_area = result["selected_area"]
    st.session_state._layout_selection_from_event = True
    if result.get("auto_fit_applied"):
        st.session_state.layout_autofit_message = result.get("message") or (
            "Title box auto-fit between service line and speaker."
        )


def _render_advanced_export_targets() -> None:
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
        f"Export Target: {current_export_target.name} — "
        f"{current_export_target.width}x{current_export_target.height}"
    )


def _image_to_png_bytes(image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _ensure_defaults(today: date) -> None:
    st.session_state.setdefault("schedule_entries", [])
    st.session_state.setdefault("service_log_year", today.year)
    st.session_state.setdefault("pending_schedule_year", None)
    st.session_state.setdefault("selected_entry_key", "")
    st.session_state.setdefault("booth_sermon_title_widget", "")
    st.session_state.setdefault("booth_speaker_widget", "")
    st.session_state.setdefault("booth_notes_widget", "")
    st.session_state.setdefault("booth_loaded_entry_id", "")
    st.session_state.setdefault("pending_booth_values", None)
    st.session_state.setdefault("pending_booth_selected_label", None)
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
    st.session_state.setdefault("auto_title_box_between_service_and_speaker", True)
    st.session_state.setdefault("title_side_padding", DEFAULT_TITLE_SIDE_PADDING)
    st.session_state.setdefault("title_vertical_gap", DEFAULT_TITLE_VERTICAL_GAP)
    st.session_state.setdefault("interactive_preview_layout_editor", False)
    st.session_state.setdefault("layout_autofit_message", "")
    st.session_state.setdefault("pending_layout_event", None)
    st.session_state.setdefault("last_layout_event_nonce", None)
    st.session_state.setdefault(
        "auto_title_area",
        st.session_state.auto_title_box_between_service_and_speaker,
    )
    st.session_state.setdefault(
        "title_top_padding", st.session_state.title_vertical_gap
    )
    st.session_state.setdefault(
        "title_bottom_padding", st.session_state.title_vertical_gap
    )
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
            "auto_title_box_between_service_and_speaker",
            "title_side_padding",
            "title_vertical_gap",
            "auto_title_area",
            "title_top_padding",
            "title_bottom_padding",
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
        layout = resolve_auto_title_layout_settings(settings)
        for key, value in layout.items():
            st.session_state[key] = value
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
            "auto_title_box_between_service_and_speaker": st.session_state.auto_title_box_between_service_and_speaker,
            "title_side_padding": st.session_state.title_side_padding,
            "title_vertical_gap": st.session_state.title_vertical_gap,
            "auto_title_area": st.session_state.auto_title_box_between_service_and_speaker,
            "title_top_padding": st.session_state.title_vertical_gap,
            "title_bottom_padding": st.session_state.title_vertical_gap,
            **_current_export_settings(),
        }
    )


def _box_controls(
    label: str,
    key: str,
    allow_line_spacing: bool = False,
    disable_geometry: bool = False,
) -> None:
    box = st.session_state[key]
    st.markdown(f"**{label}**")
    cols = st.columns(2)
    if disable_geometry:
        cols[0].number_input(
            f"{label} X (auto)",
            0,
            1920,
            int(box["x"]),
            disabled=True,
            key=f"{key}_x_auto_display",
        )
        cols[1].number_input(
            f"{label} Y (auto)",
            0,
            1080,
            int(box["y"]),
            disabled=True,
            key=f"{key}_y_auto_display",
        )
    else:
        box["x"] = cols[0].number_input(f"{label} X", 0, 1920, int(box["x"]))
        box["y"] = cols[1].number_input(f"{label} Y", 0, 1080, int(box["y"]))
    cols = st.columns(2)
    if disable_geometry:
        cols[0].number_input(
            f"{label} Width (auto)",
            50,
            1920,
            int(box["width"]),
            disabled=True,
            key=f"{key}_width_auto_display",
        )
        cols[1].number_input(
            f"{label} Height (auto)",
            30,
            1080,
            int(box["height"]),
            disabled=True,
            key=f"{key}_height_auto_display",
        )
    else:
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


def _visual_layout_controls(*, disable_title_geometry: bool = False) -> None:
    # Keep a separate widget key from Preview Layout Controls to avoid duplicates.
    st.session_state.setdefault(
        "advanced_layout_area",
        st.session_state.get("selected_layout_area", "Sermon Title"),
    )
    if st.session_state.get("_layout_selection_from_event"):
        st.session_state.advanced_layout_area = st.session_state.selected_layout_area
    selected_area = st.selectbox(
        "Text area to adjust",
        list(AREA_KEYS.keys()),
        key="advanced_layout_area",
        on_change=_on_advanced_area_change,
    )
    selected_area = normalize_area_name(selected_area)
    st.session_state.selected_layout_area = selected_area

    # Step values come from Preview Layout Controls (or defaults).
    position_step = int(st.session_state.get("position_step", 5))
    size_step = int(st.session_state.get("size_step", 10))
    font_step = int(st.session_state.get("font_step", 5))
    skew_step = float(st.session_state.get("skew_step", 2.0))
    st.caption(
        f"Using move step {position_step}, size step {size_step}, "
        f"font step {font_step}. Change steps under Preview Layout Controls."
    )
    skew_step = st.select_slider(
        "Skew step",
        options=[0.5, 1.0, 2.0, 5.0],
        value=skew_step if skew_step in {0.5, 1.0, 2.0, 5.0} else 2.0,
        key="skew_step",
    )

    geometry_locked = disable_title_geometry and selected_area == "Sermon Title"
    if geometry_locked:
        st.caption(
            "Title position/size are controlled by Auto Title Layout. "
            "Font size and italic slant can still be adjusted."
        )
    else:
        st.caption("Position")
        row = st.columns([1, 1, 1])
        row[1].button(
            "Up",
            key="adv_move_up",
            on_click=_nudge_box,
            args=(selected_area, 0, -position_step, 0, 0),
            width="stretch",
        )
        row = st.columns([1, 1, 1])
        row[0].button(
            "Left",
            key="adv_move_left",
            on_click=_nudge_box,
            args=(selected_area, -position_step, 0, 0, 0),
            width="stretch",
        )
        row[1].markdown("<div style='text-align:center'>Move</div>", unsafe_allow_html=True)
        row[2].button(
            "Right",
            key="adv_move_right",
            on_click=_nudge_box,
            args=(selected_area, position_step, 0, 0, 0),
            width="stretch",
        )
        row = st.columns([1, 1, 1])
        row[1].button(
            "Down",
            key="adv_move_down",
            on_click=_nudge_box,
            args=(selected_area, 0, position_step, 0, 0),
            width="stretch",
        )

        st.caption("Size")
        row = st.columns(4)
        row[0].button(
            "Wider",
            key="adv_wider",
            on_click=_nudge_box,
            args=(selected_area, 0, 0, size_step, 0),
            width="stretch",
        )
        row[1].button(
            "Narrower",
            key="adv_narrower",
            on_click=_nudge_box,
            args=(selected_area, 0, 0, -size_step, 0),
            width="stretch",
        )
        row[2].button(
            "Taller",
            key="adv_taller",
            on_click=_nudge_box,
            args=(selected_area, 0, 0, 0, size_step),
            width="stretch",
        )
        row[3].button(
            "Shorter",
            key="adv_shorter",
            on_click=_nudge_box,
            args=(selected_area, 0, 0, 0, -size_step),
            width="stretch",
        )

    st.caption("Font")
    row = st.columns(2 if selected_area != "Sermon Title" else 4)
    row[0].button(
        "A+",
        key="adv_font_plus",
        on_click=_nudge_font,
        args=(selected_area, font_step),
        width="stretch",
    )
    row[1].button(
        "A-",
        key="adv_font_minus",
        on_click=_nudge_font,
        args=(selected_area, -font_step),
        width="stretch",
    )
    if selected_area == "Sermon Title":
        row[2].button(
            "Italic +",
            key="adv_skew_plus",
            on_click=_nudge_skew,
            args=(selected_area, skew_step),
            width="stretch",
        )
        row[3].button(
            "Italic -",
            key="adv_skew_minus",
            on_click=_nudge_skew,
            args=(selected_area, -skew_step),
            width="stretch",
        )


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
    st.session_state.pending_booth_values = values
    st.session_state.pending_booth_selected_label = build_booth_service_label(entry)
    st.session_state.booth_loaded_entry_id = ""


def _update_selected_notes(notes: str) -> None:
    for entry in st.session_state.schedule_entries:
        if entry_key(entry) == st.session_state.selected_entry_key:
            entry["notes"] = notes
            break


def _persist_current_booth_inputs() -> None:
    st.session_state.schedule_entries = update_booth_entry(
        st.session_state.schedule_entries,
        st.session_state.selected_entry_key,
        st.session_state.get("booth_sermon_title_widget", ""),
        st.session_state.get("booth_speaker_widget", ""),
        st.session_state.get("booth_notes_widget", ""),
    )
    _save_service_log_now()


def _prepare_booth_input_widgets(entry: dict) -> None:
    pending = st.session_state.get("pending_booth_values")
    entry_id = entry_key(entry)
    if isinstance(pending, dict) and pending.get("selected_key") == entry_id:
        values = pending
        st.session_state.pending_booth_values = None
    elif st.session_state.get("booth_loaded_entry_id") != entry_id:
        values = load_entry_values(entry)
    else:
        return

    st.session_state.booth_sermon_title_widget = values.get("title", "")
    st.session_state.booth_speaker_widget = values.get("speaker", "")
    st.session_state.booth_notes_widget = values.get("notes", "")
    st.session_state.booth_loaded_entry_id = entry_id


def _prepare_booth_selector_widget(labels: list[str]) -> None:
    pending = st.session_state.get("pending_booth_selected_label")
    if pending in labels:
        st.session_state.booth_selected_entry_label = pending
        st.session_state.pending_booth_selected_label = None
        return

    if st.session_state.get("booth_selected_entry_label") not in labels:
        index = _selected_entry_index()
        if labels:
            st.session_state.booth_selected_entry_label = labels[index]


def _switch_to_entry_index(new_index: int) -> None:
    entries = st.session_state.schedule_entries
    result = switch_service(
        entries,
        _selected_entry_index(),
        new_index,
        st.session_state.get("booth_sermon_title_widget", ""),
        st.session_state.get("booth_speaker_widget", ""),
        st.session_state.get("booth_notes_widget", ""),
    )
    st.session_state.schedule_entries = result["entries"]
    st.session_state.selected_entry_key = result["selected_key"]
    st.session_state.pending_booth_values = result["values"]
    next_entry = st.session_state.schedule_entries[result["index"]]
    st.session_state.pending_booth_selected_label = build_booth_service_label(next_entry)
    st.session_state.booth_loaded_entry_id = ""
    _save_service_log_now()


def _entry_index_for_key(selected_key: str) -> int:
    for index, entry in enumerate(st.session_state.schedule_entries):
        if entry_key(entry) == selected_key:
            return index
    return _selected_entry_index()


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
    effective = get_effective_layout_boxes(
        {
            "service_box": st.session_state.service_box,
            "title_box": st.session_state.title_box,
            "speaker_box": st.session_state.speaker_box,
            "auto_title_box_between_service_and_speaker": st.session_state.get(
                "auto_title_box_between_service_and_speaker",
                st.session_state.get("auto_title_area", True),
            ),
            "title_side_padding": st.session_state.get(
                "title_side_padding", DEFAULT_TITLE_SIDE_PADDING
            ),
            "title_vertical_gap": st.session_state.get(
                "title_vertical_gap", DEFAULT_TITLE_VERTICAL_GAP
            ),
        }
    )
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
        service_line_box=_text_box(effective["service_box"]),
        title_box=_text_box(effective["title_box"]),
        speaker_box=_text_box(effective["speaker_box"]),
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
        "auto_title_box_between_service_and_speaker": st.session_state.auto_title_box_between_service_and_speaker,
        "title_side_padding": st.session_state.title_side_padding,
        "title_vertical_gap": st.session_state.title_vertical_gap,
        "auto_title_area": st.session_state.auto_title_box_between_service_and_speaker,
        "title_top_padding": st.session_state.title_vertical_gap,
        "title_bottom_padding": st.session_state.title_vertical_gap,
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
    layout = resolve_auto_title_layout_settings(settings)
    for key, value in layout.items():
        st.session_state[key] = value
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
