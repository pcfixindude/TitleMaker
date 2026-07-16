from __future__ import annotations

import unittest

from layout_controls import MAX_TITLE_FONT_SIZE, MIN_BOX_SIZE, MIN_FONT_SIZE
from layout_interaction import (
    apply_layout_event,
    auto_fit_title_box,
    center_box_horizontally,
    hit_test_layout_area,
    nudge_area_font_size,
    nudge_box,
)


class LayoutInteractionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = {
            "service_box": {
                "x": 120,
                "y": 130,
                "width": 1680,
                "height": 110,
                "font_size": 86,
                "auto_size": True,
            },
            "title_box": {
                "x": 280,
                "y": 325,
                "width": 1360,
                "height": 300,
                "font_size": 200,
                "auto_size": True,
                "max_font_size": 400,
            },
            "speaker_box": {
                "x": 120,
                "y": 700,
                "width": 1680,
                "height": 120,
                "font_size": 80,
                "auto_size": True,
            },
            "selected_layout_area": "Sermon Title",
            "title_side_padding": 120,
            "title_vertical_gap": 40,
            "auto_title_box_between_service_and_speaker": False,
        }

    def test_click_inside_title_selects_title(self) -> None:
        area = hit_test_layout_area(
            500,
            400,
            self.settings["service_box"],
            self.settings["title_box"],
            self.settings["speaker_box"],
        )
        self.assertEqual(area, "Sermon Title")

    def test_click_inside_service_selects_service(self) -> None:
        area = hit_test_layout_area(
            200,
            150,
            self.settings["service_box"],
            self.settings["title_box"],
            self.settings["speaker_box"],
        )
        self.assertEqual(area, "Service Line")

    def test_click_inside_speaker_selects_speaker(self) -> None:
        area = hit_test_layout_area(
            200,
            720,
            self.settings["service_box"],
            self.settings["title_box"],
            self.settings["speaker_box"],
        )
        self.assertEqual(area, "Speaker")

    def test_arrow_events_move_selected_box(self) -> None:
        up = apply_layout_event(
            self.settings,
            {"event": "move", "area": "title", "dy": -5, "dx": 0},
        )
        self.assertEqual(up["settings"]["title_box"]["y"], 320)

        down = apply_layout_event(
            up["settings"],
            {"event": "move", "area": "title", "direction": "down", "step": 5},
        )
        self.assertEqual(down["settings"]["title_box"]["y"], 325)

        left = apply_layout_event(
            down["settings"],
            {"event": "move", "area": "title", "dx": -5, "dy": 0},
        )
        self.assertEqual(left["settings"]["title_box"]["x"], 275)

        right = apply_layout_event(
            left["settings"],
            {"event": "move", "area": "title", "dx": 5, "dy": 0},
        )
        self.assertEqual(right["settings"]["title_box"]["x"], 280)

    def test_font_plus_and_minus(self) -> None:
        plus = apply_layout_event(
            self.settings,
            {"event": "font", "area": "title", "font_delta": 5},
        )
        self.assertEqual(plus["settings"]["title_box"]["font_size"], 205)
        self.assertFalse(plus["settings"]["title_box"]["auto_size"])

        minus = apply_layout_event(
            plus["settings"],
            {"event": "font", "area": "title", "font_delta": -5},
        )
        self.assertEqual(minus["settings"]["title_box"]["font_size"], 200)

    def test_title_font_clamps_to_400(self) -> None:
        settings = nudge_area_font_size(self.settings, "Sermon Title", 500)
        self.assertEqual(settings["title_box"]["font_size"], MAX_TITLE_FONT_SIZE)
        settings = nudge_area_font_size(settings, "Sermon Title", -1000)
        self.assertEqual(settings["title_box"]["font_size"], MIN_FONT_SIZE)

    def test_double_click_autofit_equal_gaps_and_side_padding(self) -> None:
        result = apply_layout_event(
            self.settings,
            {"event": "autofit", "area": "title"},
        )
        title = result["settings"]["title_box"]
        service = self.settings["service_box"]
        speaker = self.settings["speaker_box"]
        self.assertTrue(result["auto_fit_applied"])
        self.assertFalse(result["settings"]["auto_title_box_between_service_and_speaker"])
        self.assertEqual(title["x"], 120)
        self.assertEqual(title["width"], 1680)
        self.assertEqual(title["y"] - (service["y"] + service["height"]), 40)
        self.assertEqual(speaker["y"] - (title["y"] + title["height"]), 40)

    def test_nudge_size_and_clamp(self) -> None:
        settings = nudge_box(self.settings, "Sermon Title", dw=10)
        self.assertEqual(settings["title_box"]["width"], 1370)
        settings = nudge_box(settings, "Sermon Title", dw=-5000)
        self.assertGreaterEqual(settings["title_box"]["width"], MIN_BOX_SIZE)
        settings = nudge_box(settings, "Sermon Title", dh=-5000)
        self.assertGreaterEqual(settings["title_box"]["height"], MIN_BOX_SIZE)

    def test_center_horizontally(self) -> None:
        settings = center_box_horizontally(self.settings, "Sermon Title")
        title = settings["title_box"]
        self.assertEqual(title["x"], (1920 - title["width"]) // 2)

    def test_auto_fit_helper(self) -> None:
        settings = auto_fit_title_box(self.settings)
        title = settings["title_box"]
        self.assertEqual(title["x"], 120)
        self.assertEqual(title["width"], 1680)
        self.assertFalse(settings["auto_title_box_between_service_and_speaker"])


if __name__ == "__main__":
    unittest.main()
