"""การ์ด 0069: กดปุ่มตามคำที่เห็นบนหน้าเว็บ · เกณฑ์ K1 (หน้าจำลอง · ไม่มีเบราว์เซอร์จริง)."""

import time
import unittest

from aipc.browser import control, textclick
from aipc.browser.control import BrowserControl, Result
from aipc.skills import sitecmd
from aipc.skills.browse import BrowseCommand

try:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    from aipc.ui.handsfree import BrowserController
except ImportError:  # pragma: no cover
    BrowserController = None

VIU = "https://www.viu.com/ott/th/"


def items(*labels):
    return [{"i": i, "label": x} for i, x in enumerate(labels)]


class ChooseTest(unittest.TestCase):
    def test_spoken_target_strips_verbs_not_the_button_name(self):
        cases = {"เข้าสู่ระบบ": ("เข้าสู่ระบบ", False), "กดปุ่มเข้าสู่ระบบให้หน่อย": ("เข้าสู่ระบบ", True),
                 "ช่วยคลิกลิงก์ดูทั้งหมดครับ": ("ดูทั้งหมด", True), "เลือกเมนู ภาษาไทย": ("ภาษาไทย", True),
                 "เข้าหน้าแรก": ("หน้าแรก", True), "ปุ่มเข้าสู่ระบบอยู่ไหน": ("", False),
                 "ทำไมกดไม่ได้": ("", False)}  # fmt: skip
        for text, want in cases.items():
            self.assertEqual(textclick.spoken_target(text), want, text)

    def test_thai_words_find_english_buttons(self):
        """Pakon ที่จอ: Viu/Youku "เข้าสู่ระบบ" · ป้ายบนเว็บมักเป็นอังกฤษ."""
        pick = textclick.choose("เข้าสู่ระบบ", items("หน้าแรก", "Log in", "ภาพยนตร์"))
        self.assertEqual((pick.item["label"], pick.risky), ("Log in", False))
        self.assertEqual(textclick.choose("ล็อกอิน", items("Sign In")).item["i"], 0)

    def test_same_button_twice_takes_the_top_one(self):
        pick = textclick.choose("ดูทั้งหมด", items("ซีรีส์", "ดูทั้งหมด", "หนัง", "ดูทั้งหมด"))
        self.assertEqual(pick.item["i"], 1)

    def test_part_of_a_short_label_counts_but_not_a_long_title(self):
        self.assertEqual(textclick.choose("ภาษาไทย", items("เลือกภาษาไทย")).item["i"], 0)
        title = "รีวิวภาพยนตร์ใหม่ประจำสัปดาห์ เข้าสู่ระบบเพื่อดูต่อได้ทุกตอนแบบไม่มีโฆษณา"
        self.assertIsNone(textclick.choose("เข้าสู่ระบบ", items(title)).item)

    def test_several_different_buttons_ask_instead_of_guessing(self):
        pick = textclick.choose("ตอน", items("ตอนที่ 1", "ตอนที่ 2", "ตอนพิเศษ"))
        self.assertIsNone(pick.item)
        self.assertEqual(pick.choices, ["ตอนที่ 1", "ตอนที่ 2", "ตอนพิเศษ"])
        self.assertIn("หลายปุ่ม", textclick.refuse_text("ตอน", pick))

    def test_money_and_account_buttons_are_not_pressed(self):
        for words, label in (("สมัครสมาชิก", "สมัครสมาชิก"), ("ออกจากระบบ", "ออกจากระบบ"),
                             ("ซื้อเลย", "ซื้อเลย"), ("subscribe", "Subscribe")):  # fmt: skip
            pick = textclick.choose(words, items(label))
            self.assertTrue(pick.risky, words)
            self.assertIn("กดเองที่จอ", textclick.refuse_text(words, pick))

    def test_spelling_variants_still_match(self):
        """หน้า Viu จริง (Pi 5 2026-10-28): ป้าย "บุ๊กมาร์ก" · คนพูด/สกิลเขียน "บุ๊กมาร์ค"."""
        self.assertEqual(textclick.choose("บุ๊กมาร์ค", items("ประวัติ", "บุ๊กมาร์ก")).item["i"], 1)
        self.assertEqual(textclick.choose("กูเกิ้ล", items("กูเกิล")).item["i"], 0)
        self.assertIsNone(textclick.choose("ประวัติ", items("บุ๊กมาร์ก")).item)

    def test_login_without_a_login_button_uses_the_account_entry(self):
        """Viu: ไม่มีปุ่มเข้าสู่ระบบ มี "โปรไฟล์" · Youku: รูปคนไม่มีชื่อ (BUTTONS_JS ตั้งป้าย "ไอคอนบัญชี")."""
        pick = textclick.choose("เข้าสู่ระบบ", items("ประวัติ", "บุ๊กมาร์ก", "โปรไฟล์"))
        self.assertEqual((pick.item["label"], pick.instead), ("โปรไฟล์", True))
        self.assertEqual(textclick.choose("login", items("History", "ไอคอนบัญชี")).item["i"], 1)
        pick = textclick.choose("เข้าสู่ระบบ", items("Log in", "โปรไฟล์"))
        self.assertEqual((pick.item["label"], pick.instead), ("Log in", False))  # มีปุ่มจริง = กดปุ่มจริง
        self.assertIsNone(textclick.choose("ประวัติ", items("โปรไฟล์")).item)  # เฉพาะคำว่าเข้าสู่ระบบ

    def test_nothing_found_says_so(self):
        pick = textclick.choose("เข้าสู่ระบบ", items("หน้าแรก", "ค้นหา"))
        self.assertIn("ไม่เห็นปุ่ม “เข้าสู่ระบบ”", textclick.refuse_text("เข้าสู่ระบบ", pick))


