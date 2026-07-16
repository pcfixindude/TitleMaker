from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

from title_renderer import (
    TitleImageOptions,
    fit_title_lines_for_test,
    fit_title_metrics_for_test,
    render_title_image,
)


class TitleRendererTest(unittest.TestCase):
    def test_manual_line_breaks_are_preserved_when_fitting_title(self) -> None:
        lines = fit_title_lines_for_test(
            "THE LOVE OF GOD\nIN A DARK WORLD",
            max_width=1800,
            font_size=90,
        )
        self.assertEqual(lines, ["THE LOVE OF GOD", "IN A DARK WORLD"])

    def test_title_font_max_size_allows_400(self) -> None:
        font, _, line_height, _, _ = fit_title_metrics_for_test(
            "GO",
            max_width=5000,
            max_height=1000,
            font_size=400,
            auto_size=True,
        )
        self.assertGreaterEqual(getattr(font, "size", 0), 300)
        self.assertGreaterEqual(line_height, 250)

    def test_manual_title_font_size_can_be_400(self) -> None:
        font, _, line_height, _, _ = fit_title_metrics_for_test(
            "GO",
            max_width=5000,
            max_height=1000,
            font_size=400,
            auto_size=False,
        )
        self.assertEqual(getattr(font, "size", 0), 400)
        self.assertGreaterEqual(line_height, 300)

    def test_simplified_render_produces_full_hd(self) -> None:
        image = render_title_image(
            TitleImageOptions(
                day="Friday",
                service="Evening",
                service_date=date(2026, 7, 31),
                sermon_title="Keep Drinking",
                speaker_name="Bro. Speaker",
            )
        )
        self.assertEqual(image.size, (1920, 1080))

    def test_missing_font_paths_do_not_crash(self) -> None:
        image = render_title_image(
            TitleImageOptions(
                day="Friday",
                service="Evening",
                service_date=date(2026, 7, 31),
                sermon_title="Keep Drinking",
                speaker_name="Bro. Speaker",
                title_font_path=Path("fonts/missing-title-font.ttf"),
                speaker_font_path=Path("fonts/missing-speaker-font.ttf"),
            )
        )
        self.assertEqual(image.size, (1920, 1080))


if __name__ == "__main__":
    unittest.main()
