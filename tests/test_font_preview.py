from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image

from font_discovery import (
    BARLOW_BOLD_ITALIC_NAME,
    BARLOW_BOLD_NAME,
    FontChoice,
    discover_fonts,
    filter_fonts,
    get_font_display_name,
)
from font_preview import (
    render_font_sample,
    safely_render_font_sample,
    sample_text_for_role,
)
from title_renderer import BARLOW_BOLD, BARLOW_BOLD_ITALIC


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FontPreviewTest(unittest.TestCase):
    def test_sample_text_by_role(self) -> None:
        self.assertEqual(sample_text_for_role("service"), "FRIDAY PM 7-31-26")
        self.assertEqual(sample_text_for_role("speaker"), "FRIDAY PM 7-31-26")
        self.assertEqual(sample_text_for_role("title"), "IS GOD REAL?")

    def test_render_barlow_bold_sample(self) -> None:
        if not BARLOW_BOLD.exists():
            self.skipTest("BarlowCondensed-Bold.ttf missing")
        image = render_font_sample(BARLOW_BOLD, "FRIDAY PM 7-31-26")
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.size[0], 520)
        self.assertGreater(image.size[1], 20)

    def test_render_barlow_bold_italic_sample(self) -> None:
        if not BARLOW_BOLD_ITALIC.exists():
            self.skipTest("BarlowCondensed-BoldItalic.ttf missing")
        image = render_font_sample(BARLOW_BOLD_ITALIC, "IS GOD REAL?")
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.size, (520, 72))

    def test_missing_font_sample_falls_back_safely(self) -> None:
        image = safely_render_font_sample(
            PROJECT_ROOT / "fonts" / "definitely-missing.ttf",
            "SAMPLE",
            label="missing.ttf",
        )
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.size[0], 520)


class FontFilterTest(unittest.TestCase):
    def test_filter_returns_project_fonts_first(self) -> None:
        fonts = discover_fonts(include_system=False)
        if not fonts:
            self.skipTest("no project fonts")
        filtered = filter_fonts(fonts, "barlow", limit=10)
        self.assertTrue(filtered)
        self.assertTrue(all(choice.source == "project" for choice in filtered))
        names = {choice.path.name for choice in filtered}
        self.assertTrue(
            BARLOW_BOLD_NAME in names or BARLOW_BOLD_ITALIC_NAME in names
        )

    def test_filter_limit(self) -> None:
        fonts = discover_fonts(include_system=False)
        filtered = filter_fonts(fonts, "", limit=2)
        self.assertLessEqual(len(filtered), 2)

    def test_get_font_display_name(self) -> None:
        choice = FontChoice(
            font_id="fonts/BarlowCondensed-Bold.ttf",
            label="BarlowCondensed-Bold.ttf",
            path=BARLOW_BOLD,
            source="project",
        )
        self.assertEqual(get_font_display_name(choice), "BarlowCondensed-Bold.ttf")
        self.assertEqual(
            get_font_display_name("fonts/BarlowCondensed-Bold.ttf"),
            "BarlowCondensed-Bold.ttf",
        )


class FontEditorUiCopyTest(unittest.TestCase):
    def test_advanced_text_styling_label_in_app(self) -> None:
        source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("Advanced Text Styling", source)
        self.assertNotIn("Fancy options", source)
        self.assertIn("font_editor_selected_section", source)
        self.assertIn("_render_font_picker_rows", source)

    def test_readme_mentions_inline_font_settings(self) -> None:
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Advanced Text Styling", readme)
        self.assertIn("inline", readme.lower())
        self.assertNotIn("Fancy options", readme)


if __name__ == "__main__":
    unittest.main()
