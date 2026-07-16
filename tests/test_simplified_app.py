from __future__ import annotations

import ast
import tempfile
import unittest
from datetime import date
from pathlib import Path

from PIL import Image

from title_renderer import (
    BARLOW_BOLD_ITALIC,
    CANVAS_SIZE,
    DEFAULT_SERVICE_BOX,
    DEFAULT_SPEAKER_BOX,
    DEFAULT_TITLE_BOX,
    MAX_TITLE_FONT_SIZE,
    TEXT_COLOR_WHITE,
    TextBox,
    TitleImageOptions,
    default_font_path,
    export_filename,
    fit_single_line_text,
    fit_title_font_size_for_test,
    fit_title_lines_for_test,
    fit_title_metrics_for_test,
    format_service_line,
    format_short_date,
    list_template_backgrounds,
    render_title_image,
    resolve_layout_boxes,
    text_box_from_dict,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SimplifiedServiceLineTest(unittest.TestCase):
    def test_service_line_formats(self) -> None:
        self.assertEqual(
            format_service_line("Friday", "Morning", date(2026, 7, 31)),
            "FRIDAY AM 7-31-26",
        )
        self.assertEqual(
            format_service_line("Friday", "Afternoon", date(2026, 7, 31)),
            "FRIDAY AFT 7-31-26",
        )
        self.assertEqual(
            format_service_line("Friday", "Evening", date(2026, 7, 31)),
            "FRIDAY PM 7-31-26",
        )

    def test_date_formatting_without_leading_zeroes(self) -> None:
        self.assertEqual(format_short_date(date(2026, 7, 3)), "7-3-26")
        self.assertEqual(format_short_date(date(2026, 7, 31)), "7-31-26")

    def test_service_line_fits_in_one_line(self) -> None:
        text = format_service_line("Friday", "Morning", date(2026, 7, 31))
        _, lines, _, width, height = fit_single_line_text(
            text,
            max_width=DEFAULT_SERVICE_BOX["width"],
            max_height=DEFAULT_SERVICE_BOX["height"],
            font_path=default_font_path(),
        )
        self.assertEqual(len(lines), 1)
        self.assertLessEqual(width, DEFAULT_SERVICE_BOX["width"])
        self.assertLessEqual(height, DEFAULT_SERVICE_BOX["height"])


class SimplifiedTitleFitTest(unittest.TestCase):
    def test_short_title_fits_one_line(self) -> None:
        lines = fit_title_lines_for_test("TRUTH", max_width=1560, font_size=200)
        self.assertEqual(lines, ["TRUTH"])
        self.assertEqual(len(lines), 1)

    def test_long_title_wraps_to_two_lines(self) -> None:
        title = "THE TRUTH THE WHOLE TRUTH AND NOTHING BUT THE TRUTH"
        font, lines, _, block_width, block_height = fit_title_metrics_for_test(
            title,
            max_width=DEFAULT_TITLE_BOX["width"],
            max_height=DEFAULT_TITLE_BOX["height"],
            font_size=MAX_TITLE_FONT_SIZE,
        )
        self.assertEqual(len(lines), 2)
        self.assertLessEqual(block_width, DEFAULT_TITLE_BOX["width"])
        self.assertLessEqual(block_height, DEFAULT_TITLE_BOX["height"])
        self.assertLessEqual(getattr(font, "size", 0), MAX_TITLE_FONT_SIZE)

    def test_title_never_exceeds_two_lines(self) -> None:
        title = "ONE\nTWO\nTHREE\nFOUR"
        lines = fit_title_lines_for_test(title, max_width=1560, font_size=120)
        self.assertLessEqual(len(lines), 2)
        self.assertEqual(lines[0], "ONE")
        self.assertIn("TWO", lines[1])

    def test_title_font_can_grow_up_to_400(self) -> None:
        size = fit_title_font_size_for_test(
            "GO",
            max_width=5000,
            max_height=1000,
            font_size=MAX_TITLE_FONT_SIZE,
        )
        self.assertGreaterEqual(size, 300)
        self.assertLessEqual(size, MAX_TITLE_FONT_SIZE)

    def test_speaker_fits_in_one_line(self) -> None:
        _, lines, _, width, height = fit_single_line_text(
            "MARTY CLEVENGER",
            max_width=DEFAULT_SPEAKER_BOX["width"],
            max_height=DEFAULT_SPEAKER_BOX["height"],
            font_path=default_font_path(),
        )
        self.assertEqual(len(lines), 1)
        self.assertLessEqual(width, DEFAULT_SPEAKER_BOX["width"])
        self.assertLessEqual(height, DEFAULT_SPEAKER_BOX["height"])


class SimplifiedLayoutTest(unittest.TestCase):
    def test_default_boxes_match_open_bible_layout(self) -> None:
        self.assertEqual(DEFAULT_SERVICE_BOX["y"], 95)
        self.assertEqual(DEFAULT_TITLE_BOX["y"], 180)
        self.assertEqual(DEFAULT_SPEAKER_BOX["y"], 760)
        self.assertEqual(DEFAULT_TITLE_BOX["width"], 1560)

    def test_changing_title_box_y_height_affects_layout(self) -> None:
        base = self._options(
            title_box=text_box_from_dict({"x": 180, "y": 180, "width": 1560, "height": 520})
        )
        moved = self._options(
            title_box=text_box_from_dict({"x": 180, "y": 260, "width": 1560, "height": 400})
        )
        _, base_title, _ = resolve_layout_boxes(base)
        _, moved_title, _ = resolve_layout_boxes(moved)
        self.assertEqual(base_title.y, 180)
        self.assertEqual(moved_title.y, 260)
        self.assertEqual(moved_title.height, 400)
        self.assertEqual(render_title_image(moved).size, CANVAS_SIZE)

    def test_changing_service_and_speaker_boxes_affects_layout(self) -> None:
        options = self._options(
            service_line_box=TextBox(x=100, y=40, width=1700, height=70),
            speaker_box=TextBox(x=100, y=900, width=1700, height=80),
        )
        service, _, speaker = resolve_layout_boxes(options)
        self.assertEqual(service.y, 40)
        self.assertEqual(speaker.y, 900)
        self.assertEqual(render_title_image(options).size, CANVAS_SIZE)

    def test_title_stays_inside_title_box(self) -> None:
        box = text_box_from_dict({"x": 180, "y": 180, "width": 1560, "height": 520})
        _, lines, _, block_width, block_height = fit_title_metrics_for_test(
            "THE TRUTH THE WHOLE TRUTH AND NOTHING BUT THE TRUTH",
            max_width=box.width,
            max_height=box.height,
        )
        self.assertLessEqual(len(lines), 2)
        self.assertLessEqual(block_width, box.width)
        self.assertLessEqual(block_height, box.height)

    def _options(self, **kwargs) -> TitleImageOptions:
        values = {
            "day": "Friday",
            "service": "Evening",
            "service_date": date(2026, 7, 31),
            "sermon_title": "Keep Drinking",
            "speaker_name": "Marty Clevenger",
        }
        values.update(kwargs)
        return TitleImageOptions(**values)


class SimplifiedRenderTest(unittest.TestCase):
    def _options(self, **kwargs) -> TitleImageOptions:
        values = {
            "day": "Friday",
            "service": "Evening",
            "service_date": date(2026, 7, 31),
            "sermon_title": "Keep Drinking",
            "speaker_name": "Marty Clevenger",
            "service_line_box": text_box_from_dict(DEFAULT_SERVICE_BOX),
            "title_box": text_box_from_dict(DEFAULT_TITLE_BOX),
            "speaker_box": text_box_from_dict(DEFAULT_SPEAKER_BOX),
        }
        values.update(kwargs)
        return TitleImageOptions(**values)

    def test_bounding_boxes_render_without_crashing(self) -> None:
        image = render_title_image(self._options(show_bounding_boxes=True))
        self.assertEqual(image.size, CANVAS_SIZE)

    def test_selected_background_renders(self) -> None:
        templates = list_template_backgrounds()
        if templates:
            image = render_title_image(self._options(background_path=templates[0]))
        else:
            with tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "bg.png"
                Image.new("RGB", (100, 100), (10, 80, 160)).save(path)
                image = render_title_image(self._options(background_path=path))
        self.assertEqual(image.size, CANVAS_SIZE)

    def test_export_filename_is_safe(self) -> None:
        name = export_filename(
            self._options(sermon_title="The Truth: Whole / Truth?")
        )
        self.assertEqual(
            name,
            "2026-07-31_FRIDAY_PM_THE_TRUTH_WHOLE_TRUTH.png",
        )
        self.assertNotRegex(name, r"[^A-Za-z0-9_.-]")

    def test_barlow_is_default_font_when_available(self) -> None:
        if BARLOW_BOLD_ITALIC.exists():
            self.assertEqual(default_font_path(), BARLOW_BOLD_ITALIC)
        else:
            self.skipTest("BarlowCondensed-BoldItalic.ttf not present")

    def test_text_color_is_white_and_shadow_disabled(self) -> None:
        options = self._options()
        self.assertEqual(options.text_color, TEXT_COLOR_WHITE)
        self.assertFalse(options.shadow_enabled)

        # Render on solid black so white title pixels are obvious.
        with tempfile.TemporaryDirectory() as temp_dir:
            bg = Path(temp_dir) / "black.png"
            Image.new("RGB", CANVAS_SIZE, (0, 0, 0)).save(bg)
            image = render_title_image(self._options(background_path=bg, sermon_title="TRUTH"))

        title = DEFAULT_TITLE_BOX
        sample = image.crop(
            (
                title["x"] + title["width"] // 2 - 40,
                title["y"] + title["height"] // 2 - 40,
                title["x"] + title["width"] // 2 + 40,
                title["y"] + title["height"] // 2 + 40,
            )
        )
        bright = [
            pixel
            for pixel in sample.getdata()
            if pixel[0] > 230 and pixel[1] > 230 and pixel[2] > 230
        ]
        self.assertGreater(len(bright), 20)

        # Nearby dark pixels should stay near black (no soft shadow bloom).
        shadow_probe = image.getpixel(
            (title["x"] + title["width"] // 2 + 120, title["y"] + title["height"] // 2 + 90)
        )
        self.assertLess(sum(shadow_probe) / 3, 40)


class SimplifiedAppSafetyTest(unittest.TestCase):
    def test_app_helpers_do_not_assign_widget_keys_after_instantiation(self) -> None:
        source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
        widget_keys = {
            "simple_title_input",
            "simple_speaker_input",
            "simple_day_select",
            "simple_service_select",
            "simple_date_input",
            "simple_background_select",
            "simple_show_boxes",
        }
        for key in widget_keys:
            self.assertIn(f'key="{key}"', source)

        # Box controls use dynamic keys like simple_{prefix}_x.
        self.assertIn('key=f"simple_{prefix}_x"', source)
        self.assertIn('key=f"simple_{prefix}_y"', source)
        self.assertIn('key=f"simple_{prefix}_width"', source)
        self.assertIn('key=f"simple_{prefix}_height"', source)

        # Reset assigns box widget keys only immediately before st.rerun().
        self.assertIn("def _reset_box_defaults", source)
        self.assertIn("Reset boxes to defaults", source)
        self.assertIn("st.rerun()", source)

        tree = ast.parse(source)
        self.assertTrue(any(isinstance(node, ast.FunctionDef) for node in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
