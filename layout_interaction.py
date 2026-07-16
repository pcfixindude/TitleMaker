from __future__ import annotations

from typing import Any

from layout_controls import (
    AREA_KEYS,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    DEFAULT_TITLE_SIDE_PADDING,
    DEFAULT_TITLE_VERTICAL_GAP,
    MIN_AUTO_TITLE_HEIGHT,
    MIN_BOX_SIZE,
    calculate_auto_title_box,
    clamp_box_to_canvas,
    nudge_font_size,
    update_layout_box,
)


AREA_ALIASES = {
    "service": "Service Line",
    "title": "Sermon Title",
    "speaker": "Speaker",
    "Service Line": "Service Line",
    "Sermon Title": "Sermon Title",
    "Speaker": "Speaker",
    "Speaker / Minister": "Speaker",
}

AREA_EVENT_KEYS = {
    "Service Line": "service",
    "Sermon Title": "title",
    "Speaker": "speaker",
}


def normalize_area_name(area: str | None) -> str:
    if not area:
        return "Sermon Title"
    return AREA_ALIASES.get(str(area), "Sermon Title")


def hit_test_layout_area(
    x: float,
    y: float,
    service_box: dict[str, Any],
    title_box: dict[str, Any],
    speaker_box: dict[str, Any],
) -> str | None:
    """Return the topmost layout area containing the design-space point, if any."""
    # Prefer title when overlapping so title editing stays easy.
    ordered = (
        ("Sermon Title", title_box),
        ("Service Line", service_box),
        ("Speaker", speaker_box),
    )
    for area_name, box in ordered:
        if _point_in_box(x, y, box):
            return area_name
    return None


def _point_in_box(x: float, y: float, box: dict[str, Any]) -> bool:
    left = float(box.get("x", 0))
    top = float(box.get("y", 0))
    right = left + float(box.get("width", 0))
    bottom = top + float(box.get("height", 0))
    return left <= x <= right and top <= y <= bottom


def scale_display_point_to_design(
    display_x: float,
    display_y: float,
    display_width: float,
    display_height: float,
    design_width: int = CANVAS_WIDTH,
    design_height: int = CANVAS_HEIGHT,
) -> tuple[float, float]:
    if display_width <= 0 or display_height <= 0:
        return 0.0, 0.0
    return (
        display_x * (design_width / display_width),
        display_y * (design_height / display_height),
    )


def apply_layout_event(
    settings: dict[str, Any],
    event: dict[str, Any],
    *,
    position_step: int = 5,
    font_step: int = 5,
    size_step: int = 10,
) -> dict[str, Any]:
    """
    Apply an interactive layout event to settings.

    Returns a result dict with updated settings and status fields.
    """
    result = {
        "settings": settings,
        "selected_area": normalize_area_name(
            event.get("area") or settings.get("selected_layout_area")
        ),
        "message": "",
        "auto_fit_applied": False,
    }
    event_type = str(event.get("event") or "").lower()
    area = result["selected_area"]

    if event_type == "select":
        result["settings"]["selected_layout_area"] = area
        result["message"] = f"Selected layout area: {area}"
        return result

    if event_type == "autofit":
        settings = auto_fit_title_box(settings)
        settings["selected_layout_area"] = "Sermon Title"
        settings["auto_title_box_between_service_and_speaker"] = False
        settings["auto_title_area"] = False
        result["settings"] = settings
        result["selected_area"] = "Sermon Title"
        result["auto_fit_applied"] = True
        result["message"] = "Title box auto-fit between service line and speaker."
        return result

    if event_type == "move":
        dx = int(event.get("dx", 0))
        dy = int(event.get("dy", 0))
        if dx == 0 and dy == 0:
            # Keyboard arrow names
            direction = str(event.get("direction") or "").lower()
            step = int(event.get("step", position_step))
            if direction in {"up", "arrowup"}:
                dy = -step
            elif direction in {"down", "arrowdown"}:
                dy = step
            elif direction in {"left", "arrowleft"}:
                dx = -step
            elif direction in {"right", "arrowright"}:
                dx = step
        settings = update_layout_box(settings, area, dx=dx, dy=dy)
        settings["selected_layout_area"] = area
        # Moving manually opts out of auto title geometry.
        if area == "Sermon Title":
            settings["auto_title_box_between_service_and_speaker"] = False
            settings["auto_title_area"] = False
        result["settings"] = settings
        return result

    if event_type == "resize":
        dw = int(event.get("dw", 0))
        dh = int(event.get("dh", 0))
        settings = update_layout_box(settings, area, dw=dw, dh=dh)
        settings["selected_layout_area"] = area
        if area == "Sermon Title":
            settings["auto_title_box_between_service_and_speaker"] = False
            settings["auto_title_area"] = False
        result["settings"] = settings
        return result

    if event_type == "font":
        delta = int(event.get("font_delta", event.get("delta", font_step)))
        settings = nudge_font_size(settings, area, delta)
        # Font changes should disable auto-size so the nudge is visible.
        box = settings[AREA_KEYS[area]].copy()
        box["auto_size"] = False
        settings[AREA_KEYS[area]] = box
        settings["selected_layout_area"] = area
        result["settings"] = settings
        return result

    if event_type == "center_h":
        settings = center_box_horizontally(settings, area)
        settings["selected_layout_area"] = area
        if area == "Sermon Title":
            settings["auto_title_box_between_service_and_speaker"] = False
            settings["auto_title_area"] = False
        result["settings"] = settings
        return result

    if event_type == "center_v":
        settings = center_title_vertically_in_available_space(settings)
        settings["selected_layout_area"] = "Sermon Title"
        settings["auto_title_box_between_service_and_speaker"] = False
        settings["auto_title_area"] = False
        result["settings"] = settings
        result["selected_area"] = "Sermon Title"
        return result

    return result


