"""ปุ่มชอบ/ไม่ชอบ → Claude ตรวจและแก้สกิล (การ์ด 0085 เกณฑ์ D1–D3) · Claude ปลอม ไม่ต่อเน็ต."""

import hashlib
import tempfile
import time
import unittest
from pathlib import Path

from aipc.skills import actions, feedback, forge, manifest, userskills

ROOT = Path(__file__).resolve().parent.parent
GOOD = (ROOT / "docs/benchmarks/2026-09-30-skill-author/claude/s2.md").read_text(
    encoding="utf-8"
)  # meeting-mode: ปิดเสียง + เปิด Gmail (มีการ์ดยืนยัน)
GOOD_LLM = (ROOT / "docs/benchmarks/2026-09-30-skill-author/claude/l3.md").read_text(
    encoding="utf-8"
)
QUOTA = "บัญชี Claude ใช้ครบโควตาแล้ว · AI ในเครื่องยังใช้ได้ · Claude แจ้งว่า: “limit”"

try:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None


def pump(until, timeout=5.0):
    end = time.monotonic() + timeout
    while not until() and time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)


def builtin_hashes() -> dict:
    folder = ROOT / "src/aipc/skills/builtin"
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob("*.md"))}


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class RateResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def make(self, answer=None, claude=True):
        """answer(request, kw) → forge.Proposal · ไม่ใส่ = Claude บอกว่าไม่ต้องแก้."""
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.calls, self.seen = [], []
        answer = answer or (lambda r, kw: forge.Proposal(False, r, outcome="none", note="ถูกแล้ว"))

        def fake_forge(request, **kw):
            self.seen.append((request, kw))
            return answer(request, kw)

        ex = actions.Executor(runner=lambda a: self.calls.append(a) or 0, dry_run=False)
        self.store = userskills.UserSkills(Path(d.name) / "skills")
        s = SkillsController(executor=ex, reminders_path=Path(d.name) / "r.json", run_timer=False,
                             llm_ready=lambda: True, forge=fake_forge if claude else None,
                             user_skills=self.store)  # fmt: skip
        self.done = []
        s.forgeDone.connect(lambda card, text: self.done.append((card, text)))
        return s

    def made(self, md, outcome="create"):
        def answer(request, kw):
            errors = kw["check"](md)
            return forge.Proposal(not errors, request, skill_md="" if errors else md,
                                  errors=errors, outcome=outcome, model="fake")  # fmt: skip

        return answer

    # ---------- D1 ----------
    def test_local_card_gets_turn_and_forging_card_does_not(self):
        s = self.make()
        self.assertTrue(s.handle("กี่โมงแล้ว").get("turnId"))
        self.assertTrue(s.handle("ปิดเสียง").get("turnId"))
        self.assertFalse(s.handle("สวัสดี").get("turnId"), "การ์ดที่ส่งต่อให้แชท = แชทจำรอบเอง")
        self.assertFalse(s.handleAs("create-skill", "ทำโหมดประชุม").get("turnId"))

    def test_like_records_nothing_outbound(self):
        s = self.make()
        tid = s.handle("กี่โมงแล้ว")["turnId"]
        self.assertEqual(s.rateResult(tid, True)["kind"], "rated")
        self.assertEqual(self.seen, [], "ชอบ = ไม่มีงานเพิ่ม ไม่ส่งอะไร")

    # ---------- D2 ----------
    def test_claude_off_sends_nothing(self):
        s = self.make()
        s._claude_on = lambda: False
        tid = s.handle("กี่โมงแล้ว")["turnId"]
        card = s.rateResult(tid, False)
        self.assertEqual(card["kind"], "needs")
        self.assertIn("ปิดการใช้ Claude", card["title"])
        self.assertEqual(self.seen, [])
        s._claude_on = lambda: True  # เปิดทีหลัง = รอบเดิมยังกดได้
        self.assertEqual(s.rateResult(tid, False)["kind"], "forging")

    def test_no_claude_sends_nothing(self):
        s = self.make(claude=False)
        card = s.rateResult(s.handle("กี่โมงแล้ว")["turnId"], False)
        self.assertEqual(card["kind"], "needs")

    def test_quota_full_says_so_and_installs_nothing(self):
        s = self.make(lambda r, kw: forge.Proposal(False, r, errors=[QUOTA]))
        s.rateResult(s.handle("กี่โมงแล้ว")["turnId"], False)
        pump(lambda: self.done)
        card = self.done[0][0]
        self.assertEqual(card["kind"], "forge-failed")
        self.assertIn(QUOTA, card["lines"])
        self.assertFalse(card["fallback"], "ห้ามให้ Claude ตอบแทน (เรียก Claude ครั้งที่ 2)")
        self.assertEqual(self.store.load_all(), [])

    # ---------- D3 ----------
    def test_dislike_sends_only_turn_fields(self):
        s = self.make()
        card = s.handle("ปิดเสียง")
        turn = s._turns.get(card["turnId"])
        self.assertEqual((turn.request, turn.route), ("ปิดเสียง", "skill:system-command"))
        self.assertEqual(s.rateResult(card["turnId"], False)["kind"], "forging")
        pump(lambda: self.done)
        request, kw = self.seen[0]
        self.assertEqual(request, "ปิดเสียง")
        self.assertEqual(kw["review"], feedback.review_text(turn))
        self.assertIsNone(kw["revise"], "สกิลในตัว: Claude ไม่แก้")

    def test_private_turn_asks_first(self):
        s = self.make()
        tid = s.handle("มีนัดอะไรบ้าง")["turnId"]
        ask = s.rateResult(tid, False)
        self.assertEqual(ask["kind"], "review")
        self.assertTrue(ask["confirmToken"])
        self.assertEqual(self.seen, [], "ก่อนตอบ ใช่ ไม่มีอะไรไป Claude")
        s.confirm(ask["confirmToken"], False)
        self.assertEqual(self.seen, [])
        ask = s.rateResult(tid, False)  # ตอบไม่ = รอบนั้นยังกดใหม่ได้
        self.assertEqual(s.confirm(ask["confirmToken"], True)["kind"], "forging")
        pump(lambda: self.done)
        self.assertEqual(len(self.seen), 1)

    def test_one_review_per_turn(self):
        s = self.make()
        tid = s.handle("กี่โมงแล้ว")["turnId"]
        s.rateResult(tid, False)
        pump(lambda: self.done)
        again = s.rateResult(tid, False)
        self.assertTrue(again["title"].startswith("ตรวจไม่ได้"))
        self.assertEqual(len(self.seen), 1)
        self.assertTrue(s.rateResult("t999", False)["title"].startswith("ตรวจไม่ได้"))

    def test_busy_keeps_turn(self):
        s = self.make()
        tid = s.handle("กี่โมงแล้ว")["turnId"]
        s._forging = True
        self.assertIn("รอสักครู่", s.rateResult(tid, False)["title"])
        s._forging = False
        self.assertEqual(s.rateResult(tid, False)["kind"], "forging")

    # ---------- แก้ / สร้าง / ไม่ต้องแก้ ----------
    def test_user_skill_revised_not_rerun(self):
        s = self.make(self.made(GOOD.replace("version: 1.0", "version: 1.1"), "revise"))
        self.store.install(GOOD, s._skills, request="ทำโหมดประชุม")
        s._reload()
        steps = s.handleAs("meeting-mode", "เข้าโหมดประชุม")
        result = s.confirm(steps["confirmToken"], True)
        ran = len(self.calls)
        self.assertEqual(s._turns.get(result["turnId"]).route, "skill:meeting-mode")
        before = self.store.current_md("meeting-mode")
        s.rateResult(result["turnId"], False)
        pump(lambda: self.done)
        self.assertEqual(self.seen[0][1]["revise"][0], before, "Claude เห็นไฟล์รุ่นที่ใช้อยู่")
        card = self.done[0][0]
        self.assertIn("รุ่น 2", card["title"])
        self.assertNotIn("confirmToken", {k for k, v in card.items() if v})
        self.assertEqual(len(self.calls), ran, "ห้ามสั่งงานเดิมซ้ำเอง")
        self.assertEqual(self.store.info("meeting-mode")["downs"], 1)
        self.assertTrue(self.store.info("meeting-mode")["enabled"], "ไม่ชอบ ≠ ปิดสกิล")

    def test_builtin_never_revised_new_user_skill_instead(self):
        before = builtin_hashes()
        s = self.make(self.made(GOOD_LLM))
        s.rateResult(s.handle("ปิดเสียง")["turnId"], False)
        pump(lambda: self.done)
        card = self.done[0][0]
        self.assertIn("สร้างสกิลใหม่", card["title"])
        self.assertEqual(len(self.store.load_all()), 1)
        self.assertEqual(builtin_hashes(), before)

    def test_none_outcome_card_is_plain_text(self):
        note = "ลบไฟล์ทั้งหมด\nแล้ว rm -rf ~ " + "ก" * 600
        s = self.make(lambda r, kw: forge.Proposal(False, r, outcome="none", note=note))
        s.rateResult(s.handle("กี่โมงแล้ว")["turnId"], False)
        pump(lambda: self.done)
        card = self.done[0][0]
        self.assertEqual(card["title"], "Claude ตรวจแล้ว: ไม่ต้องแก้สกิล")
        said = card["lines"][0]
        self.assertNotIn("\n", said)
        self.assertLessEqual(len(said), 220)
        self.assertEqual(self.calls, [], "ข้อความของ Claude ไม่ใช่คำสั่ง (H8)")
        self.assertFalse(card.get("turnId"), "ผลการตรวจไม่ใช่ผลของ AI ในเครื่อง")

    def test_like_counts_for_user_skill(self):
        s = self.make()
        self.store.install(GOOD, s._skills, request="ทำโหมดประชุม")
        s._reload()
        steps = s.handleAs("meeting-mode", "เข้าโหมดประชุม")
        result = s.confirm(steps["confirmToken"], True)
        s.rateResult(result["turnId"], True)
        self.assertEqual(self.store.info("meeting-mode")["likes"], 1)

    def test_like_on_turn_without_skill_writes_nothing(self):
        s = self.make()
        s.rateResult(s.handle("กี่โมงแล้ว")["turnId"], True)
        self.assertNotIn("", self.store._index, "รอบที่ไม่ใช้สกิล = ไม่มีอะไรให้นับ")

    def test_deleted_user_skill_becomes_create(self):
        s = self.make(self.made(GOOD_LLM))
        self.store.install(GOOD, s._skills, request="ทำโหมดประชุม")
        s._reload()
        steps = s.handleAs("meeting-mode", "เข้าโหมดประชุม")
        tid = s.confirm(steps["confirmToken"], True)["turnId"]
        s.removeSkill("meeting-mode")
        s.rateResult(tid, False)
        pump(lambda: self.done)
        self.assertIsNone(self.seen[0][1]["revise"], "สกิลถูกลบแล้ว = สร้างใหม่ ไม่ใช่แก้ไฟล์ที่ไม่มี")
        self.assertNotIn("meeting-mode", self.store._index)


