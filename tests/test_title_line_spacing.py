from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw

from simple_presets import load_preset, save_preset
from title_renderer import (
    BARLOW_BOLD_ITALIC,
    DEFAULT_TITLE_BOX,
    DEFAULT_TITLE_LINE_SPACING_PX,
    TitleImageOptions,
    clamp_title_line_spacing,
    fit_title_max_2_lines,
    measure_text_block,
    render_title_image,
    text_box_from_dict,
)


class TitleLineSpacingTest(unittest.TestCase):
    def test_default_title_line_spacing_is_zero(self) -> None:
        self.assertEqual(DEFAULT_TITLE_LINE_SPACING_PX, 0)
        options = TitleImageOptions(
            day="Friday",
            service="Evening",
            service_date=date(2026, 7, 31),
            sermon_title="A LONG TITLE THAT SHOULD WRAP",
            speaker_name="Speaker",
        )
        self.assertEqual(options.title_line_spacing, 0)

    def test_clamp_title_line_spacing(self) -> None:
        self.assertEqual(clamp_title_line_spacing(-1000), -80)
        self.assertEqual(clamp_title_line_spacing(1000), 120)
        self.assertEqual(clamp_title_line_spacing(None), 0)
        self.assertEqual(clamp_title_line_spacing("-30"), -30)

    def test_negative_spacing_reduces_two_line_block_height(self) -> None:
        if not BARLOW_BOLD_ITALIC.exists():
            self.skipTest("title font missing")
        lines = ["THE LOVE OF GOD", "IN A DARK WORLD"]
        font, _, stride0, _, _ = fit_title_max_2_lines(
            "\n".join(lines),
            max_width=DEFAULT_TITLE_BOX["width"],
            max_height=DEFAULT_TITLE_BOX["height"],
            font_path=BARLOW_BOLD_ITALIC,
            line_gap_adjust=0,
        )
        probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        _, stride_neg, height_neg = measure_text_block(
            lines,
            font,
            line_gap_adjust=-40,
            draw=probe,
        )
        _, stride_pos, height_pos = measure_text_block(
            lines,
            font,
            line_gap_adjust=40,
            draw=probe,
        )
        _, stride_zero, height_zero = measure_text_block(
            lines,
            font,
            line_gap_adjust=0,
            draw=probe,
        )
        self.assertLess(height_neg, height_zero)
        self.assertGreater(height_pos, height_zero)
        self.assertLess(stride_neg, stride_zero)
        self.assertGreater(stride_pos, stride_zero)
        self.assertEqual(stride0, stride_zero)

    def test_fit_and_draw_use_same_spacing(self) -> None:
        if not BARLOW_BOLD_ITALIC.exists():
            self.skipTest("title font missing")
        title = "THE TRUTH THE WHOLE TRUTH AND NOTHING BUT"
        font, lines, stride, width, height = fit_title_max_2_lines(
            title,
            max_width=DEFAULT_TITLE_BOX["width"] - 8,
            max_height=DEFAULT_TITLE_BOX["height"] - 8,
            font_path=BARLOW_BOLD_ITALIC,
            line_gap_adjust=-30,
        )
        self.assertGreaterEqual(len(lines), 1)
        measured_w, measured_stride, measured_h = measure_text_block(
            lines, font, line_gap_adjust=-30
        )
        self.assertEqual(stride, measured_stride)
        self.assertEqual(height, measured_h)
        self.assertEqual(width, measured_w)
        self.assertLessEqual(height, DEFAULT_TITLE_BOX["height"])

    def test_two_line_title_stays_in_box_with_spacing(self) -> None:
        options = TitleImageOptions(
            day="Friday",
            service="Evening",
            service_date=date(2026, 7, 31),
            sermon_title="THE LOVE OF GOD\nIN A DARK WORLD",
            speaker_name="Marty Clevenger",
            title_line_spacing=-30,
            title_box=text_box_from_dict(DEFAULT_TITLE_BOX, line_gap_adjust=-30),
            show_bounding_boxes=False,
        )
        image = render_title_image(options)
        self.assertEqual(image.size, (1920, 1080))

    def test_preset_saves_and_loads_title_line_spacing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "simple_presets.json"
            with mock.patch("simple_presets.PRESETS_PATH", path), mock.patch(
                "simple_presets.DATA_DIR", Path(temp_dir)
            ):
                payload = {
                    "name": "Tight title",
                    "service": dict(DEFAULT_TITLE_BOX),  # wrong boxes ok if fields present
                    "title": {
                        "x": 30,
                        "y": 195,
                        "width": 1860,
                        "height": 460,
                    },
                    "speaker": {
                        "x": 280,
                        "y": 665,
                        "width": 1360,
                        "height": 90,
                    },
                    "title_line_spacing": -35,
                }
                # Fix service box to valid shape
                payload["service"] = {
                    "x": 280,
                    "y": 95,
                    "width": 1360,
                    "height": 90,
                }
                save_preset(1, payload)
                loaded = load_preset(1)
                self.assertIsNotNone(loaded)
                assert loaded is not None
                self.assertEqual(loaded["title_line_spacing"], -35)

    def test_old_preset_without_title_line_spacing_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "simple_presets.json"
            with mock.patch("simple_presets.PRESETS_PATH", path), mock.patch(
                "simple_presets.DATA_DIR", Path(temp_dir)
            ):
                payload = {
                    "name": "Legacy",
                    "service": {"x": 280, "y": 95, "width": 1360, "height": 90},
                    "title": {"x": 30, "y": 195, "width": 1860, "height": 460},
                    "speaker": {"x": 280, "y": 665, "width": 1360, "height": 90},
                }
                save_preset(2, payload)
                loaded = load_preset(2)
                self.assertIsNotNone(loaded)
                assert loaded is not None
                self.assertEqual(loaded["title_line_spacing"], 0)

    def test_app_has_title_line_spacing_control_and_reset(self) -> None:
        source = Path(__file__).resolve().parents[1].joinpath("app.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Title line spacing", source)
        self.assertIn("simple_title_line_spacing", source)
        self.assertIn(
            "st.session_state.simple_title_line_spacing = DEFAULT_TITLE_LINE_SPACING_PX",
            source,
        )


if __name__ == "__main__":
    unittest.main()
