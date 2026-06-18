from __future__ import annotations

from datetime import datetime
from typing import Any

from monark_schedule import entry_key, mark_entry_exported, update_entry_text


NO_SCHEDULE_MESSAGE = "Generate a Monark schedule first to use Booth Mode."


def booth_service_label(entry: dict[str, Any]) -> str:
    title = str(entry.get("title") or "").strip()
    speaker = str(entry.get("speaker") or "").strip()
    if entry.get("exported"):
        status = "exported"
    elif title or speaker:
        status = f"{title or 'blank'} / {speaker or 'blank'}"
    else:
        status = "blank"
    return f"{entry['service_line']} — {status}"


def booth_service_labels(entries: list[dict[str, Any]]) -> list[str]:
    return [booth_service_label(entry) for entry in entries]


def selected_entry_by_key(
    entries: list[dict[str, Any]],
    selected_key: str,
) -> dict[str, Any] | None:
    for entry in entries:
        if entry_key(entry) == selected_key:
            return entry
    return None


def load_entry_values(entry: dict[str, Any]) -> dict[str, str]:
    return {
        "selected_key": entry_key(entry),
        "title": entry.get("title", ""),
        "speaker": entry.get("speaker", ""),
        "notes": entry.get("notes", ""),
    }


def update_booth_entry(
    entries: list[dict[str, Any]],
    selected_key: str,
    title: str,
    speaker: str,
    notes: str = "",
) -> list[dict[str, Any]]:
    update_entry_text(entries, selected_key, title, speaker)
    for entry in entries:
        if entry_key(entry) == selected_key:
            entry["notes"] = notes
            break
    return entries


def mark_booth_exported(
    entries: list[dict[str, Any]],
    selected_key: str,
    exported_at: datetime | None = None,
) -> list[dict[str, Any]]:
    return mark_entry_exported(entries, selected_key, exported_at)
