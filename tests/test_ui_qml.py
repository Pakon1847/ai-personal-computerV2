"""โหลดทุกหน้าจอจริงแบบไม่มีจอ (offscreen) แล้วตรวจว่าไม่มี warning ของ QML.

warning ของ QML มักแปลว่ามีอะไรบนจอผิดเงียบ ๆ (อ้างชื่อผิด ค่าเป็น undefined)
เทสต์นี้จึงถือว่า warning แม้แต่บรรทัดเดียวคือความผิดพลาด
ข้ามอัตโนมัติถ้าเครื่องไม่มี PySide6 (เช่นเครื่องที่ลงแค่เครื่องมือวัด)
"""

import os
import shutil
import tempfile
import time
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
    *({"screen": "signup", "signup_step": n, "dev": True} for n in range(3)),
    {"screen": "recover", "dev": True},
    {"screen": "recover", "greeter_session": ["labwc"]},
    {"screen": "delete", "dev": True},
    {"screen": "delete", "greeter_session": ["labwc"], "theme": "dark"},
    {"screen": "signup", "signup_step": 1, "theme": "dark"},
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
        from unittest import mock

        # ไม่ต่อ visiond ของเครื่องจริง (พบ 2026-10-05 บน Pi 5: เทสต์สั่งสแกนหน้าจริง → scanState "unknown")
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(uiapp, "_face_client", lambda short=False: None),
        ):
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


def items_of(page):
    v = page.property("items")
    return v.toVariant() if hasattr(v, "toVariant") else v


def find_all(root, name):
    return [o for o in root.findChildren(QObject) if o.objectName() == name]


def find_items(win, name):
    """ค้นตามต้นไม้ภาพ (childItems) · ของใน delegate ของ ListView ไม่ได้เป็นลูกแบบ QObject ของหน้าต่าง"""
    out, stack = [], [win.contentItem()]
    while stack:
        item = stack.pop()
        if item.objectName() == name:
            out.append(item)
        stack.extend(item.childItems())
    return out


@unittest.skipIf(uiapp is None, "ไม่มี PySide6")
class DeleteAccountScreenTest(unittest.TestCase):
    """ลบบัญชี (ข้อเสนอ 2026-10-03): ปุ่มลบกดได้เมื่อกรอกครบ ยืนยันชื่อตรง และติ๊กเข้าใจ · ผลเป็นใบยืนยัน."""

    def test_button_needs_everything_then_shows_certificate(self):
        with tempfile.TemporaryDirectory() as tmp:
            opts = uiapp.Options(software=True, settings_path=Path(tmp) / "ui.json", screen="login",
                                 dev=True)  # fmt: skip
            app, engine, warnings = uiapp.build(opts)
            settle()
            win = engine.rootObjects()[0]
            find_all(win, "deleteAccountLink")[0].clicked.emit()
            settle(100)
            button = find_all(win, "deleteButton")[0]
            find_all(win, "deleteUser")[0].setProperty("text", "namfon")
            find_all(win, "deletePassword")[0].setProperty("text", "correct-horse-9")
            find_all(win, "deleteConfirm")[0].setProperty("text", "namfo")
            find_all(win, "deleteUnderstood")[0].setProperty("checked", True)
            settle(50)
            self.assertFalse(button.property("enabled"), "ยืนยันชื่อไม่ตรง = กดไม่ได้")
            find_all(win, "deleteConfirm")[0].setProperty("text", "namfon")
            settle(50)
            self.assertTrue(button.property("enabled"))
            button.clicked.emit()
            settle(100)
            self.assertTrue(find_all(win, "deleteCertificate")[0].property("visible"))
            self.assertEqual(len(find_items(win, "deleteCheck")), 1)  # จำลอง: บรรทัดเดียว "ไม่ได้ลบจริง"
            self.assertEqual(warnings, [])
            win.close()
            uiapp.shutdown(engine)


@unittest.skipIf(uiapp is None, "ไม่มี PySide6")
class PasswordThaiHintTest(unittest.TestCase):
    """พบ 2026-09-29: หน้า Login เคยมีแต่แป้นอังกฤษ · เมื่อสลับไทยได้แล้ว ช่องรหัสผ่านต้องเตือนถ้ามีตัวอักษรไทย
    (ช่องซ่อนตัวอักษร ผู้ใช้มองไม่เห็นเอง) · เตือนเท่านั้น ไม่ห้าม · เลขไทย ๐–๙ ไม่เตือน เพราะช่อง PIN รับได้"""

    FIELDS = [({"screen": "login"}, "loginPw"),
              ({"screen": "signup", "dev": True}, "signupPw1"),
              ({"screen": "recover", "dev": True}, "recoverPw1")]  # fmt: skip

    def test_thai_letters_in_password_show_a_hint(self):
        for case, name in self.FIELDS:
            with self.subTest(field=name), tempfile.TemporaryDirectory() as tmp:
                opts = uiapp.Options(software=True, settings_path=Path(tmp) / "ui.json", **case)
                app, engine, warnings = uiapp.build(opts)
                settle()
                win = engine.rootObjects()[0]
                field = find_all(win, name)[0]
                self.assertFalse(field.property("thaiInPassword"))
                field.setProperty("text", "รหัสผ่านไทย12")
                settle(50)
                self.assertTrue(field.property("thaiInPassword"))
                self.assertIn("กด ~", field.property("shownHint"))
                self.assertEqual(field.property("shownKind"), "warn")
                field.setProperty("text", "correct-horse-๙๘")  # เลขไทยอย่างเดียว = ไม่เตือน
                settle(50)
                self.assertFalse(field.property("thaiInPassword"))
                self.assertEqual(warnings, [])
                win.close()
                uiapp.shutdown(engine)


STEP_MD = """---
id: start-work
name: เริ่มวันทำงาน
description: เปิดอีเมลและปรับเสียง
keywords: เริ่มวันทำงาน
examples: เริ่มวันทำงาน | เริ่มงานเช้านี้ | เปิดของที่ใช้ทำงาน
permissions: run_actions
---
## ขั้นตอน
1. เปิดเว็บ gmail
2. ปรับเสียง 30
"""


@unittest.skipIf(uiapp is None, "ไม่มี PySide6")
class StepSkillCardTest(unittest.TestCase):
    """สกิลแบบขั้นตอน (.md): การ์ดที่แสดงทุกขั้นพร้อมปุ่มยืนยัน วาดได้โดยไม่มี QML warning."""

    def test_steps_card_draws_without_warnings(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        from aipc.skills import manifest

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "start-work.md").write_text(STEP_MD, encoding="utf-8")
            opts = uiapp.Options(screen="shell", software=True, settings_path=d / "ui.json")
            app, engine, warnings = uiapp.build(opts)
            settle()
            skills = engine.rootContext().contextProperty("skills")
            skills._skills = [*skills._skills, *manifest.load_dir(d)]
            win = engine.rootObjects()[0]
            chat_input = win.findChild(QObject, "chatInput")
            chat_list = win.findChild(QObject, "chatList")
            chat_input.forceActiveFocus()
            settle(100)
            chat_input.setProperty("text", "เริ่มวันทำงาน")
            QTest.keyClick(win, Qt.Key.Key_Return)
            settle(200)
            self.assertEqual(chat_list.property("count"), 2, "ข้อความผู้ใช้ + การ์ดขั้นตอน")
            self.assertEqual(warnings, [])
            win.close()
            uiapp.shutdown(engine)


