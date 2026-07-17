from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path
from unittest import mock

from PIL import Image

from font_config import (
    DEFAULT_SERVICE_FONT_PATH,
    DEFAULT_SPEAKER_FONT_PATH,
    DEFAULT_TITLE_FONT_PATH,
    FontConfig,
    default_service_font_config,
    default_speaker_font_config,
    default_title_font_config,
    font_config_from_dict,
)
from simple_presets import load_preset, save_preset
from title_renderer import (
    BARLOW_BOLD,
    BARLOW_BOLD_ITALIC,
    DEFAULT_SERVICE_BOX,
    DEFAULT_SPEAKER_BOX,
    DEFAULT_TITLE_BOX,
    TitleImageOptions,
    render_title_image,
    text_box_from_dict,
)


def _sample_options(**kwargs) -> TitleImageOptions:
    values = {
        "day": "Friday",
        "service": "Evening",
        "service_date": date(2026, 7, 31),
        "sermon_title": "The Truth",
        "speaker_name": "Marty Clevenger",
        "service_line_box": text_box_from_dict(DEFAULT_SERVICE_BOX),
        "title_box": text_box_from_dict(DEFAULT_TITLE_BOX),
        "speaker_box": text_box_from_dict(DEFAULT_SPEAKER_BOX),
        "service_font_config": default_service_font_config(),
        "title_font_config": default_title_font_config(),
        "speaker_font_config": default_speaker_font_config(),
    }
    values.update(kwargs)
    return TitleImageOptions(**values)


class FontConfigDefaultsTest(unittest.TestCase):
    def test_service_default_font_and_no_effects(self) -> None:
        cfg = default_service_font_config()
        self.assertEqual(cfg.font_path, DEFAULT_SERVICE_FONT_PATH)
        self.assertTrue(cfg.font_path.endswith("BarlowCondensed-Bold.ttf"))
        self.assertTrue(cfg.use_font_file_default_style_only)
        self.assertFalse(cfg.artificial_bold)
        self.assertFalse(cfg.artificial_italic)
        self.assertEqual(cfg.skew_angle, 0)
        self.assertFalse(cfg.underline)
        self.assertFalse(cfg.shadow_enabled)
        self.assertFalse(cfg.outline_enabled)
        effective = cfg.effective()
        self.assertEqual(effective.skew_angle, 0)
        self.assertFalse(effective.artificial_italic)

    def test_speaker_default_font_and_no_effects(self) -> None:
        cfg = default_speaker_font_config()
        self.assertEqual(cfg.font_path, DEFAULT_SPEAKER_FONT_PATH)
        self.assertTrue(cfg.font_path.endswith("BarlowCondensed-Bold.ttf"))
        self.assertFalse(cfg.artificial_italic)
        self.assertEqual(cfg.skew_angle, 0)
        self.assertFalse(cfg.shadow_enabled)

    def test_title_default_italic_font_file_without_artificial_skew(self) -> None:
        cfg = default_title_font_config()
        self.assertEqual(cfg.font_path, DEFAULT_TITLE_FONT_PATH)
        self.assertTrue(cfg.font_path.endswith("BarlowCondensed-BoldItalic.ttf"))
        self.assertTrue(cfg.use_font_file_default_style_only)
        self.assertFalse(cfg.artificial_italic)
        self.assertEqual(cfg.skew_angle, 0)
        self.assertEqual(cfg.effective().skew_angle, 0)

    def test_effects_summary_default_style(self) -> None:
        self.assertEqual(
            default_service_font_config().effects_summary(), "default style only"
        )

    def test_effects_summary_lists_enabled(self) -> None:
        cfg = default_service_font_config()
        cfg.use_font_file_default_style_only = False
        cfg.shadow_enabled = True
        cfg.underline = True
        summary = cfg.effects_summary()
        self.assertIn("shadow", summary)
        self.assertIn("underline", summary)

    def test_reset_to_default_disables_effects(self) -> None:
        cfg = font_config_from_dict(
            {
                "font_path": "fonts/BarlowCondensed-Bold.ttf",
                "use_font_file_default_style_only": False,
                "artificial_bold": True,
                "skew_angle": 12,
                "shadow_enabled": True,
                "outline_enabled": True,
                "outline_width": 3,
            },
            role="service",
        )
        reset = default_service_font_config()
        self.assertFalse(reset.artificial_bold)
        self.assertFalse(reset.shadow_enabled)
        self.assertFalse(reset.outline_enabled)
        self.assertEqual(reset.skew_angle, 0)
        self.assertNotEqual(cfg.shadow_enabled, reset.shadow_enabled)

    def test_migrate_legacy_path_string(self) -> None:
        cfg = font_config_from_dict("fonts/BarlowCondensed-Bold.ttf", role="service")
        self.assertEqual(cfg.font_path, "fonts/BarlowCondensed-Bold.ttf")
        self.assertTrue(cfg.use_font_file_default_style_only)
        self.assertFalse(cfg.shadow_enabled)


