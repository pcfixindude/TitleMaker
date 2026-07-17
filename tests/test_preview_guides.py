from __future__ import annotations

import unittest
from datetime import date

from PIL import Image, ImageDraw

from title_renderer import (
    DEFAULT_SERVICE_BOX,
    DEFAULT_SPEAKER_BOX,
    DEFAULT_TITLE_BOX,
    TextBox,
    TitleImageOptions,
    draw_preview_guides,
    normalize_selected_area,
    render_title_image,
    text_box_from_dict,
)


class PreviewGuidesTest(unittest.TestCase):
    def _boxes(self) -> tuple[TextBox, TextBox, TextBox]:
        return (
            text_box_from_dict(DEFAULT_SERVICE_BOX),
            text_box_from_dict(DEFAULT_TITLE_BOX),
            text_box_from_dict(DEFAULT_SPEAKER_BOX),
        )

    def test_normalize_selected_area_aliases(self) -> None:
        self.assertEqual(normalize_selected_area("Service line"), "service")
        self.assertEqual(normalize_selected_area("service"), "service")
        self.assertEqual(normalize_selected_area("Sermon title"), "title")
        self.assertEqual(normalize_selected_area("title"), "title")
        self.assertEqual(normalize_selected_area("Speaker / Minister"), "speaker")
        self.assertEqual(normalize_selected_area("Speaker"), "speaker")
        self.assertEqual(normalize_selected_area("Minister"), "speaker")
        self.assertIsNone(normalize_selected_area(None))
        self.assertIsNone(normalize_selected_area("unknown-area"))

    def test_draw_preview_guides_without_selected(self) -> None:
        image = Image.new("RGB", (1920, 1080), (0, 0, 0))
        draw_preview_guides(ImageDraw.Draw(image), *self._boxes())
        self.assertEqual(image.size, (1920, 1080))

    def test_draw_preview_guides_with_each_selected_key(self) -> None:
        for selected in ("service", "title", "speaker"):
            with self.subTest(selected=selected):
                image = Image.new("RGB", (1920, 1080), (0, 0, 0))
                draw_preview_guides(
                    ImageDraw.Draw(image), *self._boxes(), selected=selected
                )
                self.assertEqual(image.size, (1920, 1080))

    def test_draw_preview_guides_ignores_unknown_selected(self) -> None:
        image = Image.new("RGB", (1920, 1080), (0, 0, 0))
        draw_preview_guides(
            ImageDraw.Draw(image), *self._boxes(), selected="not-a-real-area"
        )
        self.assertEqual(image.size, (1920, 1080))

    def test_draw_preview_guides_accepts_ui_labels(self) -> None:
        image = Image.new("RGB", (1920, 1080), (0, 0, 0))
        draw_preview_guides(
            ImageDraw.Draw(image), *self._boxes(), selected="Sermon title"
        )
        self.assertEqual(image.size, (1920, 1080))

    def _options(self, **kwargs) -> TitleImageOptions:
        values = {
            "day": "Friday",
            "service": "Evening",
            "service_date": date(2026, 7, 31),
            "sermon_title": "Love",
            "speaker_name": "Marty Clevenger",
            "service_line_box": text_box_from_dict(DEFAULT_SERVICE_BOX),
            "title_box": text_box_from_dict(DEFAULT_TITLE_BOX),
            "speaker_box": text_box_from_dict(DEFAULT_SPEAKER_BOX),
        }
        values.update(kwargs)
        return TitleImageOptions(**values)

    def test_render_with_boxes_and_selected_does_not_crash(self) -> None:
        image = render_title_image(
            self._options(show_bounding_boxes=True, selected_layout_area="title")
        )
        self.assertEqual(image.size, (1920, 1080))

    def test_render_without_boxes_ignores_selected_and_draws_no_guides(self) -> None:
        image = render_title_image(
            self._options(show_bounding_boxes=False, selected_layout_area="title")
        )
        self.assertEqual(image.size, (1920, 1080))
        # Guide yellow should not appear when boxes are off.
        yellow = 0
        for y in range(DEFAULT_TITLE_BOX["y"], DEFAULT_TITLE_BOX["y"] + 8):
            for x in range(DEFAULT_TITLE_BOX["x"], DEFAULT_TITLE_BOX["x"] + DEFAULT_TITLE_BOX["width"], 20):
                r, g, b = image.getpixel((x, y))
                if r > 200 and g > 180 and b < 120:
                    yellow += 1
        self.assertEqual(yellow, 0)

    def test_clean_export_path_has_no_guides(self) -> None:
        image = render_title_image(
            self._options(show_bounding_boxes=False, selected_layout_area=None)
        )
        yellow = 0
        for y in (DEFAULT_TITLE_BOX["y"], DEFAULT_SERVICE_BOX["y"], DEFAULT_SPEAKER_BOX["y"]):
            for x in range(300, 1600, 40):
                r, g, b = image.getpixel((x, y))
                if r > 200 and g > 180 and b < 120:
                    yellow += 1
        self.assertEqual(yellow, 0)


if __name__ == "__main__":
    unittest.main()
