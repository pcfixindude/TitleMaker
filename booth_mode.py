from __future__ import annotations

from datetime import datetime
from typing import Any

from monark_schedule import entry_key, mark_entry_exported, update_entry_text


NO_SCHEDULE_MESSAGE = "Generate a Monark schedule first to use Booth Mode."
MAX_LABEL_DETAIL_LENGTH = 64


def build_booth_service_label(entry: dict[str, Any]) -> str:
    title = str(entry.get("title") or "").strip()
    speaker = str(entry.get("speaker") or "").strip()
    detail = _label_detail(title, speaker)

    if entry.get("exported"):
        status = "exported" if detail == "blank" else f"exported — {detail}"
    else:
        status = detail
    return f"{entry['service_line']} — {status}"


def booth_service_label(entry: dict[str, Any]) -> str:
    return build_booth_service_label(entry)


def booth_service_labels(entries: list[dict[str, Any]]) -> list[str]:
    return [build_booth_service_label(entry) for entry in entries]


def get_selected_service_row(
    entries: list[dict[str, Any]],
    index: int,
) -> dict[str, Any] | None:
    if not entries:
        return None
    bounded_index = max(0, min(index, len(entries) - 1))
    return entries[bounded_index]


def previous_service_index(current_index: int) -> int:
    return max(0, current_index - 1)


def next_service_index(current_index: int, total_entries: int) -> int:
    if total_entries <= 0:
        return 0
    return min(total_entries - 1, current_index + 1)


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


def update_selected_service_row(
    entries: list[dict[str, Any]],
    selected_key: str,
    title: str,
    speaker: str,
    notes: str = "",
) -> list[dict[str, Any]]:
    return update_booth_entry(entries, selected_key, title, speaker, notes)


def mark_booth_exported(
    entries: list[dict[str, Any]],
    selected_key: str,
    exported_at: datetime | None = None,
) -> list[dict[str, Any]]:
    return mark_entry_exported(entries, selected_key, exported_at)


def _label_detail(title: str, speaker: str) -> str:
    if title and speaker:
        return _truncate_label_detail(f"{title} / {speaker}")
    if title:
        return _truncate_label_detail(title)
    if speaker:
        return _truncate_label_detail(speaker)
    return "blank"


def _truncate_label_detail(value: str) -> str:
    if len(value) <= MAX_LABEL_DETAIL_LENGTH:
        return value
    return value[: MAX_LABEL_DETAIL_LENGTH - 3].rstrip() + "..."
