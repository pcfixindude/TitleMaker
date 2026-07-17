from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import simple_presets
from simple_presets import (
    atomic_write_json,
    delete_default_settings,
    get_factory_default_settings,
    load_default_settings,
    load_preset_slot,
    load_simple_presets,
    normalize_preset_settings,
    save_default_settings,
    save_preset_slot,
)


def _minimal_boxes(**overrides) -> dict:
    payload = {
        "name": "Test",
        "service": {
            "x": 280,
            "y": 95,
            "width": 1360,
            "height": 90,
            "font_size": 86,
            "auto_size": True,
        },
        "title": {
            "x": 30,
            "y": 195,
            "width": 1860,
            "height": 460,
            "font_size": 400,
            "auto_size": False,
        },
        "speaker": {
            "x": 280,
            "y": 665,
            "width": 1360,
            "height": 90,
            "font_size": 80,
            "auto_size": True,
        },
    }
    payload.update(overrides)
    return payload


class AtomicWriteTest(unittest.TestCase):
    def test_atomic_write_creates_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "out.json"
            atomic_write_json(path, {"ok": True, "n": 1})
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded, {"ok": True, "n": 1})


class PersistentPresetTest(unittest.TestCase):
    def test_saving_preset_creates_simple_presets_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            presets_path = data_dir / "simple_presets.json"
            with mock.patch.object(simple_presets, "DATA_DIR", data_dir), mock.patch.object(
                simple_presets, "PRESETS_PATH", presets_path
            ):
                self.assertFalse(presets_path.exists())
                save_preset_slot(1, _minimal_boxes(name="Booth A"))
                self.assertTrue(presets_path.exists())
                store = load_simple_presets()
                self.assertIsNotNone(store["slots"]["1"])
                loaded = load_preset_slot(1)
                assert loaded is not None
                self.assertEqual(loaded["name"], "Booth A")
                self.assertEqual(loaded["title"]["y"], 195)
                self.assertFalse(loaded["title"]["auto_size"])

    def test_loading_preset_restores_background_fonts_and_spacing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            with mock.patch.object(simple_presets, "DATA_DIR", data_dir), mock.patch.object(
                simple_presets, "PRESETS_PATH", data_dir / "simple_presets.json"
            ):
                payload = _minimal_boxes(
                    name="Full",
                    background_label="open_bible.png",
                    title_line_spacing=-25,
                    show_bounding_boxes=False,
                    service_font_config={
                        "font_path": "fonts/BarlowCondensed-Bold.ttf",
                        "use_font_file_default_style_only": False,
                        "shadow_enabled": True,
                        "shadow_offset_x": 6,
                    },
                    title_font_config={
                        "font_path": "fonts/BarlowCondensed-BoldItalic.ttf",
                        "use_font_file_default_style_only": False,
                        "outline_enabled": True,
                        "outline_width": 3,
                    },
                )
                save_preset_slot(2, payload)
                loaded = load_preset_slot(2)
                assert loaded is not None
                self.assertEqual(loaded["background_label"], "open_bible.png")
                self.assertEqual(loaded["title_line_spacing"], -25)
                self.assertFalse(loaded["show_bounding_boxes"])
                self.assertTrue(loaded["service_font_config"]["shadow_enabled"])
                self.assertEqual(loaded["service_font_config"]["shadow_offset_x"], 6)
                self.assertTrue(loaded["title_font_config"]["outline_enabled"])
                self.assertEqual(loaded["title_font_config"]["outline_width"], 3)

    def test_old_preset_missing_fields_migrates_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            with mock.patch.object(simple_presets, "DATA_DIR", data_dir), mock.patch.object(
                simple_presets, "PRESETS_PATH", data_dir / "simple_presets.json"
            ):
                save_preset_slot(
                    3,
                    {
                        "name": "Legacy",
                        "service": {"x": 1, "y": 2, "width": 3, "height": 4},
                        "title": {"x": 5, "y": 6, "width": 7, "height": 8},
                        "speaker": {"x": 9, "y": 10, "width": 11, "height": 12},
                        "service_font_path": "fonts/BarlowCondensed-Bold.ttf",
                    },
                )
                loaded = load_preset_slot(3)
                assert loaded is not None
                self.assertEqual(loaded["title_line_spacing"], 0)
                self.assertIn("service_font_config", loaded)
                self.assertTrue(
                    loaded["service_font_config"]["use_font_file_default_style_only"]
                )
                self.assertFalse(loaded["service_font_config"]["shadow_enabled"])
                self.assertTrue(loaded["show_bounding_boxes"])


