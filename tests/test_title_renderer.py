from __future__ import annotations

import unittest

from title_renderer import fit_title_lines_for_test


class TitleRendererTest(unittest.TestCase):
    def test_manual_line_breaks_are_preserved_when_fitting_title(self) -> None:
        lines = fit_title_lines_for_test(
            "THE LOVE OF GOD\nIN A DARK WORLD",
            max_width=1800,
            font_size=90,
        )

        self.assertEqual(lines, ["THE LOVE OF GOD", "IN A DARK WORLD"])


if __name__ == "__main__":
    unittest.main()
