from __future__ import annotations

import unittest
from datetime import datetime
from unittest import mock

from monark_schedule import (
    entry_key,
    find_current_service_entry,
    get_service_entry_by_row_id,
    mark_service_exported,
    update_entry_text,
)
from service_log import generate_service_log
from title_renderer import normalize_service_code


class _FakeSessionState(dict):
    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value) -> None:
        self[name] = value


class NormalizeServiceCodeTest(unittest.TestCase):
    def test_morning_and_am(self) -> None:
        self.assertEqual(normalize_service_code("Morning"), "AM")
        self.assertEqual(normalize_service_code("AM"), "AM")
        self.assertEqual(normalize_service_code("am"), "AM")

    def test_afternoon_and_aft(self) -> None:
        self.assertEqual(normalize_service_code("Afternoon"), "AFT")
        self.assertEqual(normalize_service_code("AFT"), "AFT")
        self.assertEqual(normalize_service_code("aft"), "AFT")

    def test_evening_and_pm(self) -> None:
        self.assertEqual(normalize_service_code("Evening"), "PM")
        self.assertEqual(normalize_service_code("PM"), "PM")
        self.assertEqual(normalize_service_code("pm"), "PM")

    def test_afternoon_never_maps_to_am(self) -> None:
        self.assertNotEqual(normalize_service_code("Afternoon"), "AM")
        self.assertNotEqual(normalize_service_code("AFT"), "AM")


class ServiceRowIdSelectionTest(unittest.TestCase):
    def test_friday_aft_and_pm_row_ids(self) -> None:
        entries = generate_service_log(2026)
        am_id = entry_key(entries[0])
        aft_id = entry_key(entries[1])
        pm_id = entry_key(entries[2])
        self.assertTrue(am_id.endswith("_AM"))
        self.assertTrue(aft_id.endswith("_AFT"))
        self.assertTrue(pm_id.endswith("_PM"))
        self.assertEqual(am_id, "2026-07-17_AM")
        self.assertEqual(aft_id, "2026-07-17_AFT")
        self.assertEqual(pm_id, "2026-07-17_PM")

    def test_selecting_aft_stores_aft_row_id(self) -> None:
        import app as app_module

        entries = generate_service_log(2026)
        aft_id = entry_key(entries[1])
        fake_state = _FakeSessionState(
            {
                "service_log_entries": entries,
                "service_log_current_select": aft_id,
                "selected_service_row_id": entry_key(entries[0]),
                "service_log_selected_row_id": entry_key(entries[0]),
            }
        )
        with mock.patch.object(app_module.st, "session_state", fake_state):
            selected = app_module._get_selected_service_row_id()
            self.assertEqual(selected, aft_id)
            self.assertTrue(selected.endswith("_AFT"))
            self.assertEqual(fake_state["selected_service_row_id"], aft_id)

    def test_selecting_pm_stores_pm_row_id(self) -> None:
        import app as app_module

        entries = generate_service_log(2026)
        pm_id = entry_key(entries[2])
        fake_state = _FakeSessionState({"service_log_current_select": pm_id})
        with mock.patch.object(app_module.st, "session_state", fake_state):
            selected = app_module._get_selected_service_row_id()
            self.assertTrue(selected.endswith("_PM"))


class MarkServiceExportedRowIdTest(unittest.TestCase):
    def test_export_updates_only_selected_aft_row(self) -> None:
        entries = generate_service_log(2026)
        am = entries[0]
        aft = entries[1]
        pm = entries[2]
        aft_id = entry_key(aft)

        updated = mark_service_exported(
            entries,
            aft_id,
            exported_file="exports/aft.png",
            exported_at=datetime(2026, 7, 17, 14, 0),
        )
        self.assertTrue(updated)
        self.assertFalse(am["exported"])
        self.assertTrue(aft["exported"])
        self.assertFalse(pm["exported"])
        self.assertEqual(aft["exported_file"], "exports/aft.png")
        self.assertEqual(am["exported_file"], "")
        self.assertEqual(pm["exported_file"], "")

    def test_friday_afternoon_export_does_not_update_friday_morning(self) -> None:
        entries = generate_service_log(2026)
        am_id = entry_key(entries[0])
        aft_id = entry_key(entries[1])
        self.assertNotEqual(am_id, aft_id)

        mark_service_exported(entries, aft_id, exported_file="exports/aft.png")
        self.assertFalse(entries[0]["exported"])
        self.assertTrue(entries[1]["exported"])

        # Wrong/missing id must not fall back to AM.
        entries[1]["exported"] = False
        self.assertFalse(
            mark_service_exported(entries, "2026-07-17_MISSING", exported_file="x.png")
        )
        self.assertFalse(entries[0]["exported"])
        self.assertFalse(entries[1]["exported"])

    def test_title_update_only_affects_selected_aft_row(self) -> None:
        entries = generate_service_log(2026)
        aft_id = entry_key(entries[1])
        update_entry_text(entries, aft_id, "AFTERNOON TEST", "Speaker AFT")
        self.assertEqual(entries[0]["title"], "")
        self.assertEqual(entries[1]["title"], "AFTERNOON TEST")
        self.assertEqual(entries[2]["title"], "")
        self.assertEqual(entries[1]["speaker"], "Speaker AFT")

    def test_get_service_entry_by_row_id_exact_match(self) -> None:
        entries = generate_service_log(2026)
        aft = get_service_entry_by_row_id(entries, "2026-07-17_AFT")
        assert aft is not None
        self.assertEqual(aft["service_code"], "AFT")
        self.assertEqual(aft["service_line"], "FRIDAY AFT 7-17-26")
        self.assertIsNone(get_service_entry_by_row_id(entries, "2026-07-17_AMX"))


class JumpToCurrentServiceRowIdTest(unittest.TestCase):
    def test_afternoon_time_chooses_aft_not_am(self) -> None:
        entries = generate_service_log(2026)
        current = find_current_service_entry(
            entries, datetime(2026, 7, 17, 14, 30)
        )
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(entry_key(current), "2026-07-17_AFT")
        self.assertEqual(current["service_code"], "AFT")
        self.assertNotEqual(entry_key(current), "2026-07-17_AM")


if __name__ == "__main__":
    unittest.main()
