from __future__ import annotations

import unittest
from datetime import date
from unittest import mock

from google_sheets_log import (
    SHEET_HEADERS,
    STORAGE_GOOGLE,
    STORAGE_LOCAL,
    default_storage_mode,
    is_google_sheets_configured,
    load_service_log_from_google_sheet,
    normalize_sheet_row,
    row_to_sheet_record,
    save_full_service_log_to_google_sheet,
    sheet_record_to_row,
    upsert_service_log_row,
)
from service_log import (
    generate_service_log,
    load_service_log_for_storage,
    persist_service_log_entries,
)


class _FakeWorksheet:
    def __init__(self, records: list[dict] | None = None) -> None:
        self.headers = list(SHEET_HEADERS)
        self.records = [dict(row) for row in (records or [])]

    def row_values(self, row: int) -> list[str]:
        if row == 1:
            return list(self.headers)
        return []

    def get_all_records(self) -> list[dict]:
        return [dict(row) for row in self.records]

    def append_row(self, values, value_input_option="RAW") -> None:
        if values == SHEET_HEADERS:
            self.headers = list(values)
            return
        self.records.append(dict(zip(SHEET_HEADERS, values)))

    def clear(self) -> None:
        self.records = []
        self.headers = []

    def update(self, range_name, values, value_input_option="RAW") -> None:
        # Expect single-row updates like A2:N2
        row_values = values[0]
        # Parse row number from A{n}:
        start = range_name.split(":")[0]
        digits = "".join(ch for ch in start if ch.isdigit())
        sheet_row = int(digits)
        index = sheet_row - 2
        record = dict(zip(SHEET_HEADERS, row_values))
        if 0 <= index < len(self.records):
            self.records[index] = record
        else:
            self.records.append(record)


class GoogleSheetsConfigTest(unittest.TestCase):
    def test_secrets_missing_returns_not_configured(self) -> None:
        self.assertFalse(is_google_sheets_configured({}))
        self.assertFalse(
            is_google_sheets_configured(
                {"gcp_service_account": {}, "google_sheets": {}}
            )
        )
        self.assertEqual(default_storage_mode({}), STORAGE_LOCAL)

    def test_configured_when_email_key_and_sheet_present(self) -> None:
        secrets = {
            "gcp_service_account": {
                "client_email": "titlemaker@example.iam.gserviceaccount.com",
                "private_key": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n",
            },
            "google_sheets": {"sheet_id": "sheet123", "worksheet_name": "Service Log"},
        }
        self.assertTrue(is_google_sheets_configured(secrets))
        self.assertEqual(default_storage_mode(secrets), STORAGE_GOOGLE)


class GoogleSheetsNormalizeTest(unittest.TestCase):
    def test_normalize_missing_optional_columns(self) -> None:
        row = normalize_sheet_row(
            {
                "row_id": "2026-07-17_AFT",
                "date": "2026-07-17",
                "service": "Afternoon",
                "sermon_title": "Hope",
            }
        )
        self.assertEqual(row["row_id"], "2026-07-17_AFT")
        self.assertEqual(row["title"], "Hope")
        self.assertEqual(row["service_code"], "AFT")
        self.assertEqual(row["speaker"], "")
        self.assertEqual(row["notes"], "")
        self.assertFalse(row["exported"])
        self.assertEqual(row["updated_by"], "")

    def test_generated_rows_contain_required_columns(self) -> None:
        entries = generate_service_log(2026)
        self.assertEqual(len(entries), 30)
        for key in (
            "row_id",
            "date",
            "weekday",
            "service",
            "service_line",
            "title",
            "speaker",
            "notes",
            "exported",
            "exported_at",
            "exported_file",
            "include",
            "updated_at",
            "updated_by",
        ):
            self.assertIn(key, entries[1])
        self.assertEqual(entries[1]["row_id"], "2026-07-17_AFT")

    def test_row_to_sheet_record_sets_updated_fields(self) -> None:
        entry = generate_service_log(2026)[1]
        entry["title"] = "AFTERNOON TEST"
        record = row_to_sheet_record(entry, updated_by="Booth A")
        self.assertEqual(record["row_id"], "2026-07-17_AFT")
        self.assertEqual(record["sermon_title"], "AFTERNOON TEST")
        self.assertEqual(record["updated_by"], "Booth A")
        self.assertTrue(record["updated_at"])
        restored = sheet_record_to_row(record)
        self.assertEqual(restored["title"], "AFTERNOON TEST")
        self.assertEqual(restored["updated_by"], "Booth A")


