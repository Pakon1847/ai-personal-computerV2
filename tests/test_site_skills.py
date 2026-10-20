"""การ์ด 0046: สกิลประจำเว็บ · รูปแบบไฟล์ · ตัวตรวจ (W4) · เทียบคำพูด · กดคีย์/คลิกในเบราว์เซอร์ · เส้นทางเสียง.

Claude ปลอม ไม่ต่อเน็ต · เบราว์เซอร์จำลอง (เบราว์เซอร์จริงวัดบน Pi = เกณฑ์ W2)
"""

import json
import tempfile
import time
import unittest
from pathlib import Path

from aipc.browser import control
from aipc.browser.control import BrowserControl
from aipc.skills import catalog, forge, manifest, router, sitecmd, userskills
from aipc.skills.browse import BrowseCommand

ROOT = Path(__file__).resolve().parent.parent
BAD = json.loads((ROOT / "tests/data/site_skills_bad.json").read_text(encoding="utf-8"))
YT = """---
id: yt-test
name: สั่ง YouTube ด้วยเสียง (ทดสอบ)
description: กดคีย์ลัดและปุ่มของ YouTube ด้วยเสียง
site: youtube
permissions: page_actions
---
## คำสั่ง
- ถอยหลังสิบวิ | ย้อนสิบวิ → กดคีย์ j
- เดินหน้าสิบวิ → กดคีย์ l
- วิดีโอถัดไป → กดคีย์ Shift+N
- กดไลก์ → คลิก like-button-view-model button
- ยกเลิกสมัครสมาชิก → คลิก #subscribe-button button · ยืนยันก่อน
"""
WATCH = "https://www.youtube.com/watch?v=abc"

try:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    from aipc.skills import actions
    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None


def skill(md=YT):
    m, errors = userskills.check_md(md)
    assert m is not None, errors
    return m


class FormatTest(unittest.TestCase):
    def test_commands_are_read_from_the_file(self):
        m = skill()
        self.assertEqual((m.site, m.worker, len(m.commands)), ("youtube", "code", 5))
        self.assertEqual(m.commands[0], sitecmd.SiteCommand(("ถอยหลังสิบวิ", "ย้อนสิบวิ"), "key", "j"))
        self.assertEqual(m.commands[3].kind, "click")
        self.assertTrue(m.commands[4].confirm)
        self.assertFalse(m.commands[3].confirm)
        self.assertEqual(m.examples[0], "ถอยหลังสิบวิ")  # คนอ่านเห็นว่าพูดอะไรได้

    def test_w4_every_dangerous_file_is_rejected(self):
        """เกณฑ์ W4: ชุดไฟล์อันตรายที่เขียนก่อน (tests/data/site_skills_bad.json) ตกทุกไฟล์ ·
        ไฟล์คำสั่งเสี่ยงตกด้วยเหตุที่ตั้งใจ (ไม่มี "ยืนยันก่อน")."""
        builtin = manifest.load_builtin()
        passed = [it["id"] for it in BAD["items"] if userskills.gate(it["skill_md"], builtin)[0]]
        self.assertEqual(passed, [])
        for it in BAD["items"]:
            if it["risky"]:
                with self.subTest(it["id"]):
                    errors = userskills.gate(it["skill_md"], builtin)[1]
                    self.assertTrue(any("ยืนยันก่อน" in e for e in errors), errors)

    def test_risky_commands_pass_once_they_ask_first(self):
        """ตัวตรวจไม่ได้ปัดตกทุกอย่าง: ไฟล์เสี่ยงชุดเดียวกัน เติม "· ยืนยันก่อน" แล้วผ่าน และคำสั่งนั้นต้องยืนยัน."""
        builtin = manifest.load_builtin()
        for it in BAD["items"]:
            if not it["risky"]:
                continue
            lines = it["skill_md"].rstrip("\n").split("\n")
            lines[-1] += " · ยืนยันก่อน"
            m, errors = userskills.gate("\n".join(lines) + "\n", builtin)
            with self.subTest(it["id"]):
                self.assertEqual(errors, [])
                self.assertTrue(m.commands[-1].confirm)

    def test_site_is_required_and_only_with_the_section(self):
        no_site = YT.replace("site: youtube\n", "")
        self.assertIsNone(userskills.check_md(no_site)[0])
        lone = YT.split("## คำสั่ง")[0] + "## ขั้นตอน\n1. เปิดเว็บ youtube\n"
        m, errors = userskills.check_md(lone)
        self.assertIsNone(m)
        self.assertTrue(any("site" in e for e in errors), errors)

    def test_bad_line_says_the_format(self):
        _, errors = sitecmd.parse_section([(9, "- หยุด กดคีย์ k")])
        self.assertIn("บรรทัด 9", errors[0])

    def test_too_many_commands(self):
        rows = [(i, f"- คำสั่ง{i} → กดคีย์ k") for i in range(sitecmd.MAX_COMMANDS + 1)]
        self.assertTrue(any("มากเกิน" in e for e in sitecmd.parse_section(rows)[1]))


