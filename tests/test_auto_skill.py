"""สกิลอัตโนมัติ (การ์ด 0017) · Claude ปลอม ไม่ต่อเน็ต · ชุดสกิลเสียคือเกณฑ์ข้อ 10.2 (ติดตั้งไม่ได้ 100%)."""

import json
import tempfile
import time
import unittest
from pathlib import Path

from aipc.skills import actions, forge, manifest, userskills

ROOT = Path(__file__).resolve().parent.parent
GOOD = (ROOT / "docs/benchmarks/2026-09-30-skill-author/claude/s2.md").read_text(
    encoding="utf-8"
)  # meeting-mode
GOOD_LLM = (ROOT / "docs/benchmarks/2026-09-30-skill-author/claude/l3.md").read_text(
    encoding="utf-8"
)
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
        passed = [
            it["id"]
            for it in BAD["items"]
            if userskills.gate(it["skill_md"], builtin)[0] is not None
        ]
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

    def test_several_actions_are_not_one_command(self):
        from aipc.skills import command

        self.assertIsNone(command.parse("เปิด YouTube แล้วเพิ่มเสียง"))  # เดิม: เพิ่มเสียงอย่างเดียว
        self.assertIsNone(command.parse("ปิดเสียงแล้วเปิดยูทูบ"))
        self.assertEqual(command.parse("เปิดเสียง").plan.action, "unmute")
        self.assertEqual(command.parse("ปิดเสียงหน่อย").plan.action, "mute")
        self.assertIsNone(command.parse("เปิดวิกิกับกูเกิลรอไว้เลย"))  # เดิม: เปิด Google อย่างเดียว
        self.assertIsNone(command.parse("เปิด Gmail และ Google"))
        self.assertEqual(
            command.parse("เปิดกูเกิลแมพ").plan.params, {"site": "maps"}
        )  # คำซ้อนไม่นับสองอย่าง

    def test_same_sentence_as_request_uses_that_skill(self):
        from aipc.skills import router

        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        store = userskills.UserSkills(Path(d.name))
        builtin = manifest.load_builtin()
        store.install(GOOD_LLM, builtin, request="x")
        m = store.load()[0]
        req = m.extra["request"]  # คำขอเดิมที่ stamp ไว้ในไฟล์
        r = router.route_ai_first(req + " ครับ", [*builtin, m])
        self.assertEqual((r.kind, r.skill.id), ("skill", m.id))
        self.assertIsNone(router.repeat_of("ประโยคอื่นที่ไม่เคยเห็น", [*builtin, m]))

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
            return (
                0,
                json.dumps({"result": json.dumps({"skill_md": md}), "total_cost_usd": 0.01}),
                "",
            )

        builtin = manifest.load_builtin()
        p = forge.forge(
            "โหมดประชุม",
            skills=builtin,
            runner=runner,
            revise=(GOOD, "ให้เปิด Gmail ด้วย"),
            check=lambda md: userskills.gate(md, builtin)[1],
        )
        self.assertEqual((p.skill_md != "", p.errors), (True, []))
        self.assertEqual(len(prompts), 2)
        self.assertIn("ให้เปิด Gmail ด้วย", prompts[0])
        self.assertIn("เฉพาะเว็บในรายการ", prompts[1])  # เหตุที่ประตูไม่ยอมถูกส่งกลับให้ Claude แก้


