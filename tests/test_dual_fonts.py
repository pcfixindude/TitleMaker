from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from title_renderer import (
    DEFAULT_SERVICE_FONT,
    DEFAULT_TITLE_FONT,
    BARLOW_BOLD,
    BARLOW_BOLD_ITALIC,
    DEFAULT_SERVICE_BOX,
    DEFAULT_SPEAKER_BOX,
    DEFAULT_TITLE_BOX,
    TEXT_COLOR_WHITE,
    TitleImageOptions,
    render_title_image,
    resolve_service_font_path,
    resolve_speaker_font_path,
    resolve_title_font_path,
    text_box_from_dict,
)


class DualFontResolveTest(unittest.TestCase):
    def test_title_renderer_exports_barlow_constants(self) -> None:
        import title_renderer as tr

        self.assertTrue(hasattr(tr, "BARLOW_BOLD"))
        self.assertTrue(hasattr(tr, "BARLOW_BOLD_ITALIC"))
        self.assertEqual(tr.BARLOW_BOLD.name, "BarlowCondensed-Bold.ttf")
        self.assertEqual(tr.BARLOW_BOLD_ITALIC.name, "BarlowCondensed-BoldItalic.ttf")
        self.assertEqual(tr.DEFAULT_SERVICE_FONT, tr.BARLOW_BOLD)
        self.assertEqual(tr.DEFAULT_TITLE_FONT, tr.BARLOW_BOLD_ITALIC)
        self.assertEqual(tr.DEFAULT_SPEAKER_FONT, tr.BARLOW_BOLD)

    def test_app_imports_title_renderer_successfully(self) -> None:
        # Verify the exact names app.py / callers need are importable.
        from title_renderer import (
            BARLOW_BOLD,
            BARLOW_BOLD_ITALIC,
            DEFAULT_SERVICE_FONT,
            DEFAULT_TITLE_FONT,
        )

        self.assertTrue(str(BARLOW_BOLD).endswith("BarlowCondensed-Bold.ttf"))
        self.assertTrue(str(BARLOW_BOLD_ITALIC).endswith("BarlowCondensed-BoldItalic.ttf"))
        self.assertEqual(DEFAULT_SERVICE_FONT, BARLOW_BOLD)
        self.assertEqual(DEFAULT_TITLE_FONT, BARLOW_BOLD_ITALIC)

        source = Path(__file__).resolve().parents[1].joinpath("app.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Font Choices", source)
        self.assertIn("simple_service_font_select", source)
        self.assertIn("simple_title_font_select", source)
        self.assertIn("simple_speaker_font_select", source)
        self.assertIn("resolve_selected_font", source)

    def test_service_font_resolves_to_barlow_bold(self) -> None:
        if not BARLOW_BOLD.exists():
            self.skipTest("BarlowCondensed-Bold.ttf not present")
        self.assertEqual(resolve_service_font_path(), BARLOW_BOLD)

    def test_speaker_font_resolves_to_barlow_bold(self) -> None:
        if not BARLOW_BOLD.exists():
            self.skipTest("BarlowCondensed-Bold.ttf not present")
        self.assertEqual(resolve_speaker_font_path(), BARLOW_BOLD)

    def test_title_font_resolves_to_barlow_bold_italic(self) -> None:
        if not BARLOW_BOLD_ITALIC.exists():
            self.skipTest("BarlowCondensed-BoldItalic.ttf not present")
        self.assertEqual(resolve_title_font_path(), BARLOW_BOLD_ITALIC)

    def test_missing_bold_falls_back_safely(self) -> None:
        missing = Path("/tmp/definitely-missing-barlow-bold.ttf")
        with mock.patch("title_renderer.BARLOW_BOLD", missing):
            resolved = resolve_service_font_path()
        self.assertIsNotNone(resolved)
        if BARLOW_BOLD_ITALIC.exists():
            self.assertEqual(resolved, BARLOW_BOLD_ITALIC)

    def test_missing_bold_italic_falls_back_safely(self) -> None:
        missing = Path("/tmp/definitely-missing-barlow-bold-italic.ttf")
        with mock.patch("title_renderer.BARLOW_BOLD_ITALIC", missing):
            resolved = resolve_title_font_path()
        self.assertIsNotNone(resolved)
        if BARLOW_BOLD.exists():
            self.assertEqual(resolved, BARLOW_BOLD)

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

    def test_render_with_and_without_bounding_boxes(self) -> None:
        with_boxes = render_title_image(self._options(show_bounding_boxes=True))
        without = render_title_image(self._options(show_bounding_boxes=False))
        self.assertEqual(with_boxes.size, (1920, 1080))
        self.assertEqual(without.size, (1920, 1080))

    def test_text_remains_white_with_no_shadow(self) -> None:
        options = self._options()
        self.assertEqual(options.text_color, TEXT_COLOR_WHITE)
        self.assertFalse(options.shadow_enabled)
        image = render_title_image(options)
        self.assertEqual(image.size, (1920, 1080))


if __name__ == "__main__":
    unittest.main()
