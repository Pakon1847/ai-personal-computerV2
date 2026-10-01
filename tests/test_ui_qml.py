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
        self.assertEqual(btn.property("text"), "อ่านออกเสียง")
        btn.clicked.emit()
        settle(30)
        self.assertEqual(fake.said, ["เปิด YouTube แล้ว"])  # ข้อความหลัง tidy()
        self.assertEqual(btn.property("text"), "หยุดอ่าน")
        voice._on_state(7, False, "")  # อ่านจบ
        settle(30)
        self.assertEqual(btn.property("text"), "อ่านออกเสียง")
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
