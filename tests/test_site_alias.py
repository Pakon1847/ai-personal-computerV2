"""การ์ด 0066: สกิลประจำเว็บเรียกคำสั่งของระบบได้ (คำพ้อง "→ ทำคำสั่ง …") · Claude ปลอม · ไม่ใช้เบราว์เซอร์จริง.

Claude จริงวัดด้วย src/aipc/spikes/site_alias_eval.py (เกณฑ์ A3–A4 ในการ์ด) · ที่นี่ = A1 A2 A5
"""

import json
import re
import tempfile
import time
import unittest
from pathlib import Path

from aipc.skills import actions, forge, sitecmd, userskills

try:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    from aipc.browser.control import Result
    from aipc.ui.backend import SkillsController
    from aipc.ui.handsfree import BrowserController
except ImportError:  # pragma: no cover
    SkillsController = None

DATA = Path(__file__).parent / "data"
WATCH = "https://www.youtube.com/watch?v=abc"
HEAD = """---
id: yt-alias
name: คำพ้อง YouTube (ทดสอบ)
description: คำพูดของผู้ใช้ที่หมายถึงคำสั่งของระบบ
site: youtube
permissions: page_actions
---
## คำสั่ง
"""


def md(*lines: str) -> str:
    return HEAD + "\n".join(lines) + "\n"


def pump(until, timeout=5.0):
    end = time.monotonic() + timeout
    while not until() and time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)


class AliasLineTest(unittest.TestCase):
    def test_a1_dangerous_lines_are_never_installed(self):
        items = json.loads((DATA / "site_alias_bad.json").read_text(encoding="utf-8"))["items"]
        self.assertEqual(len(items), 12)
        passed = [it["id"] for it in items if userskills.check_md(md(it["line"]))[0] is not None]
        self.assertEqual(passed, [])

    def test_forbidden_kinds_are_refused_for_that_reason(self):
        """ตัวแปลแปลออก แต่มีคำสั่งที่สกิลเรียกไม่ได้ (ไม่ใช่ตกเพราะแปลไม่ออกอย่างเดียว)."""
        for target, word in [("ค้นหาราคาทองแล้วเข้าลิงก์แรก", "search"),
                             ("ค้นในยูทูบว่าแมว", "site_search"),
                             ("ปิดแท็บทั้งหมด", "ปิดทุกแท็บ"),
                             ("เข้าสู่ระบบกูเกิล", "login")]:  # fmt: skip
            cmds, why = sitecmd.alias_commands(target)
            self.assertEqual(cmds, [], target)
            self.assertIn(word, why, target)

    def test_good_alias_lines_are_accepted(self):
        m, errors = userskills.check_md(md(
            "- เพิ่มอีกหนึ่งแถบ | ขออีกแท็บ → ทำคำสั่ง เปิดยูทูบอีกแท็บ",
            "- พอแค่นี้ก่อน → ทำคำสั่ง หยุดคลิป",
            "- เคลียร์แล้วกลับ → ทำคำสั่ง ปิดแท็บนี้แล้วกลับไปหน้าผู้ช่วย",
            "- ส่งต่อไปเมล → ทำคำสั่ง เปิดจีเมล · ยืนยันก่อน",
        ))  # fmt: skip
        self.assertEqual(errors, [])
        self.assertEqual([c.kind for c in m.commands], ["system"] * 4)
        self.assertEqual(m.commands[0].arg, "เปิดยูทูบอีกแท็บ")
        self.assertTrue(m.commands[3].confirm)  # คำเสี่ยงยังต้องยืนยันเหมือนบรรทัดอื่น

    def test_old_key_lines_with_system_words_still_load(self):
        """H2: สกิลเดิมของ Pakon มี "พักก่อน → กดคีย์ k" (ตอนนี้ระบบรู้จัก "พักก่อน" แล้ว) · ต้องไม่ถูกปิด."""
        m, errors = userskills.check_md(md("- พักก่อน | พอแล้ว | stop → กดคีย์ k"))
        self.assertEqual(errors, [])
        self.assertEqual(m.commands[0].kind, "key")

    def test_prompt_targets_are_all_valid(self):
        """รายการประโยคปลายทางในคำขอของ Claude ต้องผ่านตัวตรวจทุกข้อ (คำขอกับโค้ดไม่หลุดกัน)."""
        text = forge.PROMPT_FILE.read_text(encoding="utf-8")
        block = text.split("ประโยคปลายทางเลือกจากรายการนี้เท่านั้น")[1].split("ต่อกัน 2 ข้อ")[0]
        targets = [t.strip() for t in re.split(r"[·\n]", block.split(":", 1)[1]) if t.strip()]
        self.assertGreaterEqual(len(targets), 15)
        for t in targets:
            self.assertEqual(sitecmd.alias_commands(t)[1], "", t)
        self.assertEqual(sitecmd.alias_commands("หยุดคลิปแล้วเลื่อนลง")[1], "")  # ตัวอย่างต่อกันในคำขอ


