from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from title_renderer import (
    DEFAULT_BOTTOM_POSITION,
    DEFAULT_TITLE_POSITION,
    DEFAULT_TOP_POSITION,
    PRESETS_DIR,
    ensure_project_dirs,
)
from layout_controls import MAX_TITLE_FONT_SIZE, clamp_skew_angle


AUTOMATIC_FONT_LABEL = "Automatic fallback (Bebas Neue/system)"
GENERATED_BACKGROUND_LABEL = "Generated blue/gray background"
ALIGNMENTS = ["center", "left", "right"]
DEFAULT_SERVICE_BOX = {
    "x": 280,
    "y": DEFAULT_TOP_POSITION[1],
    "width": 1360,
    "height": 110,
    "alignment": "center",
    "auto_size": True,
    "font_size": 86,
    "max_font_size": 260,
    "line_spacing": 1.0,
    "skew_angle": 0.0,
}
DEFAULT_TITLE_BOX = {
    "x": 280,
    "y": DEFAULT_TITLE_POSITION[1] - 215,
    "width": 1360,
    "height": 430,
    "alignment": "center",
    "auto_size": True,
    "font_size": 218,
    "max_font_size": MAX_TITLE_FONT_SIZE,
    "line_spacing": 0.9,
    "skew_angle": -7.0,
}
DEFAULT_SPEAKER_BOX = {
    "x": 280,
    "y": DEFAULT_BOTTOM_POSITION[1],
    "width": 1360,
    "height": 110,
    "alignment": "center",
    "auto_size": True,
    "font_size": 80,
    "max_font_size": 260,
    "line_spacing": 1.0,
    "skew_angle": 0.0,
}

BUILT_IN_PRESETS: list[dict[str, Any]] = [
    {
        "name": "Monark Blue Gray",
        "font_choice": AUTOMATIC_FONT_LABEL,
        "auto_size": True,
        "title_font_size": 218,
        "text_color": "#FFFFFF",
        "background_choice": GENERATED_BACKGROUND_LABEL,
        "title_position": list(DEFAULT_TITLE_POSITION),
        "service_line_position": list(DEFAULT_TOP_POSITION),
        "speaker_line_position": list(DEFAULT_BOTTOM_POSITION),
        "service_line_box": DEFAULT_SERVICE_BOX,
        "title_box": DEFAULT_TITLE_BOX,
        "speaker_box": DEFAULT_SPEAKER_BOX,
        "text_alignment": "center",
        "shadow_enabled": True,
        "show_service_line": True,
        "show_layout_guides": False,
        "selected_layout_area": "Sermon Title",
        "skew_enabled": True,
    },
    {
        "name": "Plain Black Text",
        "font_choice": AUTOMATIC_FONT_LABEL,
        "auto_size": True,
        "title_font_size": 198,
        "text_color": "#111111",
        "background_choice": GENERATED_BACKGROUND_LABEL,
        "title_position": [960, 540],
        "service_line_position": [960, 112],
        "speaker_line_position": [960, 902],
        "service_line_box": {**DEFAULT_SERVICE_BOX, "alignment": "center"},
        "title_box": {**DEFAULT_TITLE_BOX, "font_size": 198},
        "speaker_box": DEFAULT_SPEAKER_BOX,
        "text_alignment": "center",
        "shadow_enabled": False,
        "show_service_line": True,
        "show_layout_guides": False,
        "selected_layout_area": "Sermon Title",
        "skew_enabled": False,
    },
    {
        "name": "Bold Service Title",
        "font_choice": AUTOMATIC_FONT_LABEL,
        "auto_size": True,
        "title_font_size": 230,
        "text_color": "#FFFFFF",
        "background_choice": GENERATED_BACKGROUND_LABEL,
        "title_position": [960, 520],
        "service_line_position": [960, 92],
        "speaker_line_position": [960, 910],
        "service_line_box": {**DEFAULT_SERVICE_BOX, "y": 92},
        "title_box": {**DEFAULT_TITLE_BOX, "y": 305, "font_size": 230},
        "speaker_box": {**DEFAULT_SPEAKER_BOX, "y": 910},
        "text_alignment": "center",
        "shadow_enabled": True,
        "show_service_line": True,
        "show_layout_guides": False,
        "selected_layout_area": "Sermon Title",
        "skew_enabled": True,
    },
]


def ensure_builtin_presets() -> None:
    ensure_project_dirs()
    for preset in BUILT_IN_PRESETS:
        path = PRESETS_DIR / f"{_slug(preset['name'])}.json"
        if not path.exists():
            _write_json(path, preset)


def list_presets() -> list[dict[str, Any]]:
    ensure_builtin_presets()
    presets: list[dict[str, Any]] = []
    for path in sorted(PRESETS_DIR.glob("*.json")):
        preset = load_preset(path)
        if preset:
            presets.append(preset)
    return presets


