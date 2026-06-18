from __future__ import annotations

import unittest
from datetime import date

from presets import (
    GENERATED_BACKGROUND_LABEL,
    PRESETS_DIR,
    list_presets,
    load_preset,
    save_preset,
    settings_from_preset,
)
from title_renderer import TitleImageOptions, export_filename, render_title_image


class PresetsSmokeTest(unittest.TestCase):
    def test_builtin_presets_are_available(self) -> None:
        preset_names = {preset["name"] for preset in list_presets()}

        self.assertIn("Monark Blue Gray", preset_names)
        self.assertIn("Plain Black Text", preset_names)
        self.assertIn("Bold Service Title", preset_names)

    def test_preset_can_be_saved_and_loaded(self) -> None:
        preset_path = save_preset(
            "Smoke Test Preset",
            {
                "font_choice": "Automatic fallback (Bebas Neue/system)",
                "auto_size": False,
                "title_font_size": 144,
                "text_color": "#222222",
                "background_choice": GENERATED_BACKGROUND_LABEL,
                "title_position": [960, 500],
                "service_line_position": [960, 100],
                "speaker_line_position": [960, 920],
                "text_alignment": "center",
                "shadow_enabled": False,
                "show_service_line": True,
            },
        )

        try:
            loaded = load_preset(preset_path)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["name"], "Smoke Test Preset")
            self.assertEqual(loaded["title_font_size"], 144)
            self.assertFalse(loaded["shadow_enabled"])
        finally:
            preset_path.unlink(missing_ok=True)

    def test_old_preset_without_skew_angle_loads_safely(self) -> None:
        loaded = settings_from_preset(
            {
                "name": "Old Preset",
                "font_choice": "Automatic fallback (Bebas Neue/system)",
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

        self.assertIn("skew_angle", loaded["title_box"])
        self.assertEqual(loaded["title_box"]["max_font_size"], 400)
        self.assertEqual(loaded["service_font"], "Automatic fallback (Bebas Neue/system)")
        self.assertTrue(loaded["title_font_matches_service_font"])
        self.assertTrue(loaded["speaker_font_matches_service_font"])

    def test_new_preset_saves_and_loads_skew_angle(self) -> None:
        preset_path = save_preset(
            "Smoke Skew Preset",
            {
                "font_choice": "Automatic fallback (Bebas Neue/system)",
                "title_box": {
                    "x": 280,
                    "y": 325,
                    "width": 1360,
                    "height": 430,
                    "font_size": 300,
                    "max_font_size": 400,
                    "auto_size": True,
                    "alignment": "center",
                    "line_spacing": 0.9,
                    "skew_angle": 12.5,
                },
            },
        )

        try:
            loaded = load_preset(preset_path)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["title_box"]["skew_angle"], 12.5)
            self.assertEqual(loaded["title_box"]["max_font_size"], 400)
        finally:
            preset_path.unlink(missing_ok=True)

    def test_new_preset_saves_and_loads_separate_fonts(self) -> None:
        preset_path = save_preset(
            "Smoke Fonts Preset",
            {
                "service_font": "Service.ttf",
                "title_font": "Title.ttf",
                "speaker_font": "Speaker.ttf",
                "title_font_matches_service_font": False,
                "speaker_font_matches_service_font": False,
            },
        )

        try:
            loaded = load_preset(preset_path)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["service_font"], "Service.ttf")
            self.assertEqual(loaded["title_font"], "Title.ttf")
            self.assertEqual(loaded["speaker_font"], "Speaker.ttf")
            self.assertFalse(loaded["title_font_matches_service_font"])
            self.assertFalse(loaded["speaker_font_matches_service_font"])
        finally:
            preset_path.unlink(missing_ok=True)

    def test_loaded_preset_can_render_title_image(self) -> None:
        preset_path = PRESETS_DIR / "bold_service_title.json"
        preset = load_preset(preset_path)

        self.assertIsNotNone(preset)
        assert preset is not None
        settings = settings_from_preset(preset)

        options = TitleImageOptions(
            day="Friday",
            service="AM",
            service_date=date(2026, 7, 18),
            sermon_title="Keep Drinking",
            speaker_name="Bro. Marty Clevenger",
            text_color=settings["text_color"],
            auto_size=settings["auto_size"],
            title_font_size=settings["title_font_size"],
            top_line_position=tuple(settings["service_line_position"]),
            title_position=tuple(settings["title_position"]),
            bottom_line_position=tuple(settings["speaker_line_position"]),
            text_alignment=settings["text_alignment"],
            shadow_enabled=settings["shadow_enabled"],
            show_service_line=settings["show_service_line"],
        )

        image = render_title_image(options)

        self.assertEqual(image.size, (1920, 1080))
        self.assertEqual(
            export_filename(options),
            "2026-07-18_FRIDAY_AM_KEEP_DRINKING.png",
        )


if __name__ == "__main__":
    unittest.main()