def auto_fit_title_box(settings: dict[str, Any]) -> dict[str, Any]:
    """Apply calculated title box once as a manual box for further fine-tuning."""
    updated = {
        "service_box": dict(settings.get("service_box") or {}),
        "speaker_box": dict(settings.get("speaker_box") or {}),
        "title_box": dict(settings.get("title_box") or {}),
        **{
            key: settings[key]
            for key in settings
            if key not in {"service_box", "speaker_box", "title_box"}
        },
    }
    side = int(settings.get("title_side_padding", DEFAULT_TITLE_SIDE_PADDING))
    gap = int(settings.get("title_vertical_gap", DEFAULT_TITLE_VERTICAL_GAP))
    fitted = calculate_auto_title_box(
        CANVAS_WIDTH,
        CANVAS_HEIGHT,
        updated["service_box"],
        updated["speaker_box"],
        side_padding=side,
        vertical_gap=gap,
        title_box=updated["title_box"],
    )
    fitted.pop("warning", None)
    fitted["height"] = max(MIN_AUTO_TITLE_HEIGHT, int(fitted.get("height", MIN_AUTO_TITLE_HEIGHT)))
    fitted["width"] = max(MIN_BOX_SIZE, int(fitted.get("width", MIN_BOX_SIZE)))
    updated["title_box"] = clamp_box_to_canvas(fitted)
    updated["auto_title_box_between_service_and_speaker"] = False
    updated["auto_title_area"] = False
    return updated


def center_box_horizontally(
    settings: dict[str, Any],
    area_name: str,
    canvas_width: int = CANVAS_WIDTH,
) -> dict[str, Any]:
    area = normalize_area_name(area_name)
    box = dict(settings[AREA_KEYS[area]])
    width = int(box.get("width", MIN_BOX_SIZE))
    box["x"] = max(0, (canvas_width - width) // 2)
    settings[AREA_KEYS[area]] = clamp_box_to_canvas(box, canvas_width=canvas_width)
    return settings


def center_title_vertically_in_available_space(
    settings: dict[str, Any],
) -> dict[str, Any]:
    service = settings.get("service_box") or {}
    speaker = settings.get("speaker_box") or {}
    title = dict(settings.get("title_box") or {})
    service_bottom = int(service.get("y", 0)) + int(service.get("height", 0))
    speaker_top = int(speaker.get("y", CANVAS_HEIGHT))
    available = speaker_top - service_bottom
    height = max(MIN_BOX_SIZE, int(title.get("height", MIN_BOX_SIZE)))
    if available > height:
        title["y"] = service_bottom + (available - height) // 2
    else:
        title["y"] = service_bottom
    settings["title_box"] = clamp_box_to_canvas(title)
    return settings


def nudge_box(
    settings: dict[str, Any],
    area: str,
    dx: int = 0,
    dy: int = 0,
    dw: int = 0,
    dh: int = 0,
) -> dict[str, Any]:
    return update_layout_box(
        settings, normalize_area_name(area), dx=dx, dy=dy, dw=dw, dh=dh
    )


def nudge_area_font_size(
    settings: dict[str, Any],
    area: str,
    delta: int,
) -> dict[str, Any]:
    return nudge_font_size(settings, normalize_area_name(area), delta)


def boxes_for_overlay(settings: dict[str, Any]) -> dict[str, dict[str, int]]:
    return {
        "service": {
            "x": int(settings["service_box"]["x"]),
            "y": int(settings["service_box"]["y"]),
            "width": int(settings["service_box"]["width"]),
            "height": int(settings["service_box"]["height"]),
        },
        "title": {
            "x": int(settings["title_box"]["x"]),
            "y": int(settings["title_box"]["y"]),
            "width": int(settings["title_box"]["width"]),
            "height": int(settings["title_box"]["height"]),
        },
        "speaker": {
            "x": int(settings["speaker_box"]["x"]),
            "y": int(settings["speaker_box"]["y"]),
            "width": int(settings["speaker_box"]["width"]),
            "height": int(settings["speaker_box"]["height"]),
        },
    }
