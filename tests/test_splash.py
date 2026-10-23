"""หน้า "กำลังเปิด…" ระหว่างเข้าระบบ (แทนจอดำ · Pakon 2026-10-23)."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_session import LOOP

try:
    from PySide6.QtGui import QColor, QGuiApplication, QImage

    from aipc.ui import splash
except ImportError:  # pragma: no cover
    splash = None


@unittest.skipIf(splash is None, "ไม่มี PySide6")
class SplashImageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_draws_theme_colour_at_screen_size(self):
        with tempfile.TemporaryDirectory() as d:
            for theme in ("dark", "light"):
                out = splash.write(Path(d) / f"{theme}.png", 640, 360, theme)
                img = QImage(str(out))
                self.assertEqual((img.width(), img.height()), (640, 360))
                self.assertEqual(img.pixelColor(5, 5), QColor(splash.COLORS[theme][0]))  # มุม = สีพื้น
            names = sorted(p.name for p in Path(d).iterdir())
            self.assertEqual(names, ["dark.png", "light.png"])  # ไม่ทิ้งไฟล์ชั่วคราว


class ShellLoopSplashTest(unittest.TestCase):
    def test_loop_shows_splash_before_app_and_survives_without_swaybg(self):
        s = LOOP.read_text(encoding="utf-8")
        self.assertLess(s.index("swaybg -m fill"), s.index("while labwc_alive"))  # ก่อนเปิดแอป
        self.assertIn("command -v swaybg", s)  # ไม่มี swaybg = ทำงานเหมือนเดิม
        self.assertIn("aipc/splash.png", s)
        self.assertIn(splash.COLORS["dark"][0] if splash else "#050506", s)


if __name__ == "__main__":
    unittest.main()
