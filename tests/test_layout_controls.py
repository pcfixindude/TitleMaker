from __future__ import annotations

import unittest

from layout_controls import (
    MAX_TITLE_FONT_SIZE,
    clamp_box_to_canvas,
    clamp_font_size,
    nudge_font_size,
    nudge_skew_angle,
    update_layout_box,
)


class LayoutControlsTest(unittest.TestCase):
    def test_nudge_position_changes_xy_correctly(self) -> None:
        settings = {"title_box": {"x": 100, "y": 200, "width": 300, "height": 100}}

        update_layout_box(settings, "Sermon Title", dx=5, dy=-10)

        self.assertEqual(settings["title_box"]["x"], 105)
        self.assertEqual(settings["title_box"]["y"], 190)

    def test_nudge_size_changes_width_height_correctly(self) -> None:
        settings = {"title_box": {"x": 100, "y": 200, "width": 300, "height": 100}}

        update_layout_box(settings, "Sermon Title", dw=25, dh=-10)

        self.assertEqual(settings["title_box"]["width"], 325)
        self.assertEqual(settings["title_box"]["height"], 90)

    def test_nudge_font_changes_font_size_correctly(self) -> None:
        settings = {"title_box": {"font_size": 200}}

        nudge_font_size(settings, "Sermon Title", 25)

        self.assertEqual(settings["title_box"]["font_size"], 225)

    def test_box_clamping_prevents_negative_width_and_height(self) -> None:
        box = clamp_box_to_canvas({"x": -10, "y": -20, "width": -1, "height": 0})

        self.assertEqual(box["x"], 0)
        self.assertEqual(box["y"], 0)
        self.assertGreaterEqual(box["width"], 20)
        self.assertGreaterEqual(box["height"], 20)

    def test_title_font_size_clamps_to_400(self) -> None:
        self.assertEqual(clamp_font_size(500), MAX_TITLE_FONT_SIZE)

    def test_positive_and_negative_skew_angles_are_accepted(self) -> None:
        settings = {"title_box": {"skew_angle": 0}}

        nudge_skew_angle(settings, "Sermon Title", 10)
        self.assertEqual(settings["title_box"]["skew_angle"], 10)

        nudge_skew_angle(settings, "Sermon Title", -20)
        self.assertEqual(settings["title_box"]["skew_angle"], -10)


if __name__ == "__main__":
    unittest.main()
