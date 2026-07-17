from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from font_discovery import (
    BARLOW_BOLD_ITALIC_NAME,
    BARLOW_BOLD_NAME,
    discover_fonts,
    resolve_selected_font,
    system_font_dirs,
)
from simple_presets import load_preset, save_preset
from title_renderer import (
    BARLOW_BOLD,
    BARLOW_BOLD_ITALIC,
    DEFAULT_SERVICE_BOX,
    DEFAULT_SPEAKER_BOX,
    DEFAULT_TITLE_BOX,
    TEXT_COLOR_WHITE,
    TitleImageOptions,
    render_title_image,
    text_box_from_dict,
)


class FontDiscoveryTest(unittest.TestCase):
    def test_project_fonts_are_discovered(self) -> None:
        fonts = discover_fonts(include_system=False)
        names = {choice.path.name for choice in fonts}
        self.assertIn(BARLOW_BOLD_NAME, names)
        self.assertIn(BARLOW_BOLD_ITALIC_NAME, names)

    def test_system_font_discovery_does_not_crash_if_folders_missing(self) -> None:
        with mock.patch(
            "font_discovery.system_font_dirs",
            return_value=[Path("/definitely/missing/fonts/dir")],
        ):
            fonts = discover_fonts(include_system=True)
        self.assertIsInstance(fonts, list)
        self.assertTrue(any(choice.source == "project" for choice in fonts))

    def test_system_font_dirs_helper_is_safe(self) -> None:
        dirs = system_font_dirs()
        self.assertIsInstance(dirs, list)

    def test_default_role_resolution(self) -> None:
        catalog = discover_fonts(include_system=False)
        service = resolve_selected_font(None, role="service", catalog=catalog)
        title = resolve_selected_font(None, role="title", catalog=catalog)
        speaker = resolve_selected_font(None, role="speaker", catalog=catalog)
        self.assertEqual(service, BARLOW_BOLD)
        self.assertEqual(title, BARLOW_BOLD_ITALIC)
        self.assertEqual(speaker, BARLOW_BOLD)

    def test_missing_selected_font_falls_back_safely(self) -> None:
        catalog = discover_fonts(include_system=False)
        resolved = resolve_selected_font(
            "fonts/does-not-exist.ttf",
            role="title",
            catalog=catalog,
        )
        self.assertEqual(resolved, BARLOW_BOLD_ITALIC)


class FontRenderAndPresetTest(unittest.TestCase):
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
            "service_font_path": BARLOW_BOLD,
            "title_font_path": BARLOW_BOLD_ITALIC,
            "speaker_font_path": BARLOW_BOLD,
        }
        values.update(kwargs)
        return TitleImageOptions(**values)

    def test_renderer_accepts_different_fonts_per_section(self) -> None:
        image = render_title_image(self._options())
        self.assertEqual(image.size, (1920, 1080))

    def test_render_with_and_without_boxes(self) -> None:
        with_boxes = render_title_image(self._options(show_bounding_boxes=True))
        without = render_title_image(self._options(show_bounding_boxes=False))
        self.assertEqual(with_boxes.size, (1920, 1080))
        self.assertEqual(without.size, (1920, 1080))

    def test_text_remains_white_no_shadow(self) -> None:
        options = self._options()
        self.assertEqual(options.text_color, TEXT_COLOR_WHITE)
        self.assertFalse(options.shadow_enabled)

    def test_preset_save_load_includes_font_selections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "simple_presets.json"
            with mock.patch("simple_presets.PRESETS_PATH", path), mock.patch(
                "simple_presets.DATA_DIR", Path(temp_dir)
            ):
                payload = {
                    "name": "Fonts A",
                    "service": {
                        "x": 280,
                        "y": 95,
                        "width": 1360,
                        "height": 90,
                    },
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
                    "service_font_path": "fonts/BarlowCondensed-Bold.ttf",
                    "title_font_path": "fonts/BarlowCondensed-BoldItalic.ttf",
                    "speaker_font_path": "fonts/BarlowCondensed-Bold.ttf",
                }
                save_preset(1, payload)
                loaded = load_preset(1)
                self.assertIsNotNone(loaded)
                assert loaded is not None
                self.assertEqual(
                    loaded["service_font_path"], "fonts/BarlowCondensed-Bold.ttf"
                )
                self.assertEqual(
                    loaded["title_font_path"],
                    "fonts/BarlowCondensed-BoldItalic.ttf",
                )

    def test_old_presets_without_font_fields_load_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "simple_presets.json"
            with mock.patch("simple_presets.PRESETS_PATH", path), mock.patch(
                "simple_presets.DATA_DIR", Path(temp_dir)
            ):
                payload = {
                    "name": "Legacy",
                    "service": {
                        "x": 280,
                        "y": 95,
                        "width": 1360,
                        "height": 90,
                    },
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
                }
                save_preset(2, payload)
                loaded = load_preset(2)
                self.assertIsNotNone(loaded)
                assert loaded is not None
                self.assertTrue(loaded["service_font_path"])
                self.assertTrue(loaded["title_font_path"])
                self.assertTrue(loaded["speaker_font_path"])

    def test_missing_preferred_font_path_does_not_crash_render(self) -> None:
        image = render_title_image(
            self._options(
                service_font_path=Path("fonts/missing-service.ttf"),
                title_font_path=Path("fonts/missing-title.ttf"),
                speaker_font_path=Path("fonts/missing-speaker.ttf"),
            )
        )
        self.assertEqual(image.size, (1920, 1080))


if __name__ == "__main__":
    unittest.main()
