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
MIN_AUTO_TITLE_HEIGHT = 80

DEFAULT_TITLE_SIDE_PADDING = 120
DEFAULT_TITLE_VERTICAL_GAP = 40
# Legacy aliases kept for migration of older settings/presets.
DEFAULT_TITLE_TOP_PADDING = DEFAULT_TITLE_VERTICAL_GAP
DEFAULT_TITLE_BOTTOM_PADDING = DEFAULT_TITLE_VERTICAL_GAP

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


def scale_side_padding(
    side_padding: int,
    canvas_width: int,
    base_width: int = CANVAS_WIDTH,
) -> int:
    """Scale horizontal padding with the canvas / export target width."""
    if base_width <= 0:
        return max(0, int(side_padding))
    return max(0, round(int(side_padding) * (canvas_width / base_width)))


def scale_vertical_gap(
    vertical_gap: int,
    canvas_height: int,
    base_height: int = CANVAS_HEIGHT,
) -> int:
    """Scale vertical gap with the canvas / export target height."""
    if base_height <= 0:
        return max(0, int(vertical_gap))
    return max(0, round(int(vertical_gap) * (canvas_height / base_height)))


def calculate_auto_title_box(
    canvas_width: int,
    canvas_height: int,
    service_box: dict[str, Any],
    speaker_box: dict[str, Any],
    side_padding: int = DEFAULT_TITLE_SIDE_PADDING,
    vertical_gap: int = DEFAULT_TITLE_VERTICAL_GAP,
    title_box: dict[str, Any] | None = None,
    *,
    scale_padding: bool = False,
) -> dict[str, Any]:
    """
    Build a wide title box between service and speaker with equal gaps and side padding.

    Returns a title box dict plus optional ``warning`` when space is tight.
    """
    base = (title_box or {}).copy()
    pad = int(side_padding)
    gap = int(vertical_gap)
    if scale_padding:
        pad = scale_side_padding(pad, canvas_width)
        gap = scale_vertical_gap(gap, canvas_height)

    pad = max(0, min(pad, max(0, (canvas_width - MIN_BOX_SIZE) // 2)))
    gap = max(0, gap)

    service_bottom = int(service_box.get("y", 0)) + int(service_box.get("height", 0))
    speaker_top = int(speaker_box.get("y", canvas_height))
    available_height = speaker_top - service_bottom

    warning = None
    title_y = service_bottom + gap
    title_height = available_height - (2 * gap)

    if available_height < MIN_AUTO_TITLE_HEIGHT + 2:
        warning = (
            "Not enough vertical space between the service and speaker lines "
            f"for an auto title box (need at least {MIN_AUTO_TITLE_HEIGHT + 2}px)."
        )
        mid = (service_bottom + speaker_top) // 2
        title_y = max(0, mid - MIN_AUTO_TITLE_HEIGHT // 2)
        title_height = MIN_AUTO_TITLE_HEIGHT
    elif title_height < MIN_AUTO_TITLE_HEIGHT:
        warning = (
            "Auto title box height was clamped because the vertical gap left "
            f"less than {MIN_AUTO_TITLE_HEIGHT}px for the sermon title."
        )
        # Shrink gaps equally to keep centering while meeting minimum height.
        usable = max(MIN_AUTO_TITLE_HEIGHT, available_height)
        title_height = min(usable, available_height)
        leftover = available_height - title_height
        title_y = service_bottom + leftover // 2

    result = {
        **base,
        "x": pad,
        "y": title_y,
        "width": max(MIN_BOX_SIZE, canvas_width - (2 * pad)),
        "height": max(MIN_BOX_SIZE, title_height),
        "alignment": base.get("alignment", "center"),
    }
    clamped = clamp_box_to_canvas(result, canvas_width, canvas_height)
    if warning:
        clamped["warning"] = warning
    return clamped


def compute_auto_title_box(
    service_box: dict[str, Any],
    speaker_box: dict[str, Any],
    title_box: dict[str, Any],
    top_padding: int = DEFAULT_TITLE_TOP_PADDING,
    bottom_padding: int = DEFAULT_TITLE_BOTTOM_PADDING,
    *,
    side_padding: int | None = None,
    vertical_gap: int | None = None,
    canvas_width: int = CANVAS_WIDTH,
    canvas_height: int = CANVAS_HEIGHT,
) -> dict[str, Any]:
    """Compatibility wrapper — prefers equal vertical_gap when provided."""
    gap = vertical_gap
    if gap is None:
        gap = max(0, (int(top_padding) + int(bottom_padding)) // 2)
    pad = DEFAULT_TITLE_SIDE_PADDING if side_padding is None else int(side_padding)
    return calculate_auto_title_box(
        canvas_width,
        canvas_height,
        service_box,
        speaker_box,
        side_padding=pad,
        vertical_gap=gap,
        title_box=title_box,
    )


def resolve_auto_title_layout_settings(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    """Migrate legacy auto-title keys into the current layout settings."""
    data = raw or {}
    if "auto_title_box_between_service_and_speaker" in data:
        auto = bool(data["auto_title_box_between_service_and_speaker"])
    elif "auto_title_area" in data:
        auto = bool(data["auto_title_area"])
    else:
        # Missing on old presets: keep stored manual title box.
        auto = False

    if "title_side_padding" in data:
        side = int(data["title_side_padding"])
    else:
        side = DEFAULT_TITLE_SIDE_PADDING

    if "title_vertical_gap" in data:
        gap = int(data["title_vertical_gap"])
    elif "title_top_padding" in data or "title_bottom_padding" in data:
        top = int(data.get("title_top_padding", DEFAULT_TITLE_VERTICAL_GAP))
        bottom = int(data.get("title_bottom_padding", DEFAULT_TITLE_VERTICAL_GAP))
        gap = max(0, (top + bottom) // 2)
    else:
        gap = DEFAULT_TITLE_VERTICAL_GAP

    return {
        "auto_title_box_between_service_and_speaker": auto,
        "title_side_padding": max(0, min(800, side)),
        "title_vertical_gap": max(0, min(400, gap)),
        # Keep legacy keys in sync for older UI/persistence paths.
        "auto_title_area": auto,
        "title_top_padding": max(0, min(400, gap)),
        "title_bottom_padding": max(0, min(400, gap)),
    }


def get_effective_layout_boxes(
    settings: dict[str, Any],
    canvas_width: int = CANVAS_WIDTH,
    canvas_height: int = CANVAS_HEIGHT,
    *,
    scale_padding: bool = False,
) -> dict[str, Any]:
    """Return service/title/speaker boxes; title is calculated when auto layout is on."""
    layout = resolve_auto_title_layout_settings(settings)
    service_box = clamp_box_to_canvas(
        dict(settings.get("service_box") or {}), canvas_width, canvas_height
    )
    speaker_box = clamp_box_to_canvas(
        dict(settings.get("speaker_box") or {}), canvas_width, canvas_height
    )
    stored_title = dict(settings.get("title_box") or {})

    warning = None
    if layout["auto_title_box_between_service_and_speaker"]:
        title_box = calculate_auto_title_box(
            canvas_width,
            canvas_height,
            service_box,
            speaker_box,
            side_padding=layout["title_side_padding"],
            vertical_gap=layout["title_vertical_gap"],
            title_box=stored_title,
            scale_padding=scale_padding,
        )
        warning = title_box.pop("warning", None)
    else:
        title_box = clamp_box_to_canvas(stored_title, canvas_width, canvas_height)

    return {
        "service_box": service_box,
        "title_box": title_box,
        "speaker_box": speaker_box,
        "auto_title_box_between_service_and_speaker": layout[
            "auto_title_box_between_service_and_speaker"
        ],
        "title_side_padding": layout["title_side_padding"],
        "title_vertical_gap": layout["title_vertical_gap"],
        "warning": warning,
    }


def resolve_title_box(
    service_box: dict[str, Any],
    speaker_box: dict[str, Any],
    title_box: dict[str, Any],
    *,
    auto_title_area: bool | None = None,
    auto_title_box_between_service_and_speaker: bool | None = None,
    title_top_padding: int = DEFAULT_TITLE_TOP_PADDING,
    title_bottom_padding: int = DEFAULT_TITLE_BOTTOM_PADDING,
    title_side_padding: int = DEFAULT_TITLE_SIDE_PADDING,
    title_vertical_gap: int | None = None,
    canvas_width: int = CANVAS_WIDTH,
    canvas_height: int = CANVAS_HEIGHT,
) -> dict[str, Any]:
    auto = auto_title_box_between_service_and_speaker
    if auto is None:
        auto = True if auto_title_area is None else bool(auto_title_area)
    if not auto:
        return clamp_box_to_canvas(title_box.copy(), canvas_width, canvas_height)

    gap = title_vertical_gap
    if gap is None:
        gap = max(0, (int(title_top_padding) + int(title_bottom_padding)) // 2)
    result = calculate_auto_title_box(
        canvas_width,
        canvas_height,
        service_box,
        speaker_box,
        side_padding=title_side_padding,
        vertical_gap=gap,
        title_box=title_box,
    )
    result.pop("warning", None)
    return result
