"""สกิลอัตโนมัติ (การ์ด 0017) · Claude ปลอม ไม่ต่อเน็ต · ชุดสกิลเสียคือเกณฑ์ข้อ 10.2 (ติดตั้งไม่ได้ 100%)."""

import json
import tempfile
import time
import unittest
from pathlib import Path

from aipc.skills import forge, manifest, userskills

ROOT = Path(__file__).resolve().parent.parent
GOOD = (ROOT / "docs/benchmarks/2026-09-30-skill-author/claude/s2.md").read_text(encoding="utf-8")  # meeting-mode
GOOD_LLM = (ROOT / "docs/benchmarks/2026-09-30-skill-author/claude/l3.md").read_text(encoding="utf-8")
BAD = json.loads((ROOT / "tests/data/bad_skills.json").read_text(encoding="utf-8"))

try:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    from aipc.skills import actions
    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None


class GateTest(unittest.TestCase):
    def test_every_bad_skill_is_rejected(self):
        builtin = manifest.load_builtin()
        passed = [it["id"] for it in BAD["items"] if userskills.gate(it["skill_md"], builtin)[0] is not None]
        self.assertEqual(passed, [], "เกณฑ์การ์ด 0017 ข้อ 10.2: สกิลเสียต้องติดตั้งไม่ได้ทุกไฟล์")

    def test_good_skills_from_claude_pass(self):
        builtin = manifest.load_builtin()
        for md in (GOOD, GOOD_LLM):
            m, errors = userskills.gate(md, builtin)
            self.assertIsNotNone(m, errors)

    def test_payload_after_colon_is_not_counted_as_overlap(self):
        # "มาช้า" อยู่ในข้อความที่ผู้ใช้วาง ไม่ใช่คำสั่งเช็กเครื่องช้า
        self.assertEqual(userskills._pick("ทำให้เป็นทางการหน่อย", manifest.load_builtin()), "")


class DefineIntentTest(unittest.TestCase):
    """กฎตั้งโหมด/งานประจำ (router.define_intent) · ประโยคจากชุดพัฒนาเท่านั้น (ไม่ใช้ชุดประเมิน)."""

    def test_mode_and_routine_go_to_create(self):
        from aipc.skills import router

        builtin = manifest.load_builtin()
        for t in ("เปิดโหมดพักผ่อนหน่อย", "เริ่มโหมดทำการบ้าน", "ต่อไปถ้าบอกว่าเช็กเมล ให้เปิด Gmail กับ Google"):
            self.assertEqual(router.route_ai_first(t, builtin).kind, "create", t)
        for t in ("โหมดเครื่องบินในมือถือคืออะไร", "เปิดหน้าสกิล", "ปิดเสียงหน่อย", "สกิลในเครื่องนี้มีอะไรบ้าง"):
            self.assertNotEqual(router.route_ai_first(t, builtin).kind, "create", t)

    def test_existing_mode_skill_is_used_not_recreated(self):
        from aipc.skills import router

        store_dir = tempfile.TemporaryDirectory()
        self.addCleanup(store_dir.cleanup)
        store = userskills.UserSkills(Path(store_dir.name))
        builtin = manifest.load_builtin()
        m = store.install(GOOD, builtin, request="โหมดประชุม")  # คำสำคัญมี "โหมดประชุม"
        r = router.route_ai_first("เข้าโหมดประชุมให้หน่อย", [*builtin, m])
        self.assertEqual((r.kind, r.skill.id), ("skill", "meeting-mode"))


class StoreTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.store = userskills.UserSkills(Path(d.name) / "skills")
        self.builtin = manifest.load_builtin()

    def test_install_revise_keeps_every_version(self):
        m = self.store.install(GOOD, self.builtin, request="โหมดประชุม")
        self.assertEqual(self.store.info(m.id)["version"], 1)
        v2 = GOOD.replace("3. บอก:", "3. บอก: (รุ่นแก้)")
        self.store.install(v2, [*self.builtin, m], request="โหมดประชุม", replacing=m.id)
        self.assertEqual(self.store.info(m.id)["version"], 2)
        self.assertIn("รุ่นแก้", self.store.current_md(m.id))
        versions = sorted(p.name for p in (self.store.folder / ".versions" / m.id).iterdir())
        self.assertEqual(versions, ["1.md", "2.md"])

    def test_bad_skill_writes_nothing(self):
        with self.assertRaises(manifest.InvalidSkill):
            self.store.install(BAD["items"][0]["skill_md"], self.builtin, request="x")
        self.assertFalse(self.store.folder.exists() and any(self.store.folder.glob("*.md")))

    def test_two_strikes_disable_and_success_resets(self):
        m = self.store.install(GOOD, self.builtin, request="โหมดประชุม")
        self.assertFalse(self.store.wrong(m.id))
        self.store.record(m.id, True)  # ใช้สำเร็จ = นับใหม่
        self.assertFalse(self.store.wrong(m.id))
        self.assertTrue(self.store.wrong(m.id))
        self.assertEqual(self.store.load(), [])
        self.store.set_enabled(m.id, True)
        self.assertEqual([s.id for s in self.store.load()], [m.id])

    def test_broken_index_still_loads(self):
        m = self.store.install(GOOD, self.builtin, request="โหมดประชุม")
        (self.store.folder / "index.json").write_text("{เสีย", encoding="utf-8")
        again = userskills.UserSkills(self.store.folder)
        self.assertEqual([s.id for s in again.load()], [m.id])
        self.assertEqual(again.info(m.id)["version"], 1)

    def test_remove(self):
        m = self.store.install(GOOD, self.builtin, request="โหมดประชุม")
        self.assertTrue(self.store.remove(m.id))
        self.assertEqual(self.store.load(), [])
        self.assertFalse((self.store.folder / ".versions" / m.id).exists())