class ReviseKeepsIdTest(unittest.TestCase):
    def test_new_id_from_claude_is_replaced_with_the_original(self):
        # พบบน Pi 5: แก้ work-mode แล้ว Claude ตั้งชื่อใหม่ open-terminal-help → ประตูไม่ยอม
        # "รุ่นแก้ต้องใช้ id เดิม"
        renamed = GOOD.replace("id: meeting-mode", "id: open-terminal-help")

        def runner(args, prompt, cwd, timeout):
            return (
                0,
                json.dumps({"result": json.dumps({"skill_md": renamed}), "total_cost_usd": 0.01}),
                "",
            )

        builtin = manifest.load_builtin()
        p = forge.forge(
            "โหมดประชุม",
            skills=builtin,
            runner=runner,
            revise=(GOOD, "ผิด"),
            check=lambda md: userskills.gate(md, builtin, "meeting-mode")[1],
        )
        self.assertEqual((p.skill_id, p.errors), ("meeting-mode", []))


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
            return forge.Proposal(
                not errors,
                request,
                skill_md=reply_md if not errors else "",
                errors=errors,
                model="fake",
                cost_usd=0.05,
            )

        ex = actions.Executor(runner=lambda a: self.calls.append(a) or 0, dry_run=False)
        store = userskills.UserSkills(Path(d.name) / "skills")
        s = SkillsController(
            executor=ex,
            reminders_path=Path(d.name) / "r.json",
            run_timer=False,
            llm_ready=lambda: True,
            forge=fake_forge,
            user_skills=store,
        )
        done = []
        s.forgeDone.connect(lambda card, text: done.append((card, text)))
        return s, done

    def test_claude_switch_off_blocks_forge(self):
        """สวิตช์ Claude ปิด (2026-10-05): ไม่มี create-skill ให้ AI · สั่งสร้างแล้วบอกตรง ๆ ·
        ไม่เรียก Claude."""
        s, done = self.make(GOOD)
        on = [False]
        s._claude_on = lambda: on[0]
        self.assertFalse(s.canForge)
        self.assertNotIn("create-skill", [t["function"]["name"] for t in s.tool_catalog()])
        card = s.handleAs("create-skill", "เข้าโหมดประชุมให้หน่อย")
        self.assertEqual(card["kind"], "needs")
        self.assertIn("ปิดการใช้ Claude", card["title"])
        # พิมพ์เอง (ไม่ผ่าน AI): เดิมส่งให้ AI ในเครื่องตอบว่าสร้างไม่ได้ โดยไม่บอกว่าต้องเปิดสวิตช์
        card = s.handle("อยากได้สกิลโหมดฟังเพลง เปิดยูทูบแล้วปรับเสียงเป็น 60")
        self.assertEqual(card["kind"], "needs")
        self.assertIn("หน้าตั้งค่า", card["lines"][0])
        self.assertEqual(self.seen, [])
        on[0] = True
        self.assertTrue(s.canForge)

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
        # การ์ด 0028: บอกประโยคที่พูดผ่านคีย์ลัดได้จริง
        self.assertEqual(card["lines"][1], "กด Alt+Space แล้วพูดได้: “เข้าโหมดประชุมให้หน่อย”")
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

    def test_export_then_import_on_another_account(self):
        # ฟีเจอร์ข้อ 9: ส่งออกเป็น .md → อีกบัญชีนำเข้า (ผ่านประตูเดียวกัน · ดูก่อนแล้วค่อยติดตั้ง)
        import os
        from unittest import mock

        s, done = self.make(GOOD)
        s.handleAs("create-skill", "เข้าโหมดประชุมให้หน่อย")
        pump(lambda: done)
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        with mock.patch.object(Path, "home", return_value=Path(home.name)):
            msg = s.exportSkill("meeting-mode")
        self.assertIn("สกิลที่ส่งออก", msg)
        exported = Path(home.name) / "สกิลที่ส่งออก" / "meeting-mode.md"
        self.assertTrue(exported.is_file())

        other, _ = self.make(GOOD)  # บัญชีอื่น (คลังว่าง)
        preview = other.importSkill(str(exported), False)
        self.assertIn("กดอีกครั้ง", preview)
        self.assertEqual(other.userSkills, [], "ดูก่อน = ยังไม่ติดตั้ง")
        self.assertIn("ติดตั้งสกิล", other.importSkill(str(exported), True))
        self.assertTrue(other.userSkills[0]["imported"])
        bad = Path(home.name) / "bad.md"
        bad.write_text(BAD["items"][2]["skill_md"], encoding="utf-8")  # เปิดลิงก์เอง
        self.assertIn("ติดตั้งไม่ได้", other.importSkill(str(bad), True))
        # โน้ต .md ธรรมดา (พบ 2026-10-12: เดิมได้ข้อความเทคนิคเรื่องส่วนหัว ---)
        note = Path(home.name) / "บันทึกประชุม.md"
        note.write_text("# บันทึกประชุม\n- ส่งงานวันศุกร์\n", encoding="utf-8")
        self.assertIn("โน้ตธรรมดา", other.importSkill(str(note), False))
        self.assertEqual(len(other.userSkills), 1)
        self.assertTrue(os.path.exists(exported))

    def test_no_claude_no_tool(self):
        s = SkillsController(run_timer=False, llm_ready=lambda: True)
        self.assertNotIn("create-skill", [t["function"]["name"] for t in s.tool_catalog()])
        self.assertEqual(s.handleAs("create-skill", "x")["kind"], "needs")


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class ForgeLedgerTest(unittest.TestCase):
    """การ์ด 0022 ข้อ ข: บันทึกส่งออกเขียน ok: false ทั้งที่สกิลติดตั้งได้ (T6 Pi 5 2026-10-08)."""

    def _run(self, proposal):
        from unittest import mock

        from aipc.cloud.ledger import Ledger
        from aipc.ui import app

        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        ledger = Ledger(Path(d.name) / "outbound.json")
        with mock.patch("aipc.cloud.ask.find_claude", return_value="claude"), \
             mock.patch.object(forge, "run_process", return_value=(0, "2.1 (Claude Code)", "")), \
             mock.patch.object(forge, "forge", return_value=proposal):  # fmt: skip
            run = app._skill_forge(None, ledger)
            run("ทำโหมดประชุม", skills=[])
        return ledger.entries()[0]

    def test_installable_skill_is_ok_even_if_rule_trial_misses(self):
        p = forge.Proposal(False, "ทำโหมดประชุม", skill_md=GOOD, skill_id="meeting-mode", attempts=1,
                           trial={"trigger_fail": ["meeting mode"]})  # fmt: skip
        e = self._run(p)
        self.assertTrue(e["ok"])
        self.assertIn("ไม่กระทบการติดตั้ง", e["note"])

    def test_no_skill_is_not_ok(self):
        e = self._run(forge.Proposal(False, "ทำโหมดประชุม", errors=["Claude ตอบไม่สำเร็จ"]))
        self.assertFalse(e["ok"])


