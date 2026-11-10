"""Pure-Python checks for the canonical Trybatec design tokens (#70).

The checks validate declared reference pairs, NOT rendered WCAG conformance:
actual Home Assistant themes, contrast, icons and focus still need manual tests.
"""
from __future__ import annotations

from pathlib import Path
import unittest

PANEL = Path(__file__).resolve().parents[1] / "custom_components" / "trybatec" / "panel" / "trybatec-panel.js"

PALETTE = {
    "ef": ("#0A84D8", "#075A9B", "#E8F3FC", "#65B8FA", "#18334B"),
    "ecs": ("#C73A5C", "#A9234A", "#FCE9F0", "#FF7897", "#43232F"),
    "cet": ("#E0A126", "#805500", "#FBF3DE", "#FFD166", "#3F3218"),
    "green": ("#4E9E4A", "#286C32", "#EBF7EC", "#8ADD8F", "#203A29"),
}

def relative_luminance(color: str) -> float:
    channels = [int(color[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return sum(v * w for v, w in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))

def contrast(a: str, b: str) -> float:
    upper, lower = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (upper + 0.05) / (lower + 0.05)

class PaletteTests(unittest.TestCase):
    def test_reference_pairs_exceed_wcag_aa_text(self) -> None:
        for label, (_, light_fg, light_bg, dark_fg, dark_bg) in PALETTE.items():
            with self.subTest(fluid=label, theme="light"):
                self.assertGreaterEqual(contrast(light_fg, light_bg), 4.5)
            with self.subTest(fluid=label, theme="dark"):
                self.assertGreaterEqual(contrast(dark_fg, dark_bg), 4.5)

    def test_panel_declares_reference_tokens(self) -> None:
        source = PANEL.read_text(encoding="utf-8")
        for label, colors in PALETTE.items():
            # Brand green uses --trybatec-brand-green; others use fluid domain tokens.
            brand_name = "--trybatec-brand-green" if label == "green" else f"--trybatec-{label}-brand"
            self.assertIn(brand_name + ":" + colors[0], source)
            for color in colors[1:]:
                self.assertIn(color, source)
        # CSS is embedded in a JavaScript string, which escapes double quotes.
        # Validate the actual theme contract instead of its JS escaping.
        self.assertIn("data-trybatec-theme", source)
        self.assertIn("this.dataset.trybatecTheme", source)

    def test_selection_without_position_shift(self) -> None:
        source = PANEL.read_text(encoding="utf-8")
        self.assertNotIn(".selected{background:rgba(66,138,223,.1)", source)
        self.assertIn("aria-pressed", source)

if __name__ == "__main__":
    unittest.main()
