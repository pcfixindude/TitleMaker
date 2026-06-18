from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from title_renderer import PROJECT_ROOT, format_service_line, service_code


DATA_DIR = PROJECT_ROOT / "data"
SERVICE_LOG_PATH = DATA_DIR / "service_log.json"
SETTINGS_PATH = DATA_DIR / "settings.json"


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_service_log(
    entries: list[dict[str, Any]],
    year: int | None = None,
    path: Path = SERVICE_LOG_PATH,
) -> None:
    ensure_data_dir()
    payload = {
        "year": year or infer_log_year(entries),
        "rows": [_serialize_entry(entry) for entry in entries],
    }
    _atomic_write_json(path, payload)


def load_service_log(path: Path = SERVICE_LOG_PATH) -> dict[str, Any] | None:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return None

    rows = payload.get("rows")
    if not isinstance(rows, list):
        return None

    entries = [_normalize_entry(row) for row in rows if isinstance(row, dict)]
    return {
        "year": int(payload.get("year") or infer_log_year(entries)),
        "rows": entries,
    }


def archive_service_log(
    entries: list[dict[str, Any]],
    year: int | None = None,
) -> Path:
    archive_year = year or infer_log_year(entries)
    archive_path = DATA_DIR / f"service_log_{archive_year}.json"
    save_service_log(entries, archive_year, archive_path)
    return archive_path


def infer_log_year(entries: list[dict[str, Any]]) -> int:
    if entries:
        entry_date = entries[0].get("date")
        if isinstance(entry_date, date):
            return entry_date.year
        return date.fromisoformat(str(entry_date)).year
    return date.today().year


def can_replace_log(
    existing_year: int | None,
    requested_year: int,
    confirmed: bool,
) -> bool:
    return confirmed or existing_year in (None, requested_year)


def save_settings(settings: dict[str, Any], path: Path = SETTINGS_PATH) -> None:
    ensure_data_dir()
    _atomic_write_json(path, settings)


def load_settings(path: Path = SETTINGS_PATH) -> dict[str, Any] | None:
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else None


def _serialize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    entry_date = entry.get("date")
    if isinstance(entry_date, date):
        date_value = entry_date.isoformat()
    else:
        date_value = str(entry_date)

    return {
        "include": bool(entry.get("include")),
        "date": date_value,
        "weekday": entry.get("weekday", ""),
        "service": entry.get("service", ""),
        "service_code": entry.get("service_code", ""),
        "service_line": entry.get("service_line", ""),
        "title": entry.get("title", ""),
        "speaker": entry.get("speaker", ""),
        "notes": entry.get("notes", ""),
        "exported": bool(entry.get("exported")),
        "exported_at": entry.get("exported_at", ""),
    }


def _normalize_entry(row: dict[str, Any]) -> dict[str, Any]:
    entry_date = date.fromisoformat(str(row["date"]))
    service = row.get("service") or "Morning"
    weekday = row.get("weekday") or entry_date.strftime("%A")
    code = row.get("service_code") or service_code(service)
    return {
        "include": bool(row.get("include")),
        "date": entry_date,
        "weekday": weekday,
        "service": service,
        "service_code": code,
        "service_line": row.get("service_line")
        or format_service_line(weekday, service, entry_date),
        "title": row.get("title", ""),
        "speaker": row.get("speaker", ""),
        "notes": row.get("notes", ""),
        "exported": bool(row.get("exported")),
        "exported_at": row.get("exported_at", ""),
    }


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2) + "\n")
    os.replace(temp_path, path)
