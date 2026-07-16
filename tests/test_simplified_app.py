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
    MAX_TITLE_FONT_SIZE,
    SERVICE_BOX,
    SPEAKER_BOX,
    TITLE_SIDE_PADDING,
    TITLE_VERTICAL_GAP,
    TitleImageOptions,
    compute_title_box,
    default_font_path,
    export_filename,
    fit_title_font_size_for_test,
    fit_title_lines_for_test,
    fit_title_metrics_for_test,
    format_service_line,
    format_short_date,
    list_template_backgrounds,
    render_title_image,
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


class SimplifiedTitleFitTest(unittest.TestCase):
    def test_short_title_fits_one_line(self) -> None:
        lines = fit_title_lines_for_test("TRUTH", max_width=1680, font_size=200)
        self.assertEqual(lines, ["TRUTH"])
        self.assertEqual(len(lines), 1)

    def test_long_title_wraps_to_two_lines(self) -> None:
        title = "THE TRUTH THE WHOLE TRUTH AND NOTHING BUT THE TRUTH"
        font, lines, _, block_width, block_height = fit_title_metrics_for_test(
            title,
            max_width=1680,
            max_height=440,
            font_size=MAX_TITLE_FONT_SIZE,
        )
        self.assertLessEqual(len(lines), 2)
        self.assertGreaterEqual(len(lines), 1)
        self.assertLessEqual(block_width, 1680)
        self.assertLessEqual(block_height, 440)
        self.assertLessEqual(getattr(font, "size", 0), MAX_TITLE_FONT_SIZE)

    def test_title_never_exceeds_two_lines(self) -> None:
        title = "ONE\nTWO\nTHREE\nFOUR"
        lines = fit_title_lines_for_test(title, max_width=1680, font_size=120)
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


class SimplifiedLayoutTest(unittest.TestCase):
    def test_title_box_uses_full_width_with_equal_side_padding(self) -> None:
        box = compute_title_box(0)
        self.assertEqual(box["x"], TITLE_SIDE_PADDING)
        self.assertEqual(box["width"], 1920 - (2 * TITLE_SIDE_PADDING))
        service_bottom = SERVICE_BOX["y"] + SERVICE_BOX["height"]
        speaker_top = SPEAKER_BOX["y"]
        expected_height = speaker_top - service_bottom - (2 * TITLE_VERTICAL_GAP)
        self.assertEqual(box["height"], expected_height)
        self.assertEqual(box["y"], service_bottom + TITLE_VERTICAL_GAP)

    def test_title_vertical_offset_changes_title_box_y(self) -> None:
        base = compute_title_box(0)
        up = compute_title_box(-40)
        down = compute_title_box(40)
        self.assertLess(up["y"], base["y"])
        self.assertGreater(down["y"], base["y"])
        self.assertEqual(up["height"], base["height"])
        self.assertEqual(down["height"], base["height"])


class SimplifiedRenderTest(unittest.TestCase):
    def _options(self, **kwargs) -> TitleImageOptions:
        values = {
            "day": "Friday",
            "service": "Evening",
            "service_date": date(2026, 7, 31),
            "sermon_title": "Keep Drinking",
            "speaker_name": "Bro. Speaker",
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

    def test_generated_background_when_missing(self) -> None:
        image = render_title_image(self._options(background_path=None))
        self.assertEqual(image.size, CANVAS_SIZE)

    def test_export_filename_is_safe(self) -> None:
        name = export_filename(
            self._options(
                sermon_title="The Truth: Whole / Truth?",
            )
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


class SimplifiedAppSafetyTest(unittest.TestCase):
    def test_app_helpers_do_not_assign_widget_keys_after_instantiation(self) -> None:
        source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        widget_keys = {
            "simple_title_input",
            "simple_speaker_input",
            "simple_day_select",
            "simple_service_select",
            "simple_date_input",
            "simple_background_select",
            "simple_show_boxes",
            "simple_title_offset",
        }
        # Ensure the simplified keys exist as widget keys in source.
        for key in widget_keys:
            self.assertIn(f'key="{key}"', source)

        # Disallow patterns that assign session_state[key] = ... after a widget
        # with the same key in the same function without an intervening rerun.
        # Heuristic: button handlers that assign simple_* keys must call st.rerun().
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            text = ast.get_source_segment(source, node) or ""
            if "simple_title_offset" in text and "session_state.simple_title_offset" in text:
                if "simple_title_offset =" in text.replace(" ", ""):
                    self.assertIn("st.rerun()", text)


if __name__ == "__main__":
    unittest.main()
