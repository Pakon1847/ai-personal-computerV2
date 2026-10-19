"""การ์ด 0041 เกณฑ์ U1: ตัวหนังสือทุกสีอ่านชัดบนพื้นที่มันอยู่ (WCAG 2.x contrast ≥ 4.5:1) ทั้งธีมมืดและสว่าง.

อ่านค่าสีจาก Theme.qml ตรง ๆ (ไม่พิมพ์เลขสีซ้ำในเทสต์) · สูตร relative luminance ของ WCAG 2.x
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

THEME = Path(__file__).resolve().parent.parent / "src/aipc/ui/qml/AipcUi/Theme.qml"
MIN = 4.5

# (ตัวหนังสือ, พื้น) ที่หน้าจอใช้คู่กันจริง
TEXT_ON_PLAIN = ["ink", "inkMuted", "inkFaint", "accent", "accentInk", "ok", "warn", "danger"]
PLAINS = ["bg", "surface", "surface2"]
PAIRS = [
    ("okInk", "okSoft"), ("ok", "okSoft"), ("warnInk", "warnSoft"), ("warn", "warnSoft"),
    ("dangerInk", "dangerSoft"), ("danger", "dangerSoft"),
    ("accentInk", "accentSoft"), ("accent", "accentSoft"),
    ("bubbleInk", "accentSoft"), ("textOnAccent", "accentFill"), ("textOnWarn", "warnFill"),
    ("textOnDanger", "dangerFill"), ("textOnInk", "inkFill"),
]  # fmt: skip


def palette(dark: bool) -> dict[str, str]:
    text = THEME.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for name, d, light in re.findall(
        r'property color (\w+): dark \? "(#\w{6})" : "(#\w{6})"', text
    ):
        out[name] = d if dark else light
    for name, ref in re.findall(r"property color (\w+): (\w+)\s*$", text, re.M):
        out[name] = out[ref]
    return out


def luminance(hex_: str) -> float:
    c = [int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class ThemeContrastTest(unittest.TestCase):
    def test_every_text_colour_is_readable_in_both_themes(self):
        for dark in (True, False):
            p = palette(dark)
            pairs = [(t, b) for t in TEXT_ON_PLAIN for b in PLAINS] + PAIRS
            for fg, bg in pairs:
                with self.subTest(dark=dark, fg=fg, bg=bg):
                    self.assertGreaterEqual(
                        round(contrast(p[fg], p[bg]), 2), MIN, f"{p[fg]} บน {p[bg]}"
                    )

    def test_dark_theme_is_black(self):
        """การ์ด 0041: พื้นธีมมืดเป็นโทนดำ (ไม่ใช่เทาอมน้ำเงินแบบเดิม)."""
        p = palette(True)
        self.assertLess(luminance(p["bg"]), 0.002)
        self.assertLess(luminance(p["surface"]), 0.01)

    def test_new_users_get_dark_existing_files_keep_their_choice(self):
        import json
        import tempfile

        from aipc.ui import settings

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ui.json"
            self.assertEqual(settings.load(path).theme, "dark")  # ไม่มีไฟล์ = ผู้ใช้ใหม่
            path.write_text(json.dumps({"theme": "light"}), encoding="utf-8")
            self.assertEqual(settings.load(path).theme, "light")  # ทาง ก: ไม่ทับค่าเดิม


if __name__ == "__main__":
    unittest.main()
