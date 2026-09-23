"""ความต่างสีของ token ใน Theme.qml (การ์ด 0002 ข้อ 8) · ทุกคู่ตัวอักษร/พื้นที่ใช้จริง >= 4.5:1 ทั้งสองธีม.

อ่านค่าสีจากไฟล์ QML ตรง ๆ จึงไม่ต้องมี PySide6 · สูตรตาม WCAG 2.1 (relative luminance).
"""

import re
import unittest
from pathlib import Path

THEME = Path(__file__).parents[1] / "src" / "aipc" / "ui" / "qml" / "AipcUi" / "Theme.qml"
PAIR = re.compile(r'property color (\w+): dark \? "(#[0-9A-Fa-f]{6})" : "(#[0-9A-Fa-f]{6})"')
FIXED = re.compile(r'property color (\w+): "(#[0-9A-Fa-f]{6})"')

# (ตัวอักษร, พื้น) ที่หน้าจอใช้จริง
PAIRS = [
    ("ink", "bg"),
    ("ink", "surface"),
    ("ink", "surface2"),
    ("inkMuted", "bg"),
    ("inkMuted", "surface"),
    ("inkMuted", "surface2"),
    ("inkFaint", "bg"),
    ("inkFaint", "surface"),
    ("textOnAccent", "accentFill"),
    ("accent", "bg"),
    ("accent", "surface"),
    ("accentInk", "accentSoft"),
    ("bubbleInk", "accentSoft"),
    ("okInk", "okSoft"),
    ("warnInk", "warnSoft"),
    ("dangerInk", "dangerSoft"),
    ("textOnWarn", "warnFill"),
    ("textOnDanger", "dangerFill"),
    ("textOnInk", "inkFill"),
    ("danger", "bg"),
    ("cameraText", "camera"),
]


def themes() -> tuple[dict, dict]:
    text = THEME.read_text(encoding="utf-8")
    dark, light = {}, {}
    for name, dk, lt in PAIR.findall(text):
        dark[name], light[name] = dk, lt
    for name, v in FIXED.findall(text):
        dark[name] = light[name] = v
    # ค่าที่อ้างชื่ออื่น เช่น accentFill: accent
    for name, ref in re.findall(r"property color (\w+): (\w+)\s*$", text, re.M):
        if ref in dark:
            dark[name], light[name] = dark[ref], light[ref]
    return dark, light


def luminance(hex_: str) -> float:
    c = [int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class ContrastTest(unittest.TestCase):
    def test_all_pairs_meet_aa(self):
        failed = []
        for label, t in zip(("มืด", "สว่าง"), themes(), strict=True):
            for fg, bg in PAIRS:
                self.assertIn(fg, t, fg)
                self.assertIn(bg, t, bg)
                ratio = contrast(t[fg], t[bg])
                if ratio < 4.5:
                    failed.append(f"{label}: {fg} บน {bg} = {ratio:.2f}")
        self.assertEqual(failed, [], "\n".join(failed))

    def test_formula_known_values(self):
        self.assertAlmostEqual(contrast("#000000", "#FFFFFF"), 21.0, places=1)
        self.assertAlmostEqual(contrast("#777777", "#777777"), 1.0)


if __name__ == "__main__":
    unittest.main()