class SiteSkillLineTest(unittest.TestCase):
    def test_button_label_line(self):
        cmds, errors = sitecmd.parse_section(
            [(1, "- เข้าสู่ระบบ | ล็อกอิน → กดปุ่มที่เขียนว่า เข้าสู่ระบบ|Log in|Sign in")]
        )
        self.assertEqual(errors, [])
        self.assertEqual((cmds[0].kind, cmds[0].arg), ("click_text", "เข้าสู่ระบบ|Log in|Sign in"))
        for bad in ("เข้า|", "javascript:alert(1)", "x" * 60):
            errors = sitecmd.parse_section([(1, f"- เข้า → กดปุ่มที่เขียนว่า {bad}")])[1]
            self.assertTrue(any("ป้ายปุ่ม" in e for e in errors), bad)


class FakeProc:
    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


class FakeCdp:
    """หน้าเว็บจำลอง: ปุ่มที่มองเห็น (ป้าย) · จดเลขปุ่มที่ถูกกด."""

    def __init__(self, url, labels):
        self.url, self.labels, self.clicked, self.closed = url, list(labels), [], False

    def call(self, method, params=None, session="", timeout=15.0):
        if method == "Target.getTargets":
            return {"targetInfos": [{"type": "page", "targetId": "T1"}]}
        if method == "Target.attachToTarget":
            return {"sessionId": "S1"}
        if method == "Browser.getWindowForTarget":
            return {"windowId": 1}
        if method == "Runtime.evaluate":
            return {"result": {"value": self.evaluate(params["expression"])}}
        return {}

    def evaluate(self, js):
        if js == "location.href":
            return self.url
        if js == control.BUTTONS_JS:
            return items(*self.labels)
        if js.startswith(control.CLICK_TEXT_JS):
            self.clicked.append(int(js[len(control.CLICK_TEXT_JS) + 1 : -1]))
            return True
        if js.startswith(control.SELECTOR_CLICK_JS):
            return "none"
        if js.startswith("window.__aipcOld"):
            return self.url
        return None

    def close(self):
        self.closed = True


def browser(labels, url=VIU):
    cdp = FakeCdp(url, labels)
    bc = BrowserControl(launcher=lambda argv: (FakeProc(), cdp), load_timeout=3)
    bc._start("about:blank")
    return bc, cdp


