from __future__ import annotations

from typing import Any


CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080
MIN_BOX_SIZE = 20
MIN_FONT_SIZE = 8
MAX_TITLE_FONT_SIZE = 400
MAX_OTHER_FONT_SIZE = 260
MIN_SKEW_ANGLE = -25.0
MAX_SKEW_ANGLE = 25.0

AREA_KEYS = {
    "Service Line": "service_box",
    "Sermon Title": "title_box",
    "Speaker": "speaker_box",
}


def get_layout_box(settings: dict[str, Any], area_name: str) -> dict[str, Any]:
    return settings[AREA_KEYS[area_name]]


def update_layout_box(
    settings: dict[str, Any],
    area_name: str,
    dx: int = 0,
    dy: int = 0,
    dw: int = 0,
    dh: int = 0,
) -> dict[str, Any]:
    box = get_layout_box(settings, area_name).copy()
    box["x"] = int(box.get("x", 0)) + dx
    box["y"] = int(box.get("y", 0)) + dy
    box["width"] = int(box.get("width", MIN_BOX_SIZE)) + dw
    box["height"] = int(box.get("height", MIN_BOX_SIZE)) + dh
    settings[AREA_KEYS[area_name]] = clamp_box_to_canvas(box)
    return settings


def nudge_font_size(
    settings: dict[str, Any],
    area_name: str,
    delta: int,
) -> dict[str, Any]:
    box = get_layout_box(settings, area_name).copy()
    max_size = MAX_TITLE_FONT_SIZE if area_name == "Sermon Title" else MAX_OTHER_FONT_SIZE
    box["font_size"] = clamp_font_size(box.get("font_size", MIN_FONT_SIZE) + delta, max_size=max_size)
    settings[AREA_KEYS[area_name]] = box
    return settings


def nudge_skew_angle(
    settings: dict[str, Any],
    area_name: str,
    delta: float,
) -> dict[str, Any]:
    box = get_layout_box(settings, area_name).copy()
    box["skew_angle"] = clamp_skew_angle(float(box.get("skew_angle", 0)) + delta)
    settings[AREA_KEYS[area_name]] = box
    return settings


def clamp_box_to_canvas(
    box: dict[str, Any],
    canvas_width: int = CANVAS_WIDTH,
    canvas_height: int = CANVAS_HEIGHT,
) -> dict[str, Any]:
    clamped = box.copy()
    clamped["x"] = max(0, min(int(clamped.get("x", 0)), canvas_width - MIN_BOX_SIZE))
    clamped["y"] = max(0, min(int(clamped.get("y", 0)), canvas_height - MIN_BOX_SIZE))
    max_width = canvas_width - clamped["x"]
    max_height = canvas_height - clamped["y"]
    clamped["width"] = max(MIN_BOX_SIZE, min(int(clamped.get("width", MIN_BOX_SIZE)), max_width))
    clamped["height"] = max(MIN_BOX_SIZE, min(int(clamped.get("height", MIN_BOX_SIZE)), max_height))
    return clamped


def clamp_font_size(
    value: int,
    min_size: int = MIN_FONT_SIZE,
    max_size: int = MAX_TITLE_FONT_SIZE,
) -> int:
    return max(min_size, min(max_size, int(value)))


def clamp_skew_angle(value: float) -> float:
    return max(MIN_SKEW_ANGLE, min(MAX_SKEW_ANGLE, float(value)))


DEFAULT_TITLE_TOP_PADDING = 100
DEFAULT_TITLE_BOTTOM_PADDING = 140


def compute_auto_title_box(
    service_box: dict[str, Any],
    speaker_box: dict[str, Any],
    title_box: dict[str, Any],
    top_padding: int = DEFAULT_TITLE_TOP_PADDING,
    bottom_padding: int = DEFAULT_TITLE_BOTTOM_PADDING,
) -> dict[str, Any]:
    """Derive title y/height between service and speaker boxes, keeping other title settings."""
    result = title_box.copy()
    service_bottom = int(service_box.get("y", 0)) + int(service_box.get("height", 0))
    speaker_top = int(speaker_box.get("y", CANVAS_HEIGHT))
    top = service_bottom + max(0, int(top_padding))
    bottom = speaker_top - max(0, int(bottom_padding))
    if bottom <= top + MIN_BOX_SIZE:
        mid = (service_bottom + speaker_top) // 2
        top = max(0, mid - MIN_BOX_SIZE // 2)
        bottom = top + MIN_BOX_SIZE
    result["y"] = top
    result["height"] = max(MIN_BOX_SIZE, bottom - top)
    result["x"] = int(title_box.get("x", service_box.get("x", 280)))
    result["width"] = int(title_box.get("width", service_box.get("width", 1360)))
    return clamp_box_to_canvas(result)


def resolve_title_box(
    service_box: dict[str, Any],
    speaker_box: dict[str, Any],
    title_box: dict[str, Any],
    *,
    auto_title_area: bool = True,
    title_top_padding: int = DEFAULT_TITLE_TOP_PADDING,
    title_bottom_padding: int = DEFAULT_TITLE_BOTTOM_PADDING,
) -> dict[str, Any]:
    if auto_title_area:
        return compute_auto_title_box(
            service_box,
            speaker_box,
            title_box,
            top_padding=title_top_padding,
            bottom_padding=title_bottom_padding,
        )
    return clamp_box_to_canvas(title_box.copy())
