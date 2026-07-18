from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta
from io import StringIO
from typing import Any

from title_renderer import format_service_line, normalize_service_code, service_code


SERVICES = ["Morning", "Afternoon", "Evening"]


def get_monark_start_date(year: int) -> date:
    current = date(year, 7, 31)
    while current.weekday() != 4:
        current -= timedelta(days=1)
    return current


def get_monark_schedule_dates(year: int) -> list[date]:
    start_date = get_monark_start_date(year)
    return [start_date + timedelta(days=offset) for offset in range(10)]


def get_monark_service_entries(year: int) -> list[dict]:
    entries: list[dict] = []
    for service_date in get_monark_schedule_dates(year):
        weekday = service_date.strftime("%A")
        for service in SERVICES:
            code = service_code(service)
            entries.append(
                {
                    "row_id": row_id(service_date, code),
                    "include": False,
                    "date": service_date,
                    "weekday": weekday,
                    "service": service,
                    "service_code": code,
                    "service_line": format_service_line(
                        weekday, service, service_date
                    ),
                    "title": "",
                    "speaker": "",
                    "notes": "",
                    "exported": False,
                    "exported_at": "",
                    "exported_file": "",
                }
            )
    return entries


def entry_key(entry: dict[str, Any]) -> str:
    if entry.get("row_id"):
        return str(entry["row_id"])
    entry_date = _coerce_date(entry["date"])
    return row_id(entry_date, entry["service_code"])


def row_id(service_date: date, code: str) -> str:
    return f"{service_date.isoformat()}_{code}"


def update_entry_text(
    entries: list[dict[str, Any]],
    selected_key: str,
    title: str,
    speaker: str,
    notes: str | None = None,
) -> list[dict[str, Any]]:
    for entry in entries:
        if entry_key(entry) == selected_key:
            entry["title"] = title
            entry["speaker"] = speaker
            if notes is not None:
                entry["notes"] = notes
            break
    return entries


def mark_entry_exported(
    entries: list[dict[str, Any]],
    selected_key: str,
    exported_at: datetime | None = None,
    exported_file: str = "",
) -> list[dict[str, Any]]:
    mark_service_exported(
        entries,
        selected_key,
        exported_file=exported_file,
        exported_at=exported_at,
    )
    return entries


def mark_service_exported(
    entries: list[dict[str, Any]],
    selected_row_id: str | None,
    exported_file: str = "",
    exported_at: datetime | None = None,
) -> bool:
    """
    Mark exactly one service-log row exported by exact row_id match.

    Returns True if a matching row was updated. Never falls back to another
    row for the same date/weekday.
    """
    if not selected_row_id:
        return False
    timestamp = (exported_at or datetime.now()).isoformat(timespec="seconds")
    for entry in entries:
        if entry_key(entry) == selected_row_id:
            entry["exported"] = True
            entry["exported_at"] = timestamp
            entry["exported_file"] = exported_file
            return True
    return False


def find_entry_by_row_id(
    entries: list[dict[str, Any]], row_id_value: str | None
) -> dict[str, Any] | None:
    if not row_id_value:
        return None
    for entry in entries:
        if entry_key(entry) == row_id_value:
            return entry
    return None


def get_service_entry_by_row_id(
    entries: list[dict[str, Any]], row_id_value: str | None
) -> dict[str, Any] | None:
    """Alias for find_entry_by_row_id — row_id is the only lookup key."""
    return find_entry_by_row_id(entries, row_id_value)


def find_entry_index(
    entries: list[dict[str, Any]], row_id_value: str | None
) -> int | None:
    if not row_id_value:
        return None
    for index, entry in enumerate(entries):
        if entry_key(entry) == row_id_value:
            return index
    return None


def adjacent_entry(
    entries: list[dict[str, Any]],
    row_id_value: str | None,
    *,
    step: int,
) -> dict[str, Any] | None:
    if not entries:
        return None
    index = find_entry_index(entries, row_id_value)
    if index is None:
        return entries[0] if step >= 0 else entries[-1]
    next_index = index + step
    if next_index < 0 or next_index >= len(entries):
        return None
    return entries[next_index]


def service_option_label(entry: dict[str, Any]) -> str:
    line = str(entry.get("service_line") or "")
    if entry.get("exported"):
        suffix = "exported"
    elif str(entry.get("title") or "").strip():
        suffix = "title entered"
    else:
        suffix = "blank"
    return f"{line} — {suffix}"


def find_current_service_entry(
    entries: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any] | None:
    current = now or datetime.now()
    service = service_for_time(current.time())
    code = normalize_service_code(service)

    for entry in entries:
        entry_code = normalize_service_code(
            str(entry.get("service_code") or entry.get("service") or "")
        )
        if _coerce_date(entry["date"]) == current.date() and entry_code == code:
            return entry
    return None


def service_for_time(value: time) -> str:
    if value < time(12, 0):
        return "Morning"
    if value < time(17, 0):
        return "Afternoon"
    return "Evening"


CSV_FIELDNAMES = [
    "row_id",
    "include",
    "date",
    "weekday",
    "service",
    "service_code",
    "service_line",
    "title",
    "speaker",
    "notes",
    "exported",
    "exported_at",
    "exported_file",
]


def entries_to_csv(entries: list[dict[str, Any]]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDNAMES)
    writer.writeheader()
    for entry in entries:
        row = {field: entry.get(field, "") for field in CSV_FIELDNAMES}
        row["row_id"] = entry_key(entry)
        row["date"] = _coerce_date(row["date"]).isoformat()
        row["include"] = bool(entry.get("include"))
        row["exported"] = bool(entry.get("exported"))
        writer.writerow(row)
    return output.getvalue()


def entries_from_csv(csv_text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(StringIO(csv_text))
    entries: list[dict[str, Any]] = []
    for row in reader:
        entry_date = _coerce_date(row.get("date", ""))
        service = row.get("service") or "Morning"
        # Accept friendly CSV headers as aliases.
        title = row.get("title") or row.get("Sermon Title") or ""
        speaker = row.get("speaker") or row.get("Minister / Speaker") or ""
        notes = row.get("notes") or row.get("Notes") or ""
        weekday = row.get("weekday") or row.get("Weekday") or entry_date.strftime("%A")
        code = row.get("service_code") or service_code(service)
        entry = {
            "row_id": row.get("row_id") or row_id(entry_date, code),
            "include": _coerce_bool(row.get("include") if "include" in row else row.get("Include")),
            "date": entry_date,
            "weekday": weekday,
            "service": service,
            "service_code": code,
            "service_line": row.get("service_line")
            or row.get("Service Line")
            or format_service_line(weekday, service, entry_date),
            "title": title,
            "speaker": speaker,
            "notes": notes,
            "exported": _coerce_bool(
                row.get("exported") if "exported" in row else row.get("Exported")
            ),
            "exported_at": row.get("exported_at") or row.get("Exported At") or "",
            "exported_file": row.get("exported_file") or row.get("Exported File") or "",
        }
        entries.append(entry)
    return sort_service_entries(entries)


def sort_service_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {"AM": 0, "AFT": 1, "PM": 2}

    def sort_key(entry: dict[str, Any]) -> tuple:
        code = str(entry.get("service_code") or service_code(str(entry.get("service") or "")))
        return (_coerce_date(entry["date"]), order.get(code, 99), code)

    return sorted(entries, key=sort_key)


def batch_export_candidates(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        entry
        for entry in entries
        if entry.get("include") or entry.get("title") or entry.get("speaker")
    ]


def _coerce_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return date.today()
    return date.fromisoformat(text[:10])


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
