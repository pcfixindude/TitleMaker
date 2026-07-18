from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

import service_log
from monark_schedule import (
    adjacent_entry,
    entry_key,
    find_current_service_entry,
    get_monark_service_entries,
    mark_entry_exported,
    service_option_label,
    update_entry_text,
)
from service_log import (
    apply_display_edits,
    entries_to_display_rows,
    export_service_log_csv,
    generate_service_log,
    import_service_log_csv,
    load_service_log,
    normalize_entry,
    save_service_log,
)


class ServiceLogScheduleTest(unittest.TestCase):
    def test_generated_log_shape(self) -> None:
        entries = generate_service_log(2026)
        self.assertEqual(len(entries), 30)
        self.assertEqual(entries[0]["date"], date(2026, 7, 31))
        self.assertEqual(entries[0]["weekday"], "Friday")
        codes = [entry["service_code"] for entry in entries[:3]]
        self.assertEqual(codes, ["AM", "AFT", "PM"])
        ids = [entry_key(entry) for entry in entries]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(entries[0]["service_line"], "FRIDAY AM 7-31-26")
        self.assertTrue(all(entry["title"] == "" for entry in entries))

    def test_service_order_not_alphabetical(self) -> None:
        entries = get_monark_service_entries(2026)
        self.assertEqual(
            [entry["service_code"] for entry in entries[:3]],
            ["AM", "AFT", "PM"],
        )


class ServiceLogPersistenceTest(unittest.TestCase):
    def test_save_and_load_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "service_log.json"
            entries = generate_service_log(2026)
            entries[0]["title"] = "Hope"
            entries[0]["speaker"] = "Speaker"
            with mock.patch.object(service_log, "SERVICE_LOG_PATH", path), mock.patch.object(
                service_log, "DATA_DIR", Path(temp_dir)
            ):
                save_service_log(entries, year=2026)
                self.assertTrue(path.exists())
                loaded, warning = load_service_log()
                self.assertIsNone(warning)
                self.assertEqual(len(loaded), 30)
                self.assertEqual(loaded[0]["title"], "Hope")
                self.assertEqual(loaded[0]["speaker"], "Speaker")

    def test_corrupted_json_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "service_log.json"
            path.write_text("{bad", encoding="utf-8")
            with mock.patch.object(service_log, "SERVICE_LOG_PATH", path):
                loaded, warning = load_service_log()
                self.assertEqual(loaded, [])
                self.assertIsNotNone(warning)

    def test_missing_fields_migrate(self) -> None:
        entry = normalize_entry(
            {
                "date": "2026-07-31",
                "service": "Morning",
                "title": "Truth",
            }
        )
        self.assertEqual(entry["row_id"], "2026-07-31_AM")
        self.assertEqual(entry["service_code"], "AM")
        self.assertEqual(entry["exported_file"], "")
        self.assertFalse(entry["exported"])


class ServiceLogCsvTest(unittest.TestCase):
    def test_csv_round_trip(self) -> None:
        entries = generate_service_log(2026)
        entries[1]["title"] = "Love"
        entries[1]["notes"] = "note"
        csv_text = export_service_log_csv(entries)
        self.assertIn("exported_file", csv_text)
        self.assertIn("title", csv_text)
        restored = import_service_log_csv(csv_text)
        self.assertEqual(len(restored), 30)
        self.assertEqual(restored[1]["title"], "Love")
        self.assertEqual(restored[1]["notes"], "note")

    def test_import_derives_row_id(self) -> None:
        csv_text = (
            "date,service,title,speaker\n"
            "2026-07-31,Morning,Hope,Marty\n"
        )
        restored = import_service_log_csv(csv_text)
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0]["row_id"], "2026-07-31_AM")
        self.assertEqual(restored[0]["title"], "Hope")