@unittest.skipIf(uiapp is None, "ไม่มี PySide6")
class AiPicksSkillQmlTest(unittest.TestCase):
    """AI เลือกสกิล → หน้าแชทแสดงการ์ดของสกิลนั้นแทนคำตอบ · ไม่มี QML warning."""

    def test_skill_requested_shows_the_skill_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            opts = uiapp.Options(screen="shell", software=True, settings_path=Path(tmp) / "ui.json")
            app, engine, warnings = uiapp.build(opts)
            settle()
            win = engine.rootObjects()[0]
            chat = engine.rootContext().contextProperty("chat")
            chat_list = win.findChild(QObject, "chatList")
            chat.skillRequested.emit("machine-status", "คอมหน่วงมาก")
            settle(200)
            self.assertEqual(chat_list.property("count"), 1, "การ์ดถามเครื่อง 1 ใบ")
            self.assertEqual(warnings, [])
            win.close()
            uiapp.shutdown(engine)


@unittest.skipIf(uiapp is None, "ไม่มี PySide6")
class ShellCardTest(unittest.TestCase):
    maxDiff = None
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

    def test_chat_scrolls_to_newest_after_a_very_long_message(self):
        # พบบน Pi 5 2026-10-12: วางข้อความยาวมาก → แชทค้างบนสุด ไม่เห็นคำตอบใหม่อีกเลย
        _, win, warnings = self.open_shell()
        win.resize(1280, 800)
        page = find_all(win, "workspace")[0]
        chat_list = find_all(win, "chatList")[0]
        items = [{"user": True, "text": "สรุปข้อความนี้: " + "การประชุมมีวาระสำคัญหลายเรื่อง " * 300}]
        for i in range(4):
            items = items + [
                {"ai": True, "text": f"คำตอบ {i} " + "ข้อความ " * 80, "note": "", "done": True},
                {"user": True, "text": f"ถามต่อ {i}"},
            ]
            page.setProperty("items", items)
            settle(200)
            self.assertTrue(chat_list.property("atYEnd"), f"ข้อความที่ {i}: ต้องเห็นข้อความล่าสุด")
        self.assertEqual(warnings, [])

    def test_ai_answers_draw_without_warnings(self):
        """การ์ด 0013: ข้อความ AI (กำลังตอบ / จบ / หยุด) วาดได้โดยไม่มี warning
        · พบ 2026-09-28: ข้อความ AI ไม่มีช่อง user ทำให้ binding ได้ undefined."""
        _, win, warnings = self.open_shell()
        page = find_all(win, "workspace")[0]
        page.setProperty("items", [
            {"user": True, "text": "ถาม"},
            {"ai": True, "text": "ตอบจบแล้ว", "note": "", "done": True, "skill": ""},
            {"ai": True, "text": "ครึ่ง", "note": "หยุดแล้ว", "done": True, "skill": "แปลไทย ↔ อังกฤษ"},
            {"ai": True, "text": "", "note": "", "done": False, "skill": ""},
        ])  # fmt: skip
        settle(100)
        self.assertEqual(find_all(win, "chatList")[0].property("count"), 4)
        self.assertEqual(warnings, [])

    def test_hands_free_voice_answers_pending_card_and_never_chats(self):
        """การ์ด 0024: พูด "ใช่" ตอบการ์ดที่รอยืนยัน (ไม่ต้องกดปุ่ม) ·
        การ์ด 0027: ประโยคที่ไม่ใช่คำสั่ง = บอกว่าไม่รู้จัก ไม่ส่งเข้าแชท (เดิมได้การ์ดเวลา/คำตอบของ AI)."""
        _, win, warnings = self.open_shell()
        page = find_all(win, "workspace")[0]
        base = {"chips": [], "lines": [], "page": "", "badge": {}, "kind": "command"}
        page.setProperty("items", [{"user": True, "text": "ยกเลิกนัดกินยา"},
                                   {"user": False, "card": {**base, "title": "ลบนัด 1 รายการ ใช่ไหม",
                                                            "confirmToken": "tok-1"}}])  # fmt: skip
        settle(50)
        page.voiceCommand("ใช่ครับ")
        settle(50)
        answered = page.property("answered")
        answered = answered.toVariant() if hasattr(answered, "toVariant") else answered
        self.assertTrue(answered.get("tok-1"))
        n = len(items_of(page))
        page.voiceCommand("แต่งกลอนให้หน่อย")
        settle(100)
        rows = items_of(page)
        self.assertEqual(len(rows), n + 2)  # ข้อความที่ได้ยิน + คำบอก · ไม่มีคำตอบของ AI ตามมา
        self.assertEqual(rows[n]["text"], "แต่งกลอนให้หน่อย")
        self.assertIn("ไม่รู้จักคำสั่ง", rows[-1]["text"])
        self.assertNotIn("card", rows[-1])
        # การ์ด 0029: คำถามที่โค้ดตอบเองได้ = การ์ดเวลาจากนาฬิกาเครื่อง (ไม่ใช่ AI · 0027 เดิมได้ "ไม่รู้จักคำสั่ง")
        page.voiceCommand("ตอนนี้กี่โมง")
        settle(100)
        rows = items_of(page)
        self.assertEqual(rows[-2]["text"], "ตอนนี้กี่โมง")
        self.assertEqual(rows[-1]["card"]["kind"], "clock")
        self.assertEqual(warnings, [])

    def test_hands_free_command_mode_routes(self):
        """การ์ด 0027: "เลื่อนลง" ก่อนเปิดเบราว์เซอร์ = บอกให้เปิดก่อน · "เปิดเบราว์เซอร์" = เบราว์เซอร์ของผู้ช่วย ·
        คำสั่งเครื่อง = ทางเดิมของแชท (ทำคำสั่ง ไม่ถึง AI)."""
        engine, win, warnings = self.open_shell()
        page = find_all(win, "workspace")[0]
        browser = engine._backends["browser"]
        ran = []

        class Control:  # ไม่เปิด Chromium จริงในเทสต์
            running = False

            def run(self, cmd):
                ran.append(cmd.as_dict())
                self.running = True
                from aipc.browser.control import Result

                return Result(True, "เปิดแล้ว")

        browser._control = Control()
        page.voiceCommand("เลื่อนลง")
        settle(50)
        rows = items_of(page)
        self.assertIn("เปิดเบราว์เซอร์", rows[-1]["text"])
        self.assertEqual(ran, [])
        page.voiceCommand("เปิดเบราว์เซอร์")
        settle(200)
        self.assertEqual(ran, [{"kind": "site", "site": "google"}])
        self.assertEqual(items_of(page)[-2]["text"], "เปิดเบราว์เซอร์")
        n = len(items_of(page))
        page.voiceCommand("เปิดหน้าตั้งค่า")
        settle(100)
        rows = items_of(page)
        self.assertEqual(rows[n]["text"], "เปิดหน้าตั้งค่า")
        self.assertIn("card", rows[-1])  # การ์ดคำสั่งเครื่อง ไม่ใช่คำตอบของ AI
        self.assertEqual(warnings, [])

    def test_hands_free_command_never_goes_to_claude_or_wipes_draft(self):
        """ตรวจทั้งระบบ 2026-10-18 ข้อ 2.1 2.2 2.7: กด "ไม่ใช่แบบนี้" ค้างไว้ + พิมพ์ค้าง แล้วพูดคำสั่งเครื่อง =
        ทำคำสั่ง ไม่ส่งให้ Claude แก้สกิล และข้อความที่พิมพ์ยังอยู่ · "ตกลงไม่ลบแล้ว" = ไม่ ไม่ใช่ใช่."""
        engine, win, warnings = self.open_shell()
        page = find_all(win, "workspace")[0]
        skills = engine._backends["skills"]
        sent = []
        skills._forge = lambda request, **kw: sent.append(request)  # Claude ปลอม: จดว่าถูกเรียกไหม
        skills._start_forge = lambda *a, **kw: sent.append(a) or {}
        page.setProperty("feedbackFor", {"id": "work-mode", "name": "โหมดทำงาน"})
        box = find_all(win, "chatInput")[0]
        box.setProperty("text", "ร่างที่พิมพ์ค้างไว้")
        page.voiceCommand("เปิดหน้าตั้งค่า")
        settle(100)
        rows = items_of(page)
        self.assertEqual(rows[-2]["text"], "เปิดหน้าตั้งค่า")
        self.assertIn("card", rows[-1])  # การ์ดคำสั่งเครื่อง
        self.assertEqual(sent, [])  # ไม่ถึง Claude
        self.assertEqual(box.property("text"), "ร่างที่พิมพ์ค้างไว้")
        base = {"chips": [], "lines": [], "page": "", "badge": {}, "kind": "command"}
        page.setProperty("items", [{"user": True, "text": "ยกเลิกนัดกินยา"},
                                   {"user": False, "card": {**base, "title": "ลบนัด 1 รายการ ใช่ไหม",
                                                            "confirmToken": "tok-2"}}])  # fmt: skip
        settle(50)
        page.voiceCommand("ตกลงไม่ลบแล้ว")
        settle(100)
        self.assertNotEqual(items_of(page)[-1]["card"]["title"], "ลบนัด 1 รายการ ใช่ไหม")
        answered = page.property("answered")
        answered = answered.toVariant() if hasattr(answered, "toVariant") else answered
        self.assertTrue(answered.get("tok-2"))  # ตอบแล้ว (ว่าไม่)
        self.assertEqual(warnings, [])

    def test_hands_free_create_skill_asks_before_sending(self):
        """การ์ด 0030: พูดขอโหมดใหม่ → การ์ดยืนยันข้อความก่อนส่ง Claude · พูด "ไม่" = ไม่ส่งอะไร."""
        engine, win, warnings = self.open_shell()
        page = find_all(win, "workspace")[0]
        skills = engine._backends["skills"]
        sent = []
        skills._forge = lambda request, **kw: sent.append(request)  # Claude ปลอม: จดว่าถูกเรียกไหม
        skills._claude_on = lambda: True
        page.voiceCommand("ทำโหมดฟังเพลง: เปิดยูทูบแล้วปรับเสียง 60")
        settle(50)
        card = items_of(page)[-1]["card"]
        self.assertEqual(card["title"], "ส่งให้ Claude สร้างสกิลนี้ ใช่ไหม")
        page.voiceCommand("ไม่")
        settle(100)
        self.assertEqual(items_of(page)[-1]["card"]["title"], "ยกเลิกแล้ว ไม่ได้ทำอะไร")
        self.assertEqual(sent, [])
        self.assertEqual(warnings, [])

    def test_hands_free_runs_claude_made_skill_by_exact_phrase(self):
        """การ์ด 0028: พูดประโยคของสกิลที่ Claude สร้าง = การ์ดสกิลเดียวกับตอนพิมพ์ · ได้ยินเพี้ยน = คำใบ้ ไม่ทำ."""
        engine, win, warnings = self.open_shell()
        page = find_all(win, "workspace")[0]
        skills = engine._backends["skills"]
        md = (Path(__file__).resolve().parent.parent / "docs/benchmarks/2026-09-30-skill-author"
              / "claude/s2.md").read_text(encoding="utf-8")  # fmt: skip
        skills._user.install(md, skills._skills, request="อยากได้สกิลโหมดประชุม")
        skills._reload()
        n = len(items_of(page))
        page.voiceCommand("เข้าโหมดประชุม")
        settle(100)
        rows = items_of(page)
        self.assertEqual(len(rows), n + 2)  # ข้อความที่ได้ยิน + การ์ดสกิล · ไม่มีคำตอบของ AI
        self.assertEqual(rows[n]["text"], "เข้าโหมดประชุม")
        self.assertEqual(rows[-1]["card"]["badge"]["name"], "โหมดประชุม")
        # ทาง ก: ได้ยินใกล้เคียง = การ์ด "หมายถึง … ใช่ไหม" · พูด "ไม่" = ไม่ทำ
        # (ไม่ทดสอบ "ใช่" ที่นี่: บน Pi ตัวสั่งเครื่องทำจริง · ทดสอบใน test_auto_skill ด้วยตัวจำลอง)
        page.voiceCommand("เข้าโหมดประชม")
        settle(50)
        card = items_of(page)[-1]["card"]
        self.assertEqual(card["title"], "หมายถึง “โหมดประชุม” ใช่ไหม")
        self.assertNotEqual(card["confirmToken"], "")
        page.voiceCommand("ไม่")
        settle(50)
        self.assertEqual(items_of(page)[-1]["card"]["title"], "ยกเลิกแล้ว ไม่ได้ทำอะไร")
        self.assertEqual(warnings, [])

    def test_hands_free_while_browser_busy_says_wait(self):
        """เบราว์เซอร์ยังทำคำสั่งก่อนอยู่ → บอกให้รอ ไม่หลุดไปเป็นคำสั่งของแอป ("ย้อนกลับ" · พบใน 0025)."""
        engine, win, warnings = self.open_shell()
        page = find_all(win, "workspace")[0]
        browser = engine._backends["browser"]
        browser._busy = True
        browser.busyChanged.emit()
        settle(50)
        page.voiceCommand("ย้อนกลับ")
        settle(50)
        rows = items_of(page)
        self.assertEqual(rows[-2]["text"], "ย้อนกลับ")
        self.assertIn("รอสักครู่", rows[-1]["text"])
        self.assertEqual(warnings, [])

    def test_claude_made_skill_cards_draw_with_undo_and_wrong_buttons(self):
        """การ์ด 0017: กำลังสร้าง / สร้างไม่สำเร็จ / สกิลที่ Claude สร้าง (มีปุ่ม) วาดได้
        · ปุ่ม "ไม่ใช่แบบนี้" เปลี่ยนช่องพิมพ์."""
        _, win, warnings = self.open_shell()
        page = find_all(win, "workspace")[0]
        base = {"chips": [], "lines": ["x"], "confirmToken": "", "page": ""}
        page.setProperty("items", [
            # การ์ดที่ต้องตรวจอยู่บนสุด (ListView สร้างเฉพาะแถวที่อยู่ในจอ)
            {"user": False, "card": {**base, "kind": "steps", "title": "ทำครบ 2 ขั้นแล้ว",
                                     "badge": {"name": "โหมดทำงาน", "reason": "r", "worker": "โค้ด",
                                               "forgedId": "work-mode", "forgedVersion": 1}}},
            {"user": False, "card": {**base, "kind": "forging", "badge": {},
                                     "title": "กำลังให้ Claude สร้างสกิล…"}},
            {"user": False, "card": {**base, "kind": "forge-failed", "badge": {},
                                     "title": "สร้างสกิลไม่สำเร็จ", "fallback": True}},
        ])  # fmt: skip
        settle(100)
        rows = [r for r in find_items(win, "forgedRow") if r.property("visible")]
        self.assertEqual(len(rows), 1, "ปุ่มลบ/ไม่ใช่แบบนี้ขึ้นเฉพาะการ์ดของสกิลที่ Claude สร้าง")
        page.setProperty("feedbackFor", {"id": "work-mode", "name": "โหมดทำงาน"})
        settle(50)
        self.assertIn("โหมดทำงาน", find_all(win, "chatInput")[0].property("placeholderText"))
        banner = find_items(win, "feedbackBanner") or find_all(win, "feedbackBanner")
        self.assertTrue(banner and banner[0].property("visible"), "แถบบอกโหมดแก้สกิลต้องเห็นชัด")
        page.setProperty("feedbackFor", None)
        settle(30)
        self.assertFalse(banner[0].property("visible"))
        self.assertEqual(warnings, [])

    def test_undo_button_shows_once_and_reports(self):
        """ปุ่มย้อนกลับ (ข้อเสนอ 2026-10-03): ขึ้นเฉพาะการ์ดที่มี undoToken · กดแล้วหาย และขึ้นการ์ดผล."""
        _, win, warnings = self.open_shell()
        page = find_all(win, "workspace")[0]
        base = {"chips": [], "lines": [], "confirmToken": "", "page": "", "badge": {}}
        page.setProperty("items", [
            {"user": False, "card": {**base, "kind": "command", "title": "ตั้งเสียง 90%",
                                     "undoToken": "u-old"}},
            {"user": False, "card": {**base, "kind": "command", "title": "เปิด YouTube"}},
        ])  # fmt: skip
        settle(100)
        buttons = [b for b in find_items(win, "undoButton") if b.property("visible")]
        self.assertEqual(len(buttons), 1)
        buttons[0].clicked.emit()
        settle(100)
        visible = [b for b in find_items(win, "undoButton") if b.property("visible")]
        self.assertEqual(visible, [], "กดแล้วต้องหาย ไม่ให้กดซ้ำ")  # แถวถูกสร้างใหม่ จึงหาใหม่
        self.assertEqual(find_all(win, "chatList")[0].property("count"), 3)  # การ์ดผลต่อท้าย
        self.assertEqual(warnings, [])

    def test_why_panel_opens_on_cards_and_ai_answers(self):
        """ทำไมได้คำตอบนี้ (ข้อเสนอ 2026-10-03): ปิดไว้ก่อน · กดแล้วเห็นทุกแถว · ไม่มีข้อมูล = ไม่มีปุ่ม."""
        _, win, warnings = self.open_shell()
        page = find_all(win, "workspace")[0]
        why = [{"k": "ใครตอบ", "v": "AI ในเครื่อง"}, {"k": "ข้อมูลออกนอกเครื่อง", "v": "ไม่มี"}]
        base = {"chips": [], "lines": [], "confirmToken": "", "page": "", "badge": {}}
        page.setProperty("items", [
            {"user": False, "card": {**base, "kind": "command", "title": "เปิด YouTube",
                                     "why": why}},
            {"ai": True, "text": "สวัสดีครับ", "note": "", "done": True, "why": why},
            {"user": False, "card": {**base, "kind": "command", "title": "ไม่มีเหตุผล"}},
        ])  # fmt: skip
        settle(100)
        buttons = [b for b in find_items(win, "whyButton") if b.property("visible")]
        self.assertEqual(len(buttons), 2)
        self.assertEqual(find_items(win, "whyRow"), [])
        for b in buttons:
            b.clicked.emit()
        settle(50)
        texts = [r.property("text") for r in find_items(win, "whyRow")]
        self.assertEqual(texts.count("ใครตอบ: AI ในเครื่อง"), 2)
        self.assertEqual(warnings, [])

    def test_skills_page_manages_claude_made_skills(self):
        """หน้า Skill (การ์ด 0017 ชั้นที่ 3): สกิลที่ Claude สร้างมีการ์ดของตัวเอง · ปิด/ย้อนรุ่น/ลบได้ไม่มี warning."""
        from aipc.skills import manifest, userskills

        engine, win, warnings = self.open_shell("skills")
        skills = engine.rootContext().contextProperty("skills")
        self.assertTrue(find_items(win, "userSkillsEmpty")[0].property("visible"))
        root = Path(__file__).resolve().parent.parent
        md = (root / "docs/benchmarks/2026-09-30-skill-author/claude/s2.md").read_text(
            encoding="utf-8"
        )
        store = userskills.UserSkills(Path(os.environ["XDG_DATA_HOME"]) / "aipc" / "skills")
        builtin = manifest.load_builtin()
        m = store.install(md, builtin, request="เข้าโหมดประชุม")
        store.install(
            md.replace("3. บอก:", "3. บอก: (รุ่น 2)"), [*builtin, m], request="x", replacing=m.id
        )
        skills._user = store
        skills._reload()
        settle(100)
        self.assertEqual(len(find_items(win, "userSkillCard")), 1)
        entry = skills.userSkills[0]
        self.assertEqual((entry["version"], entry["versions"], entry["enabled"]), (2, [1, 2], True))
        self.assertEqual(skills.revertSkill(m.id, 1), "")
        self.assertEqual(skills.userSkills[0]["version"], 1)
        skills.setSkillEnabled(m.id, False)
        self.assertFalse(skills.userSkills[0]["enabled"])
        self.assertNotIn(m.id, [t["function"]["name"] for t in skills.tool_catalog()])
        skills.removeSkill(m.id)
        settle(50)
        self.assertEqual(skills.userSkills, [])
        self.assertEqual(warnings, [])

    def test_backup_card_backs_up_to_a_drive(self):
        """ฟีเจอร์ข้อ 7: การ์ดสำรองในหน้าตั้งค่า · ไดรฟ์ปลอม (โฟลเดอร์) · สำรองในเธรด แล้วบอกผล."""
        engine, win, warnings = self.open_shell("settings")
        ctl = engine.rootContext().contextProperty("backupCtl")
        home = Path(os.environ["XDG_DATA_HOME"]) / "home"
        (home / ".local/share/aipc").mkdir(parents=True)
        (home / ".local/share/aipc/x.json").write_text("{}", encoding="utf-8")
        usb = Path(os.environ["XDG_DATA_HOME"]) / "usb"
        usb.mkdir()
        ctl._home, ctl._drives_fn = home, lambda: [usb]
        ctl.refresh()
        settle(50)
        self.assertEqual(ctl.drives[0]["count"], 0)
        ctl.backupTo(0)
        end = time.monotonic() + 10
        while ctl.busy and time.monotonic() < end:
            settle(50)
        self.assertIn("สำรองแล้ว", ctl.message)
        self.assertEqual(ctl.drives[0]["count"], 1)
        self.assertEqual(warnings, [])

    def test_outbound_card_lists_what_left_the_machine(self):
        """บันทึกสิ่งที่ส่งออกนอกเครื่อง: การ์ดในหน้าตั้งค่าแสดงข้อความที่ส่งจริง · ล้างต้องกดสองครั้ง."""
        from datetime import datetime

        from aipc.cloud.budget import Budget
        from aipc.cloud.ledger import Ledger

        engine, win, warnings = self.open_shell("settings")
        usage = engine.rootContext().contextProperty("cloudUsage")
        tmp = Path(os.environ["XDG_DATA_HOME"])
        led = Ledger(tmp / "outbound-test.json", now=lambda: datetime(2026, 10, 1, 14, 5))
        led.record("ask", "คำถาม:\nอากาศเชียงใหม่วันนี้", 0.021)
        usage._b, usage._ledger, usage._available = Budget(tmp / "usage-test.json"), led, True
        usage.changed.emit()
        settle(50)
        card = find_items(win, "outboundCard")[0]
        self.assertTrue(card.property("visible"))
        self.assertIn("1 ครั้ง", find_items(win, "outboundSummary")[0].property("text"))
        self.assertEqual(usage.outbound[0]["sent"], "คำถาม:\nอากาศเชียงใหม่วันนี้")
        self.assertEqual(usage.outbound[0]["kind"], "ถาม Claude")
        self.assertEqual(len(find_items(win, "outboundRow")), 1)
        btn = find_items(win, "clearOutbound")[0]
        btn.clicked.emit()
        settle(30)
        self.assertEqual(usage.outboundTotal, 1)  # ครั้งแรกแค่ถามยืนยัน
        btn.clicked.emit()
        settle(30)
        self.assertEqual(usage.outboundTotal, 0)
        self.assertEqual(warnings, [])

    def test_claude_guide_only_without_claude(self):
        """การ์ด 0021 เกณฑ์ข้อ 3: ไม่มี claude = ปุ่มคู่มือ กดแล้วเห็นทุกขั้นพร้อมกรอบคำสั่ง · มี claude = ไม่มีคู่มือ."""
        engine, win, warnings = self.open_shell("settings")
        usage = engine.rootContext().contextProperty("cloudUsage")
        usage._user, usage._addresses, usage._available = "pakon", lambda: ["172.20.10.3"], False
        usage.changed.emit()
        settle(50)
        btn = find_items(win, "claudeGuideButton")[0]
        self.assertTrue(btn.property("visible"))
        self.assertFalse(find_items(win, "claudeGuideStep"))  # ยังไม่กด = ยังไม่สร้างขั้นตอน
        btn.clicked.emit()
        settle(50)
        self.assertTrue(find_items(win, "claudeGuide")[0].property("visible"))
        self.assertEqual(len(find_items(win, "claudeGuideStep")), len(usage.guideSteps))
        boxes = [c for c in find_items(win, "claudeGuideCommand") if c.isVisible()]
        self.assertEqual(len(boxes), 3)  # ssh · ติดตั้ง · เข้าสู่ระบบ
        self.assertIn("ssh pakon@172.20.10.3", [s["command"] for s in usage.guideSteps])
        usage._available = True
        usage.changed.emit()
        settle(50)
        self.assertFalse(btn.property("visible"))
        self.assertFalse(find_items(win, "claudeGuide")[0].property("visible"))
        self.assertEqual(warnings, [])

    def test_claude_connect_card_on_assistant_page(self):
        """การ์ด 0021 เกณฑ์ข้อ 3ข: หน้าผู้ช่วยมีแถบเชื่อมต่อใต้คำทักทาย · กดแล้วขั้นตอนขึ้นกลางจอ ·
        "ไว้ทีหลัง" ซ่อน · มี claude แล้วไม่แสดง."""
        engine, win, warnings = self.open_shell("workspace")
        usage = engine.rootContext().contextProperty("cloudUsage")
        usage._user, usage._addresses, usage._available = "pakon", lambda: ["172.20.10.2"], False
        usage.changed.emit()
        settle(50)
        card = find_items(win, "claudeConnectCard")[0]
        self.assertTrue(card.isVisible())
        greeting = find_items(win, "greeting")[0]
        below = card.mapToScene(card.position()).y()
        self.assertGreater(below, greeting.mapToScene(greeting.position()).y())
        find_items(win, "claudeConnectOpen")[0].clicked.emit()
        settle(100)
        popup = find_all(win, "claudeGuidePopup")[0]
        self.assertTrue(popup.property("opened"))
        # หน้าตั้งค่าก็มีคู่มือ (ซ่อนอยู่) → นับเฉพาะที่เห็น
        shown = [s for s in find_items(win, "claudeGuideStep") if s.isVisible()]
        self.assertEqual(len(shown), len(usage.guideSteps))
        self.assertIn("ssh pakon@172.20.10.2", [s["command"] for s in usage.guideSteps])
        find_items(win, "claudeGuideClose")[0].clicked.emit()
        settle(300)
        self.assertFalse(popup.property("opened"))
        find_items(win, "claudeConnectLater")[0].clicked.emit()
        settle(30)
        self.assertFalse(card.isVisible())
        card.setProperty("later", False)
        usage._available = True
        usage.changed.emit()
        settle(30)
        self.assertFalse(card.isVisible())
        self.assertEqual(warnings, [])

    def test_connect_here_opens_one_fixed_terminal(self):
        """การ์ด 0021 เกณฑ์ข้อ 7 และ 9: ปุ่มเปิด lxterminal ที่รัน aipc.cloud.connect เท่านั้น · กดซ้ำไม่เปิดเพิ่ม ·
        ปิดหน้าต่างแล้วมี claude = บอกให้ออกแล้วเข้าใหม่ · ไม่มีเทอร์มินัล = ไม่มีปุ่ม."""
        import sys

        engine, win, warnings = self.open_shell("workspace")
        usage = engine.rootContext().contextProperty("cloudUsage")
        spawned = []

        class Proc:
            done = False

            def poll(self):
                return 0 if self.done else None

        def spawn(cmd):
            spawned.append(cmd)
            return proc

        proc = Proc()
        usage._addresses, usage._available = (lambda: []), False
        usage._terminal, usage._spawn, usage._find = "/usr/bin/lxterminal", spawn, lambda: None
        usage.changed.emit()
        usage.refreshGuide()
        find_items(win, "claudeConnectOpen")[0].clicked.emit()
        settle(100)
        btn = [b for b in find_items(win, "claudeConnectHere") if b.isVisible()][0]
        btn.clicked.emit()
        settle(30)
        btn.clicked.emit()  # หน้าต่างเดิมยังเปิด = ไม่เปิดเพิ่ม
        settle(30)
        self.assertEqual(len(spawned), 1)
        cmd = spawned[0]
        self.assertEqual(cmd[0], "/usr/bin/lxterminal")
        self.assertIn("--no-remote", cmd)
        inner = cmd[-1].removeprefix("--command=")
        self.assertTrue(inner.endswith("-m aipc.cloud.connect"))
        self.assertIn(Path(sys.executable).name, inner)
        self.assertFalse(btn.property("enabled"))
        usage._find = lambda: "/home/pakon/.local/bin/claude"
        proc.done = True
        usage._check_connect()
        settle(30)
        self.assertTrue(usage.connectedNow)
        self.assertTrue(find_items(win, "claudeConnectedNow")[0].isVisible())
        self.assertTrue(btn.property("enabled"))
        usage._terminal = ""  # ไม่มีเทอร์มินัล = เหลือทาง SSH
        usage.guideChanged.emit()
        settle(30)
        self.assertFalse(btn.isVisible())
        self.assertEqual(warnings, [])

    def test_file_search_box_finds_by_content(self):
        """ค้นไฟล์ด้วยเนื้อหาในหน้าไฟล์ของฉัน · ค้นในเธรดแยก แล้วผลขึ้นพร้อมปุ่มถาม AI."""
        engine, win, warnings = self.open_shell("files")
        fb = engine.rootContext().contextProperty("filesBrowser")
        root = Path(os.environ["XDG_DATA_HOME"]) / "home-search"
        (root / "บ้าน").mkdir(parents=True)
        (root / "บ้าน" / "aircon.txt").write_text("ใบเสร็จค่าซ่อมแอร์ ร้านช่างเอก", encoding="utf-8")
        (root / "food.txt").write_text("สูตรต้มยำกุ้ง", encoding="utf-8")
        fb._root, fb._search = root, None
        fb.search("ใบเสร็จแอร์")
        end = time.monotonic() + 10
        while fb.searching and time.monotonic() < end:
            settle(30)
        settle(50)
        self.assertEqual(fb.searchResults[0]["name"], "aircon.txt")
        self.assertEqual(fb.searchResults[0]["folder"], "ไฟล์ของฉัน / บ้าน")
        self.assertTrue(find_items(win, "fileSearchResults")[0].property("visible"))
        self.assertIn("ไม่ออกนอกเครื่อง", fb.searchNote)
        self.assertTrue(fb.resultPath(fb.searchResults[0]["path"]).endswith("aircon.txt"))
        self.assertEqual(fb.resultPath("../../etc/passwd"), "")  # ออกนอก home ไม่ได้
        fb.search("")
        settle(30)
        self.assertEqual(fb.searchResults, [])
        self.assertEqual(warnings, [])

    def test_briefing_button_reads_today_summary(self):
        """อ่านสรุปวันนี้ให้ฟัง: ทักทาย วันที่ นัด สถานะเครื่อง · ไม่มีตัวอ่าน = ไม่มีปุ่ม."""
        engine, win, warnings = self.open_shell()
        voice = engine._backends["voice"]
        said = []

        class FakeSpeaker:
            available, current = True, -1

            def say(self, text):
                said.append(text)
                self.current = 3
                return 3

            def stop(self):
                self.current = -1

            def idle_check(self):
                return False

            def close(self):
                pass

        voice._speaker = None
        voice.changed.emit()
        settle(30)
        btn = find_items(win, "briefingButton")[0]
        self.assertFalse(btn.property("visible"))
        voice._speaker = FakeSpeaker()
        voice.changed.emit()
        settle(30)
        self.assertTrue(btn.property("visible"))
        btn.clicked.emit()
        settle(30)
        text = said[0]
        system = engine._backends["system"]
        self.assertIn(system.greeting, text)
        self.assertIn(system.longDate, text)
        self.assertIn("ยังไม่มีนัด", text)  # ไฟล์นัดว่างในเทสต์
        self.assertIn("เครื่อง", text)
        self.assertEqual(btn.property("text"), "หยุดอ่าน")
        self.assertEqual(warnings, [])

    def test_reminder_is_spoken_only_when_enabled(self):
        """เตือนนัดด้วยเสียง: ปิดอยู่ (ค่าเริ่มต้น) = เงียบ · เปิดในหน้าตั้งค่า = อ่านว่าถึงเวลาแล้ว + เรื่อง."""
        engine, win, warnings = self.open_shell()
        voice, ui, skills = (engine._backends[k] for k in ("voice", "uiSettings", "skills"))
        said = []

        class FakeSpeaker:
            available, current = True, -1

            def say(self, text):
                said.append(text)
                return 5

            def stop(self):
                pass

            def idle_check(self):
                return False

            def close(self):
                pass

        voice._speaker = FakeSpeaker()
        voice.changed.emit()
        self.assertFalse(ui.speakReminders)
        skills.reminderDue.emit({"what": "กินยา", "when": "วันนี้ 20:00", "id": "x"})
        settle(30)
        self.assertEqual(said, [])
        ui.setSpeakReminders(True)
        skills.reminderDue.emit({"what": "โทรหาแม่", "when": "วันนี้ 20:30", "id": "y"})
        settle(30)
        self.assertEqual(said, ["ถึงเวลาแล้ว โทรหาแม่ วันนี้ 20:30"])
        from aipc.ui import settings

        self.assertTrue(settings.load(ui._path).speak_reminders)  # จำไว้ในไฟล์ตั้งค่า
        self.assertEqual(warnings, [])

    def test_find_file_from_chat_shows_hits(self):
        """หาไฟล์ด้วยการพิมพ์ในแชท: กฎจับคำขอ → การ์ดผลค้นพร้อมปุ่มถาม AI · ไม่ผ่าน AI."""
        engine, win, warnings = self.open_shell()
        skills = engine._backends["skills"]
        home = Path(os.environ["XDG_DATA_HOME"]) / "chat-home"
        (home / "บ้าน").mkdir(parents=True)
        (home / "บ้าน" / "scan_0412.txt").write_text(
            "ใบเสร็จค่าซ่อมแอร์ ร้านช่างเอก 1,800 บาท", encoding="utf-8"
        )
        (home / "note.txt").write_text("สูตรต้มยำกุ้ง", encoding="utf-8")
        skills._home, skills._file_search = home, None
        card = skills.handle("หาไฟล์ใบเสร็จซ่อมแอร์ให้หน่อย")
        self.assertEqual(card["kind"], "files")
        self.assertEqual(card["files"][0]["name"], "scan_0412.txt")
        self.assertTrue(card["files"][0]["abs"].endswith("scan_0412.txt"))
        page = find_all(win, "workspace")[0]
        page.showCard(card)
        settle(50)
        self.assertGreaterEqual(len(find_items(win, "chatFileHit")), 1)
        chat = engine._backends["chat"]
        find_items(win, "summarizeFileButton")[
            0
        ].clicked.emit()  # AI ไม่พร้อมในเทสต์ = ส่งไม่ออก แต่แนบและขึ้นข้อความแล้ว
        settle(30)
        self.assertEqual(chat.attachedFile, "scan_0412.txt")
        items = find_all(win, "workspace")[0].property("items").toVariant()
        self.assertTrue(any("สรุปเนื้อหาไฟล์นี้" in (i.get("text") or "") for i in items))
        self.assertEqual(skills.handle("แปลงไฟล์ Word เป็น PDF ยังไง")["kind"] != "files", True)
        self.assertEqual(warnings, [])

    def test_auto_speak_reads_finished_answer(self):
        """อ่านคำตอบออกเสียง: ค่าเริ่มต้นเปิด · ปุ่มลำโพงในหน้าแชทปิดได้ทันที · ตอบไม่จบไม่อ่าน."""
        engine, win, warnings = self.open_shell()
        voice, ui, chat = (engine._backends[k] for k in ("voice", "uiSettings", "chat"))
        said = []

        class FakeSpeaker:
            available, current = True, -1

            def say(self, text):
                said.append(text)
                return 9

            def stop(self):
                pass

            def idle_check(self):
                return False

            def close(self):
                pass

        voice._speaker = FakeSpeaker()
        voice.changed.emit()
        page = find_all(win, "workspace")[0]

        def answer(text, note=""):
            pending = {"ai": True, "text": "", "note": "", "done": False, "skill": ""}
            page.setProperty("items", [{"user": True, "text": "q"}, pending])
            chat.finished.emit(text, note)
            settle(30)

        self.assertTrue(ui.speakAnswers)  # ค่าเริ่มต้นเปิด
        answer("น้ำคือ **H2O**")
        self.assertEqual(said, ["น้ำคือ H2O"])
        answer("ครึ่ง", "หยุดแล้ว")
        self.assertEqual(len(said), 1)  # ตอบไม่จบไม่อ่าน
        sw = find_items(win, "speakSwitch")[0]
        self.assertTrue(sw.property("visible"))
        self.assertEqual(sw.property("text"), "อ่านคำตอบออกเสียง: เปิด")  # สถานะเป็นคำ ไม่ใช่แค่สี
        sw.clicked.emit()  # ปิดจากแถวบนของหน้าแชท
        settle(30)
        self.assertFalse(ui.speakAnswers)
        self.assertEqual(sw.property("text"), "อ่านคำตอบออกเสียง: ปิด")
        answer("ตอบอีกครั้ง")
        self.assertEqual(len(said), 1)
        sw.clicked.emit()  # เปลี่ยนกลับได้ตลอด
        settle(30)
        self.assertTrue(ui.speakAnswers)
        answer("ตอบครั้งที่สาม")
        self.assertEqual(said[-1], "ตอบครั้งที่สาม")
        self.assertEqual(warnings, [])

    def test_files_by_time_from_chat(self):
        """ดูไฟล์ตามเวลา: "ไฟล์ที่แก้เมื่อวาน" กรองตามเวลาแก้ไข · มีเรื่องที่ค้นก็จัดอันดับตามเนื้อหา."""
        from datetime import datetime, timedelta

        engine, win, warnings = self.open_shell()
        skills = engine._backends["skills"]
        home = Path(os.environ["XDG_DATA_HOME"]) / "time-home"
        home.mkdir(parents=True)
        now = datetime.now()
        yday = (now - timedelta(days=1)).replace(hour=12, minute=0).timestamp()
        old = (now - timedelta(days=40)).timestamp()
        for name, text, t in (("a.txt", "รายงานยอดขาย", yday), ("b.txt", "สูตรแกงเขียวหวาน", yday),
                              ("c.txt", "รายงานเก่า", old)):  # fmt: skip
            (home / name).write_text(text, encoding="utf-8")
            os.utime(home / name, (t, t))
        skills._home, skills._file_search = home, None
        card = skills.handle("ขอดูไฟล์ที่แก้เมื่อวานหน่อย")
        self.assertEqual(card["kind"], "files")
        self.assertEqual(sorted(f["name"] for f in card["files"]), ["a.txt", "b.txt"])  # ไม่มีไฟล์เก่า
        self.assertEqual(card["title"], "ไฟล์ที่แก้ไขเมื่อวาน")
        card = skills.handle("หาไฟล์รายงานที่แก้เมื่อวาน")
        self.assertEqual(card["files"][0]["name"], "a.txt")
        self.assertIn("รายงาน", card["title"])
        self.assertEqual(warnings, [])

    def test_push_to_talk_fills_input_without_sending(self):
        """แตะเพื่อพูด: ป้ายไมค์เปิดตอนฟัง · แตะซ้ำ = หยุด · ข้อความใส่ช่องพิมพ์ ไม่ส่งเอง · ไม่มีตัวถอด = ไม่มีปุ่ม."""
        engine, win, warnings = self.open_shell()
        voice = engine._backends["voice"]

        class FakeListener:
            available, listening = True, False

            def start(self, fast=False):
                self.listening = True
                return ""

            def stop(self):
                self.listening = False
                voice._heard.emit("เปิด ยูทูบ", "", 1.8)

            def cancel(self):
                self.listening = False

        voice._listener = None
        voice.micChanged.emit()
        settle(30)
        mic = find_items(win, "micButton")[0]
        self.assertFalse(mic.property("visible"))
        voice._listener = FakeListener()
        voice.micChanged.emit()
        settle(30)
        self.assertTrue(mic.property("visible"))
        page = find_all(win, "workspace")[0]
        before = len(page.property("items").toVariant())
        mic.clicked.emit()
        settle(30)
        self.assertIn("ไมค์เปิด", find_items(win, "micIndicator")[0].property("text"))
        mic.clicked.emit()  # แตะซ้ำ = หยุดทันที
        settle(50)
        self.assertEqual(find_all(win, "chatInput")[0].property("text"), "เปิด ยูทูบ")
        self.assertEqual(len(page.property("items").toVariant()), before)  # ไม่ได้ส่งเอง
        self.assertEqual(find_items(win, "micIndicator")[0].property("text"), "ไมค์ปิด")
        self.assertIn("ตรวจข้อความ", voice.micMessage)
        self.assertEqual(warnings, [])

    def test_tap_to_talk_stops_by_itself(self):
        """แตะครั้งเดียว: ตัวอัดหยุดเองเมื่อพูดจบ → หน้าจอขึ้น "กำลังถอด" แล้วข้อความเข้าช่องพิมพ์."""
        engine, win, warnings = self.open_shell()
        voice = engine._backends["voice"]

        class SelfStopping:
            available, listening = True, False

            def start(self, fast=False):
                self.listening = True
                return ""

            def stop(self):
                self.listening = False

            def cancel(self):
                self.listening = False

        fake = voice._listener = SelfStopping()
        voice.micChanged.emit()
        settle(30)
        mic = find_items(win, "micButton")[0]
        mic.clicked.emit()
        settle(30)
        self.assertTrue(voice.listening)
        fake.listening = False  # Endpointer: พูดจบแล้วเงียบ 1 วิ → หยุดเอง (จากเธรดของตัวอัด)
        settle(400)
        self.assertTrue(voice.transcribing)
        self.assertEqual(mic.property("text"), "กำลังถอด…")
        voice._heard.emit("ตั้ง เสียง สามสิบ", "", 2.1)
        settle(50)
        self.assertFalse(voice.transcribing)
        self.assertEqual(find_all(win, "chatInput")[0].property("text"), "ตั้ง เสียง สามสิบ")
        self.assertEqual(warnings, [])

    def test_weather_asks_city_then_answers_without_claude(self):
        """สกิลอากาศ: ไม่บอกเมือง = ถามกลับ · ตอบชื่อเมือง = พยากรณ์ Open-Meteo · ความรู้ไม่เข้าสกิล."""
        from aipc.skills.weather import Weather

        engine, win, warnings = self.open_shell()
        skills = engine._backends["skills"]
        sent = []
        fc = {"current": {"temperature_2m": 30.2, "relative_humidity_2m": 60, "weather_code": 3},
              "daily": {"temperature_2m_max": [33.0], "temperature_2m_min": [24.0],
                        "precipitation_probability_max": [70], "weather_code": [61]}}  # fmt: skip
        geo = {
            "results": [
                {"name": "เชียงใหม่", "country_code": "TH", "latitude": 18.79, "longitude": 98.98}
            ]
        }

        def get(url, params, timeout=10):
            return geo if "geocoding" in url else fc

        skills._weather = Weather(get=get,
                                  record=sent.append)  # fmt: skip
        card = skills.handle("อากาศวันนี้เป็นยังไงบ้าง")
        self.assertEqual((card["kind"], card["title"]), ("weather", "อากาศที่เมืองไหนครับ"))
        self.assertEqual(sent, [])  # ยังไม่ส่งอะไรออก
        card = skills.handle("เชียงใหม่")
        self.assertEqual(card["title"], "เชียงใหม่ วันนี้ ฝนตกเล็กน้อย")
        self.assertIn("โอกาสฝนตก 70% · พกร่มไปด้วยดีกว่า", card["lines"])
        self.assertEqual(len(sent), 2)
        self.assertNotEqual(skills.handle("ทำไมอากาศร้อนขึ้นทุกปี")["kind"], "weather")

        def offline(*a, **k):
            raise OSError("no network")

        skills._weather = Weather(get=offline)
        self.assertEqual(skills.handle("ตอนนี้กรุงเทพฝนตกไหม")["title"], "ดูพยากรณ์อากาศไม่ได้ตอนนี้")
        page = find_all(win, "workspace")[0]
        page.showCard(card)
        settle(50)
        self.assertEqual(warnings, [])

    def test_ready_check_on_health_page(self):
        """ตรวจความพร้อมก่อนสาธิต: กดแล้วตรวจในเธรดแยก · การ์ดสรุปพร้อมวิธีแก้."""
        engine, win, warnings = self.open_shell("health")
        system = engine._backends["system"]
        inputs = {"ai_ready": False, "voice_available": True, "mic_available": True,
                  "claude": "/usr/bin/claude"}  # fmt: skip
        system.ready_inputs = lambda: inputs
        find_items(win, "readyButton")[0].clicked.emit()
        end = time.monotonic() + 15
        while (system.readyBusy or not system.readyChecks) and time.monotonic() < end:
            settle(50)
        self.assertTrue(find_items(win, "readyCard")[0].property("visible"))
        self.assertIn("ยังไม่พร้อม", system.readySummary)  # AI ไม่พร้อม = ต้องแก้
        ai = [c for c in system.readyChecks if c["title"] == "AI ในเครื่อง"][0]
        self.assertEqual(ai["level"], "danger")
        self.assertEqual(warnings, [])

    def test_latex_answers_become_plain_text(self):
        """พบในผลสอบ 2026-10-01: Gemma ตอบเป็น LaTeX → หน้าจอแสดงข้อความอ่านง่าย."""
        _, win, warnings = self.open_shell()
        page = find_all(win, "workspace")[0]
        cases = {
            r"สูตรเคมีของน้ำคือ $\text{H}_2\text{O}$ ครับ": "สูตรเคมีของน้ำคือ H₂O ครับ",
            r"0.25 เท่ากับ $\frac{1}{4}$": "0.25 เท่ากับ 1/4",
            r"พื้นที่ $\pi r^2$ และ $$a \times b \div 2$$": "พื้นที่ π r² และ a × b ÷ 2",
            r"น้ำเดือดที่ $100^\circ C$": "น้ำเดือดที่ 100° C",
            "ราคา $5 กับ $10": "ราคา $5 กับ $10",
        }
        for src, want in cases.items():
            with self.subTest(src=src):
                self.assertEqual(page.tidy(src), want)
        self.assertEqual(warnings, [])

    def test_speak_button_reads_answer_and_stops(self):
        """การ์ด 0019: ปุ่มอ่านออกเสียงขึ้นเฉพาะเมื่อมีตัวอ่าน · กดแล้วเป็น "หยุดอ่าน" · กดอีกครั้งหยุด."""
        engine, win, warnings = self.open_shell()
        voice = engine._backends["voice"]
        page = find_all(win, "workspace")[0]
        answer = {"ai": True, "text": "เปิด **YouTube** แล้ว", "note": "", "done": True, "skill": ""}
        page.setProperty("items", [answer])
        settle(100)
        btn = [b for b in find_items(win, "speakAnswer")][0]
        voice._speaker = None
        voice.changed.emit()
        settle(30)
        self.assertFalse(btn.property("visible"))  # ไม่มีตัวอ่าน = ไม่มีปุ่ม

        class FakeSpeaker:
            available, current, said, stopped = True, -1, [], 0

            def say(self, text):
                self.said.append(text)
                self.current = 7
                return 7

            def stop(self):
                self.stopped += 1
                self.current = -1

            def idle_check(self):
                return False

            def close(self):
                pass

        fake = voice._speaker = FakeSpeaker()
        voice.changed.emit()
        settle(30)
        self.assertTrue(btn.property("visible"))
        self.assertEqual(btn.property("text"), "ฟังคำตอบนี้")
        btn.clicked.emit()
        settle(30)
        self.assertEqual(fake.said, ["เปิด YouTube แล้ว"])  # ข้อความหลัง tidy()
        self.assertEqual(btn.property("text"), "หยุดอ่าน")
        voice._on_state(7, False, "")  # อ่านจบ
        settle(30)
        self.assertEqual(btn.property("text"), "ฟังคำตอบนี้")
        btn.clicked.emit()
        btn.clicked.emit()  # กดซ้ำระหว่างอ่าน = หยุด
        settle(30)
        self.assertGreaterEqual(fake.stopped, 1)
        self.assertEqual(warnings, [])

    def test_ai_answer_is_plain_text_and_links_readable(self):
        """พบบนจอ Pi 2026-10-01: ลิงก์ markdown ดิบ
        · และข้อความหน้าตาเหมือน HTML ต้องไม่ถูกแสดงเป็น HTML (รูปจากเว็บ = รั่ว)."""
        _, win, warnings = self.open_shell()
        page = find_all(win, "workspace")[0]
        page.setProperty(
            "items",
            [
                {
                    "ai": True,
                    "done": True,
                    "skill": "",
                    "note": "ตอบโดย Claude (cloud) · x",
                    "text": "[กรมอุตุฯ](https://www.tmd.go.th/x) **ฝน** <img src='https://e.x/a.png'>",
                }
            ],
        )
        settle(100)
        t = [o for o in find_items(win, "aiText") if o.property("visible")][0]
        # PySide อ่าน enum textFormat ไม่ได้ · ตรวจในไฟล์ QML แทนว่าบังคับ PlainText
        qml = (
            Path(__file__).resolve().parent.parent / "src/aipc/ui/qml/AipcUi/WorkspacePage.qml"
        ).read_text("utf-8")
        self.assertIn("textFormat: Text.PlainText", qml)
        self.assertIn("กรมอุตุฯ (https://www.tmd.go.th/x) ฝน", t.property("text"))
        self.assertEqual(warnings, [])

    def test_chat_input_has_focus_when_workspace_opens(self):
        """ทดสอบบนจอ Pi 2026-10-01: เปิดหน้าผู้ช่วยแล้วต้องกด Tab หลายครั้งกว่าจะพิมพ์ได้."""
        _, win, warnings = self.open_shell()
        win.requestActivate()
        settle(200)
        self.assertTrue(find_all(win, "chatInput")[0].property("activeFocus"))
        self.assertEqual(warnings, [])

    def test_onboarding_shows_once(self):
        """ฟีเจอร์ข้อ 8: หน้าแนะนำขึ้นครั้งแรก · กด "เข้าใจแล้ว" = จำในไฟล์ตั้งค่า ไม่ขึ้นอีก."""
        from aipc.ui import settings

        engine, win, warnings = self.open_shell()
        ui = engine.rootContext().contextProperty("uiSettings")
        card = find_items(win, "onboarding")[0]
        self.assertTrue(card.property("visible"))
        ui.finishOnboarding()
        settle(50)
        self.assertFalse(card.property("visible"))
        self.assertTrue(settings.load(ui._path).onboarded)
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