class ForgeReviseTest(unittest.TestCase):
    def test_revise_sends_old_file_and_feedback_and_gate_errors_go_back(self):
        prompts = []
        replies = [BAD["items"][2]["skill_md"], GOOD]  # รอบแรกเปิดลิงก์เอง (ประตูไม่ยอม) → รอบสองแก้แล้ว

        def runner(args, prompt, cwd, timeout):
            prompts.append(prompt)
            md = replies[len(prompts) - 1]
            return 0, json.dumps({"result": json.dumps({"skill_md": md}), "total_cost_usd": 0.01}), ""

        builtin = manifest.load_builtin()
        p = forge.forge("โหมดประชุม", skills=builtin, runner=runner, revise=(GOOD, "ให้เปิด Gmail ด้วย"),
                        check=lambda md: userskills.gate(md, builtin)[1])  # fmt: skip
        self.assertEqual((p.skill_md != "", p.errors), (True, []))
        self.assertEqual(len(prompts), 2)
        self.assertIn("ให้เปิด Gmail ด้วย", prompts[0])
        self.assertIn("เฉพาะเว็บในรายการ", prompts[1])  # เหตุที่ประตูไม่ยอมถูกส่งกลับให้ Claude แก้


def pump(until, timeout=5.0):
    end = time.monotonic() + timeout
    while not until() and time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class ControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def make(self, reply_md):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.calls = []
        seen = self.seen = []

        def fake_forge(request, **kw):
            seen.append((request, kw))
            errors = kw["check"](reply_md)
            return forge.Proposal(not errors, request, skill_md=reply_md if not errors else "",
                                  errors=errors, model="fake", cost_usd=0.05)  # fmt: skip

        ex = actions.Executor(runner=lambda a: self.calls.append(a) or 0, dry_run=False)
        store = userskills.UserSkills(Path(d.name) / "skills")
        s = SkillsController(executor=ex, reminders_path=Path(d.name) / "r.json", run_timer=False,
                             llm_ready=lambda: True, forge=fake_forge, user_skills=store)  # fmt: skip
        done = []
        s.forgeDone.connect(lambda card, text: done.append((card, text)))
        return s, done

    def test_create_installs_then_runs_and_ai_sees_it_next_time(self):
        s, done = self.make(GOOD)
        names = [t["function"]["name"] for t in s.tool_catalog()]
        self.assertIn("create-skill", names)
        card = s.handleAs("create-skill", "เข้าโหมดประชุมให้หน่อย")
        self.assertEqual(card["kind"], "forging")
        pump(lambda: done)
        card, text = done[0]
        self.assertEqual(card["badge"]["forgedId"], "meeting-mode")
        self.assertIn("Claude สร้าง", card["lines"][0])
        self.assertNotEqual(card["confirmToken"], "")  # ขั้นที่สั่งเครื่องยังถามยืนยันตามกติกาเดิม
        s.confirm(card["confirmToken"], True)
        self.assertEqual(len(self.calls), 2)  # ปิดเสียง + เปิด Gmail
        self.assertIn("meeting-mode", [t["function"]["name"] for t in s.tool_catalog()])
        self.assertTrue(any(k["byClaude"] for k in s.skills))

    def test_failed_forge_installs_nothing_and_asks_cloud_instead(self):
        s, done = self.make(BAD["items"][0]["skill_md"])
        s.handleAs("create-skill", "ล้างเครื่องให้หน่อย")
        pump(lambda: done)
        card, _ = done[0]
        self.assertEqual(card["kind"], "forge-failed")
        self.assertTrue(card["fallback"])
        self.assertEqual(len(s._skills), len(manifest.load_builtin()))

    def test_wrong_twice_disables_and_remove_deletes(self):
        s, done = self.make(GOOD)
        s.handleAs("create-skill", "เข้าโหมดประชุมให้หน่อย")
        pump(lambda: done)
        card = s.reviseSkill("meeting-mode", "ให้เปิด Gmail ก่อนปิดเสียง", "")
        self.assertEqual(card["kind"], "forging")
        self.assertEqual(self.seen[-1][1]["revise"][1], "ให้เปิด Gmail ก่อนปิดเสียง")
        pump(lambda: len(done) == 2)
        card = s.reviseSkill("meeting-mode", "ยังไม่ถูก", "")
        self.assertEqual(card["title"], "ปิดสกิลนี้แล้ว")
        self.assertNotIn("meeting-mode", [t["function"]["name"] for t in s.tool_catalog()])
        self.assertEqual(s.removeSkill("meeting-mode")["title"], "ลบสกิลนี้แล้ว")
        self.assertEqual(s.removeSkill("translate")["title"], "ลบไม่ได้: ไม่ใช่สกิลที่ Claude สร้าง")

    def test_no_claude_no_tool(self):
        s = SkillsController(run_timer=False, llm_ready=lambda: True)
        self.assertNotIn("create-skill", [t["function"]["name"] for t in s.tool_catalog()])
        self.assertEqual(s.handleAs("create-skill", "x")["kind"], "needs")


if __name__ == "__main__":
    unittest.main()