class ServiceLogSelectionTest(unittest.TestCase):
    def test_update_selected_row(self) -> None:
        entries = generate_service_log(2026)
        key = entry_key(entries[2])
        update_entry_text(entries, key, "Title", "Speaker")
        self.assertEqual(entries[2]["title"], "Title")
        self.assertEqual(entries[1]["title"], "")

    def test_next_and_previous_include_blanks(self) -> None:
        entries = generate_service_log(2026)
        first = entry_key(entries[0])
        nxt = adjacent_entry(entries, first, step=1)
        self.assertIsNotNone(nxt)
        assert nxt is not None
        self.assertEqual(entry_key(nxt), entry_key(entries[1]))
        self.assertEqual(nxt["title"], "")
        prev = adjacent_entry(entries, entry_key(nxt), step=-1)
        assert prev is not None
        self.assertEqual(entry_key(prev), first)

    def test_jump_finds_blank_current_row(self) -> None:
        entries = generate_service_log(2026)
        current = find_current_service_entry(
            entries, datetime(2026, 7, 31, 13, 0)
        )
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current["service_code"], "AFT")
        self.assertEqual(current["title"], "")

    def test_option_label(self) -> None:
        entries = generate_service_log(2026)
        self.assertIn("blank", service_option_label(entries[0]))
        entries[0]["title"] = "Hope"
        self.assertIn("title entered", service_option_label(entries[0]))
        entries[0]["exported"] = True
        self.assertIn("exported", service_option_label(entries[0]))


class ServiceLogExportTest(unittest.TestCase):
    def test_export_marks_row(self) -> None:
        entries = generate_service_log(2026)
        key = entry_key(entries[0])
        mark_entry_exported(
            entries,
            key,
            exported_at=datetime(2026, 7, 31, 20, 15),
            exported_file="exports/demo.png",
        )
        self.assertTrue(entries[0]["exported"])
        self.assertEqual(entries[0]["exported_at"], "2026-07-31T20:15:00")
        self.assertEqual(entries[0]["exported_file"], "exports/demo.png")

    def test_display_edit_round_trip(self) -> None:
        entries = generate_service_log(2026)
        rows = entries_to_display_rows(entries)
        rows[0]["Sermon Title"] = "Edited"
        rows[0]["Minister / Speaker"] = "Speaker"
        rows[0]["Notes"] = "note"
        rows[0]["Include"] = True
        updated = apply_display_edits(entries, rows)
        self.assertEqual(updated[0]["title"], "Edited")
        self.assertEqual(updated[0]["speaker"], "Speaker")
        self.assertEqual(updated[0]["notes"], "note")
        self.assertTrue(updated[0]["include"])


class ServiceLogUiCopyTest(unittest.TestCase):
    def test_app_has_service_log_controls(self) -> None:
        source = Path(__file__).resolve().parents[1].joinpath("app.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Service Log", source)
        self.assertIn("Generate Monark Service Log", source)
        self.assertIn("Current Service", source)
        self.assertIn("Previous Service", source)
        self.assertIn("Next Service", source)
        self.assertIn("Export Service Log CSV", source)

    def test_only_apply_pending_helper_assigns_widget_title_keys(self) -> None:
        source = Path(__file__).resolve().parents[1].joinpath("app.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def _stage_service_row_reload", source)
        self.assertIn("def _apply_pending_input_values_before_widgets", source)
        self.assertNotIn("def _load_service_row_into_inputs", source)
        self.assertIn("needs_input_reload", source)
        self.assertIn("pending_title_input", source)

        in_apply = False
        for line in source.splitlines():
            if line.startswith("def _apply_pending_input_values_before_widgets"):
                in_apply = True
                continue
            if line.startswith("def ") and in_apply:
                in_apply = False
            if "setdefault" in line:
                continue
            if "simple_title_input =" in line or "simple_speaker_input =" in line:
                self.assertTrue(
                    in_apply,
                    f"Widget key assignment outside apply helper: {line.strip()}",
                )

    def test_generate_and_navigation_stage_reload(self) -> None:
        source = Path(__file__).resolve().parents[1].joinpath("app.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("_stage_service_row_reload(first_id)", source)
        self.assertIn("on_click=_generate_service_log_clicked", source)
        # Navigation/selection should stage, not assign widget keys directly.
        for needle in (
            "def _on_current_service_changed",
            "def _move_service",
            "def _jump_to_current_service",
            "def _generate_service_log",
        ):
            self.assertIn(needle, source)
        self.assertGreaterEqual(source.count("_stage_service_row_reload("), 5)


if __name__ == "__main__":
    unittest.main()
