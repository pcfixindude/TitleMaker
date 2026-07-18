from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta
from io import StringIO
from typing import Any

from title_renderer import format_service_line, normalize_service_code, service_code


SERVICES = ["Morning", "Afternoon", "Evening"]

# Service start times (local). Titles are usually created after the service starts.
SERVICE_START_AM = time(10, 0)
SERVICE_START_AFT = time(14, 0)
SERVICE_START_PM = time(19, 30)


def get_third_friday_of_july(year: int) -> date:
    """
    Return the third Friday of July for the given year.

    July 1 → first Friday on or after that day → add 14 days.
    """
    july_first = date(year, 7, 1)
    # Monday=0 … Friday=4
    days_until_friday = (4 - july_first.weekday()) % 7
    first_friday = july_first + timedelta(days=days_until_friday)
    return first_friday + timedelta(days=14)


def get_monark_start_date(year: int) -> date:
    """Monark meeting starts on the third Friday of July."""
    return get_third_friday_of_july(year)


def get_monark_schedule_dates(year: int) -> list[date]:
    """
    Return the 10 Monark meeting dates for a year.

    Day 1 = third Friday of July; day 10 = Sunday nine days later.
    Do not compute “second Sunday” separately — range(10) from Friday is enough.
    """
    start = get_third_friday_of_july(year)
    return [start + timedelta(days=i) for i in range(10)]


def get_monark_service_entries(year: int) -> list[dict]:
    """Build 30 service rows: 10 days × AM / AFT / PM."""
    entries: list[dict] = []
    for service_date in get_monark_schedule_dates(year):
        weekday = service_date.strftime("%A")
        for service in SERVICES:  # Morning, Afternoon, Evening → AM, AFT, PM
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


def service_log_schedule_warning(
    entries: list[dict[str, Any]],
    year: int | None = None,
) -> str | None:
    """
    Warn when a saved log does not start on the third Friday for its year.

    Old logs (e.g. last-Friday-of-July) must be regenerated deliberately.
    """
    if not entries:
        return None
    first = entries[0]
    first_date = _coerce_date(first.get("date"))
    check_year = int(year or first_date.year)
    expected_start = get_third_friday_of_july(check_year)
    if first_date == expected_start and len(entries) == 30:
        return None
    expected_end = expected_start + timedelta(days=9)
    return (
        f"This service log does not match the Monark schedule for {check_year}. "
        f"Expected start {expected_start.isoformat()} (third Friday) through "
        f"{expected_end.isoformat()} (10 days, Sunday night), 30 rows. "
        f"Found start {first_date.isoformat()} with {len(entries)} rows. "
        "Check “Replace existing…” and click Regenerate Monark Service Log."
    )


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


def suggest_current_service_code(now_datetime: datetime | None = None) -> str:
    """
    Suggest AM / AFT / PM from the most recent service start time.

    AM 10:00, AFT 2:00, PM 7:30. Before 10:00 AM defaults to AM (upcoming Morning).
    """
    current = now_datetime or datetime.now()
    clock = current.time() if isinstance(current, datetime) else current
    if clock < SERVICE_START_AFT:
        return "AM"
    if clock < SERVICE_START_PM:
        return "AFT"
    return "PM"


def find_current_service_entry(
    entries: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any] | None:
    current = now or datetime.now()
    code = suggest_current_service_code(current)

    for entry in entries:
        entry_code = normalize_service_code(
            str(entry.get("service_code") or entry.get("service") or "")
        )
        if _coerce_date(entry["date"]) == current.date() and entry_code == code:
            return entry
    return None


def service_for_time(value: time) -> str:
    code = suggest_current_service_code(datetime.combine(date.today(), value))
    return {"AM": "Morning", "AFT": "Afternoon", "PM": "Evening"}[code]


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
