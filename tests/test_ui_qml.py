"""โหลดทุกหน้าจอจริงแบบไม่มีจอ (offscreen) แล้วตรวจว่าไม่มี warning ของ QML.

warning ของ QML มักแปลว่ามีอะไรบนจอผิดเงียบ ๆ (อ้างชื่อผิด ค่าเป็น undefined)
เทสต์นี้จึงถือว่า warning แม้แต่บรรทัดเดียวคือความผิดพลาด
ข้ามอัตโนมัติถ้าเครื่องไม่มี PySide6 (เช่นเครื่องที่ลงแค่เครื่องมือวัด)
"""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

    from aipc.ui import app as uiapp
except ImportError:  # pragma: no cover
    uiapp = None

CASES = [
    {"screen": "login"},
    {"screen": "login", "demo_scan": "scanning"},
    {"screen": "login", "demo_scan": "found"},
    {"screen": "login", "demo_scan": "unknown"},
    {"screen": "login", "demo_scan": "manual", "theme": "dark"},
]


def settle(ms: int = 300) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


@unittest.skipIf(uiapp is None, "ไม่มี PySide6")
class QmlLoadTest(unittest.TestCase):
    def test_every_screen_loads_without_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            for case in CASES:
                with self.subTest(**case):
                    opts = uiapp.Options(software=True, settings_path=Path(tmp) / "ui.json", **case)
                    app, engine, warnings = uiapp.build(opts)
                    settle()
                    self.assertTrue(engine.rootObjects(), "โหลดไม่ขึ้น")
                    self.assertEqual(warnings, [])
                    for root in engine.rootObjects():
                        root.close()
                    engine.deleteLater()
                    QCoreApplication.processEvents()


if __name__ == "__main__":
    unittest.main()