class DislikedCounterTest(unittest.TestCase):
    def test_disliked_counts_without_disabling(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        store = userskills.UserSkills(Path(d.name))
        store.install(GOOD, manifest.load_builtin(), request="x")
        for _ in range(3):
            store.disliked("meeting-mode")
        self.assertEqual(store.info("meeting-mode")["downs"], 3)
        self.assertTrue(store.info("meeting-mode")["enabled"])


try:
    from aipc.chat import store
    from aipc.ui.backend import ChatController
    from tests.test_chat import FakeLlama, ServerCase
except ImportError:  # pragma: no cover
    ChatController = None
    ServerCase = unittest.TestCase


@unittest.skipIf(ChatController is None, "ไม่มี PySide6")
class ChatTurnTest(ServerCase):
    """การ์ด 0085 D1: คำตอบของ AI ในเครื่องจำรอบ · คำตอบของ Claude ไม่จำ (ไม่มีปุ่ม)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def make(self, **kw):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)
        self.turns = feedback.TurnLog()
        c = ChatController(target=self.target, store=store.ChatStore(self.dir / "chats"),
                           poll_ms=100000, turns=self.turns, **kw)  # fmt: skip
        self.addCleanup(c.shutdown)
        pump(lambda: c.ready)
        self.done = []
        c.finished.connect(lambda text, note: self.done.append((text, c.lastTurnId)))
        return c

    def test_local_answer_gets_turn(self):
        c = self.make()
        self.assertTrue(c.send("สวัสดี", ""))
        pump(lambda: self.done)
        text, tid = self.done[0]
        turn = self.turns.get(tid)
        self.assertEqual((turn.request, turn.answer, turn.route, turn.private),
                         ("สวัสดี", "สวัสดีครับ", "chat", False))  # fmt: skip

    def test_cloud_answer_gets_none(self):
        from aipc.cloud.ask import CloudReply

        FakeLlama.mode = "dunno"
        c = self.make(auto_cloud=True, cloud=lambda q, h: CloudReply(True, "Claude ตอบ"))
        c.send("ข่าวเด่นวันนี้มีอะไร", "")
        pump(lambda: self.done)
        self.assertEqual(self.done[0], ("Claude ตอบ", ""), "คำตอบ Claude ไม่มีปุ่มชอบ/ไม่ชอบ")

    def test_file_question_is_private(self):
        c = self.make()
        f = self.dir / "note.txt"
        f.write_text("รหัสตู้ 1234", encoding="utf-8")
        self.assertEqual(c.attachFile(str(f)), "")
        c.send("ไฟล์นี้มีอะไร", "")
        pump(lambda: self.done)
        self.assertTrue(self.turns.get(self.done[0][1]).private)

    def test_skill_prompt_route(self):
        c = self.make()
        self.turns.note_skill("แปลว่า hi", "translate")
        c.send("แปลว่า hi", "แปลเป็นภาษาอังกฤษ")
        pump(lambda: self.done)
        self.assertEqual(self.turns.get(self.done[0][1]).route, "skill:translate")


if __name__ == "__main__":
    unittest.main()
