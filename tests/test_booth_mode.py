from __future__ import annotations

import unittest
from datetime import datetime

from booth_mode import (
    NO_SCHEDULE_MESSAGE,
    booth_service_label,
    load_entry_values,
    mark_booth_exported,
    update_booth_entry,
)
from monark_schedule import (
    entry_key,
    find_current_service_entry,
    get_monark_service_entries,
)


class BoothModeTest(unittest.TestCase):
    def test_service_option_labels_include_service_line_and_status(self) -> None:
        entries = get_monark_service_entries(2026)

        self.assertEqual(booth_service_label(entries[0]), "FRIDAY AM 7-31-26 — blank")

        entries[1]["title"] = "IS GOD REAL?"
        entries[1]["speaker"] = "BRO. MARTY CLEVENGER"
        self.assertEqual(
            booth_service_label(entries[1]),
            "FRIDAY AFT 7-31-26 — IS GOD REAL? / BRO. MARTY CLEVENGER",
        )

        entries[2]["exported"] = True
        self.assertEqual(booth_service_label(entries[2]), "FRIDAY PM 7-31-26 — exported")

    def test_selecting_service_loads_correct_row(self) -> None:
        entries = get_monark_service_entries(2026)
        entries[2]["title"] = "Evening Title"
        entries[2]["speaker"] = "Evening Speaker"

        values = load_entry_values(entries[2])

        self.assertEqual(values["selected_key"], entry_key(entries[2]))
        self.assertEqual(values["title"], "Evening Title")
        self.assertEqual(values["speaker"], "Evening Speaker")

    def test_editing_title_updates_selected_row(self) -> None:
        entries = get_monark_service_entries(2026)
        selected_key = entry_key(entries[0])

        update_booth_entry(entries, selected_key, "New Title", "", "")

        self.assertEqual(entries[0]["title"], "New Title")

    def test_editing_speaker_updates_selected_row(self) -> None:
        entries = get_monark_service_entries(2026)
        selected_key = entry_key(entries[0])

        update_booth_entry(entries, selected_key, "", "Bro. Speaker", "")

        self.assertEqual(entries[0]["speaker"], "Bro. Speaker")

    def test_export_marks_selected_row_exported(self) -> None:
        entries = get_monark_service_entries(2026)
        selected_key = entry_key(entries[0])

        mark_booth_exported(entries, selected_key, datetime(2026, 7, 31, 9, 0))

        self.assertTrue(entries[0]["exported"])
        self.assertEqual(entries[0]["exported_at"], "2026-07-31T09:00:00")

    def test_reexport_updates_exported_at(self) -> None:
        entries = get_monark_service_entries(2026)
        selected_key = entry_key(entries[0])

        mark_booth_exported(entries, selected_key, datetime(2026, 7, 31, 9, 0))
        mark_booth_exported(entries, selected_key, datetime(2026, 7, 31, 9, 30))

        self.assertEqual(entries[0]["exported_at"], "2026-07-31T09:30:00")

    def test_no_schedule_message_is_friendly(self) -> None:
        self.assertIn("Generate a Monark schedule first", NO_SCHEDULE_MESSAGE)

    def test_jump_to_current_service_still_selects_time_based_service(self) -> None:
        entries = get_monark_service_entries(2026)

        self.assertEqual(
            find_current_service_entry(entries, datetime(2026, 7, 31, 9, 0))[
                "service_code"
            ],
            "AM",
        )
        self.assertEqual(
            find_current_service_entry(entries, datetime(2026, 7, 31, 13, 0))[
                "service_code"
            ],
            "AFT",
        )
        self.assertEqual(
            find_current_service_entry(entries, datetime(2026, 7, 31, 17, 0))[
                "service_code"
            ],
            "PM",
        )


if __name__ == "__main__":
    unittest.main()
