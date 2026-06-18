from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta

from monark_schedule import (
    batch_export_candidates,
    entry_key,
    find_current_service_entry,
    get_monark_schedule_dates,
    get_monark_service_entries,
    get_monark_start_date,
    mark_entry_exported,
    update_entry_text,
)
from title_renderer import format_service_line


class MonarkScheduleTest(unittest.TestCase):
    def test_get_monark_start_date_returns_last_friday_in_july(self) -> None:
        start_date = get_monark_start_date(2026)

        self.assertEqual(start_date, date(2026, 7, 31))
        self.assertEqual(start_date.weekday(), 4)
        self.assertEqual(start_date.month, 7)
        self.assertGreater(start_date.day + 7, 31)

    def test_sample_year_first_day_is_friday_in_july(self) -> None:
        first_day = get_monark_schedule_dates(2027)[0]

        self.assertEqual(first_day.weekday(), 4)
        self.assertEqual(first_day.month, 7)

    def test_schedule_ends_on_second_sunday_after_start(self) -> None:
        dates = get_monark_schedule_dates(2026)

        self.assertEqual(dates[-1], dates[0] + timedelta(days=9))
        self.assertEqual(dates[-1].weekday(), 6)

    def test_schedule_generates_ten_days(self) -> None:
        self.assertEqual(len(get_monark_schedule_dates(2026)), 10)

    def test_service_entries_generates_thirty_entries(self) -> None:
        self.assertEqual(len(get_monark_service_entries(2026)), 30)

    def test_generated_rows_start_with_blank_title_and_speaker(self) -> None:
        entry = get_monark_service_entries(2026)[0]

        self.assertEqual(entry["title"], "")
        self.assertEqual(entry["speaker"], "")
        self.assertFalse(entry["include"])
        self.assertFalse(entry["exported"])

    def test_service_entry_contains_expected_fields(self) -> None:
        entry = get_monark_service_entries(2026)[1]

        self.assertEqual(entry["date"], date(2026, 7, 31))
        self.assertEqual(entry["weekday"], "Friday")
        self.assertEqual(entry["service"], "Afternoon")
        self.assertEqual(entry["service_code"], "AFT")
        self.assertEqual(entry["service_line"], "FRIDAY AFT 7-31-26")

    def test_date_formatting_has_no_leading_zeroes(self) -> None:
        self.assertEqual(
            format_service_line("Friday", "Morning", date(2026, 7, 3)),
            "FRIDAY AM 7-3-26",
        )

    def test_editing_live_entry_updates_matching_schedule_row(self) -> None:
        entries = get_monark_service_entries(2026)
        selected_key = entry_key(entries[2])

        update_entry_text(entries, selected_key, "The Love of God", "Bro. Speaker")

        self.assertEqual(entries[2]["title"], "The Love of God")
        self.assertEqual(entries[2]["speaker"], "Bro. Speaker")
        self.assertEqual(entries[1]["title"], "")

    def test_jump_to_current_service_uses_time_of_day(self) -> None:
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
            find_current_service_entry(entries, datetime(2026, 7, 31, 19, 0))[
                "service_code"
            ],
            "PM",
        )

    def test_single_service_export_marks_row_exported(self) -> None:
        entries = get_monark_service_entries(2026)
        selected_key = entry_key(entries[0])

        mark_entry_exported(entries, selected_key, datetime(2026, 7, 31, 20, 15))

        self.assertTrue(entries[0]["exported"])
        self.assertEqual(entries[0]["exported_at"], "2026-07-31T20:15:00")

    def test_batch_export_candidates_do_not_require_placeholders(self) -> None:
        entries = get_monark_service_entries(2026)
        entries[0]["include"] = True
        entries[1]["title"] = "Known Title"

        candidates = batch_export_candidates(entries)

        self.assertEqual([entry_key(entry) for entry in candidates], [
            entry_key(entries[0]),
            entry_key(entries[1]),
        ])


if __name__ == "__main__":
    unittest.main()
