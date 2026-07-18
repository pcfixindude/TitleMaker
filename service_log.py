from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from monark_schedule import (
    CSV_FIELDNAMES,
    entries_from_csv,
    entries_to_csv,
    entry_key,
    get_monark_service_entries,
    sort_service_entries,
)
from simple_presets import DATA_DIR, atomic_write_json, ensure_data_dir
from title_renderer import format_service_line, normalize_service_code, service_code


PROJECT_ROOT = Path(__file__).resolve().parent
SERVICE_LOG_PATH = DATA_DIR / "service_log.json"

# Friendly labels for the spreadsheet UI.
DISPLAY_COLUMNS = [
    ("date", "Date"),
    ("weekday", "Weekday"),
    ("service", "Service"),
    ("service_line", "Service Line"),
    ("title", "Sermon Title"),
    ("speaker", "Minister / Speaker"),
    ("notes", "Notes"),
    ("exported", "Exported"),
    ("exported_at", "Exported At"),
    ("exported_file", "Exported File"),
    ("include", "Include"),
]

EDITABLE_INTERNAL = {"title", "speaker", "notes", "include"}
READONLY_INTERNAL = {
    "date",
    "weekday",
    "service",
    "service_line",
    "exported",
    "exported_at",
    "exported_file",
}


def ensure_service_log_dir() -> None:
    ensure_data_dir()


def normalize_entry(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Migrate partial/old rows into a complete service-log entry."""
    data = dict(raw or {})
    entry_date = _as_date(data.get("date"))
    service = str(data.get("service") or "Morning")
    code = str(data.get("service_code") or service_code(service))
    weekday = str(data.get("weekday") or entry_date.strftime("%A"))
    rid = str(data.get("row_id") or f"{entry_date.isoformat()}_{code}")
    return {
        "row_id": rid,
        "date": entry_date,
        "weekday": weekday,
        "service": service,
        "service_code": code,
        "service_line": str(
            data.get("service_line")
            or format_service_line(weekday, service, entry_date)
        ),
        "title": str(data.get("title") or data.get("sermon_title") or ""),
        "speaker": str(data.get("speaker") or data.get("minister") or ""),
        "notes": str(data.get("notes") or ""),
        "exported": _as_bool(data.get("exported")),
        "exported_at": str(data.get("exported_at") or ""),
        "exported_file": str(data.get("exported_file") or ""),
        "include": _as_bool(data.get("include")),
    }


def normalize_entries(entries: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized = [normalize_entry(entry) for entry in (entries or [])]
    return sort_service_entries(normalized)


def generate_service_log(year: int) -> list[dict[str, Any]]:
    return normalize_entries(get_monark_service_entries(int(year)))


def load_service_log(
    path: Path | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Load service log. Returns (entries, warning)."""
    target = path or SERVICE_LOG_PATH
    if not target.exists():
        return [], None
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], "Service log was unreadable and was ignored."
    if isinstance(raw, dict):
        rows = raw.get("entries") or raw.get("rows") or []
    elif isinstance(raw, list):
        rows = raw
    else:
        return [], "Service log was invalid and was ignored."
    if not isinstance(rows, list):
        return [], "Service log was invalid and was ignored."
    try:
        return normalize_entries([row for row in rows if isinstance(row, dict)]), None
    except Exception:
        return [], "Service log could not be normalized and was ignored."


def save_service_log(
    entries: list[dict[str, Any]],
    path: Path | None = None,
    *,
    year: int | None = None,
) -> None:
    target = path or SERVICE_LOG_PATH
    ensure_service_log_dir()
    payload = {
        "version": 1,
        "year": year,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "entries": [_entry_to_json(entry) for entry in normalize_entries(entries)],
    }
    atomic_write_json(target, payload)


def archive_service_log(
    entries: list[dict[str, Any]],
    *,
    year: int | None = None,
) -> Path | None:
    if not entries:
        return None
    ensure_service_log_dir()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = DATA_DIR / f"service_log_archive_{stamp}.json"
    save_service_log(entries, path=archive_path, year=year)
    return archive_path


def export_service_log_csv(entries: list[dict[str, Any]]) -> str:
    return entries_to_csv(normalize_entries(entries))


def import_service_log_csv(csv_text: str) -> list[dict[str, Any]]:
    return normalize_entries(entries_from_csv(csv_text))


def entries_to_display_rows(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in normalize_entries(entries):
        rows.append(
            {
                "Date": _as_date(entry["date"]).isoformat(),
                "Weekday": entry["weekday"],
                "Service": entry["service"],
                "Service Line": entry["service_line"],
                "Sermon Title": entry["title"],
                "Minister / Speaker": entry["speaker"],
                "Notes": entry["notes"],
                "Exported": bool(entry["exported"]),
                "Exported At": entry["exported_at"],
                "Exported File": entry["exported_file"],
                "Include": bool(entry["include"]),
                "_row_id": entry_key(entry),
            }
        )
    return rows


def apply_display_edits(
    entries: list[dict[str, Any]],
    edited_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge editable spreadsheet columns back into the service log."""
    by_id = {entry_key(entry): dict(entry) for entry in normalize_entries(entries)}
    for row in edited_rows:
        rid = str(row.get("_row_id") or "")
        if not rid or rid not in by_id:
            # Fall back only with an explicit Service value (never default to Morning).
            try:
                service = row.get("Service")
                if not service:
                    continue
                d = _as_date(row.get("Date"))
                rid = f"{d.isoformat()}_{normalize_service_code(str(service))}"
            except Exception:
                continue
        if rid not in by_id:
            continue
        entry = by_id[rid]
        entry["title"] = str(row.get("Sermon Title") or "")
        entry["speaker"] = str(row.get("Minister / Speaker") or "")
        entry["notes"] = str(row.get("Notes") or "")
        entry["include"] = _as_bool(row.get("Include"))
        by_id[rid] = entry
    return sort_service_entries(list(by_id.values()))


def _entry_to_json(entry: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_entry(entry)
    return {
        **normalized,
        "date": _as_date(normalized["date"]).isoformat(),
    }


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return date.today()
    return date.fromisoformat(text[:10])


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