class BuiltinSiteSkillsTest(unittest.TestCase):
    def test_w1_claude_wrote_youtube_and_spotify(self):
        """W1: สกิลประจำเว็บของ YouTube และ Spotify (Claude เขียน) ผ่านตัวตรวจ · คำสั่ง ≥ 10 ต่อเว็บ."""
        got = {s.site: s for s in manifest.load_builtin() if s.site}
        self.assertEqual(sorted(got), ["spotify", "youtube"])
        for site, s in got.items():
            with self.subTest(site=site):
                self.assertGreaterEqual(len(s.commands), 10)
                self.assertIn("Claude", s.author)
                md = (manifest.BUILTIN_DIR / f"{s.id}.md").read_text(encoding="utf-8")
                self.assertEqual(userskills.check_md(md)[1], [])


class SiteMatchTest(unittest.TestCase):
    def test_domain(self):
        self.assertTrue(sitecmd.on_site("youtube", WATCH))
        self.assertTrue(sitecmd.on_site("youtube", "https://m.youtube.com/watch?v=1"))
        self.assertFalse(sitecmd.on_site("youtube", "https://evil-youtube.com/watch"))
        self.assertFalse(sitecmd.on_site("youtube", "https://youtube.com.evil.example/"))
        self.assertFalse(sitecmd.on_site("youtube", "https://www.netflix.com/browse"))
        self.assertFalse(sitecmd.on_site("youtube", ""))
        self.assertTrue(sitecmd.on_site("https://www.example.org/x", "https://example.org/page"))

    def test_exact_near_and_wrong_site(self):
        skills = [skill()]
        s, c, exact = sitecmd.match("ย้อน สิบวิ ครับ", skills, WATCH)
        self.assertEqual((s.id, c.arg, exact), ("yt-test", "j", True))
        s, c, exact = sitecmd.match("ถอยหลังสิบวี", skills, WATCH)  # ได้ยินเพี้ยน = ใกล้ (ต้องถามก่อน)
        self.assertEqual((c.arg, exact), ("j", False))
        self.assertEqual(sitecmd.match("ถอยหลังสิบวิ", skills, "https://www.netflix.com/")[0], None)
        for text in ("สวัสดีครับ", "วันนี้อากาศดีจัง", "เปิดเพลงหน่อย", ""):
            with self.subTest(text=text):
                self.assertIsNone(sitecmd.match(text, skills, WATCH)[0])

    def test_site_skills_stay_out_of_chat_routing(self):
        """สกิลประจำเว็บไม่เข้าตัวคัดสกิลของแชท/รายการเครื่องมือของ AI (ใช้ทางเสียงในเว็บนั้นเท่านั้น)."""
        pool = [*manifest.load_builtin(), skill()]
        r = router.route("ถอยหลังสิบวิ", pool, {"llm"})
        self.assertNotEqual(getattr(r.skill, "id", ""), "yt-test")
        names = [t["function"]["name"] for t in catalog.tools(pool, {"llm"})]
        self.assertNotIn("yt-test", names)
        self.assertTrue(forge.trial(skill(), manifest.load_builtin(), [], []).ok)