class FontConfigRendererTest(unittest.TestCase):
    def test_render_with_default_configs(self) -> None:
        image = render_title_image(_sample_options())
        self.assertEqual(image.size, (1920, 1080))

    def test_render_with_shadow(self) -> None:
        cfg = default_service_font_config()
        cfg.use_font_file_default_style_only = False
        cfg.shadow_enabled = True
        cfg.shadow_offset_x = 6
        cfg.shadow_offset_y = 6
        image = render_title_image(_sample_options(service_font_config=cfg))
        self.assertEqual(image.size, (1920, 1080))

    def test_render_with_outline(self) -> None:
        cfg = default_title_font_config()
        cfg.use_font_file_default_style_only = False
        cfg.outline_enabled = True
        cfg.outline_width = 4
        image = render_title_image(_sample_options(title_font_config=cfg))
        self.assertEqual(image.size, (1920, 1080))

    def test_render_with_underline(self) -> None:
        cfg = default_speaker_font_config()
        cfg.use_font_file_default_style_only = False
        cfg.underline = True
        image = render_title_image(_sample_options(speaker_font_config=cfg))
        self.assertEqual(image.size, (1920, 1080))

    def test_render_with_skew(self) -> None:
        cfg = default_title_font_config()
        cfg.use_font_file_default_style_only = False
        cfg.skew_angle = 12
        image = render_title_image(_sample_options(title_font_config=cfg))
        self.assertEqual(image.size, (1920, 1080))

    def test_render_with_artificial_bold(self) -> None:
        cfg = default_service_font_config()
        cfg.use_font_file_default_style_only = False
        cfg.artificial_bold = True
        image = render_title_image(_sample_options(service_font_config=cfg))
        self.assertEqual(image.size, (1920, 1080))

    def test_missing_font_path_falls_back_safely(self) -> None:
        cfg = default_title_font_config()
        cfg.font_path = "fonts/definitely-missing-font.ttf"
        image = render_title_image(_sample_options(title_font_config=cfg))
        self.assertEqual(image.size, (1920, 1080))

    def test_section_effects_do_not_require_global_shadow(self) -> None:
        options = _sample_options()
        self.assertFalse(options.shadow_enabled)
        service = deepcopy(default_service_font_config())
        service.use_font_file_default_style_only = False
        service.shadow_enabled = True
        image = render_title_image(_sample_options(service_font_config=service))
        self.assertIsInstance(image, Image.Image)

    def test_outline_fitting_accounts_for_stroke(self) -> None:
        from title_renderer import fit_single_line_text

        if not BARLOW_BOLD.exists():
            self.skipTest("bold font missing")
        plain = fit_single_line_text(
            "FRIDAY PM 7-31-26",
            max_width=DEFAULT_SERVICE_BOX["width"] - 8,
            max_height=DEFAULT_SERVICE_BOX["height"] - 8,
            font_path=BARLOW_BOLD,
            outline_width=0,
        )
        outlined = fit_single_line_text(
            "FRIDAY PM 7-31-26",
            max_width=DEFAULT_SERVICE_BOX["width"] - 8,
            max_height=DEFAULT_SERVICE_BOX["height"] - 8,
            font_path=BARLOW_BOLD,
            outline_width=8,
        )
        # With thick outline, fitted font size should not grow vs plain.
        self.assertLessEqual(int(getattr(outlined[0], "size", 0)), int(getattr(plain[0], "size", 0)) + 1)


class FontConfigPresetTest(unittest.TestCase):
    def test_preset_saves_and_restores_font_configs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "simple_presets.json"
            with mock.patch("simple_presets.PRESETS_PATH", path), mock.patch(
                "simple_presets.DATA_DIR", Path(temp_dir)
            ):
                service_cfg = default_service_font_config()
                service_cfg.use_font_file_default_style_only = False
                service_cfg.shadow_enabled = True
                service_cfg.shadow_offset_x = 8
                title_cfg = default_title_font_config()
                title_cfg.use_font_file_default_style_only = False
                title_cfg.outline_enabled = True
                title_cfg.outline_width = 3
                speaker_cfg = default_speaker_font_config()
                speaker_cfg.use_font_file_default_style_only = False
                speaker_cfg.underline = True
                payload = {
                    "name": "Fancy",
                    "service": dict(DEFAULT_SERVICE_BOX),
                    "title": dict(DEFAULT_TITLE_BOX),
                    "speaker": dict(DEFAULT_SPEAKER_BOX),
                    "service_font_config": service_cfg.to_dict(),
                    "title_font_config": title_cfg.to_dict(),
                    "speaker_font_config": speaker_cfg.to_dict(),
                }
                save_preset(1, payload)
                loaded = load_preset(1)
                self.assertIsNotNone(loaded)
                assert loaded is not None
                self.assertTrue(loaded["service_font_config"]["shadow_enabled"])
                self.assertEqual(loaded["service_font_config"]["shadow_offset_x"], 8)
                self.assertTrue(loaded["title_font_config"]["outline_enabled"])
                self.assertEqual(loaded["title_font_config"]["outline_width"], 3)
                self.assertTrue(loaded["speaker_font_config"]["underline"])

    def test_old_preset_without_font_configs_loads_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "simple_presets.json"
            with mock.patch("simple_presets.PRESETS_PATH", path), mock.patch(
                "simple_presets.DATA_DIR", Path(temp_dir)
            ):
                payload = {
                    "name": "Legacy",
                    "service": dict(DEFAULT_SERVICE_BOX),
                    "title": dict(DEFAULT_TITLE_BOX),
                    "speaker": dict(DEFAULT_SPEAKER_BOX),
                    "service_font_path": "fonts/BarlowCondensed-Bold.ttf",
                    "title_font_path": "fonts/BarlowCondensed-BoldItalic.ttf",
                    "speaker_font_path": "fonts/BarlowCondensed-Bold.ttf",
                }
                save_preset(2, payload)
                loaded = load_preset(2)
                self.assertIsNotNone(loaded)
                assert loaded is not None
                self.assertIn("service_font_config", loaded)
                self.assertTrue(
                    loaded["service_font_config"]["use_font_file_default_style_only"]
                )
                self.assertFalse(loaded["service_font_config"]["shadow_enabled"])
                self.assertEqual(
                    loaded["title_font_config"]["font_path"],
                    "fonts/BarlowCondensed-BoldItalic.ttf",
                )


if __name__ == "__main__":
    unittest.main()
