from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from monark_schedule import entry_key, get_monark_service_entries, mark_entry_exported
from persistence import (
    can_replace_log,
    load_service_log,
    load_settings,
    save_service_log,
    save_settings,
)


class PersistenceTest(unittest.TestCase):
    def test_service_log_can_be_saved_and_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "service_log.json"
            entries = get_monark_service_entries(2026)
            entries[0]["title"] = "Known Title"
            entries[0]["speaker"] = "Bro. Speaker"

            save_service_log(entries, 2026, path)
            loaded = load_service_log(path)

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["year"], 2026)
            self.assertEqual(loaded["rows"][0]["title"], "Known Title")
            self.assertEqual(loaded["rows"][0]["speaker"], "Bro. Speaker")

    def test_corrupted_service_log_json_falls_back_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "service_log.json"
            path.write_text("{not valid json")

            self.assertIsNone(load_service_log(path))

    def test_different_year_does_not_replace_without_confirmation(self) -> None:
        self.assertFalse(can_replace_log(2026, 2027, confirmed=False))
        self.assertTrue(can_replace_log(2026, 2027, confirmed=True))
        self.assertTrue(can_replace_log(2026, 2026, confirmed=False))

    def test_settings_save_load_includes_text_boxes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            settings = {
                "selected_preset": "Monark Blue Gray",
                "font_label": "Automatic fallback (Bebas Neue/system)",
                "text_color": "#FFFFFF",
                "background_label": "Generated blue/gray background",
                "service_box": {"x": 10, "y": 20, "width": 300, "height": 40},
                "title_box": {"x": 30, "y": 40, "width": 500, "height": 200},
                "speaker_box": {"x": 50, "y": 60, "width": 300, "height": 40},
                "show_service_line": True,
                "show_layout_guides": False,
                "shadow_enabled": True,
                "skew_enabled": True,
            }

            save_settings(settings, path)
            loaded = load_settings(path)

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["title_box"]["width"], 500)
            self.assertEqual(loaded["service_box"]["x"], 10)

    def test_exported_status_survives_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "service_log.json"
            entries = get_monark_service_entries(2026)
            mark_entry_exported(
                entries,
                entry_key(entries[0]),
                datetime(2026, 7, 31, 19, 30),
            )

            save_service_log(entries, 2026, path)
            loaded = load_service_log(path)

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertTrue(loaded["rows"][0]["exported"])
            self.assertEqual(loaded["rows"][0]["exported_at"], "2026-07-31T19:30:00")


if __name__ == "__main__":
    unittest.main()
