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
    *({"screen": "signup", "signup_step": n, "dev": True} for n in range(3)),
    {"screen": "recover", "dev": True},
    {"screen": "recover", "greeter_session": ["labwc"]},
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

    def test_claude_made_skill_cards_draw_with_undo_and_wrong_buttons(self):
        """การ์ด 0017: กำลังสร้าง / สร้างไม่สำเร็จ / สกิลที่ Claude สร้าง (มีปุ่ม) วาดได้ · ปุ่ม "ไม่ใช่แบบนี้" เปลี่ยนช่องพิมพ์."""
        _, win, warnings = self.open_shell()
        page = find_all(win, "workspace")[0]
        base = {"chips": [], "lines": ["x"], "confirmToken": "", "page": ""}
        page.setProperty("items", [
            # การ์ดที่ต้องตรวจอยู่บนสุด (ListView สร้างเฉพาะแถวที่อยู่ในจอ)
            {"user": False, "card": {**base, "kind": "steps", "title": "ทำครบ 2 ขั้นแล้ว",
                                     "badge": {"name": "โหมดทำงาน", "reason": "r", "worker": "โค้ด",
                                               "forgedId": "work-mode", "forgedVersion": 1}}},
            {"user": False, "card": {**base, "kind": "forging", "badge": {}, "title": "กำลังให้ Claude สร้างสกิล…"}},
            {"user": False, "card": {**base, "kind": "forge-failed", "badge": {}, "title": "สร้างสกิลไม่สำเร็จ",
                                     "fallback": True}},
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

    def test_skills_page_manages_claude_made_skills(self):
        """หน้า Skill (การ์ด 0017 ชั้นที่ 3): สกิลที่ Claude สร้างมีการ์ดของตัวเอง · ปิด/ย้อนรุ่น/ลบได้ไม่มี warning."""
        from aipc.skills import manifest, userskills

        engine, win, warnings = self.open_shell("skills")
        skills = engine.rootContext().contextProperty("skills")
        self.assertTrue(find_items(win, "userSkillsEmpty")[0].property("visible"))
        root = Path(__file__).resolve().parent.parent
        md = (root / "docs/benchmarks/2026-09-30-skill-author/claude/s2.md").read_text(encoding="utf-8")
        store = userskills.UserSkills(Path(os.environ["XDG_DATA_HOME"]) / "aipc" / "skills")
        builtin = manifest.load_builtin()
        m = store.install(md, builtin, request="เข้าโหมดประชุม")
        store.install(md.replace("3. บอก:", "3. บอก: (รุ่น 2)"), [*builtin, m], request="x", replacing=m.id)
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
