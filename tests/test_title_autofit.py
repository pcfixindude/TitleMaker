from __future__ import annotations

import unittest
from datetime import date

from layout_controls import (
    DEFAULT_TITLE_BOTTOM_PADDING,
    DEFAULT_TITLE_TOP_PADDING,
    compute_auto_title_box,
    resolve_title_box,
)
from presets import (
    DEFAULT_SERVICE_BOX,
    DEFAULT_SPEAKER_BOX,
    DEFAULT_TITLE_BOX,
)
from title_renderer import (
    TextBox,
    TitleImageOptions,
    fit_title_font_size_for_test,
    fit_title_lines_for_test,
    fit_title_metrics_for_test,
    render_title_image,
)


class TitleAutoFitTest(unittest.TestCase):
    def test_short_title_fits_one_large_line(self) -> None:
        font, lines, _, block_width, block_height = fit_title_metrics_for_test(
            "GO",
            max_width=1360,
            max_height=430,
            font_size=400,
        )
        self.assertEqual(len(lines), 1)
        self.assertGreaterEqual(getattr(font, "size", 0), 300)
        self.assertLessEqual(block_width, 1360)
        self.assertLessEqual(block_height, 430)

    def test_medium_title_wraps_to_two_lines(self) -> None:
        _, lines, _, block_width, block_height = fit_title_metrics_for_test(
            "THE LOVE OF GOD IN A DARK WORLD TODAY",
            max_width=900,
            max_height=430,
            font_size=400,
        )
        self.assertGreaterEqual(len(lines), 2)
        self.assertLessEqual(block_width, 900)
        self.assertLessEqual(block_height, 430)

    def test_long_title_wraps_to_three_or_more_lines(self) -> None:
        _, lines, _, block_width, block_height = fit_title_metrics_for_test(
            "WHAT WILL YOU DO WHEN THE FOUNDATIONS ARE DESTROYED AND THE FAITHFUL ARE FEW",
            max_width=900,
            max_height=430,
            font_size=400,
        )
        self.assertGreaterEqual(len(lines), 3)
        self.assertLessEqual(block_width, 900)
        self.assertLessEqual(block_height, 430)

    def test_manual_line_breaks_are_preserved(self) -> None:
        lines = fit_title_lines_for_test(
            "THE LOVE OF GOD\nIN A DARK WORLD",
            max_width=1800,
            font_size=90,
        )
        self.assertEqual(lines, ["THE LOVE OF GOD", "IN A DARK WORLD"])

    def test_title_font_size_never_exceeds_400(self) -> None:
        size = fit_title_font_size_for_test("GO", max_width=5000, max_height=1000)
        self.assertLessEqual(size, 400)

    def test_title_does_not_exceed_box_width_or_height(self) -> None:
        _, lines, line_height, block_width, block_height = fit_title_metrics_for_test(
            "KEEP DRINKING FROM THE LIVING WATER EVERY DAY OF YOUR LIFE",
            max_width=1100,
            max_height=360,
            font_size=400,
        )
        self.assertTrue(lines)
        self.assertLessEqual(block_width, 1100)
        self.assertLessEqual(block_height, 360)
        self.assertEqual(block_height, line_height * len(lines))

    def test_auto_title_area_between_service_and_speaker(self) -> None:
        title = compute_auto_title_box(
            DEFAULT_SERVICE_BOX,
            DEFAULT_SPEAKER_BOX,
            DEFAULT_TITLE_BOX,
            top_padding=DEFAULT_TITLE_TOP_PADDING,
            bottom_padding=DEFAULT_TITLE_BOTTOM_PADDING,
        )
        service_bottom = DEFAULT_SERVICE_BOX["y"] + DEFAULT_SERVICE_BOX["height"]
        speaker_top = DEFAULT_SPEAKER_BOX["y"]
        self.assertEqual(title["y"], service_bottom + DEFAULT_TITLE_TOP_PADDING)
        self.assertEqual(
            title["y"] + title["height"],
            speaker_top - DEFAULT_TITLE_BOTTOM_PADDING,
        )

    def test_manual_title_box_used_when_auto_off(self) -> None:
        manual = {**DEFAULT_TITLE_BOX, "y": 400, "height": 200}
        resolved = resolve_title_box(
            DEFAULT_SERVICE_BOX,
            DEFAULT_SPEAKER_BOX,
            manual,
            auto_title_area=False,
        )
        self.assertEqual(resolved["y"], 400)
        self.assertEqual(resolved["height"], 200)

    def test_long_title_stays_inside_title_box_without_overlap_region(self) -> None:
        service = DEFAULT_SERVICE_BOX
        speaker = DEFAULT_SPEAKER_BOX
        title = compute_auto_title_box(service, speaker, DEFAULT_TITLE_BOX)
        image = render_title_image(
            TitleImageOptions(
                day="Friday",
                service="Evening",
                service_date=date(2026, 7, 31),
                sermon_title=(
                    "WHAT WILL YOU DO WHEN THE FOUNDATIONS ARE DESTROYED "
                    "AND THE FAITHFUL ARE FEW IN THE LAST DAYS"
                ),
                speaker_name="Bro. Speaker",
                service_line_box=TextBox(
                    x=service["x"],
                    y=service["y"],
                    width=service["width"],
                    height=service["height"],
                    alignment=service["alignment"],
                    auto_size=True,
                    font_size=service["font_size"],
                ),
                title_box=TextBox(
                    x=title["x"],
                    y=title["y"],
                    width=title["width"],
                    height=title["height"],
                    alignment="center",
                    auto_size=True,
                    font_size=218,
                    max_font_size=400,
                    line_spacing=0.9,
                    skew_angle=-7.0,
                ),
                speaker_box=TextBox(
                    x=speaker["x"],
                    y=speaker["y"],
                    width=speaker["width"],
                    height=speaker["height"],
                    alignment=speaker["alignment"],
                    auto_size=True,
                    font_size=speaker["font_size"],
                ),
                show_layout_guides=True,
            )
        )
        self.assertEqual(image.size, (1920, 1080))
        self.assertGreaterEqual(title["y"], service["y"] + service["height"])
        self.assertLessEqual(title["y"] + title["height"], speaker["y"])


if __name__ == "__main__":
    unittest.main()
