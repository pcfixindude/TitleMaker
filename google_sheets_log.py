"""Shared Google Sheets service-log backend (one service account for all users)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from service_log import normalize_entries, normalize_entry
from title_renderer import service_code

SHEET_HEADERS = [
    "row_id",
    "date",
    "weekday",
    "service",
    "service_line",
    "sermon_title",
    "speaker",
    "notes",
    "exported",
    "exported_at",
    "exported_file",
    "include",
    "updated_at",
    "updated_by",
]

STORAGE_LOCAL = "Local JSON"
STORAGE_GOOGLE = "Google Sheets"
STORAGE_OPTIONS = (STORAGE_LOCAL, STORAGE_GOOGLE)


def _read_secrets(secrets: Any | None = None) -> Any:
    if secrets is not None:
        return secrets
    try:
        import streamlit as st

        return st.secrets
    except Exception:
        return {}


def _secret_mapping(section: Any) -> dict[str, Any]:
    if section is None:
        return {}
    if isinstance(section, dict):
        return dict(section)
    try:
        return dict(section)
    except Exception:
        return {}


def is_google_sheets_configured(secrets: Any | None = None) -> bool:
    """True when Streamlit secrets include a usable service account + sheet id."""
    raw = _read_secrets(secrets)
    try:
        gcp = _secret_mapping(raw.get("gcp_service_account"))  # type: ignore[union-attr]
        sheets = _secret_mapping(raw.get("google_sheets"))  # type: ignore[union-attr]
    except Exception:
        return False
    email = str(gcp.get("client_email") or "").strip()
    key = str(gcp.get("private_key") or "").strip()
    sheet_id = str(sheets.get("sheet_id") or "").strip()
    return bool(email and key and sheet_id and "BEGIN PRIVATE KEY" in key)


def default_storage_mode(secrets: Any | None = None) -> str:
    """Prefer Google Sheets when configured; otherwise Local JSON."""
    if is_google_sheets_configured(secrets):
        return STORAGE_GOOGLE
    return STORAGE_LOCAL


def get_google_sheets_client(secrets: Any | None = None):
    """Authorize a gspread client from service-account secrets."""
    if not is_google_sheets_configured(secrets):
        raise RuntimeError(
            "Google Sheets is not configured. Add gcp_service_account and "
            "google_sheets secrets, and share the Sheet with the service account."
        )
    raw = _read_secrets(secrets)
    gcp = _secret_mapping(raw["gcp_service_account"])  # type: ignore[index]
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_info(gcp, scopes=scopes)
    return gspread.authorize(credentials)


def open_service_log_sheet(secrets: Any | None = None, client=None):
    """Open the configured worksheet (creates it if missing)."""
    raw = _read_secrets(secrets)
    sheets = _secret_mapping(raw["google_sheets"])  # type: ignore[index]
    sheet_id = str(sheets.get("sheet_id") or "").strip()
    worksheet_name = str(sheets.get("worksheet_name") or "Service Log").strip()
    if not sheet_id:
        raise RuntimeError("google_sheets.sheet_id is missing from secrets.")

    gc = client or get_google_sheets_client(secrets)
    spreadsheet = gc.open_by_key(sheet_id)
    try:
        return spreadsheet.worksheet(worksheet_name)
    except Exception:
        return spreadsheet.add_worksheet(
            title=worksheet_name, rows=100, cols=len(SHEET_HEADERS)
        )


def ensure_headers(worksheet) -> None:
    """Ensure the first row matches SHEET_HEADERS."""
    try:
        current = worksheet.row_values(1)
    except Exception:
        current = []
    if current[: len(SHEET_HEADERS)] == SHEET_HEADERS:
        return
    if not current:
        worksheet.append_row(SHEET_HEADERS, value_input_option="RAW")
        return
    end_col = _column_letter(len(SHEET_HEADERS))
    worksheet.update(f"A1:{end_col}1", [SHEET_HEADERS], value_input_option="RAW")


def normalize_sheet_row(row: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize a sheet/API dict into an internal service-log entry."""
    data = dict(row or {})
    # Accept sheet column sermon_title as title.
    if "sermon_title" in data and not data.get("title"):
        data["title"] = data.get("sermon_title")
    if "service" in data and not data.get("service_code"):
        data["service_code"] = service_code(str(data.get("service") or ""))
    normalized = normalize_entry(data)
    normalized["updated_at"] = str(data.get("updated_at") or normalized.get("updated_at") or "")
    normalized["updated_by"] = str(data.get("updated_by") or normalized.get("updated_by") or "")
    return normalized