# สกิลที่ขั้นสุดท้ายถาม AI (code+llm) · ใช้ตรวจว่าไม่เข้าทางเสียง (การ์ด 0028)
ASK_AI = GOOD
for old, new in (
    ("id: meeting-mode", "id: news-mode"),
    ("name: โหมดประชุม", "name: โหมดข่าว"),
    ("worker: code", "worker: code+llm"),
    ("  - จะเข้าประชุมแล้ว", "  - ขอฟังข่าวหน่อย"),
    ("  - เข้าโหมดประชุมให้หน่อย", "  - เข้าโหมดข่าวให้หน่อย"),
    ("  - meeting mode", "  - news mode"),
):
    ASK_AI = ASK_AI.replace(old, new)
ASK_AI = ASK_AI.split("## ขั้นตอน")[0] + "## ขั้นตอน\n1. ปิดเสียง\n2. ถาม AI: สรุปข่าวเด่นสั้น ๆ\n"


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class VoiceSkillTest(unittest.TestCase):
    """การ์ด 0028: พูดประโยคของสกิลที่ทำด้วยโค้ดผ่านคีย์ลัด = ทำสกิลนั้น · ตรงเป๊ะเท่านั้น."""

    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.store = userskills.UserSkills(Path(d.name) / "skills")
        builtin = manifest.load_builtin()
        self.store.install(GOOD, builtin, request="อยากได้สกิลโหมดประชุม: ปิดเสียงเครื่อง แล้วเปิด Gmail ให้")
        self.store.install(GOOD_LLM, builtin + self.store.load(), request="อยากได้สกิลคิดเมนู")
        self.ran = []  # ตัวสั่งเครื่องจำลอง: จดคำสั่งแทนการปิดเสียง/เปิดเว็บจริง
        ex = actions.Executor(runner=lambda a: self.ran.append(a) or 0, dry_run=False)
        self.s = SkillsController(executor=ex, reminders_path=Path(d.name) / "r.json",
                                  run_timer=False, llm_ready=lambda: True,
                                  user_skills=self.store)  # fmt: skip
        ask = Path(d.name) / "news-mode.md"
        ask.write_text(ASK_AI, encoding="utf-8")
        self.ask_ai = manifest.load(ask)

    def test_exact_phrases_of_code_skills_only(self):
        s = self.s
        for text in ("เข้าโหมดประชุมให้หน่อย", "ช่วยเข้าโหมดประชุม", "meeting mode", "จะเข้าประชุมแล้วครับ",
                     "อยากได้สกิลโหมดประชุม: ปิดเสียงเครื่อง แล้วเปิด Gmail ให้"):  # fmt: skip
            self.assertEqual(s.voiceSkill(text), "meeting-mode", text)
        self.assertEqual(s.voiceSkill("ในตู้เย็นมีไข่ หมูสับ ผักกาด ทำอะไรกินดี"), "")  # สกิล llm
        s._skills = [*s._skills, self.ask_ai]
        self.assertEqual(self.ask_ai.worker, "code+llm")
        self.assertEqual(s.voiceSkill("เข้าโหมดข่าวให้หน่อย"), "")  # ขั้นสุดท้ายถาม AI
        self.assertEqual(s.voiceSkill("เข้าโหมดประชม"), "")  # ได้ยินเพี้ยน = ไม่ทำ
        self.assertEqual(s.voiceSkill("ปิดเสียง"), "")  # คำสั่งเครื่องไม่ใช่สกิลของผู้ใช้

    def test_near_miss_asks_once_and_does_nothing_until_yes(self):
        """ทาง ก (การ์ด 0028 หัวข้อ 12): ได้ยินใกล้เคียง = "หมายถึง … ใช่ไหม" · ไม่สั่งเครื่องก่อนตอบ."""
        card = self.s.voiceConfirm("โหมดประชุมให้หน่อย")  # คำแรก "เข้า" หาย (พบในข้อ 3)
        self.assertEqual(card["title"], "หมายถึง “โหมดประชุม” ใช่ไหม")
        self.assertIn("ใกล้กับ “เข้าโหมดประชุมให้หน่อย”", card["lines"][0])
        self.assertEqual(card["lines"][1:], ["1. ปิดเสียง", "2. เปิด Gmail",
                                             card["lines"][3]])  # fmt: skip
        self.assertEqual(self.ran, [])  # ยังไม่ทำอะไร
        done = self.s.confirm(card["confirmToken"], True)
        self.assertEqual(len(self.ran), 2)  # ปิดเสียง + เปิด Gmail · ยืนยันครั้งเดียว
        self.assertEqual(done["kind"], "steps")
        no = self.s.voiceConfirm("เข้าโหมดประชม")
        self.s.confirm(no["confirmToken"], False)
        self.assertEqual(len(self.ran), 2)  # "ไม่" = ไม่ทำ

    def test_exact_or_far_phrases_get_no_confirm_card(self):
        self.assertEqual(self.s.voiceConfirm("เข้าโหมดประชุมให้หน่อย"), {})  # ตรงเป๊ะ = ทางสกิลปกติ
        self.assertEqual(self.s.voiceConfirm("ราคาทองวันนี้"), {})  # ไม่ใกล้ = ไม่รู้จักคำสั่ง
        self.assertEqual(self.s.voiceConfirm("คิดเมนูจากของในตู้เย็นหน่อย"), {})  # สกิล llm ไม่เข้า

    def test_disabled_skill_is_not_voice_command(self):
        self.store.set_enabled("meeting-mode", False)
        self.s._reload()
        self.assertEqual(self.s.voiceSkill("เข้าโหมดประชุมให้หน่อย"), "")

    def test_spoken_example_skips_phrases_that_are_existing_commands(self):
        """การ์ดสร้างสกิลบอกประโยคที่พูดแล้วถึงสกิลจริง ·
        "เปิดแผนที่ให้หน่อย" = คำสั่งเปิด Google Maps เดิม (H5)."""
        s3 = (ROOT / "docs/benchmarks/2026-09-30-skill-author/claude/s3.md").read_text(
            encoding="utf-8"
        )
        self.store.install(s3, self.s._skills, request="อยากได้สกิลดูแผนที่")
        self.s._reload()
        self.assertEqual(self.s.voiceExample("map-open"), "อยากไปสยามพารากอน ไปยังไง")
        self.assertEqual(self.s.voiceExample("meeting-mode"), "เข้าโหมดประชุมให้หน่อย")
        self.assertEqual(self.s.voiceExample("fridge-menu"), "")  # สกิลที่ใช้ AI ไม่มีประโยคเสียง

    def test_voice_runs_the_same_card_as_typing(self):
        card = self.s.handleAs(self.s.voiceSkill("เข้าโหมดประชุม"), "เข้าโหมดประชุม")
        self.assertEqual(card["kind"], "steps")
        self.assertEqual(card["badge"]["name"], "โหมดประชุม")
