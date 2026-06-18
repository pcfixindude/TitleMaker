from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from export_settings import (
    BUILT_IN_EXPORT_TARGETS,
    ExportTarget,
    export_filename_for_target,
    migrate_export_settings,
    render_for_export,
    resolve_export_target,
    sanitize_suffix,
    scale_design_box,
)
from persistence import load_settings, save_settings
from title_renderer import TitleImageOptions


class ExportSettingsTest(unittest.TestCase):
    def test_builtin_export_target_definitions(self) -> None:
        self.assertEqual((BUILT_IN_EXPORT_TARGETS["Stream 1080p"].width, BUILT_IN_EXPORT_TARGETS["Stream 1080p"].height), (1920, 1080))
        self.assertEqual((BUILT_IN_EXPORT_TARGETS["YouTube Thumbnail"].width, BUILT_IN_EXPORT_TARGETS["YouTube Thumbnail"].height), (1280, 720))
        self.assertEqual((BUILT_IN_EXPORT_TARGETS["Facebook / Instagram Square"].width, BUILT_IN_EXPORT_TARGETS["Facebook / Instagram Square"].height), (1080, 1080))
        self.assertEqual((BUILT_IN_EXPORT_TARGETS["Facebook / Instagram Story or Reel"].width, BUILT_IN_EXPORT_TARGETS["Facebook / Instagram Story or Reel"].height), (1080, 1920))

    def test_export_target_suffix_is_added_to_filename(self) -> None:
        options = _sample_options()
        filename = export_filename_for_target(options, BUILT_IN_EXPORT_TARGETS["YouTube Thumbnail"])

        self.assertEqual(filename, "2026-07-31_FRIDAY_PM_IS_GOD_REAL_youtube_thumb.png")

    def test_custom_suffix_is_sanitized(self) -> None:
        self.assertEqual(sanitize_suffix("Custom 1600 x 900!"), "custom_1600_x_900")

    def test_custom_target_resolves_suffix(self) -> None:
        target = resolve_export_target(
            {
                "selected_export_target": "Custom",
                "custom_export_width": 1600,
                "custom_export_height": 900,
                "custom_export_suffix": "Custom 1600x900",
            }
        )

        self.assertEqual((target.width, target.height), (1600, 900))
        self.assertEqual(target.suffix, "custom_1600x900")

    def test_1920_boxes_remain_unchanged(self) -> None:
        box = {"x": 280, "y": 325, "width": 1360, "height": 430, "font_size": 200}

        self.assertEqual(scale_design_box(box, 1920, 1080), box)

    def test_1280_720_scales_box_and_font(self) -> None:
        box = {"x": 300, "y": 150, "width": 600, "height": 300, "font_size": 90}

        scaled = scale_design_box(box, 1280, 720)

        self.assertEqual(scaled["x"], 200)
        self.assertEqual(scaled["y"], 100)
        self.assertEqual(scaled["width"], 400)
        self.assertEqual(scaled["height"], 200)
        self.assertEqual(scaled["font_size"], 60)

    def test_renderer_exports_multiple_target_sizes(self) -> None:
        options = _sample_options()
        for target in (
            BUILT_IN_EXPORT_TARGETS["Stream 1080p"],
            BUILT_IN_EXPORT_TARGETS["YouTube Thumbnail"],
            BUILT_IN_EXPORT_TARGETS["Facebook / Instagram Square"],
            BUILT_IN_EXPORT_TARGETS["Facebook / Instagram Story or Reel"],
        ):
            with self.subTest(target=target.name):
                image = render_for_export(options, target)
                self.assertEqual(image.size, (target.width, target.height))

    def test_square_and_vertical_targets_do_not_crash(self) -> None:
        options = _sample_options()
        square = render_for_export(options, ExportTarget("Square", 1080, 1080, "square", "1:1"))
        vertical = render_for_export(options, ExportTarget("Vertical", 1080, 1920, "vertical", "9:16"))

        self.assertEqual(square.size, (1080, 1080))
        self.assertEqual(vertical.size, (1080, 1920))

    def test_old_settings_default_to_stream_1080p(self) -> None:
        settings = migrate_export_settings({})

        self.assertEqual(settings["selected_export_target"], "Stream 1080p")

    def test_new_settings_save_and_load_export_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            save_settings(
                {
                    "selected_export_target": "Custom",
                    "custom_export_width": 1600,
                    "custom_export_height": 900,
                    "custom_export_suffix": "custom_1600x900",
                    "export_layout_mode": "Fill/crop",
                    "multi_target_selection": ["Stream 1080p", "YouTube Thumbnail"],
                },
                path,
            )

            loaded = load_settings(path)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            migrated = migrate_export_settings(loaded)
            self.assertEqual(migrated["selected_export_target"], "Custom")
            self.assertEqual(migrated["custom_export_width"], 1600)
            self.assertEqual(migrated["export_layout_mode"], "Fill/crop")


def _sample_options() -> TitleImageOptions:
    return TitleImageOptions(
        day="Friday",
        service="Evening",
        service_date=date(2026, 7, 31),
        sermon_title="Is God Real?",
        speaker_name="Bro. Speaker",
    )


if __name__ == "__main__":
    unittest.main()