class KeyEventTest(unittest.TestCase):
    def test_keys(self):
        want = {"key": "j", "code": "KeyJ", "windowsVirtualKeyCode": 74, "modifiers": 0}
        self.assertEqual(control.key_event("j"), want)
        self.assertEqual(control.key_event("Shift+N")["key"], "N")
        self.assertEqual(control.key_event("Shift+N")["modifiers"], 8)
        self.assertEqual(control.key_event("Space")["key"], " ")
        self.assertEqual(control.key_event("ArrowRight")["windowsVirtualKeyCode"], 39)
        self.assertEqual(control.key_event(">")["modifiers"], 8)  # > = Shift + .
        self.assertEqual(control.key_event("Ctrl+Shift+k")["modifiers"], 10)
        self.assertEqual(control.key_event("5")["code"], "Digit5")

    def test_no_text_is_typed(self):
        for spec in ("j", "Space", "Shift+N", "5", "/"):
            self.assertNotIn("text", control.key_event(spec))

    def test_every_allowed_key_has_an_event(self):
        """ทุกคีย์ที่ตัวตรวจยอมให้ผ่าน แปลงเป็นเหตุการณ์ได้ (ไม่พังตอนพูด)."""
        for spec in (*sitecmd._SPECIAL, *",./;'[]=<>?-", "a", "Z", "0", "Alt+Shift+b"):
            with self.subTest(spec=spec):
                self.assertTrue(sitecmd.KEY_RE.fullmatch(spec))
                control.key_event(spec)

    def test_browser_keys_are_rejected(self):
        for spec in ("Ctrl+W", "ctrl+shift+w", "Ctrl+T", "Ctrl+L"):
            with self.subTest(spec=spec):
                errors = sitecmd.parse_section([(1, f"- ปิด → กดคีย์ {spec}")])[1]
                self.assertTrue(any("เบราว์เซอร์" in e for e in errors), errors)


class FakeProc:
    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


class FakeCdp:
    """เว็บจำลอง: ที่อยู่ปัจจุบัน + ตัวเลือกที่มีปุ่มอยู่ · จดคีย์ที่กดและปุ่มที่คลิก."""

    def __init__(self, url, buttons=()):
        self.url, self.buttons, self.closed = url, set(buttons), False
        self.keys, self.clicked, self.blurred = [], [], 0

    def call(self, method, params=None, session="", timeout=15.0):
        params = params or {}
        if method == "Target.getTargets":
            return {"targetInfos": [{"type": "page", "targetId": "T1"}]}
        if method == "Target.attachToTarget":
            return {"sessionId": "S1"}
        if method == "Browser.getWindowForTarget":
            return {"windowId": 1}
        if method == "Input.dispatchKeyEvent":
            self.keys.append((params["type"], params["key"], params["modifiers"], "text" in params))
            return {}
        if method == "Runtime.evaluate":
            return {"result": {"value": self.evaluate(params["expression"])}}
        return {}

    def evaluate(self, js):
        if js == "location.href":
            return self.url
        if js == control.BLUR_JS:
            self.blurred += 1
            return None
        if js.startswith(control.SELECTOR_CLICK_JS):
            sel = json.loads(js[len(control.SELECTOR_CLICK_JS) + 1 : -1])
            if sel.startswith("[["):
                return "bad"
            if sel in self.buttons:
                self.clicked.append(sel)
                return "ok"
            return "none"
        if js.startswith("window.__aipcOld"):
            return self.url
        return None

    def close(self):
        self.closed = True