class ControlTest(unittest.TestCase):
    def test_click_by_label(self):
        bc, cdp = browser(["หน้าแรก", "Log in", "Log in"])
        r = bc.run(BrowseCommand("click_text", query="เข้าสู่ระบบ"))
        self.assertTrue(r.ok, r.say)
        self.assertEqual((cdp.clicked, r.say), ([1], "กด “Log in” แล้ว"))
        r = bc.run(BrowseCommand("click_text", query="สมัครสมาชิก"))
        self.assertFalse(r.ok)
        self.assertEqual(cdp.clicked, [1])  # หาไม่เจอ = ไม่กดอย่างอื่นแทน

    def test_guessed_selector_falls_back_to_the_words(self):
        """สกิล Viu ที่ Claude สร้าง (2026-10-28): `a[href*="login"]` ไม่มีในหน้า → หาจากคำของคำสั่ง."""
        bc, cdp = browser(["ซีรีส์", "เข้าสู่ระบบ"])
        guess = 'a[href*="login"]'
        cmd = BrowseCommand("click", query=guess, site="viu", direction="เข้าสู่ระบบ|ล็อกอิน")
        r = bc.run(cmd)
        self.assertTrue(r.ok, r.say)
        self.assertEqual(cdp.clicked, [1])

    def test_skill_label_missing_falls_back_to_the_words(self):
        """สกิล Viu ที่ Claude สร้าง: ป้าย "รายการของฉัน|My List" ไม่มีในหน้า · คำพูด "บุ๊กมาร์ก" มี."""
        bc, cdp = browser(["ประวัติ", "บุ๊กมาร์ก", "โปรไฟล์"])
        cmd = BrowseCommand("click_text", query="รายการของฉัน|My List", site="viu",
                            direction="บุ๊กมาร์ค|bookmark|ดูทีหลัง")  # fmt: skip
        r = bc.run(cmd)
        self.assertEqual((cdp.clicked, r.ok), ([1], True))
        guess = 'a[href*="login"]'
        r = bc.run(BrowseCommand("click", query=guess, site="viu", direction="เข้าสู่ระบบ|login"))
        self.assertEqual(cdp.clicked, [1, 2])
        self.assertIn("แทน", r.say)

    def test_skill_label_only_on_its_site(self):
        bc, cdp = browser(["เข้าสู่ระบบ"], url="https://www.netflix.com/th/")
        r = bc.run(BrowseCommand("click_text", query="เข้าสู่ระบบ", site="viu"))
        self.assertIn("เฉพาะในเว็บของสกิล", r.say)
        self.assertEqual(cdp.clicked, [])


class FakeControl:
    running = True

    def __init__(self, labels):
        self.labels, self.ran = labels, []

    def buttons(self):
        return items(*self.labels)

    def run(self, cmd):
        self.ran.append(cmd.as_dict())
        return Result(True, "กดแล้ว")

    def close(self):
        self.running = False


def pump(until, timeout=5.0):
    end = time.monotonic() + timeout
    while not until() and time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)


@unittest.skipIf(BrowserController is None, "ไม่มี PySide6")
class VoiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_voice_presses_the_button_it_sees(self):
        ctl = FakeControl(["หน้าแรก", "Log in", "ตอนที่ 1", "ตอนที่ 2", "สมัครสมาชิก"])
        b = BrowserController(control=ctl)
        done = []
        b.finished.connect(lambda say, ok: done.append(ok))
        self.assertEqual(b.clickText("เข้าสู่ระบบ"), {"started": True})
        pump(lambda: done)
        self.assertEqual(ctl.ran, [{"kind": "click_text", "query": "Log in"}])
        self.assertIn("หลายปุ่ม", b.clickText("กดตอน")["say"])
        self.assertIn("กดเองที่จอ", b.clickText("กดสมัครสมาชิก")["say"])
        self.assertIn("ไม่เห็นปุ่ม", b.clickText("กดดาวน์โหลด")["say"])
        self.assertEqual(b.clickText("ดาวน์โหลด"), {})  # ไม่ได้พูด "กด" = ให้ทางเสียงอื่นทำต่อ
        self.assertEqual(b.clickText("วันนี้อากาศเป็นยังไง"), {})
        self.assertEqual(len(ctl.ran), 1)

    def test_skill_click_passes_its_words_for_the_fallback(self):
        ctl = FakeControl([])
        b = BrowserController(control=ctl)
        done = []
        b.finished.connect(lambda say, ok: done.append(ok))
        self.assertTrue(b.runSite("click", 'a[href*="login"]', "viu", "เข้าสู่ระบบ|ล็อกอิน"))
        pump(lambda: done)
        self.assertTrue(b.runSite("click_text", "เข้าสู่ระบบ|Log in", "viu", "ล็อกอิน"))
        pump(lambda: len(done) == 2)
        guess = {"kind": "click", "query": 'a[href*="login"]', "site": "viu"}
        label = {"kind": "click_text", "query": "เข้าสู่ระบบ|Log in", "site": "viu"}
        self.assertEqual(
            ctl.ran,
            [{**guess, "direction": "เข้าสู่ระบบ|ล็อกอิน"}, {**label, "direction": "ล็อกอิน"}],
        )