def sheet_record_to_row(record: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_sheet_row(record)


def row_to_sheet_record(
    row: dict[str, Any],
    *,
    updated_by: str | None = None,
    updated_at: datetime | None = None,
) -> dict[str, str]:
    """Convert an internal entry into a Google Sheet record (string cells)."""
    entry = normalize_sheet_row(row)
    stamp = (updated_at or datetime.now()).isoformat(timespec="seconds")
    operator = (
        updated_by
        if updated_by is not None
        else str(entry.get("updated_by") or "")
    )
    if updated_by is not None or not entry.get("updated_at"):
        entry["updated_at"] = stamp
    if updated_by is not None:
        entry["updated_by"] = operator
    entry_date = entry["date"]
    if isinstance(entry_date, datetime):
        date_text = entry_date.date().isoformat()
    elif isinstance(entry_date, date):
        date_text = entry_date.isoformat()
    else:
        date_text = str(entry_date)[:10]
    return {
        "row_id": str(entry.get("row_id") or ""),
        "date": date_text,
        "weekday": str(entry.get("weekday") or ""),
        "service": str(entry.get("service") or ""),
        "service_line": str(entry.get("service_line") or ""),
        "sermon_title": str(entry.get("title") or ""),
        "speaker": str(entry.get("speaker") or ""),
        "notes": str(entry.get("notes") or ""),
        "exported": "TRUE" if entry.get("exported") else "FALSE",
        "exported_at": str(entry.get("exported_at") or ""),
        "exported_file": str(entry.get("exported_file") or ""),
        "include": "TRUE" if entry.get("include") else "FALSE",
        "updated_at": str(entry.get("updated_at") or stamp),
        "updated_by": str(entry.get("updated_by") or operator),
    }


def load_service_log_from_google_sheet(
    secrets: Any | None = None,
    worksheet=None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Load all service-log rows from Google Sheets."""
    try:
        ws = worksheet or open_service_log_sheet(secrets)
        ensure_headers(ws)
        records = ws.get_all_records()
        rows = [
            sheet_record_to_row(record)
            for record in records
            if str(record.get("row_id") or "").strip()
            or str(record.get("date") or "").strip()
        ]
        return normalize_entries(rows), None
    except Exception as exc:
        return [], f"Could not load Google Sheet service log: {exc}"


def save_full_service_log_to_google_sheet(
    rows: list[dict[str, Any]],
    *,
    updated_by: str = "",
    secrets: Any | None = None,
    worksheet=None,
) -> list[dict[str, Any]]:
    """Replace worksheet contents with the given service-log rows."""
    ws = worksheet or open_service_log_sheet(secrets)
    ws.clear()
    ws.append_row(SHEET_HEADERS, value_input_option="RAW")
    saved: list[dict[str, Any]] = []
    stamp = datetime.now()
    for row in normalize_entries(rows):
        record = row_to_sheet_record(row, updated_by=updated_by, updated_at=stamp)
        ws.append_row(
            [record[header] for header in SHEET_HEADERS],
            value_input_option="RAW",
        )
        saved.append(sheet_record_to_row(record))
    return normalize_entries(saved)


def upsert_service_log_row(
    row: dict[str, Any],
    *,
    updated_by: str = "",
    secrets: Any | None = None,
    worksheet=None,
) -> dict[str, Any]:
    """
    Insert or update exactly one row matched by row_id.

    Never falls back to date-only matching.
    """
    ws = worksheet or open_service_log_sheet(secrets)
    ensure_headers(ws)
    record = row_to_sheet_record(row, updated_by=updated_by)
    target_id = str(record.get("row_id") or "").strip()
    if not target_id:
        raise ValueError("Cannot upsert a service-log row without row_id.")

    values = [record[header] for header in SHEET_HEADERS]
    end_col = _column_letter(len(SHEET_HEADERS))
    existing_records = ws.get_all_records()
    for index, existing in enumerate(existing_records):
        existing_id = str(existing.get("row_id") or "").strip()
        if existing_id == target_id:
            sheet_row = index + 2  # header is row 1
            ws.update(
                f"A{sheet_row}:{end_col}{sheet_row}",
                [values],
                value_input_option="RAW",
            )
            return sheet_record_to_row(record)

    ws.append_row(values, value_input_option="RAW")
    return sheet_record_to_row(record)


def _column_letter(index: int) -> str:
    """1-based column index → A, B, … Z, AA, …"""
    result = ""
    n = index
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result or "A"