def browser(url, buttons=()):
    cdp = FakeCdp(url, buttons)
    bc = BrowserControl(launcher=lambda argv: (FakeProc(), cdp), load_timeout=3)
    bc._start("about:blank")  # เปิดเบราว์เซอร์จำลองไว้ก่อน (คำสั่งในหน้าเว็บต้องมีหน้าเปิดอยู่)
    return bc, cdp


class BrowserTest(unittest.TestCase):
    def test_key_on_the_right_site(self):
        bc, cdp = browser(WATCH)
        r = bc.run(BrowseCommand("key", query="Shift+N", site="youtube"))
        self.assertTrue(r.ok, r.say)
        self.assertEqual(cdp.keys, [("rawKeyDown", "N", 8, False), ("keyUp", "N", 8, False)])
        self.assertEqual(cdp.blurred, 1)  # ช่องค้นหาที่ค้างโฟกัสไม่กินคีย์ลัด

    def test_nothing_happens_on_another_site(self):
        """W3: หน้าที่เปิดอยู่ไม่ใช่เว็บของสกิล = ไม่กด ไม่คลิก."""
        bc, cdp = browser("https://www.netflix.com/browse", buttons=["button.like"])
        for cmd in (BrowseCommand("key", query="k", site="youtube"),
                    BrowseCommand("click", query="button.like", site="youtube")):  # fmt: skip
            r = bc.run(cmd)
            self.assertFalse(r.ok)
            self.assertIn("เฉพาะในเว็บของสกิล", r.say)
        self.assertEqual((cdp.keys, cdp.clicked), ([], []))

    def test_click(self):
        bc, cdp = browser(WATCH, buttons=["like-button-view-model button"])
        r = bc.run(BrowseCommand("click", query="like-button-view-model button", site="youtube"))
        self.assertTrue(r.ok, r.say)
        self.assertEqual(cdp.clicked, ["like-button-view-model button"])
        r = bc.run(BrowseCommand("click", query="button.gone", site="youtube"))
        self.assertFalse(r.ok)
        self.assertIn("ไม่มีปุ่มนั้น", r.say)  # หาไม่เจอ = บอกตามจริง ไม่กดอย่างอื่นแทน
        r = bc.run(BrowseCommand("click", query="[[x", site="youtube"))
        self.assertIn("ผิดรูป", r.say)

    def test_needs_an_open_page(self):
        bc = BrowserControl(launcher=lambda argv: (FakeProc(), FakeCdp(WATCH)), load_timeout=3)
        r = bc.run(BrowseCommand("key", query="k", site="youtube"))
        self.assertFalse(r.handled)  # เบราว์เซอร์ยังไม่เปิด = ไม่ใช่งานของคำสั่งนี้ (ไม่เปิดเบราว์เซอร์เอง)


