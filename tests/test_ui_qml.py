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
    from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, QTimer

    from aipc.ui import app as uiapp
except ImportError:  # pragma: no cover
    uiapp = None

CASES = [
    {"screen": "login"},
    {"screen": "login", "demo_scan": "scanning"},
    {"screen": "login", "demo_scan": "found"},
    {"screen": "login", "demo_scan": "unknown"},
    {"screen": "login", "demo_scan": "manual", "theme": "dark"},
    *({"screen": "signup", "signup_step": n, "dev": True} for n in range(6)),
    {"screen": "signup", "signup_step": 3, "theme": "dark"},
    *(({"screen": "shell", "page": p} for p in uiapp.PAGES) if uiapp else ()),
    {"screen": "shell", "page": "workspace", "theme": "dark"},
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


@unittest.skipIf(uiapp is None, "ไม่มี PySide6")
class ChatInputTest(unittest.TestCase):
    """BRIEF 5.4 ข้อ 7: Enter ส่ง · Shift+Enter ขึ้นบรรทัดใหม่."""

    def test_enter_sends_and_shift_enter_adds_newline(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        with tempfile.TemporaryDirectory() as tmp:
            opts = uiapp.Options(screen="shell", software=True, settings_path=Path(tmp) / "ui.json")
            app, engine, warnings = uiapp.build(opts)
            settle()
            win = engine.rootObjects()[0]
            chat_input = win.findChild(QObject, "chatInput")
            chat_list = win.findChild(QObject, "chatList")
            chat_input.forceActiveFocus()
            settle(100)

            chat_input.setProperty("text", "บรรทัดแรก")
            chat_input.setProperty("cursorPosition", len("บรรทัดแรก"))
            QTest.keyClick(win, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
            settle(100)
            self.assertEqual(chat_list.property("count"), 0, "Shift+Enter ต้องไม่ส่ง")
            self.assertIn(chr(10), chat_input.property("text").replace(chr(0x2029), chr(10)))

            QTest.keyClick(win, Qt.Key.Key_Return)
            settle(100)
            # ข้อความของผู้ใช้ 1 + ประกาศจากระบบว่ายังไม่มีโมเดล 1
            self.assertEqual(chat_list.property("count"), 2, "Enter ต้องส่ง")
            self.assertEqual(chat_input.property("text"), "")
            self.assertEqual(warnings, [])
            win.close()
            engine.deleteLater()


if __name__ == "__main__":
    unittest.main()
