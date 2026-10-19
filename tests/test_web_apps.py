"""แอปเว็บที่ใช้บ่อย (การ์ด 0031 เกณฑ์ข้อ 1) · ไม่เปิด Chromium และ xdg-open จริงในเทสต์.

ตรวจ: คำเรียกทุกคำ (พิมพ์และเสียง) · ปุ่ม/พิมพ์/สกิลไปเบราว์เซอร์ของผู้ช่วยตัวเดียว · ไม่ว่าง = เบราว์เซอร์ปกติ + บอก ·
ออกจากบัญชีเว็บทั้งหมด (ลบเฉพาะโปรไฟล์ · ไม่แตะดาวน์โหลด · ไม่มีเจ้าของเซสชัน = ปฏิเสธ) · ประโยคชน (การ์ดหัวข้อ 6) ·
หน้าจอไม่มี QML warning
"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aipc.browser import control
from aipc.browser.control import BrowserControl, Result
from aipc.skills import actions, browse, command, mdskill
from aipc.skills.browse import BrowseCommand

try:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtGui import QGuiApplication

    from aipc.ui.backend import SkillsController
    from aipc.ui.handsfree import BROWSER, COMMAND, BrowserController, route
except ImportError:  # pragma: no cover
    BrowserController = None

URL = {k: v[1] for k, v in actions.SITES.items()}

# คำเรียกตามการ์ดหัวข้อ 5 (+ สะกดที่พบบ่อย) · "ปฏิทิน" เฉย ๆ = หน้าปฏิทินของเครื่อง (การ์ด 0038)
TYPED = {
    "calendar": ["เปิดปฏิทินกูเกิล", "เปิดกูเกิลปฏิทิน", "เปิดปฏิทินกูเกิ้ล", "เปิด Google Calendar"],
    "drive": ["เปิดกูเกิลไดรฟ์", "เปิดกูเกิ้ลไดรฟ์", "เปิดกูเกิลไดร์ฟ", "เปิดไดรฟ์", "เปิดไดร์ฟ",
              "เปิด google drive"],
    "gmail": ["เปิดจีเมล"],
    "youtube": ["เปิดยูทูบ"],
}  # fmt: skip
VOICE = {
    "calendar": ["เปิดปฏิทินกูเกิล", "เปิดกูเกิลปฏิทิน"],
    "drive": ["เปิดกูเกิลไดรฟ์", "เปิดไดรฟ์", "เปิดไดร์ฟ"],
}


class AliasTest(unittest.TestCase):
    def test_typed_aliases_open_the_right_site(self):
        for key, texts in TYPED.items():
            for t in texts:
                with self.subTest(t=t):
                    cmd = command.parse(t)
                    self.assertIsNotNone(cmd)
                    self.assertEqual(cmd.plan.action, "open_url")
                    self.assertEqual(cmd.plan.params, {"site": key})
                    self.assertFalse(cmd.needs_confirmation)

    def test_voice_aliases_open_the_right_site(self):
        for key, texts in VOICE.items():
            for t in texts:
                with self.subTest(t=t):
                    self.assertEqual(browse.parse(t), [BrowseCommand("site", site=key)])

    def test_plain_calendar_is_our_page_not_the_web(self):
        self.assertEqual(browse.parse("เปิดปฏิทิน"), [])
        self.assertEqual(command.parse("เปิดปฏิทิน").plan.params, {"page": "calendar"})
        self.assertEqual(command.parse("เปิดหน้าปฏิทิน").plan.params, {"page": "calendar"})

    def test_collisions_from_card_section_6(self):
        # ไดรฟ์ USB (หน้าสำรองข้อมูลใช้คำนี้) ไม่ใช่ Google Drive
        for t in ("เปิดแฟลชไดรฟ์", "เปิดไดรฟ์ USB", "เปิดไดรฟ์ยูเอสบี", "เปิดฮาร์ดไดรฟ์"):
            with self.subTest(t=t):
                cmd = command.parse(t)
                self.assertFalse(cmd and cmd.plan.params.get("site") == "drive")
                self.assertEqual(browse.parse(t), [])
        # ไดรฟ์ ≠ ไฟล์ · เปิดเสียง ≠ เปิดเฟส… · นัดในปฏิทิน = งานทีหลัง ไม่ใช่คำสั่งตอนนี้
        self.assertEqual(command.parse("เปิดไฟล์").plan.params, {"page": "files"})
        self.assertEqual(command.parse("เปิดเสียง").plan.action, "unmute")
        self.assertEqual(browse.parse("เปิดเสียง"), [])
        self.assertIsNone(command.parse("เพิ่มนัดในปฏิทินพรุ่งนี้บ่ายสอง"))
        self.assertIsNone(command.parse("หาไฟล์ในไดรฟ์"))
        self.assertEqual(browse.parse("หาไฟล์ในไดรฟ์"), [])
        # สองเว็บในประโยคเดียว = ไม่ใช่คำสั่งเดี่ยว (เดิม · การ์ด 0017)
        self.assertIsNone(command.parse("เปิดจีเมลกับกูเกิลไดรฟ์"))

    def test_removed_and_missing_services_are_said_plainly(self):
        """Pakon 2026-10-19: เอา Facebook/Instagram ออก · LINE ไม่มี → ไม่เปิด ไม่เดาเป็นอย่างอื่น
        (เดิม "เปิดไลน์" ใกล้ "ไฟล์" → การ์ดถามว่าเปิดหน้าไฟล์ไหม)."""
        for t, name in [("เปิดเฟซบุ๊ก", "Facebook"), ("ช่วยเปิดเฟสบุ๊คหน่อย", "Facebook"),
                        ("เปิดไอจี", "Instagram"), ("เปิด instagram", "Instagram"),
                        ("เปิดไลน์", "LINE"), ("เข้าไลน์ให้หน่อย", "LINE")]:  # fmt: skip
            with self.subTest(t=t):
                self.assertEqual(command.unsupported(t), name)
                self.assertIsNone(command.parse(t))
                self.assertEqual(browse.parse(t), [])
        for t in ("เปิดไฟล์", "ไลน์ใหม่ของโทรศัพท์ดีไหม", "เฟซบุ๊กล่มหรือเปล่า"):
            self.assertIsNone(command.unsupported(t), t)
        self.assertNotIn("facebook", actions.SITES)
        self.assertNotIn("instagram", actions.SITES)

    def test_skill_step_names_the_new_sites(self):
        for key in ("calendar", "drive"):
            step, err = mdskill.parse_step(f"เปิดเว็บ {key}")
            self.assertEqual(err, "")
            self.assertEqual(step.plan.params, {"site": key})


class ExecutorTest(unittest.TestCase):
    def make(self, hook_result: bool, dry_run=False):
        self.ran, self.hooked = [], []

        def hook(site, url):
            self.hooked.append((site, url))
            return hook_result

        return actions.Executor(runner=lambda a: self.ran.append(a) or 0, dry_run=dry_run,
                                browser=hook)  # fmt: skip

    def test_open_goes_to_assistant_browser(self):
        out = self.make(True).execute(command.parse("เปิดยูทูบ").plan)
        self.assertTrue(out.ok)
        self.assertEqual(self.hooked, [("youtube", URL["youtube"])])
        self.assertEqual(self.ran, [])  # ไม่เปิดเบราว์เซอร์ปกติซ้อน
        self.assertEqual(out.message, "เปิด YouTube ในเบราว์เซอร์ของผู้ช่วย")

    def test_busy_assistant_browser_falls_back_and_says_so(self):
        out = self.make(False).execute(command.parse("เปิดกูเกิลไดรฟ์").plan)
        self.assertTrue(out.ok)
        self.assertEqual(self.ran, [["xdg-open", URL["drive"]]])
        self.assertIn("เปิดด้วยเบราว์เซอร์ปกติแทน", out.message)  # H2 ไม่เงียบ

    def test_sites_blocked_in_criterion_0_use_system_browser(self):
        with mock.patch.object(actions, "SYSTEM_BROWSER_SITES", frozenset({"gmail"})):
            out = self.make(True).execute(command.parse("เปิดจีเมล").plan)
        self.assertEqual(self.hooked, [])
        self.assertEqual(self.ran, [["xdg-open", URL["gmail"]]])
        self.assertEqual(out.message, "เปิด Gmail")

    def test_skill_steps_use_the_same_browser(self):
        ex = self.make(True)
        for line in ("เปิดเว็บ youtube", "เปิดเว็บ https://example.org/a"):
            step, _ = mdskill.parse_step(line)
            self.assertTrue(ex.execute(step.plan).ok)
        self.assertEqual(self.hooked, [("youtube", URL["youtube"]), ("", "https://example.org/a")])

    def test_dry_run_and_other_actions_never_touch_the_browser(self):
        out = self.make(True, dry_run=True).execute(command.parse("เปิดยูทูบ").plan)
        self.assertTrue(out.simulated)
        self.assertEqual(self.hooked, [])
        out = self.make(True).execute(actions.Plan("open_page", {"page": "settings"}))
        self.assertEqual((out.page, self.hooked, self.ran), ("settings", [], []))


class ControlTest(unittest.TestCase):
    def test_url_step_opens_https_only(self):
        from tests.test_browser_control import make

        bc, cdp = make({})
        r = bc.run(BrowseCommand("url", query="https://example.org/a"))
        self.assertTrue(r.ok)
        self.assertEqual(cdp.cur.url, "https://example.org/a")
        self.assertFalse(bc.run(BrowseCommand("url", query="http://example.org/a")).ok)
        self.assertFalse(bc.run(BrowseCommand("url", query="file:///etc/passwd")).ok)

    def test_profile_in_use_reads_chromium_lock(self):
        prof = Path("/nonexistent-profile")
        self.assertFalse(control.profile_in_use(prof))  # ไม่มีลิงก์ = ไม่มีใครใช้
        with mock.patch("os.readlink", return_value="ai-pc-4242"):
            with mock.patch.object(Path, "exists", lambda p: p.as_posix() == "/proc/4242"):
                self.assertTrue(control.profile_in_use(prof))
            with mock.patch.object(Path, "exists", lambda p: False):
                self.assertFalse(control.profile_in_use(prof))  # ลิงก์ค้างจากไฟดับ
        with mock.patch("os.readlink", return_value="garbage"):
            self.assertFalse(control.profile_in_use(prof))

    def test_available_follows_chromium_program(self):
        with mock.patch("shutil.which", return_value=None):
            self.assertFalse(BrowserControl().available)
        with mock.patch("shutil.which", return_value="/usr/bin/chromium"):
            self.assertTrue(BrowserControl().available)


def pump(cond, ms=3000):
    loop, waited = QEventLoop(), 0
    while not cond() and waited < ms:
        QTimer.singleShot(20, loop.quit)
        loop.exec()
        waited += 20
    return cond()


class FakeControl:
    """เบราว์เซอร์ของผู้ช่วยจำลอง (ไม่เปิด Chromium จริง)."""

    def __init__(self, available=True):
        self.available, self.running, self.ran, self.closed = available, False, [], 0

    def run(self, cmd):
        self.ran.append(cmd.as_dict())
        self.running = True
        return Result(True, f"เปิด {cmd.site or cmd.query} แล้ว")

    def close(self):
        self.closed += 1
        self.running = False


@unittest.skipIf(BrowserController is None, "ไม่มี PySide6")
class BrowserControllerWebTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.prof = self.root / "aipc" / "browser"
        (self.prof / "Default").mkdir(parents=True)
        (self.prof / "Default" / "Cookies").write_text("cookie", encoding="utf-8")
        self.dl = self.root / "Downloads"
        self.dl.mkdir()
        (self.dl / "งาน.pdf").write_text("pdf", encoding="utf-8")

    def make(self, **kw):
        self.ctl = kw.pop("control", None) or FakeControl()
        b = BrowserController(control=self.ctl, profile=self.prof, **kw)
        self.opened, self.finished = [], []
        b.opened.connect(lambda say, ok: self.opened.append((say, ok)))
        b.finished.connect(lambda say, ok: self.finished.append((say, ok)))
        return b

    def test_open_web_is_quiet_and_uses_assistant_browser(self):
        b = self.make()
        self.assertTrue(b.open_web("youtube", URL["youtube"]))
        self.assertTrue(pump(lambda: self.opened))
        self.assertEqual(self.ctl.ran, [{"kind": "site", "site": "youtube"}])
        self.assertEqual(self.opened, [("เปิด youtube แล้ว", True)])
        self.assertEqual(self.finished, [])  # ไม่แก้ข้อความล่าสุดในแชทแบบคำสั่งเสียง
        self.assertTrue(b.open_web("", "https://example.org/a"))
        self.assertTrue(pump(lambda: len(self.opened) == 2))
        self.assertEqual(self.ctl.ran[-1], {"kind": "url", "query": "https://example.org/a"})

    def test_open_web_refuses_when_it_cannot_take_the_job(self):
        b = self.make()
        b._busy = True  # กำลังทำคำสั่งเสียงอยู่
        self.assertFalse(b.open_web("youtube", URL["youtube"]))
        self.assertFalse(self.make(active=False).open_web("youtube", URL["youtube"]))  # หน้า Login
        no_chromium = self.make(control=FakeControl(available=False))
        self.assertFalse(no_chromium.open_web("drive", URL["drive"]))
        self.assertEqual(self.ctl.ran, [])

    def test_sign_out_removes_only_the_profile(self):
        left = self.prof.with_name("browser" + control.REMOVING + "1")  # ของค้างจากไฟดับรอบก่อน
        left.mkdir()
        b = self.make()
        msg = b.signOutAll()
        self.assertIn("ออกจากบัญชีเว็บในเบราว์เซอร์ของผู้ช่วยแล้ว", msg)
        self.assertEqual(self.ctl.closed, 1)  # ปิดเบราว์เซอร์ก่อนลบ
        self.assertFalse(self.prof.exists())  # ออกจากบัญชีทันที (เปลี่ยนชื่อแล้ว)
        end = time.monotonic() + 5
        while list(self.prof.parent.glob("browser*")) and time.monotonic() < end:
            time.sleep(0.02)
        self.assertEqual(list(self.prof.parent.glob("browser*")), [])  # ลบเบื้องหลังจนหมด
        self.assertTrue((self.dl / "งาน.pdf").exists())  # ไม่แตะไฟล์ดาวน์โหลด
        self.assertIn("ออกจากบัญชีเว็บ", b.signOutAll())  # กดซ้ำตอนไม่มีโปรไฟล์ = ไม่พัง

    def test_sign_out_refusals_keep_the_profile(self):
        self.assertIn("หน้าเข้าสู่ระบบ", self.make(active=False).signOutAll())  # H7 ไม่มีเจ้าของเซสชัน
        b = self.make()
        b._busy = True
        self.assertIn("กำลังทำงาน", b.signOutAll())
        with mock.patch.object(control, "profile_in_use", return_value=True):
            self.assertIn("เปิดค้าง", self.make().signOutAll())
        with mock.patch.object(Path, "rename", side_effect=OSError(13, "Permission denied")):
            self.assertIn("ลบไม่สำเร็จ", self.make().signOutAll())
        self.assertTrue((self.prof / "Default" / "Cookies").exists())

    def test_voice_routes(self):
        self.assertEqual(route("เปิดยูทูบ", False), BROWSER)
        self.assertEqual(route("เปิดกูเกิลไดรฟ์", False), BROWSER)
        self.assertEqual(route("เปิดปฏิทิน", False), COMMAND)  # หน้าปฏิทินของเครื่อง


@unittest.skipIf(BrowserController is None, "ไม่มี PySide6")
class OpenSiteBackendTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ran, self.hooked, self.free = [], [], True

        def hook(site, url):
            self.hooked.append((site, url))
            return self.free

        ex = actions.Executor(runner=lambda a: self.ran.append(a) or 0, dry_run=False, browser=hook)
        self.s = SkillsController(executor=ex, reminders_path=Path(self.tmp.name) / "r.json",
                                  run_timer=False)  # fmt: skip

    def test_button_takes_only_names_from_the_list(self):
        self.assertEqual(self.s.openSite("https://evil.example"), "ไม่มีเว็บนี้ในรายการ")  # H7
        self.assertEqual((self.ran, self.hooked), ([], []))
        self.assertEqual(self.s.openSite("instagram"), "ไม่มีเว็บนี้ในรายการ")  # เอาออกแล้ว
        self.assertEqual(self.s.openSite("gmail"), "เปิด Gmail ในเบราว์เซอร์ของผู้ช่วย")
        self.assertEqual(self.hooked, [("gmail", URL["gmail"])])

    def test_typed_open_says_which_browser(self):
        card = self.s.handle("เปิดยูทูบ")
        self.assertIn("เปิด YouTube ในเบราว์เซอร์ของผู้ช่วย", card["lines"])
        self.assertEqual(self.s.handle("เปิดเฟซบุ๊ก")["title"], "ระบบนี้ไม่มี Facebook")
        self.free = False
        card = self.s.handle("เปิดกูเกิลไดรฟ์")
        self.assertTrue(any("เบราว์เซอร์ปกติ" in x for x in card["lines"]))
        self.assertEqual(self.ran, [["xdg-open", URL["drive"]]])


try:
    from tests import test_ui_qml as qml
except ImportError:  # pragma: no cover
    qml = None


@unittest.skipIf(qml is None or qml.uiapp is None, "ไม่มี PySide6")
class WebAppsQmlTest(unittest.TestCase):
    open_shell = qml.ShellCardTest.open_shell if qml and qml.uiapp else None

    @classmethod
    def setUpClass(cls):
        qml.setUpModule()

    @classmethod
    def tearDownClass(cls):
        qml.tearDownModule()

    def test_home_tiles(self):
        engine, win, warnings = self.open_shell("workspace")
        skills, browser = engine._backends["skills"], engine._backends["browser"]
        skills._exec = actions.Executor(dry_run=True)  # ไม่เปิดเว็บจริงแม้รันบน Pi
        keys = ["youtube", "gmail", "calendar", "drive"]
        tiles = [qml.find_items(win, "webApp_" + k) for k in keys]
        self.assertEqual([len(t) for t in tiles], [1] * 4)
        self.assertEqual(qml.find_items(win, "webApp_facebook"), [])  # เอาออกแล้ว (Pakon 2026-10-19)
        note = qml.find_items(win, "webAppsNote")[0]
        tiles[1][0].clicked.emit()
        qml.settle(50)
        # เครื่องนี้จำลอง = บอกตามจริง
        self.assertIn("xdg-open https://mail.google.com", note.property("text"))
        browser.opened.emit("เปิดเบราว์เซอร์ไม่ได้: ไม่พบโปรแกรม", False)
        qml.settle(50)
        self.assertEqual(note.property("text"), "เปิดเบราว์เซอร์ไม่ได้: ไม่พบโปรแกรม")
        browser.opened.emit("เปิด Gmail แล้ว", True)
        qml.settle(50)
        self.assertEqual(note.property("text"), "")
        self.assertEqual(warnings, [])

    def test_settings_sign_out_needs_two_presses(self):
        engine, win, warnings = self.open_shell("settings")
        browser = engine._backends["browser"]
        prof = Path(os.environ["XDG_DATA_HOME"]) / "prof"
        (prof / "Default").mkdir(parents=True)
        browser._profile = prof
        btn = qml.find_items(win, "webSignOut")[0]
        btn.clicked.emit()
        qml.settle(50)
        self.assertIn("กดอีกครั้ง", btn.property("text"))
        self.assertTrue(prof.exists())  # กดครั้งเดียวยังไม่ลบ
        btn.clicked.emit()
        qml.settle(50)
        self.assertFalse(prof.exists())
        result = qml.find_items(win, "webSignOutResult")[0]
        self.assertIn("ออกจากบัญชีเว็บในเบราว์เซอร์ของผู้ช่วยแล้ว", result.property("text"))
        self.assertEqual(warnings, [])

    def test_large_font_and_dark_theme_have_no_warnings(self):
        for page in ("workspace", "settings"):
            with self.subTest(page=page):
                engine, win, warnings = self.open_shell(page)
                ui = engine._backends["uiSettings"]
                ui.setFontScale(2.0)
                ui.setTheme("dark")
                qml.settle(80)
                name = "webAppsCard" if page == "workspace" else "webAccountsCard"
                self.assertEqual(len(qml.find_items(win, name)), 1)
                self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
