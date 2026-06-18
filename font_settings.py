from __future__ import annotations

from typing import Any


AUTOMATIC_FONT_LABEL = "Automatic fallback (Bebas Neue/system)"


def default_font_settings(base_font: str = AUTOMATIC_FONT_LABEL) -> dict[str, Any]:
    return {
        "service_font": base_font,
        "title_font": base_font,
        "speaker_font": base_font,
        "title_font_matches_service_font": True,
        "speaker_font_matches_service_font": True,
    }


def migrate_font_settings(raw: dict[str, Any]) -> dict[str, Any]:
    base_font = raw.get("service_font") or raw.get("font_choice") or raw.get("font_label") or AUTOMATIC_FONT_LABEL
    settings = default_font_settings(str(base_font))
    settings.update(
        {
            "service_font": str(raw.get("service_font") or base_font),
            "title_font": str(raw.get("title_font") or base_font),
            "speaker_font": str(raw.get("speaker_font") or base_font),
            "title_font_matches_service_font": bool(
                raw.get("title_font_matches_service_font", True)
            ),
            "speaker_font_matches_service_font": bool(
                raw.get("speaker_font_matches_service_font", True)
            ),
        }
    )
    return settings


def get_effective_service_font(settings: dict[str, Any]) -> str:
    return migrate_font_settings(settings)["service_font"]


def get_effective_title_font(settings: dict[str, Any]) -> str:
    migrated = migrate_font_settings(settings)
    if migrated["title_font_matches_service_font"]:
        return migrated["service_font"]
    return migrated["title_font"]


def get_effective_speaker_font(settings: dict[str, Any]) -> str:
    migrated = migrate_font_settings(settings)
    if migrated["speaker_font_matches_service_font"]:
        return migrated["service_font"]
    return migrated["speaker_font"]