def load_preset(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(raw, dict):
        return None

    return normalize_preset(raw)


def save_preset(name: str, settings: dict[str, Any]) -> Path:
    ensure_project_dirs()
    preset = normalize_preset({"name": name, **settings})
    path = PRESETS_DIR / f"{_slug(preset['name'])}.json"
    _write_json(path, preset)
    return path


def normalize_preset(raw: dict[str, Any]) -> dict[str, Any]:
    name = str(raw.get("name") or "Untitled Preset").strip() or "Untitled Preset"
    auto_size = bool(raw.get("auto_size", True))
    title_font_size = _int_in_range(raw.get("title_font_size", 218), 48, MAX_TITLE_FONT_SIZE)
    alignment = str(raw.get("text_alignment", "center")).lower()
    if alignment not in ALIGNMENTS:
        alignment = "center"
    service_line_box = _box(
        raw.get("service_line_box"),
        {**DEFAULT_SERVICE_BOX, "y": _position(raw.get("service_line_position"), DEFAULT_TOP_POSITION)[1]},
        alignment,
    )
    title_box = _box(
        raw.get("title_box"),
        {
            **DEFAULT_TITLE_BOX,
            "y": _position(raw.get("title_position"), DEFAULT_TITLE_POSITION)[1] - 215,
            "font_size": title_font_size,
            "auto_size": auto_size,
        },
        alignment,
    )
    speaker_box = _box(
        raw.get("speaker_box"),
        {
            **DEFAULT_SPEAKER_BOX,
            "y": _position(raw.get("speaker_line_position"), DEFAULT_BOTTOM_POSITION)[1],
        },
        alignment,
    )

    return {
        "name": name,
        "font_choice": str(raw.get("font_choice") or AUTOMATIC_FONT_LABEL),
        "auto_size": auto_size,
        "title_font_size": title_font_size,
        "text_color": str(raw.get("text_color") or "#FFFFFF"),
        "background_choice": str(raw.get("background_choice") or GENERATED_BACKGROUND_LABEL),
        "title_position": _position(raw.get("title_position"), DEFAULT_TITLE_POSITION),
        "service_line_position": _position(
            raw.get("service_line_position"), DEFAULT_TOP_POSITION
        ),
        "speaker_line_position": _position(
            raw.get("speaker_line_position"), DEFAULT_BOTTOM_POSITION
        ),
        "service_line_box": service_line_box,
        "title_box": title_box,
        "speaker_box": speaker_box,
        "text_alignment": alignment,
        "shadow_enabled": bool(raw.get("shadow_enabled", True)),
        "show_service_line": bool(raw.get("show_service_line", True)),
        "show_layout_guides": bool(raw.get("show_layout_guides", False)),
        "selected_layout_area": raw.get("selected_layout_area")
        if raw.get("selected_layout_area") in {"Service Line", "Sermon Title", "Speaker"}
        else "Sermon Title",
        "skew_enabled": bool(raw.get("skew_enabled", True)),
    }


def settings_from_preset(preset: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_preset(preset)
    return {key: value for key, value in normalized.items() if key != "name"}


def _position(value: Any, fallback: tuple[int, int]) -> list[int]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [
            _int_in_range(value[0], 0, 1920),
            _int_in_range(value[1], 0, 1080),
        ]
    return [fallback[0], fallback[1]]


def _box(value: Any, fallback: dict[str, Any], alignment: str) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    return {
        "x": _int_in_range(raw.get("x", fallback["x"]), 0, 1920),
        "y": _int_in_range(raw.get("y", fallback["y"]), 0, 1080),
        "width": _int_in_range(raw.get("width", fallback["width"]), 50, 1920),
        "height": _int_in_range(raw.get("height", fallback["height"]), 30, 1080),
        "alignment": raw.get("alignment", fallback.get("alignment", alignment))
        if raw.get("alignment", fallback.get("alignment", alignment)) in ALIGNMENTS
        else alignment,
        "auto_size": bool(raw.get("auto_size", fallback.get("auto_size", True))),
        "font_size": _int_in_range(raw.get("font_size", fallback["font_size"]), 12, 260),
        "max_font_size": _int_in_range(
            raw.get("max_font_size", fallback.get("max_font_size", 260)), 12, MAX_TITLE_FONT_SIZE
        ),
        "line_spacing": _float_in_range(
            raw.get("line_spacing", fallback.get("line_spacing", 1.0)), 0.5, 2.0
        ),
        "skew_angle": clamp_skew_angle(
            raw.get("skew_angle", fallback.get("skew_angle", 0.0))
        ),
    }


def _int_in_range(value: Any, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _float_in_range(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "untitled_preset"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")
