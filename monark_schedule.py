from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta
from io import StringIO
from typing import Any

from title_renderer import format_service_line, service_code


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
                }
            )
    return entries


def entry_key(entry: dict[str, Any]) -> str:
    entry_date = _coerce_date(entry["date"])
    return f"{entry_date.isoformat()}|{entry['service_code']}"


def update_entry_text(
    entries: list[dict[str, Any]],
    selected_key: str,
    title: str,
    speaker: str,
) -> list[dict[str, Any]]:
    for entry in entries:
        if entry_key(entry) == selected_key:
            entry["title"] = title
            entry["speaker"] = speaker
            break
    return entries


def mark_entry_exported(
    entries: list[dict[str, Any]],
    selected_key: str,
    exported_at: datetime | None = None,
) -> list[dict[str, Any]]:
    timestamp = (exported_at or datetime.now()).isoformat(timespec="seconds")
    for entry in entries:
        if entry_key(entry) == selected_key:
            entry["exported"] = True
            entry["exported_at"] = timestamp
            break
    return entries


def find_current_service_entry(
    entries: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any] | None:
    current = now or datetime.now()
    service = service_for_time(current.time())
    code = service_code(service)

    for entry in entries:
        if _coerce_date(entry["date"]) == current.date() and entry["service_code"] == code:
            return entry
    return None


def service_for_time(value: time) -> str:
    if value < time(12, 0):
        return "Morning"
    if value < time(17, 0):
        return "Afternoon"
    return "Evening"


def entries_to_csv(entries: list[dict[str, Any]]) -> str:
    output = StringIO()
    fieldnames = [
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
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for entry in entries:
        row = {field: entry.get(field, "") for field in fieldnames}
        row["date"] = _coerce_date(row["date"]).isoformat()
        writer.writerow(row)
    return output.getvalue()


def entries_from_csv(csv_text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(StringIO(csv_text))
    entries: list[dict[str, Any]] = []
    for row in reader:
        entry_date = _coerce_date(row.get("date", ""))
        service = row.get("service") or "Morning"
        weekday = row.get("weekday") or entry_date.strftime("%A")
        entry = {
            "include": _coerce_bool(row.get("include")),
            "date": entry_date,
            "weekday": weekday,
            "service": service,
            "service_code": row.get("service_code") or service_code(service),
            "service_line": row.get("service_line")
            or format_service_line(weekday, service, entry_date),
            "title": row.get("title") or "",
            "speaker": row.get("speaker") or "",
            "notes": row.get("notes") or "",
            "exported": _coerce_bool(row.get("exported")),
            "exported_at": row.get("exported_at") or "",
        }
        entries.append(entry)
    return entries


def batch_export_candidates(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        entry
        for entry in entries
        if entry.get("include") or entry.get("title") or entry.get("speaker")
    ]


def _coerce_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
