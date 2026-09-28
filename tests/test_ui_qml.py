"""โหลดทุกหน้าจอจริงแบบไม่มีจอ (offscreen) แล้วตรวจว่าไม่มี warning ของ QML.

warning ของ QML มักแปลว่ามีอะไรบนจอผิดเงียบ ๆ (อ้างชื่อผิด ค่าเป็น undefined)
เทสต์นี้จึงถือว่า warning แม้แต่บรรทัดเดียวคือความผิดพลาด
ข้ามอัตโนมัติถ้าเครื่องไม่มี PySide6 (เช่นเครื่องที่ลงแค่เครื่องมือวัด)
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_OLD_DATA_HOME = os.environ.get("XDG_DATA_HOME")


def setUpModule():
    # ไม่ให้เทสต์เขียนนัดหมายลง home จริงของผู้ใช้ · ตั้งเฉพาะช่วงเทสต์ไฟล์นี้ แล้วคืนค่าเดิม
    # (เดิมตั้งตอน import ค้างทั้งโปรเซส → เทสต์ไฟล์อื่นหาโมเดลที่ดาวน์โหลดไว้ไม่เจอ)
    os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp(prefix="aipc-test-")


def tearDownModule():
    if _OLD_DATA_HOME is None:
        os.environ.pop("XDG_DATA_HOME", None)
    else:
        os.environ["XDG_DATA_HOME"] = _OLD_DATA_HOME


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
    # หน้า login จริงผ่าน greetd (การ์ด 0003) · ใส่ dev/demo มาด้วยเพื่อตรวจว่าถูกปิดทิ้ง
    {"screen": "login", "greeter_session": ["labwc"], "dev": True, "demo_scan": "found"},
    # เซสชันจริงหลัง login (การ์ด 0004) · ขอ login/dev มาแต่ต้องได้ Shell ไม่มีโหมดพัฒนา
    {"screen": "login", "session": True, "dev": True, "demo_scan": "found"},
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
                    if case.get("greeter_session"):
                        ctx = engine.rootContext()
                        self.assertFalse(ctx.contextProperty("devMode"), "greeter ต้องไม่มีโหมดพัฒนา")
                        self.assertEqual(ctx.contextProperty("login").scanState, "unavailable")
                        # พบ 2026-09-28: Ctrl+Alt+Q ปิดหน้า Login จริงได้ → ใครอยู่หน้าเครื่องก็ปิดได้
                        win = engine.rootObjects()[0]
                        self.assertFalse(win.property("quitKeyEnabled"), "หน้า Login จริงห้ามปิดได้")
                    if case.get("session"):
                        ctx = engine.rootContext()
                        self.assertFalse(ctx.contextProperty("devMode"), "เซสชันจริงต้องไม่มีโหมดพัฒนา")
                        self.assertEqual(ctx.contextProperty("startScreen"), "shell")
                        self.assertTrue(ctx.contextProperty("session").active)
                        win = engine.rootObjects()[0]
                        self.assertFalse(win.property("quitKeyEnabled"), "ปิด Ctrl+Alt+Q")
                    for root in engine.rootObjects():
                        root.close()
                    uiapp.shutdown(engine)
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
            uiapp.shutdown(engine)


def find_all(root, name):
    return [o for o in root.findChildren(QObject) if o.objectName() == name]


@unittest.skipIf(uiapp is None, "ไม่มี PySide6")
class ShellCardTest(unittest.TestCase):
    """เกณฑ์การ์ด 0002 ข้อ 8: ไฟกล้อง/ไมค์ทุกหน้า และการ์ดนัดถัดไปจาก upcoming จริง."""

    def open_shell(self, page="workspace"):
        tmp = tempfile.mkdtemp(prefix="aipc-shell-")
        os.environ["XDG_DATA_HOME"] = tmp  # ไฟล์นัดใหม่เปล่า ๆ ต่อเทสต์ ไม่ปนกับเทสต์อื่น
        opts = uiapp.Options(screen="shell", page=page, software=True,
                             settings_path=Path(tmp) / "ui.json")  # fmt: skip
        app, engine, warnings = uiapp.build(opts)
        settle()
        win = engine.rootObjects()[0]

        def close():
            win.close()
            uiapp.shutdown(engine)
            QCoreApplication.processEvents()
            shutil.rmtree(tmp, ignore_errors=True)  # ไม่ทิ้งโฟลเดอร์ชั่วคราวไว้ใน /tmp ของ Pi

        self.addCleanup(close)
        return engine, win, warnings

    def test_camera_and_mic_indicators_on_every_page(self):
        # H3: ไฟกล้อง/ไมค์ต้องเห็นตลอด ไม่ว่าอยู่หน้าไหนของ Shell
        for page in uiapp.PAGES:
            with self.subTest(page=page):
                _, win, warnings = self.open_shell(page)
                for name in ("cameraIndicator", "micIndicator"):
                    found = find_all(win, name)
                    self.assertEqual(len(found), 1, name)
                    self.assertTrue(found[0].property("visible"), name)
                    self.assertTrue(found[0].property("text"), name)
                self.assertEqual(warnings, [])

    def test_face_panel_and_camera_in_use(self):
        engine, win, warnings = self.open_shell("settings")
        face = engine.rootContext().contextProperty("face")
        self.assertEqual(len(find_all(win, "facePanel")), 1)
        self.assertEqual(find_all(win, "faceStatus")[0].property("text"), "ยังไม่ได้ลงทะเบียน")
        cam = find_all(win, "cameraIndicator")[0]
        self.assertNotEqual(cam.property("text"), "กล้องกำลังใช้")
        face._busy = True  # จำลองว่ากำลังใช้กล้อง (ไม่เปิดกล้องจริงในเทสต์)
        face.changed.emit()
        settle(50)
        self.assertEqual(cam.property("text"), "กล้องกำลังใช้", "H3: ต้องเห็นว่ากล้องกำลังใช้")
        face._busy = False
        face.changed.emit()
        self.assertEqual(warnings, [])

    def test_enroll_preview_every_pose_without_warnings(self):
        from PySide6.QtGui import QImage

        engine, win, warnings = self.open_shell("settings")
        face = engine.rootContext().contextProperty("face")
        preview = find_all(win, "facePreview")[0]
        self.assertFalse(preview.property("visible"), "ไม่ลงทะเบียน = ไม่มีภาพสด")
        img = QImage(480, 270, QImage.Format.Format_RGB888)
        img.fill(0x404040)
        # จำลองสถานะระหว่างลงทะเบียน (ไม่เปิดกล้องจริงในเทสต์)
        face._busy, face._preview_on, face._preview_img = True, True, img
        face._preview_serial, face._face_box = 1, [0.35, 0.2, 0.3, 0.55]
        counts = {"front": 0, "left": 0, "right": 0, "up": 0, "down": 0}
        for pose in ("front", "left", "right", "up", "down", None):
            face._poses = dict(counts)
            face.changed.emit()
            face.previewChanged.emit()
            settle(30)
            self.assertTrue(preview.property("visible") or pose is None, pose)
            if pose:
                self.assertEqual(face.currentPose, pose)
                counts[pose] = 2
        self.assertTrue(
            find_all(win, "facePoses")[0].property("visible") is False
        )  # ครบ = ไม่ใช่ท่าไหนแล้ว
        face._busy = False
        face._clear_preview()
        face.changed.emit()
        settle(30)
        self.assertFalse(preview.property("visible"))
        self.assertEqual(warnings, [])

    def test_next_reminder_card_empty_then_real(self):
        engine, win, warnings = self.open_shell()
        skills = engine.rootContext().contextProperty("skills")
        what = find_all(win, "nextReminderWhat")[0]
        when = find_all(win, "nextReminderWhen")[0]
        self.assertEqual(what.property("text"), "ยังไม่มีนัด")
        self.assertFalse(when.property("visible"))

        card = skills.handle("เตือนส่งรายงานพรุ่งนี้บ่ายสอง")
        skills.confirm(card["confirmToken"], True)
        settle(100)
        self.assertEqual(what.property("text"), skills.upcoming[0]["what"])
        self.assertIn("ส่งรายงาน", what.property("text"))
        self.assertTrue(when.property("visible"))
        self.assertEqual(when.property("text"), skills.upcoming[0]["when"])
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
