from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from font_config import (
    DEFAULT_SERVICE_FONT_PATH,
    DEFAULT_SPEAKER_FONT_PATH,
    DEFAULT_TITLE_FONT_PATH,
    default_font_config_for_role,
    font_config_from_dict,
)
from font_discovery import (
    BARLOW_BOLD_ITALIC_NAME,
    BARLOW_BOLD_NAME,
    default_font_id_for_role,
)
from title_renderer import (
    DEFAULT_SERVICE_BOX,
    DEFAULT_SPEAKER_BOX,
    DEFAULT_TITLE_BOX,
    DEFAULT_TITLE_LINE_SPACING_PX,
    MAX_TITLE_FONT_SIZE,
    clamp_title_line_spacing,
)


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
PRESETS_PATH = DATA_DIR / "simple_presets.json"
DEFAULT_SETTINGS_PATH = DATA_DIR / "default_settings.json"
PRESET_SLOTS = (1, 2, 3, 4)

DEFAULT_FONT_SIZES = {
    "service": 86,
    "title": MAX_TITLE_FONT_SIZE,
    "speaker": 80,
}

DEFAULT_FONT_IDS = {
    "service_font_path": default_font_id_for_role("service"),
    "title_font_path": default_font_id_for_role("title"),
    "speaker_font_path": default_font_id_for_role("speaker"),
}


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON via a temp file, then replace the target (crash-safe)."""
    ensure_data_dir()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise


def get_factory_default_settings() -> dict[str, Any]:
    """Built-in hardcoded defaults used when no saved default exists."""
    service_cfg = default_font_config_for_role("service").to_dict()
    title_cfg = default_font_config_for_role("title").to_dict()
    speaker_cfg = default_font_config_for_role("speaker").to_dict()
    return normalize_preset_settings(
        {
            "name": "Factory Defaults",
            "service": {
                **DEFAULT_SERVICE_BOX,
                "font_size": DEFAULT_FONT_SIZES["service"],
                "auto_size": True,
            },
            "title": {
                **DEFAULT_TITLE_BOX,
                "font_size": DEFAULT_FONT_SIZES["title"],
                "auto_size": True,
            },
            "speaker": {
                **DEFAULT_SPEAKER_BOX,
                "font_size": DEFAULT_FONT_SIZES["speaker"],
                "auto_size": True,
            },
            "service_font_config": service_cfg,
            "title_font_config": title_cfg,
            "speaker_font_config": speaker_cfg,
            "service_font_path": service_cfg["font_path"],
            "title_font_path": title_cfg["font_path"],
            "speaker_font_path": speaker_cfg["font_path"],
            "title_line_spacing": DEFAULT_TITLE_LINE_SPACING_PX,
            "background_label": None,
            "show_bounding_boxes": True,
        }
    )


def normalize_preset_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    """Fill missing fields from factory defaults; never raise on partial data."""
    factory = {
        "name": "Preset",
        "service": {
            **DEFAULT_SERVICE_BOX,
            "font_size": DEFAULT_FONT_SIZES["service"],
            "auto_size": True,
        },
        "title": {
            **DEFAULT_TITLE_BOX,
            "font_size": DEFAULT_FONT_SIZES["title"],
            "auto_size": True,
        },
        "speaker": {
            **DEFAULT_SPEAKER_BOX,
            "font_size": DEFAULT_FONT_SIZES["speaker"],
            "auto_size": True,
        },
        "title_line_spacing": DEFAULT_TITLE_LINE_SPACING_PX,
        "background_label": None,
        "show_bounding_boxes": True,
    }
    raw = dict(settings or {})
    service_cfg = _preset_font_config(raw, "service")
    title_cfg = _preset_font_config(raw, "title")
    speaker_cfg = _preset_font_config(raw, "speaker")
    return {
        "name": str(raw.get("name") or factory["name"]),
        "service": _normalize_box(raw.get("service"), factory["service"]),
        "title": _normalize_box(raw.get("title"), factory["title"]),
        "speaker": _normalize_box(raw.get("speaker"), factory["speaker"]),
        "service_font_config": service_cfg,
        "title_font_config": title_cfg,
        "speaker_font_config": speaker_cfg,
        "service_font_path": str(
            service_cfg.get("font_path")
            or raw.get("service_font_path")
            or DEFAULT_FONT_IDS["service_font_path"]
            or DEFAULT_SERVICE_FONT_PATH
            or BARLOW_BOLD_NAME
        ),
        "title_font_path": str(
            title_cfg.get("font_path")
            or raw.get("title_font_path")
            or DEFAULT_FONT_IDS["title_font_path"]
            or DEFAULT_TITLE_FONT_PATH
            or BARLOW_BOLD_ITALIC_NAME
        ),
        "speaker_font_path": str(
            speaker_cfg.get("font_path")
            or raw.get("speaker_font_path")
            or DEFAULT_FONT_IDS["speaker_font_path"]
            or DEFAULT_SPEAKER_FONT_PATH
            or BARLOW_BOLD_NAME
        ),
        "background_label": raw.get("background_label"),
        "title_line_spacing": clamp_title_line_spacing(
            raw.get("title_line_spacing", factory["title_line_spacing"])
        ),
        "show_bounding_boxes": bool(
            raw["show_bounding_boxes"]
            if "show_bounding_boxes" in raw
            else factory["show_bounding_boxes"]
        ),
    }


def ensure_presets_file() -> None:
    ensure_data_dir()
    if not PRESETS_PATH.exists():
        atomic_write_json(PRESETS_PATH, _empty_store())


def load_simple_presets() -> dict[str, Any]:
    ensure_presets_file()
    try:
        raw = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_store()
    if not isinstance(raw, dict):
        return _empty_store()
    slots = raw.get("slots")
    if not isinstance(slots, dict):
        return _empty_store()
    cleaned = _empty_store()
    for slot in PRESET_SLOTS:
        key = str(slot)
        entry = slots.get(key)
        if isinstance(entry, dict) and _valid_preset(entry):
            cleaned["slots"][key] = normalize_preset_settings(entry)
    return cleaned


def save_simple_presets(presets: dict[str, Any]) -> None:
    store = _empty_store()
    slots = presets.get("slots") if isinstance(presets, dict) else None
    if isinstance(slots, dict):
        for slot in PRESET_SLOTS:
            key = str(slot)
            entry = slots.get(key)
            if isinstance(entry, dict) and _valid_preset(entry):
                store["slots"][key] = normalize_preset_settings(entry)
    atomic_write_json(PRESETS_PATH, store)


def save_preset_slot(
    slot_number: int,
    settings: dict[str, Any],
    name: str | None = None,
) -> dict[str, Any]:
    if slot_number not in PRESET_SLOTS:
        raise ValueError(f"Preset slot must be one of {PRESET_SLOTS}")
    payload = dict(settings)
    if name is not None:
        payload["name"] = name
    elif not payload.get("name"):
        payload["name"] = f"Preset {slot_number}"
    if not _valid_preset(payload):
        raise ValueError("Preset is missing required box fields")
    normalized = normalize_preset_settings(payload)
    store = load_simple_presets()
    store["slots"][str(slot_number)] = normalized
    save_simple_presets(store)
    return normalized


def load_preset_slot(slot_number: int) -> dict[str, Any] | None:
    if slot_number not in PRESET_SLOTS:
        return None
    store = load_simple_presets()
    entry = store["slots"].get(str(slot_number))
    return dict(entry) if isinstance(entry, dict) else None


def save_default_settings(settings: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_preset_settings(settings)
    normalized["name"] = str(settings.get("name") or "Startup Default")
    atomic_write_json(DEFAULT_SETTINGS_PATH, normalized)
    return normalized


def load_default_settings() -> tuple[dict[str, Any] | None, str | None]:
    """
    Load startup defaults.

    Returns (settings, warning). warning is set when the file exists but is invalid.
    """
    if not DEFAULT_SETTINGS_PATH.exists():
        return None, None
    try:
        raw = json.loads(DEFAULT_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "Saved default settings were unreadable and were ignored."
    if not isinstance(raw, dict) or not _valid_preset(raw):
        return None, "Saved default settings were invalid and were ignored."
    return normalize_preset_settings(raw), None


def delete_default_settings() -> bool:
    if not DEFAULT_SETTINGS_PATH.exists():
        return False
    try:
        DEFAULT_SETTINGS_PATH.unlink()
        return True
    except OSError:
        return False


def preset_slot_labels() -> dict[int, str]:
    store = load_simple_presets()
    labels: dict[int, str] = {}
    for slot in PRESET_SLOTS:
        entry = store["slots"].get(str(slot))
        if isinstance(entry, dict) and entry.get("name"):
            labels[slot] = str(entry["name"])
        elif isinstance(entry, dict):
            labels[slot] = f"Preset {slot}"
        else:
            labels[slot] = f"Empty {slot}"
    return labels


# Backward-compatible aliases used by older call sites / tests.
def load_preset_store() -> dict[str, Any]:
    return load_simple_presets()


def save_preset(slot: int, preset: dict[str, Any]) -> None:
    save_preset_slot(slot, preset, name=preset.get("name"))


def load_preset(slot: int) -> dict[str, Any] | None:
    return load_preset_slot(slot)


def _normalize_preset(entry: dict[str, Any]) -> dict[str, Any]:
    return normalize_preset_settings(entry)


def _empty_store() -> dict[str, Any]:
    return {"slots": {str(slot): None for slot in PRESET_SLOTS}}


def _valid_preset(entry: dict[str, Any]) -> bool:
    for key in ("service", "title", "speaker"):
        box = entry.get(key)
        if not isinstance(box, dict):
            return False
        for field in ("x", "y", "width", "height"):
            if field not in box:
                return False
    return True


def _normalize_box(raw: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    base = dict(fallback)
    if not isinstance(raw, dict):
        return base
    for field in ("x", "y", "width", "height", "font_size"):
        if field in raw and raw[field] is not None:
            try:
                base[field] = int(raw[field])
            except (TypeError, ValueError):
                pass
    if "auto_size" in raw:
        base["auto_size"] = bool(raw["auto_size"])
    base["width"] = max(1, int(base["width"]))
    base["height"] = max(1, int(base["height"]))
    return base


def _preset_font_config(entry: dict[str, Any], role: str) -> dict[str, Any]:
    key = f"{role}_font_config"
    if isinstance(entry.get(key), dict):
        return font_config_from_dict(entry[key], role=role).to_dict()
    legacy_path = entry.get(f"{role}_font_path")
    if legacy_path:
        return font_config_from_dict(str(legacy_path), role=role).to_dict()
    return default_font_config_for_role(role).to_dict()
