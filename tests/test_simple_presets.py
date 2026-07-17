from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import simple_presets


class SimplePresetsTest(unittest.TestCase):
    def test_save_and_load_preset_slot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "simple_presets.json"
            with mock.patch.object(simple_presets, "PRESETS_PATH", path), mock.patch.object(
                simple_presets, "DATA_DIR", Path(temp_dir)
            ):
                payload = {
                    "name": "Booth A",
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
                simple_presets.save_preset(1, payload)
                loaded = simple_presets.load_preset(1)
                self.assertIsNotNone(loaded)
                assert loaded is not None
                self.assertEqual(loaded["name"], "Booth A")
                self.assertEqual(loaded["title"]["y"], 195)
                self.assertFalse(loaded["title"]["auto_size"])
                self.assertTrue(loaded["service_font_path"])
                self.assertTrue(loaded["title_font_path"])
                self.assertTrue(loaded["speaker_font_path"])
                self.assertIsNone(simple_presets.load_preset(2))
                labels = simple_presets.preset_slot_labels()
                self.assertEqual(labels[1], "Booth A")
                self.assertEqual(labels[2], "Empty 2")


if __name__ == "__main__":
    unittest.main()
