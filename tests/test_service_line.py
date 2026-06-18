from __future__ import annotations

import unittest
from datetime import date

from title_renderer import TitleImageOptions, export_filename, format_service_line


class ServiceLineTest(unittest.TestCase):
    def test_friday_afternoon_service_line(self) -> None:
        self.assertEqual(
            format_service_line("Friday", "Afternoon", date(2022, 7, 22)),
            "FRIDAY AFT 7-22-22",
        )

    def test_friday_evening_service_line(self) -> None:
        self.assertEqual(
            format_service_line("Friday", "Evening", date(2022, 7, 22)),
            "FRIDAY PM 7-22-22",
        )

    def test_saturday_evening_service_line(self) -> None:
        self.assertEqual(
            format_service_line("Saturday", "Evening", date(2022, 7, 23)),
            "SATURDAY PM 7-23-22",
        )

    def test_service_line_omits_leading_zeroes(self) -> None:
        self.assertEqual(
            format_service_line("Friday", "Morning", date(2026, 7, 3)),
            "FRIDAY AM 7-3-26",
        )

    def test_export_filename_uses_service_code(self) -> None:
        options = TitleImageOptions(
            day="Friday",
            service="Afternoon",
            service_date=date(2022, 7, 22),
            sermon_title="Is God Real?",
            speaker_name="Bro. Marty Clevenger",
        )

        self.assertEqual(
            export_filename(options),
            "2022-07-22_FRIDAY_AFT_IS_GOD_REAL.png",
        )


if __name__ == "__main__":
    unittest.main()
