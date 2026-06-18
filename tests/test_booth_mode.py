from __future__ import annotations

import unittest
from datetime import datetime

from booth_mode import (
    NO_SCHEDULE_MESSAGE,
    build_booth_service_label,
    booth_service_label,
    get_selected_service_row,
    load_entry_values,
    mark_booth_exported,
    next_service_index,
    previous_service_index,
    switch_service,
    update_selected_service_row,
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

        self.assertEqual(build_booth_service_label(entries[0]), "FRIDAY AM 7-31-26 — blank")

        entries[1]["title"] = "IS GOD REAL?"
        entries[1]["speaker"] = "BRO. MARTY CLEVENGER"
        self.assertEqual(
            booth_service_label(entries[1]),
            "FRIDAY AFT 7-31-26 — IS GOD REAL? / BRO. MARTY CLEVENGER",
        )

        entries[2]["exported"] = True
        self.assertEqual(booth_service_label(entries[2]), "FRIDAY PM 7-31-26 — exported")

    def test_service_option_label_handles_title_only_and_speaker_only(self) -> None:
        entries = get_monark_service_entries(2026)
        entries[0]["title"] = "Title Only"
        entries[1]["speaker"] = "Speaker Only"

        self.assertEqual(booth_service_label(entries[0]), "FRIDAY AM 7-31-26 — Title Only")
        self.assertEqual(
            booth_service_label(entries[1]), "FRIDAY AFT 7-31-26 — Speaker Only"
        )

    def test_service_option_label_truncates_long_details(self) -> None:
        entries = get_monark_service_entries(2026)
        entries[0]["title"] = "A" * 100

        self.assertTrue(booth_service_label(entries[0]).endswith("..."))

    def test_selecting_service_loads_correct_row(self) -> None:
        entries = get_monark_service_entries(2026)
        entries[2]["title"] = "Evening Title"
        entries[2]["speaker"] = "Evening Speaker"

        values = load_entry_values(entries[2])

        self.assertEqual(values["selected_key"], entry_key(entries[2]))
        self.assertEqual(values["title"], "Evening Title")
        self.assertEqual(values["speaker"], "Evening Speaker")

    def test_selecting_service_by_index_returns_correct_row(self) -> None:
        entries = get_monark_service_entries(2026)

        self.assertEqual(get_selected_service_row(entries, 2), entries[2])

    def test_editing_title_updates_selected_row(self) -> None:
        entries = get_monark_service_entries(2026)
        selected_key = entry_key(entries[0])

        update_booth_entry(entries, selected_key, "New Title", "", "")

        self.assertEqual(entries[0]["title"], "New Title")
        self.assertEqual(entries[1]["title"], "")

    def test_editing_speaker_updates_selected_row(self) -> None:
        entries = get_monark_service_entries(2026)
        selected_key = entry_key(entries[0])

        update_booth_entry(entries, selected_key, "", "Bro. Speaker", "")

        self.assertEqual(entries[0]["speaker"], "Bro. Speaker")
        self.assertEqual(entries[1]["speaker"], "")

    def test_update_selected_service_row_alias_updates_selected_row(self) -> None:
        entries = get_monark_service_entries(2026)
        selected_key = entry_key(entries[0])

        update_selected_service_row(entries, selected_key, "Alias Title", "Alias Speaker")

        self.assertEqual(entries[0]["title"], "Alias Title")
        self.assertEqual(entries[0]["speaker"], "Alias Speaker")

    def test_previous_service_does_not_go_below_zero(self) -> None:
        self.assertEqual(previous_service_index(0), 0)
        self.assertEqual(previous_service_index(3), 2)

    def test_next_service_does_not_go_past_last_index(self) -> None:
        self.assertEqual(next_service_index(2, 3), 2)
        self.assertEqual(next_service_index(0, 3), 1)

    def test_switching_next_preserves_current_edits_and_loads_next_values(self) -> None:
        entries = get_monark_service_entries(2026)
        entries[1]["title"] = "Next Title"
        entries[1]["speaker"] = "Next Speaker"
        entries[1]["notes"] = "Next Notes"

        result = switch_service(
            entries,
            current_index=0,
            new_index=1,
            title="Current Title",
            speaker="Current Speaker",
            notes="Current Notes",
        )

        self.assertEqual(entries[0]["title"], "Current Title")
        self.assertEqual(entries[0]["speaker"], "Current Speaker")
        self.assertEqual(entries[0]["notes"], "Current Notes")
        self.assertEqual(result["index"], 1)
        self.assertEqual(result["values"]["title"], "Next Title")
        self.assertEqual(result["values"]["speaker"], "Next Speaker")
        self.assertEqual(result["values"]["notes"], "Next Notes")

    def test_full_navigation_includes_blank_rows(self) -> None:
        entries = get_monark_service_entries(2026)[:5]
        entries[0]["title"] = "First Title"
        entries[0]["speaker"] = "First Speaker"
        entries[3]["title"] = "Fourth Title"
        entries[3]["speaker"] = "Fourth Speaker"

        result = switch_service(entries, 0, 1, "Saved First", "Saved Speaker", "")

        self.assertEqual(result["index"], 1)
        self.assertEqual(result["selected_key"], entry_key(entries[1]))
        self.assertEqual(result["values"]["title"], "")
        self.assertEqual(result["values"]["speaker"], "")

    def test_next_into_blank_service_clears_loaded_inputs(self) -> None:
        entries = get_monark_service_entries(2026)[:2]
        entries[0]["title"] = "Current Title"
        entries[0]["speaker"] = "Current Speaker"

        result = switch_service(entries, 0, 1, "Current Title", "Current Speaker", "")

        self.assertEqual(result["values"]["title"], "")
        self.assertEqual(result["values"]["speaker"], "")
        self.assertEqual(result["values"]["notes"], "")

    def test_previous_into_blank_service_works(self) -> None:
        entries = get_monark_service_entries(2026)[:2]
        entries[1]["title"] = "Current AFT"
        entries[1]["speaker"] = "Current Speaker"

        result = switch_service(entries, 1, 0, "Current AFT", "Current Speaker", "")

        self.assertEqual(result["index"], 0)
        self.assertEqual(result["selected_key"], entry_key(entries[0]))
        self.assertEqual(result["values"]["title"], "")

    def test_dropdown_labels_include_blank_rows(self) -> None:
        entries = get_monark_service_entries(2026)[:5]
        labels = [booth_service_label(entry) for entry in entries]

        self.assertEqual(len(labels), 5)
        self.assertIn("FRIDAY AFT 7-31-26 — blank", labels)
        self.assertIn("FRIDAY PM 7-31-26 — blank", labels)

    def test_blank_rows_have_stable_unique_ids(self) -> None:
        entries = get_monark_service_entries(2026)[:3]
        keys = [entry_key(entry) for entry in entries]

        self.assertEqual(keys, ["2026-07-31_AM", "2026-07-31_AFT", "2026-07-31_PM"])
        self.assertEqual(len(set(keys)), 3)

    def test_switching_previous_preserves_current_edits(self) -> None:
        entries = get_monark_service_entries(2026)

        result = switch_service(
            entries,
            current_index=1,
            new_index=0,
            title="Edited AFT",
            speaker="Speaker AFT",
            notes="Notes AFT",
        )

        self.assertEqual(entries[1]["title"], "Edited AFT")
        self.assertEqual(entries[1]["speaker"], "Speaker AFT")
        self.assertEqual(result["index"], 0)

    def test_jump_to_current_service_can_update_selected_index_safely(self) -> None:
        entries = get_monark_service_entries(2026)
        current = find_current_service_entry(entries, datetime(2026, 7, 31, 17, 0))
        assert current is not None
        current_index = entries.index(current)

        result = switch_service(entries, 0, current_index, "Title", "Speaker", "Notes")

        self.assertEqual(result["index"], 2)
        self.assertEqual(result["selected_key"], entry_key(entries[2]))

    def test_jump_to_current_service_finds_blank_row(self) -> None:
        entries = get_monark_service_entries(2026)
        current = find_current_service_entry(entries, datetime(2026, 7, 31, 13, 0))

        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current["service_code"], "AFT")
        self.assertEqual(current["title"], "")
        self.assertEqual(current["speaker"], "")

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
