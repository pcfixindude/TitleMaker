from __future__ import annotations

import unittest
from datetime import date

from layout_controls import (
    DEFAULT_TITLE_SIDE_PADDING,
    DEFAULT_TITLE_VERTICAL_GAP,
    calculate_auto_title_box,
    get_effective_layout_boxes,
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
            max_width=1680,
            max_height=380,
            font_size=400,
        )
        self.assertEqual(len(lines), 1)
        self.assertGreaterEqual(getattr(font, "size", 0), 300)
        self.assertLessEqual(block_width, 1680)
        self.assertLessEqual(block_height, 380)

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

    def test_wide_box_delays_wrapping(self) -> None:
        narrow_lines = fit_title_lines_for_test(
            "KEEP DRINKING FROM THE LIVING WATER",
            max_width=700,
            font_size=180,
        )
        wide_lines = fit_title_lines_for_test(
            "KEEP DRINKING FROM THE LIVING WATER",
            max_width=1680,
            font_size=180,
        )
        self.assertLessEqual(len(wide_lines), len(narrow_lines))

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
            max_width=1680,
            max_height=380,
            font_size=400,
        )
        self.assertTrue(lines)
        self.assertLessEqual(block_width, 1680)
        self.assertLessEqual(block_height, 380)
        self.assertEqual(block_height, line_height * len(lines))

    def test_auto_title_box_equal_gaps_and_side_padding(self) -> None:
        title = calculate_auto_title_box(
            1920,
            1080,
            DEFAULT_SERVICE_BOX,
            DEFAULT_SPEAKER_BOX,
            side_padding=DEFAULT_TITLE_SIDE_PADDING,
            vertical_gap=DEFAULT_TITLE_VERTICAL_GAP,
            title_box=DEFAULT_TITLE_BOX,
        )
        service_bottom = DEFAULT_SERVICE_BOX["y"] + DEFAULT_SERVICE_BOX["height"]
        speaker_top = DEFAULT_SPEAKER_BOX["y"]
        self.assertEqual(title["x"], DEFAULT_TITLE_SIDE_PADDING)
        self.assertEqual(title["width"], 1920 - 2 * DEFAULT_TITLE_SIDE_PADDING)
        self.assertEqual(title["y"] - service_bottom, DEFAULT_TITLE_VERTICAL_GAP)
        self.assertEqual(
            speaker_top - (title["y"] + title["height"]),
            DEFAULT_TITLE_VERTICAL_GAP,
        )

    def test_manual_title_box_used_when_auto_off(self) -> None:
        manual = {**DEFAULT_TITLE_BOX, "x": 400, "y": 400, "width": 200, "height": 200}
        effective = get_effective_layout_boxes(
            {
                "service_box": DEFAULT_SERVICE_BOX,
                "speaker_box": DEFAULT_SPEAKER_BOX,
                "title_box": manual,
                "auto_title_box_between_service_and_speaker": False,
            }
        )
        self.assertEqual(effective["title_box"]["x"], 400)
        self.assertEqual(effective["title_box"]["width"], 200)

    def test_renderer_accepts_effective_calculated_boxes(self) -> None:
        effective = get_effective_layout_boxes(
            {
                "service_box": DEFAULT_SERVICE_BOX,
                "speaker_box": DEFAULT_SPEAKER_BOX,
                "title_box": DEFAULT_TITLE_BOX,
                "auto_title_box_between_service_and_speaker": True,
                "title_side_padding": 120,
                "title_vertical_gap": 40,
            }
        )
        title = effective["title_box"]
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
                    x=DEFAULT_SERVICE_BOX["x"],
                    y=DEFAULT_SERVICE_BOX["y"],
                    width=DEFAULT_SERVICE_BOX["width"],
                    height=DEFAULT_SERVICE_BOX["height"],
                    alignment="center",
                    auto_size=True,
                    font_size=86,
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
                    x=DEFAULT_SPEAKER_BOX["x"],
                    y=DEFAULT_SPEAKER_BOX["y"],
                    width=DEFAULT_SPEAKER_BOX["width"],
                    height=DEFAULT_SPEAKER_BOX["height"],
                    alignment="center",
                    auto_size=True,
                    font_size=80,
                ),
                show_layout_guides=True,
            )
        )
        self.assertEqual(image.size, (1920, 1080))
        self.assertGreaterEqual(
            title["y"], DEFAULT_SERVICE_BOX["y"] + DEFAULT_SERVICE_BOX["height"]
        )
        self.assertLessEqual(title["y"] + title["height"], DEFAULT_SPEAKER_BOX["y"])


if __name__ == "__main__":
    unittest.main()