class GoogleSheetsUpsertTest(unittest.TestCase):
    def test_upsert_uses_row_id_and_only_updates_aft(self) -> None:
        entries = generate_service_log(2026)
        worksheet = _FakeWorksheet(
            [
                row_to_sheet_record(entries[0]),
                row_to_sheet_record(entries[1]),
                row_to_sheet_record(entries[2]),
            ]
        )
        aft = dict(entries[1])
        aft["title"] = "AFT ONLY"
        aft["speaker"] = "Speaker AFT"
        saved = upsert_service_log_row(aft, updated_by="Operator", worksheet=worksheet)
        self.assertEqual(saved["title"], "AFT ONLY")
        self.assertEqual(saved["updated_by"], "Operator")
        self.assertEqual(worksheet.records[1]["sermon_title"], "AFT ONLY")
        self.assertEqual(worksheet.records[0]["sermon_title"], "")
        self.assertEqual(worksheet.records[2]["sermon_title"], "")
        self.assertTrue(str(worksheet.records[1]["row_id"]).endswith("_AFT"))

    def test_load_preserves_title_speaker_notes_exported_file(self) -> None:
        record = row_to_sheet_record(
            {
                "row_id": "2026-07-17_AFT",
                "date": date(2026, 7, 17),
                "weekday": "Friday",
                "service": "Afternoon",
                "service_code": "AFT",
                "service_line": "FRIDAY AFT 7-17-26",
                "title": "Kept Title",
                "speaker": "Kept Speaker",
                "notes": "Kept notes",
                "exported": True,
                "exported_at": "2026-07-17T14:00:00",
                "exported_file": "/Users/irds/Downloads/aft.png",
                "include": False,
            },
            updated_by="Booth",
        )
        worksheet = _FakeWorksheet([record])
        rows, warning = load_service_log_from_google_sheet(worksheet=worksheet)
        self.assertIsNone(warning)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Kept Title")
        self.assertEqual(rows[0]["speaker"], "Kept Speaker")
        self.assertEqual(rows[0]["notes"], "Kept notes")
        self.assertEqual(rows[0]["exported_file"], "/Users/irds/Downloads/aft.png")
        self.assertTrue(rows[0]["exported"])

    def test_save_full_rewrites_sheet(self) -> None:
        entries = generate_service_log(2026)[:3]
        worksheet = _FakeWorksheet([row_to_sheet_record(entries[0])])
        saved = save_full_service_log_to_google_sheet(
            entries, updated_by="Booth", worksheet=worksheet
        )
        self.assertEqual(len(saved), 3)
        self.assertEqual(len(worksheet.records), 3)
        self.assertEqual(worksheet.headers, SHEET_HEADERS)
        self.assertEqual(worksheet.records[1]["row_id"], "2026-07-17_AFT")
        self.assertEqual(worksheet.records[1]["updated_by"], "Booth")


class PersistFallbackTest(unittest.TestCase):
    def test_local_json_fallback_when_sheets_not_configured(self) -> None:
        entries = generate_service_log(2026)[:1]
        with mock.patch("service_log.save_service_log") as save_mock:
            saved, warning = persist_service_log_entries(
                entries,
                year=2026,
                storage_mode=STORAGE_GOOGLE,
                updated_by="Booth",
                secrets={},
            )
            self.assertIsNotNone(warning)
            assert warning is not None
            self.assertIn("missing", warning)
            self.assertEqual(len(saved), 1)
            save_mock.assert_called_once()

    def test_load_for_storage_defaults_safely(self) -> None:
        with mock.patch(
            "service_log.load_service_log", return_value=([], None)
        ) as load_mock:
            entries, warning = load_service_log_for_storage(
                STORAGE_GOOGLE, secrets={}
            )
            self.assertEqual(entries, [])
            self.assertIsNotNone(warning)
            load_mock.assert_called()

    def test_local_mode_uses_local_loader(self) -> None:
        sample = generate_service_log(2026)[:1]
        with mock.patch(
            "service_log.load_service_log", return_value=(sample, None)
        ):
            entries, warning = load_service_log_for_storage(STORAGE_LOCAL)
            self.assertEqual(entries, sample)
            self.assertIsNone(warning)


if __name__ == "__main__":
    unittest.main()