def pump(until, timeout=5.0):
    end = time.monotonic() + timeout
    while not until() and time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class VoiceFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def make(self, reply_md=""):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.seen = []

        def fake_forge(request, **kw):
            self.seen.append((request, kw))
            errors = kw["check"](reply_md)
            return forge.Proposal(not errors, request, skill_md="" if errors else reply_md,
                                  errors=errors, model="fake", cost_usd=0.05)  # fmt: skip

        store = userskills.UserSkills(Path(d.name) / "u")
        s = SkillsController(executor=actions.Executor(dry_run=True), run_timer=False,
                             reminders_path=Path(d.name) / "r.json", llm_ready=lambda: True,
                             forge=fake_forge, user_skills=store)  # fmt: skip
        s._claude_on = lambda: True
        done = []
        s.forgeDone.connect(lambda card, text: done.append(card))
        return s, done

    def test_exact_runs_risky_asks_near_asks(self):
        s, _ = self.make()
        s._skills = [*s._skills, skill()]
        card = s.siteCommand("ถอยหลังสิบวิ", WATCH)
        self.assertEqual(card["siteRun"], {"kind": "key", "arg": "j", "site": "youtube"})
        self.assertEqual(s.siteCommand("ถอยหลังสิบวิ", "https://www.netflix.com/"), {})
        risky = s.siteCommand("ยกเลิกสมัครสมาชิก", WATCH)
        self.assertNotIn("siteRun", risky)  # คำสั่งที่มี "ยืนยันก่อน" ไม่ทำเอง
        self.assertEqual(s.confirm(risky["confirmToken"], False).get("siteRun"), None)
        risky = s.siteCommand("ยกเลิกสมัครสมาชิก", WATCH)
        self.assertEqual(
            s.confirm(risky["confirmToken"], True)["siteRun"]["arg"], "#subscribe-button button"
        )
        self.assertEqual(s.siteCommand("ถอยหลังสิบวี", WATCH), {})  # ใกล้ ≠ ทำเลย
        near = s.siteNear("ถอยหลังสิบวี", WATCH)
        self.assertIn("หมายถึง", near["title"])
        self.assertEqual(s.confirm(near["confirmToken"], True)["siteRun"]["arg"], "j")
        self.assertEqual(s.siteNear("ถอยหลังสิบวิ", WATCH), {})  # ตรงเป๊ะไม่ใช่งานของ siteNear
        self.assertIn("ถอยหลังสิบวิ", s.voicePhrases())  # คำพูดเข้าคำใบ้ของตัวถอดเสียง

    def test_unknown_on_site_asks_to_add_then_works(self):
        """W5 (Claude ปลอม): ไม่รู้จัก → ถาม → ใช่ → Claude เพิ่ม → พูดซ้ำแล้วทำได้ · ครั้งต่อไปแก้สกิลเดิม."""
        mine = YT.replace("id: yt-test", "id: yt-mine") + "- เปิดหน้าช่อง → คลิก ytd-channel-name a\n"
        s, done = self.make(mine)
        self.assertEqual(s.siteCommand("เปิดหน้าช่อง", WATCH), {})
        ask = s.siteLearn("เปิดหน้าช่อง", WATCH)
        self.assertIn("เพิ่มคำสั่ง “เปิดหน้าช่อง”", ask["title"])
        self.assertEqual(self.seen, [])  # ยังไม่ส่งอะไรจนกว่าจะตอบใช่
        card = s.confirm(ask["confirmToken"], True)
        self.assertEqual(card["kind"], "forging")
        pump(lambda: done)
        self.assertIn("เปิดหน้าช่อง", self.seen[0][0])
        self.assertIn("ไม่ต้องใส่ซ้ำ", self.seen[0][0])  # บอก Claude ว่าสกิลในเครื่องมีคำสั่งอะไรแล้ว
        self.assertIn("สร้างสกิล", done[0]["title"])
        self.assertTrue(done[0]["voice"])
        self.assertEqual(s.siteCommand("เปิดหน้าช่อง", WATCH)["siteRun"]["arg"], "ytd-channel-name a")
        # ครั้งต่อไป: แก้สกิลของผู้ใช้ตัวเดิม (ไม่สร้างใหม่ทุกครั้ง)
        ask = s.siteLearn("ซ่อนแชทสด", WATCH)
        s.confirm(ask["confirmToken"], True)
        pump(lambda: len(done) > 1)
        self.assertIsNotNone(self.seen[1][1]["revise"])
        self.assertIn("เพิ่มคำสั่งเสียง", self.seen[1][1]["revise"][1])

    def test_learn_only_where_it_can(self):
        s, _ = self.make()
        self.assertEqual(s.siteLearn("ซ่อนแชทสด", ""), {})  # ไม่มีหน้าเว็บ
        self.assertEqual(s.siteLearn("ซ่อนแชทสด", "https://unknown.example/"), {})  # เว็บนอกรายการ
        self.assertEqual(s.siteLearn("ทำไมวิดีโอกระตุก", WATCH), {})  # คำถาม = ทางเดิม (ส่งไปถามในแชท)
        s._claude_on = lambda: False
        self.assertEqual(s.siteLearn("ซ่อนแชทสด", WATCH), {})  # ปิด Claude = ไม่ถาม


if __name__ == "__main__":
    unittest.main()
