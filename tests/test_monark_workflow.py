from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest import mock

from monark_schedule import (
    entry_key,
    find_current_service_entry,
    get_monark_schedule_dates,
    get_monark_service_entries,
    get_monark_start_date,
    get_third_friday_of_july,
    mark_service_exported,
    suggest_current_service_code,
)
from service_log import generate_service_log
from title_renderer import (
    EXPORTS_DIR,
    format_short_youtube_title,
    format_youtube_title,
    get_default_downloads_dir,
    resolve_export_dir,
)


class ThirdFridayScheduleTest(unittest.TestCase):
    def test_third_friday_known_years(self) -> None:
        expected = {
            2022: date(2022, 7, 15),
            2023: date(2023, 7, 21),
            2024: date(2024, 7, 19),
            2025: date(2025, 7, 18),
            2026: date(2026, 7, 17),
            2027: date(2027, 7, 16),
            2028: date(2028, 7, 21),
        }
        for year, day in expected.items():
            with self.subTest(year=year):
                self.assertEqual(get_third_friday_of_july(year), day)
                self.assertEqual(get_monark_start_date(year), day)
                self.assertEqual(day.weekday(), 4)
                self.assertEqual(day.month, 7)

    def test_generated_log_starts_on_third_friday(self) -> None:
        entries = generate_service_log(2026)
        self.assertEqual(entries[0]["date"], date(2026, 7, 17))
        self.assertEqual(entries[0]["service_line"], "FRIDAY AM 7-17-26")
        self.assertEqual(len(entries), 30)

    def test_schedule_has_ten_days_ending_second_sunday(self) -> None:
        dates = get_monark_schedule_dates(2026)
        self.assertEqual(len(dates), 10)
        self.assertEqual(dates[0], date(2026, 7, 17))
        self.assertEqual(dates[-1], date(2026, 7, 26))
        self.assertEqual(dates[-1], dates[0] + timedelta(days=9))
        self.assertEqual(dates[-1].weekday(), 6)
        self.assertEqual(len(get_monark_service_entries(2026)), 30)


class ServiceSuggestionTest(unittest.TestCase):
    def test_suggest_current_service_code_boundaries(self) -> None:
        cases = [
            (time(9, 30), "AM"),
            (time(10, 0), "AM"),
            (time(13, 59), "AM"),
            (time(14, 0), "AFT"),
            (time(19, 29), "AFT"),
            (time(19, 30), "PM"),
            (time(22, 0), "PM"),
        ]
        for clock, expected in cases:
            with self.subTest(clock=clock):
                now = datetime(2026, 7, 17, clock.hour, clock.minute)
                self.assertEqual(suggest_current_service_code(now), expected)

    def test_jump_selects_aft_after_2pm(self) -> None:
        entries = generate_service_log(2026)
        current = find_current_service_entry(entries, datetime(2026, 7, 17, 14, 5))
        assert current is not None
        self.assertEqual(entry_key(current), "2026-07-17_AFT")
        self.assertNotEqual(entry_key(current), "2026-07-17_AM")

    def test_jump_selects_pm_after_730pm(self) -> None:
        entries = generate_service_log(2026)
        current = find_current_service_entry(entries, datetime(2026, 7, 17, 19, 30))
        assert current is not None
        self.assertEqual(entry_key(current), "2026-07-17_PM")

    def test_outside_schedule_returns_none(self) -> None:
        entries = generate_service_log(2026)
        self.assertIsNone(
            find_current_service_entry(entries, datetime(2026, 1, 1, 12, 0))
        )


class ExportDirectoryTest(unittest.TestCase):
    def test_default_downloads_when_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            downloads = home / "Downloads"
            downloads.mkdir()
            with mock.patch.object(Path, "home", return_value=home):
                self.assertEqual(get_default_downloads_dir(), downloads)

    def test_fallback_to_exports_when_downloads_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            with mock.patch.object(Path, "home", return_value=home):
                resolved = get_default_downloads_dir()
                self.assertEqual(resolved, EXPORTS_DIR)

    def test_resolve_export_dir_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            downloads = home / "Downloads"
            downloads.mkdir()
            with mock.patch.object(Path, "home", return_value=home):
                self.assertEqual(
                    resolve_export_dir("Downloads folder"), downloads
                )
                self.assertEqual(
                    resolve_export_dir("App exports folder"), EXPORTS_DIR
                )

    def test_export_records_full_path_on_aft_only(self) -> None:
        entries = generate_service_log(2026)
        aft_id = "2026-07-17_AFT"
        path = "/Users/irds/Downloads/2026-07-17_FRIDAY_AFT_TEST.png"
        mark_service_exported(entries, aft_id, exported_file=path)
        self.assertTrue(entries[1]["exported"])
        self.assertEqual(entries[1]["exported_file"], path)
        self.assertFalse(entries[0]["exported"])
        self.assertFalse(entries[2]["exported"])


class YouTubeTitleTest(unittest.TestCase):
    def test_full_youtube_title(self) -> None:
        self.assertEqual(
            format_youtube_title(
                "FRIDAY AFT 7-18-26",
                "Is God Real?",
                "Bro. Marty Clevenger",
            ),
            "FRIDAY AFT 7-18-26 | IS GOD REAL? | BRO. MARTY CLEVENGER",
        )

    def test_short_youtube_title(self) -> None:
        self.assertEqual(
            format_short_youtube_title(
                "Friday",
                "Is God Real?",
                "Bro. Marty Clevenger",
            ),
            "FRIDAY | IS GOD REAL? | BRO. MARTY CLEVENGER",
        )

    def test_blank_parts_safe(self) -> None:
        self.assertEqual(
            format_youtube_title("FRIDAY AM 7-17-26", "", ""),
            "FRIDAY AM 7-17-26",
        )


if __name__ == "__main__":
    unittest.main()
