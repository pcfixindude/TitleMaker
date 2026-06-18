from __future__ import annotations

import unittest

from font_settings import (
    AUTOMATIC_FONT_LABEL,
    default_font_settings,
    get_effective_service_font,
    get_effective_speaker_font,
    get_effective_title_font,
    migrate_font_settings,
)


class FontSettingsTest(unittest.TestCase):
    def test_defaults_make_title_and_speaker_match_service_font(self) -> None:
        settings = default_font_settings("Service.ttf")

        self.assertTrue(settings["title_font_matches_service_font"])
        self.assertTrue(settings["speaker_font_matches_service_font"])
        self.assertEqual(get_effective_title_font(settings), "Service.ttf")
        self.assertEqual(get_effective_speaker_font(settings), "Service.ttf")

    def test_effective_title_font_uses_custom_when_matching_disabled(self) -> None:
        settings = default_font_settings("Service.ttf")
        settings["title_font_matches_service_font"] = False
        settings["title_font"] = "Title.ttf"

        self.assertEqual(get_effective_title_font(settings), "Title.ttf")

    def test_effective_speaker_font_uses_custom_when_matching_disabled(self) -> None:
        settings = default_font_settings("Service.ttf")
        settings["speaker_font_matches_service_font"] = False
        settings["speaker_font"] = "Speaker.ttf"

        self.assertEqual(get_effective_speaker_font(settings), "Speaker.ttf")

    def test_old_single_font_setting_migrates_to_service_font(self) -> None:
        settings = migrate_font_settings({"font_label": "Old.ttf"})

        self.assertEqual(get_effective_service_font(settings), "Old.ttf")
        self.assertEqual(get_effective_title_font(settings), "Old.ttf")
        self.assertEqual(get_effective_speaker_font(settings), "Old.ttf")

    def test_missing_font_settings_use_safe_default(self) -> None:
        settings = migrate_font_settings({})

        self.assertEqual(get_effective_service_font(settings), AUTOMATIC_FONT_LABEL)


if __name__ == "__main__":
    unittest.main()
