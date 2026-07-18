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
    service_log_schedule_warning,
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
from workflow_links import WHATSAPP_WEB_URL, YOUTUBE_PLAYLIST_URL


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
        self.assertEqual(entries[0]["weekday"], "Friday")
        self.assertEqual(entries[0]["service_line"], "FRIDAY AM 7-17-26")
        self.assertEqual(len(entries), 30)

    def test_2026_schedule_ten_days_friday_through_sunday(self) -> None:
        dates = get_monark_schedule_dates(2026)
        self.assertEqual(len(dates), 10)
        self.assertEqual(dates[0], date(2026, 7, 17))
        self.assertEqual(dates[0].strftime("%A"), "Friday")
        self.assertEqual(dates[-1], date(2026, 7, 26))
        self.assertEqual(dates[-1].strftime("%A"), "Sunday")
        self.assertEqual(dates[-1], dates[0] + timedelta(days=9))

        entries = get_monark_service_entries(2026)
        self.assertEqual(len(entries), 30)
        self.assertEqual(
            [entry_key(e) for e in entries[:3]],
            ["2026-07-17_AM", "2026-07-17_AFT", "2026-07-17_PM"],
        )
        self.assertEqual(
            [entry_key(e) for e in entries[-3:]],
            ["2026-07-26_AM", "2026-07-26_AFT", "2026-07-26_PM"],
        )
        self.assertEqual(entries[-1]["service_line"], "SUNDAY PM 7-26-26")

        # Exactly 3 services per date, ordered AM / AFT / PM.
        by_date: dict[date, list[str]] = {}
        for entry in entries:
            by_date.setdefault(entry["date"], []).append(entry["service_code"])
        self.assertEqual(len(by_date), 10)
        for codes in by_date.values():
            self.assertEqual(codes, ["AM", "AFT", "PM"])

    def test_explicit_third_friday_years(self) -> None:
        self.assertEqual(get_third_friday_of_july(2024), date(2024, 7, 19))
        self.assertEqual(get_third_friday_of_july(2025), date(2025, 7, 18))
        self.assertEqual(get_third_friday_of_july(2026), date(2026, 7, 17))
        self.assertEqual(get_third_friday_of_july(2027), date(2027, 7, 16))
        self.assertEqual(get_third_friday_of_july(2028), date(2028, 7, 21))

    def test_warning_for_last_friday_legacy_log(self) -> None:
        legacy = generate_service_log(2026)
        # Simulate an old last-Friday-of-July log.
        legacy[0]["date"] = date(2026, 7, 31)
        warning = service_log_schedule_warning(legacy, year=2026)
        self.assertIsNotNone(warning)
        assert warning is not None
        self.assertIn("2026-07-17", warning)
        self.assertIn("Regenerate", warning)
        self.assertIsNone(service_log_schedule_warning(generate_service_log(2026), 2026))


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


class WorkflowLinksTest(unittest.TestCase):
    def test_whatsapp_and_youtube_urls(self) -> None:
        self.assertEqual(WHATSAPP_WEB_URL, "https://web.whatsapp.com/")
        self.assertEqual(
            YOUTUBE_PLAYLIST_URL,
            "https://studio.youtube.com/playlist/PLC0_dngm_51A/videos",
        )

    def test_app_imports_workflow_links(self) -> None:
        import app as app_module

        self.assertEqual(app_module.WHATSAPP_WEB_URL, WHATSAPP_WEB_URL)
        self.assertEqual(app_module.YOUTUBE_PLAYLIST_URL, YOUTUBE_PLAYLIST_URL)


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
