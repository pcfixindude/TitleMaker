from __future__ import annotations

import json
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


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
PRESETS_PATH = DATA_DIR / "simple_presets.json"
PRESET_SLOTS = (1, 2, 3, 4)

DEFAULT_FONT_IDS = {
    "service_font_path": default_font_id_for_role("service"),
    "title_font_path": default_font_id_for_role("title"),
    "speaker_font_path": default_font_id_for_role("speaker"),
}


def ensure_presets_file() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not PRESETS_PATH.exists():
        PRESETS_PATH.write_text(json.dumps(_empty_store(), indent=2) + "\n", encoding="utf-8")


def load_preset_store() -> dict[str, Any]:
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
            cleaned["slots"][key] = _normalize_preset(entry)
    return cleaned


def save_preset(slot: int, preset: dict[str, Any]) -> None:
    if slot not in PRESET_SLOTS:
        raise ValueError(f"Preset slot must be one of {PRESET_SLOTS}")
    if not _valid_preset(preset):
        raise ValueError("Preset is missing required box fields")
    store = load_preset_store()
    store["slots"][str(slot)] = _normalize_preset(preset)
    ensure_presets_file()
    PRESETS_PATH.write_text(json.dumps(store, indent=2) + "\n", encoding="utf-8")


def load_preset(slot: int) -> dict[str, Any] | None:
    if slot not in PRESET_SLOTS:
        return None
    store = load_preset_store()
    entry = store["slots"].get(str(slot))
    return dict(entry) if isinstance(entry, dict) else None


def preset_slot_labels() -> dict[int, str]:
    store = load_preset_store()
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


def _normalize_preset(entry: dict[str, Any]) -> dict[str, Any]:
    service_cfg = _preset_font_config(entry, "service")
    title_cfg = _preset_font_config(entry, "title")
    speaker_cfg = _preset_font_config(entry, "speaker")
    return {
        "name": str(entry.get("name") or "Preset"),
        "service": dict(entry["service"]),
        "title": dict(entry["title"]),
        "speaker": dict(entry["speaker"]),
        "service_font_config": service_cfg,
        "title_font_config": title_cfg,
        "speaker_font_config": speaker_cfg,
        # Legacy path fields kept for older readers / tests.
        "service_font_path": str(
            service_cfg.get("font_path")
            or entry.get("service_font_path")
            or DEFAULT_FONT_IDS["service_font_path"]
            or DEFAULT_SERVICE_FONT_PATH
            or BARLOW_BOLD_NAME
        ),
        "title_font_path": str(
            title_cfg.get("font_path")
            or entry.get("title_font_path")
            or DEFAULT_FONT_IDS["title_font_path"]
            or DEFAULT_TITLE_FONT_PATH
            or BARLOW_BOLD_ITALIC_NAME
        ),
        "speaker_font_path": str(
            speaker_cfg.get("font_path")
            or entry.get("speaker_font_path")
            or DEFAULT_FONT_IDS["speaker_font_path"]
            or DEFAULT_SPEAKER_FONT_PATH
            or BARLOW_BOLD_NAME
        ),
        "background_label": entry.get("background_label"),
    }


def _preset_font_config(entry: dict[str, Any], role: str) -> dict[str, Any]:
    key = f"{role}_font_config"
    if isinstance(entry.get(key), dict):
        return font_config_from_dict(entry[key], role=role).to_dict()
    # Migrate legacy path-only presets.
    legacy_path = entry.get(f"{role}_font_path")
    if legacy_path:
        return font_config_from_dict(str(legacy_path), role=role).to_dict()
    return default_font_config_for_role(role).to_dict()