class DefaultSettingsTest(unittest.TestCase):
    def test_save_and_load_default_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            defaults_path = data_dir / "default_settings.json"
            with mock.patch.object(simple_presets, "DATA_DIR", data_dir), mock.patch.object(
                simple_presets, "DEFAULT_SETTINGS_PATH", defaults_path
            ):
                payload = _minimal_boxes(
                    name="Startup Default",
                    title_line_spacing=-10,
                    background_label="Generated blue/gray background",
                )
                saved = save_default_settings(payload)
                self.assertTrue(defaults_path.exists())
                self.assertEqual(saved["title_line_spacing"], -10)
                loaded, warning = load_default_settings()
                self.assertIsNone(warning)
                assert loaded is not None
                self.assertEqual(loaded["title"]["width"], 1860)
                self.assertEqual(loaded["title_line_spacing"], -10)
                self.assertEqual(
                    loaded["background_label"], "Generated blue/gray background"
                )

    def test_corrupted_default_settings_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            defaults_path = data_dir / "default_settings.json"
            defaults_path.write_text("{not-json", encoding="utf-8")
            with mock.patch.object(simple_presets, "DATA_DIR", data_dir), mock.patch.object(
                simple_presets, "DEFAULT_SETTINGS_PATH", defaults_path
            ):
                loaded, warning = load_default_settings()
                self.assertIsNone(loaded)
                self.assertIsNotNone(warning)
                self.assertIn("unreadable", warning.lower())

    def test_invalid_default_settings_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            defaults_path = data_dir / "default_settings.json"
            defaults_path.write_text(json.dumps({"name": "bad"}), encoding="utf-8")
            with mock.patch.object(simple_presets, "DATA_DIR", data_dir), mock.patch.object(
                simple_presets, "DEFAULT_SETTINGS_PATH", defaults_path
            ):
                loaded, warning = load_default_settings()
                self.assertIsNone(loaded)
                self.assertIsNotNone(warning)

    def test_factory_defaults_and_delete(self) -> None:
        factory = get_factory_default_settings()
        self.assertEqual(factory["title_line_spacing"], 0)
        self.assertTrue(factory["show_bounding_boxes"])
        self.assertIn("service_font_config", factory)
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            defaults_path = data_dir / "default_settings.json"
            with mock.patch.object(simple_presets, "DATA_DIR", data_dir), mock.patch.object(
                simple_presets, "DEFAULT_SETTINGS_PATH", defaults_path
            ):
                save_default_settings(_minimal_boxes())
                self.assertTrue(defaults_path.exists())
                self.assertTrue(delete_default_settings())
                self.assertFalse(defaults_path.exists())
                self.assertFalse(delete_default_settings())

    def test_normalize_fills_missing_fields(self) -> None:
        normalized = normalize_preset_settings(
            {
                "service": {"x": 1, "y": 2, "width": 3, "height": 4},
                "title": {"x": 5, "y": 6, "width": 7, "height": 8},
                "speaker": {"x": 9, "y": 10, "width": 11, "height": 12},
            }
        )
        self.assertEqual(normalized["title_line_spacing"], 0)
        self.assertTrue(normalized["service_font_config"]["font_path"])
        self.assertFalse(normalized["title_font_config"]["shadow_enabled"])


class AppPersistenceUiTest(unittest.TestCase):
    def test_app_has_default_and_factory_controls(self) -> None:
        source = Path(__file__).resolve().parents[1].joinpath("app.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Save Current Settings as Default", source)
        self.assertIn("Reset to Factory Defaults", source)
        self.assertIn("Delete Saved Default Settings", source)
        self.assertIn("Preset loaded.", source)
        self.assertIn("Current settings saved as startup default.", source)
        self.assertIn("load_default_settings", source)


if __name__ == "__main__":
    unittest.main()