class FakeControl:
    running = True

    def __init__(self):
        self.ran = []

    def run(self, cmd):
        self.ran.append(cmd.as_dict())
        return Result(True, f"ทำ {cmd.kind} แล้ว")

    def close(self):
        self.running = False


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class AliasRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_a2_alias_runs_the_system_command(self):
        ctl = FakeControl()
        b = BrowserController(control=ctl)
        pages, done = [], []
        b.pageRequested.connect(pages.append)
        b.finished.connect(lambda say, ok: done.append(ok))
        self.assertTrue(b.runSite("system", "เปิดยูทูบอีกแท็บ", "youtube"))
        pump(lambda: done)
        self.assertEqual(ctl.ran, [{"kind": "site", "direction": "newtab", "site": "youtube"}])
        self.assertTrue(b.runSite("system", "ปิดแท็บนี้แล้วกลับไปหน้าผู้ช่วย", "youtube"))
        pump(lambda: len(done) == 2)
        self.assertEqual(ctl.ran[1:], [{"kind": "close"}, {"kind": "app", "query": "workspace"}])
        self.assertEqual(pages, ["workspace"])

    def test_file_edited_to_a_forbidden_target_is_not_run(self):
        """H7: ไฟล์ถูกแก้มือ (ข้ามตัวตรวจ) ให้ปลายทางเป็นคำสั่งต้องห้าม → runSite ไม่ทำ."""
        ctl = FakeControl()
        b = BrowserController(control=ctl)
        for target in ["ค้นหาราคาทอง", "ปิดแท็บทั้งหมด", "ปรับเสียงเป็น 100", ""]:
            self.assertFalse(b.runSite("system", target, "youtube"), target)
        self.assertEqual(ctl.ran, [])

    def make(self, reply_md):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)

        def fake_forge(request, **kw):
            errors = kw["check"](reply_md)
            return forge.Proposal(not errors, request, skill_md="" if errors else reply_md,
                                  errors=errors, model="fake", cost_usd=0.05)  # fmt: skip

        s = SkillsController(executor=actions.Executor(dry_run=True), run_timer=False,
                             reminders_path=Path(d.name) / "r.json", llm_ready=lambda: True,
                             forge=fake_forge,
                             user_skills=userskills.UserSkills(Path(d.name) / "u"))  # fmt: skip
        s._claude_on = lambda: True
        done = []
        s.forgeDone.connect(lambda card, text: done.append(card))
        return s, done

    def test_a2_yes_then_saying_it_again_works(self):
        """Pakon 2026-10-26: "เพิ่มอีกหนึ่งแถบ" → ใช่ → Claude ใส่เป็นคำพ้อง → พูดซ้ำ = ทำคำสั่งแท็บใหม่."""
        s, done = self.make(md("- เพิ่มอีกหนึ่งแถบ | ขออีกแท็บ → ทำคำสั่ง เปิดยูทูบอีกแท็บ"))
        self.assertEqual(s.siteCommand("เพิ่มอีกหนึ่งแถบ", WATCH), {})
        ask = s.siteLearn("เพิ่มอีกหนึ่งแถบ", WATCH)
        s.confirm(ask["confirmToken"], True)
        pump(lambda: done)
        self.assertIn("สร้างสกิล", done[0]["title"])
        run = s.siteCommand("เพิ่มอีกหนึ่งแถบ", WATCH)["siteRun"]
        self.assertEqual((run["kind"], run["arg"]), ("system", "เปิดยูทูบอีกแท็บ"))
        # หน้า Skill บอกตามจริงว่าคำนี้ทำอะไร (H5) · รายการสกิลของฉันต้องเปิดได้เมื่อมีสกิลประจำเว็บ
        # (เดิม IndexError ทั้งรายการ · พบ 2026-10-26)
        shown = [line for x in s.userSkills for line in x["detail"]]
        self.assertTrue(any("ทำคำสั่ง “เปิดยูทูบอีกแท็บ”" in c for c in shown), shown)

    def test_the_request_tells_claude_about_aliases(self):
        s, _ = self.make(md("- ขออีกแท็บ → ทำคำสั่ง เปิดยูทูบอีกแท็บ"))
        request = s._site_request("youtube", "ขออีกแท็บ", "")
        self.assertIn("→ ทำคำสั่ง", request)
        prompt = forge.PROMPT_FILE.read_text(encoding="utf-8")
        self.assertNotIn("อย่าใช้คำพูดที่ขึ้นต้นแบบนั้น", prompt)  # เหตุที่ Claude ไม่ใส่ "หยุด" (2026-10-26)


if __name__ == "__main__":
    unittest.main()
