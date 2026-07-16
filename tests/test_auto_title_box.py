from __future__ import annotations

import unittest

from layout_controls import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    DEFAULT_TITLE_SIDE_PADDING,
    DEFAULT_TITLE_VERTICAL_GAP,
    MIN_AUTO_TITLE_HEIGHT,
    calculate_auto_title_box,
    get_effective_layout_boxes,
    resolve_auto_title_layout_settings,
    scale_side_padding,
)
from presets import (
    DEFAULT_SERVICE_BOX,
    DEFAULT_SPEAKER_BOX,
    DEFAULT_TITLE_BOX,
    normalize_preset,
    save_preset,
    load_preset,
)


class AutoTitleBoxLayoutTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = {
            "x": 120,
            "y": 130,
            "width": 1680,
            "height": 110,
            "alignment": "center",
        }
        self.speaker = {
            "x": 120,
            "y": 700,
            "width": 1680,
            "height": 120,
            "alignment": "center",
        }
        self.title = {
            "x": 280,
            "y": 325,
            "width": 1360,
            "height": 430,
            "alignment": "center",
            "auto_size": True,
            "font_size": 218,
            "max_font_size": 400,
            "line_spacing": 0.9,
            "skew_angle": -7.0,
        }

    def test_equal_vertical_gaps(self) -> None:
        box = calculate_auto_title_box(
            CANVAS_WIDTH,
            CANVAS_HEIGHT,
            self.service,
            self.speaker,
            side_padding=120,
            vertical_gap=40,
            title_box=self.title,
        )
        service_bottom = self.service["y"] + self.service["height"]
        speaker_top = self.speaker["y"]
        gap_above = box["y"] - service_bottom
        gap_below = speaker_top - (box["y"] + box["height"])
        self.assertEqual(gap_above, 40)
        self.assertEqual(gap_below, 40)

    def test_side_padding_spans_canvas(self) -> None:
        box = calculate_auto_title_box(
            CANVAS_WIDTH,
            CANVAS_HEIGHT,
            self.service,
            self.speaker,
            side_padding=120,
            vertical_gap=40,
            title_box=self.title,
        )
        self.assertEqual(box["x"], 120)
        self.assertEqual(box["width"], 1680)
        self.assertEqual(box["x"] + box["width"], CANVAS_WIDTH - 120)

    def test_height_from_service_bottom_and_speaker_top(self) -> None:
        box = calculate_auto_title_box(
            CANVAS_WIDTH,
            CANVAS_HEIGHT,
            self.service,
            self.speaker,
            side_padding=120,
            vertical_gap=40,
            title_box=self.title,
        )
        self.assertEqual(box["y"], 280)
        self.assertEqual(box["height"], 380)

    def test_clamps_safely_when_space_is_too_small(self) -> None:
        cramped_speaker = {**self.speaker, "y": 250}
        box = calculate_auto_title_box(
            CANVAS_WIDTH,
            CANVAS_HEIGHT,
            self.service,
            cramped_speaker,
            side_padding=120,
            vertical_gap=40,
            title_box=self.title,
        )
        self.assertGreaterEqual(box["height"], MIN_AUTO_TITLE_HEIGHT)
        self.assertIn("warning", box)

    def test_manual_title_box_when_auto_disabled(self) -> None:
        settings = {
            "service_box": self.service,
            "speaker_box": self.speaker,
            "title_box": self.title,
            "auto_title_box_between_service_and_speaker": False,
            "title_side_padding": 120,
            "title_vertical_gap": 40,
        }
        effective = get_effective_layout_boxes(settings)
        self.assertEqual(effective["title_box"]["x"], self.title["x"])
        self.assertEqual(effective["title_box"]["width"], self.title["width"])
        self.assertEqual(effective["title_box"]["y"], self.title["y"])
        self.assertEqual(effective["title_box"]["height"], self.title["height"])

    def test_effective_boxes_return_calculated_title_when_auto_enabled(self) -> None:
        settings = {
            "service_box": self.service,
            "speaker_box": self.speaker,
            "title_box": self.title,
            "auto_title_box_between_service_and_speaker": True,
            "title_side_padding": DEFAULT_TITLE_SIDE_PADDING,
            "title_vertical_gap": DEFAULT_TITLE_VERTICAL_GAP,
        }
        effective = get_effective_layout_boxes(settings)
        self.assertEqual(effective["title_box"]["x"], 120)
        self.assertEqual(effective["title_box"]["width"], 1680)
        self.assertEqual(effective["title_box"]["y"], 280)
        self.assertEqual(effective["title_box"]["height"], 380)
        self.assertIsNone(effective["warning"])

    def test_side_padding_scales_for_smaller_canvas(self) -> None:
        self.assertEqual(scale_side_padding(120, 960), 60)
        box = calculate_auto_title_box(
            960,
            540,
            {"x": 60, "y": 65, "width": 840, "height": 55},
            {"x": 60, "y": 350, "width": 840, "height": 60},
            side_padding=120,
            vertical_gap=40,
            title_box=self.title,
            scale_padding=True,
        )
        self.assertEqual(box["x"], 60)
        self.assertEqual(box["width"], 840)

    def test_old_presets_without_auto_fields_load_safely(self) -> None:
        loaded = normalize_preset(
            {
                "name": "Legacy Layout Preset",
                "title_box": {
                    "x": 280,
                    "y": 325,
                    "width": 1360,
                    "height": 430,
                    "font_size": 218,
                    "auto_size": True,
                    "alignment": "center",
                    "line_spacing": 0.9,
                },
            }
        )
        self.assertFalse(loaded["auto_title_box_between_service_and_speaker"])
        self.assertEqual(loaded["title_side_padding"], DEFAULT_TITLE_SIDE_PADDING)
        self.assertEqual(loaded["title_vertical_gap"], DEFAULT_TITLE_VERTICAL_GAP)

    def test_legacy_auto_title_area_migrates(self) -> None:
        layout = resolve_auto_title_layout_settings(
            {
                "auto_title_area": True,
                "title_top_padding": 100,
                "title_bottom_padding": 140,
            }
        )
        self.assertTrue(layout["auto_title_box_between_service_and_speaker"])
        self.assertEqual(layout["title_vertical_gap"], 120)

    def test_new_preset_saves_and_loads_auto_title_layout_fields(self) -> None:
        path = save_preset(
            "Auto Title Layout Smoke",
            {
                "auto_title_box_between_service_and_speaker": True,
                "title_side_padding": 100,
                "title_vertical_gap": 35,
                "service_line_box": DEFAULT_SERVICE_BOX,
                "title_box": DEFAULT_TITLE_BOX,
                "speaker_box": DEFAULT_SPEAKER_BOX,
            },
        )
        try:
            loaded = load_preset(path)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertTrue(loaded["auto_title_box_between_service_and_speaker"])
            self.assertEqual(loaded["title_side_padding"], 100)
            self.assertEqual(loaded["title_vertical_gap"], 35)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
