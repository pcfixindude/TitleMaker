from __future__ import annotations

import unittest

from booth_mode import advanced_sections_default_collapsed
from presets import (
    default_preset_name,
    delete_preset,
    is_builtin_preset,
    list_presets,
    save_preset,
)


class BoothUiHelpersTest(unittest.TestCase):
    def test_advanced_sections_default_collapsed(self) -> None:
        self.assertTrue(advanced_sections_default_collapsed())


class PresetDeletionTest(unittest.TestCase):
    def test_builtin_preset_is_not_deletable_by_default(self) -> None:
        self.assertTrue(is_builtin_preset("Monark Blue Gray"))
        result = delete_preset("Monark Blue Gray")
        self.assertFalse(result["deleted"])
        self.assertEqual(result["reason"], "builtin_protected")
        names = {preset["name"] for preset in list_presets()}
        self.assertIn("Monark Blue Gray", names)

    def test_user_preset_can_be_deleted(self) -> None:
        path = save_preset(
            "Temp Delete Me Preset",
            {"text_color": "#ABCDEF", "shadow_enabled": False},
        )
        try:
            result = delete_preset("Temp Delete Me Preset")
            self.assertTrue(result["deleted"])
            self.assertFalse(path.exists())
            names = {preset["name"] for preset in list_presets()}
            self.assertNotIn("Temp Delete Me Preset", names)
        finally:
            path.unlink(missing_ok=True)

    def test_deleting_active_preset_reports_default_fallback(self) -> None:
        path = save_preset("Active Delete Fallback", {"text_color": "#111111"})
        try:
            result = delete_preset("Active Delete Fallback")
            self.assertTrue(result["deleted"])
            self.assertEqual(result["fallback_name"], default_preset_name())
            self.assertEqual(default_preset_name(), "Monark Blue Gray")
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
