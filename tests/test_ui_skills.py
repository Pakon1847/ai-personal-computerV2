"""การต่อสกิลเข้ากับหน้าแชท (SkillsController) · ใช้ตัวสั่งงานปลอม ไม่รันคำสั่งจริง."""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

try:
    from aipc.skills import actions
    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class SkillsControllerTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        ex = actions.Executor(runner=lambda a: self.calls.append(a) or 0, dry_run=False)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "reminders.json"
        self.now = datetime(2026, 9, 23, 10, 0).astimezone()
        self.s = SkillsController(executor=ex, reminders_path=self.path, clock=lambda: self.now)

    def test_sure_command_runs_immediately(self):
        card = self.s.handle("เปิดยูทูบ")
        self.assertEqual(card["kind"], "command")
        self.assertEqual(card["title"], "เปิด YouTube")
        self.assertEqual(card["confirmToken"], "")
        self.assertEqual(self.calls, [["xdg-open", "https://www.youtube.com"]])

    def test_unsure_command_waits_for_yes(self):
        card = self.s.handle("เปิดยูทิว")
        token = card["confirmToken"]
        self.assertTrue(token)
        self.assertEqual(self.calls, [], "ต้องไม่รันก่อนผู้ใช้ตอบ")
        done = self.s.confirm(token, True)
        self.assertEqual(done["title"], "เปิด YouTube")
        self.assertEqual(len(self.calls), 1)
        again = self.s.confirm(token, True)  # ใช้ token ซ้ำไม่ได้
        self.assertIn("หมดอายุ", again["title"])
        self.assertEqual(len(self.calls), 1)

    def test_no_means_nothing_runs(self):
        token = self.s.handle("เปิดยูทิว")["confirmToken"]
        self.assertIn("ยกเลิก", self.s.confirm(token, False)["title"])
        self.assertEqual(self.calls, [])

    def test_page_command_tells_ui_where_to_go(self):
        self.assertEqual(self.s.handle("เปิดหน้าตั้งค่า")["page"], "settings")

    def test_llm_skill_says_what_is_missing(self):
        card = self.s.handle("แปลเป็นอังกฤษให้หน่อย")
        self.assertEqual(card["kind"], "needs")
        self.assertTrue(any("โมเดลภาษา" in line for line in card["lines"]))

    def test_general_chat_is_not_faked(self):
        card = self.s.handle("เล่าเรื่องตลกหน่อย")
        self.assertEqual(card["kind"], "chat")
        self.assertIn("ยังตอบไม่ได้", card["title"])

    def test_skill_list_marks_ready_ones(self):
        ready = {s["id"]: s["ready"] for s in self.s.skills}
        self.assertTrue(ready["system-command"])
        self.assertTrue(ready["machine-status"])
        self.assertFalse(ready["translate"])  # รอแชท LLM (การ์ด 0013)
        self.assertNotIn("what-is-this", ready)  # ตัดออกในขอบเขตรอบ 3


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class ReminderSkillTest(unittest.TestCase):
    """การ์ด 0001: จดนัดต้องให้ผู้ใช้ยืนยันก่อน · เตือนครั้งเดียว · พลาดแล้วต้องบอก."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "reminders.json"
        self.now = datetime(2026, 9, 23, 10, 0).astimezone()

    def make(self):
        return SkillsController(reminders_path=self.path, clock=lambda: self.now)

    def test_saves_only_after_yes(self):
        s = self.make()
        card = s.handle("เตือนส่งรายงานพรุ่งนี้บ่ายสอง")
        self.assertEqual(card["kind"], "reminder")
        self.assertIn("ส่งรายงาน", card["title"])
        self.assertIn("24 ก.ย. 2569 · 14:00", card["chips"][0]["text"])
        self.assertFalse(self.path.exists(), "ต้องยังไม่บันทึกก่อนผู้ใช้ตอบ")
        done = s.confirm(card["confirmToken"], True)
        self.assertIn("บันทึกแล้ว", done["title"])
        self.assertEqual([r["what"] for r in s.upcoming], ["ส่งรายงาน"])

    def test_no_means_not_saved(self):
        s = self.make()
        s.confirm(s.handle("เตือนส่งรายงานพรุ่งนี้บ่ายสอง")["confirmToken"], False)
        self.assertEqual(s.upcoming, [])

    def test_unsupported_sentence_is_refused(self):
        card = self.make().handle("เตือนจ่ายค่าเน็ตทุกสิ้นเดือน")
        self.assertEqual(card["title"], "ยังจดนัดนี้ไม่ได้")
        self.assertEqual(card["confirmToken"], "")

    def test_fires_once_when_due(self):
        s = self.make()
        s.confirm(s.handle("เตือนกินยาอีก 30 นาที")["confirmToken"], True)
        got = []
        s.reminderDue.connect(got.append)
        s.tick()
        self.assertEqual(got, [])
        self.now += timedelta(minutes=30)
        s.tick()
        s.tick()
        self.assertEqual([r["what"] for r in got], ["กินยา"])

    def test_missed_reported_once_on_next_session(self):
        s = self.make()
        s.confirm(s.handle("เตือนกินยาอีก 30 นาที")["confirmToken"], True)
        self.now += timedelta(hours=3)  # ปิดเครื่องไประหว่างนั้น
        again = self.make()
        self.assertEqual([r["what"] for r in again.missed], ["กินยา"])
        self.assertEqual(self.make().missed, [], "รายงานพลาดครั้งเดียว")

    def test_broken_file_blocks_saving_and_warns(self):
        self.path.write_text("{เสีย", encoding="utf-8")
        s = self.make()
        self.assertIn("อ่านไฟล์นัดหมายไม่ได้", s.reminderWarning)
        self.assertEqual(s.handle("เตือนส่งรายงานพรุ่งนี้บ่ายสอง")["title"], "จดนัดไม่ได้ตอนนี้")
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{เสีย")


STEP_SKILL = """---
id: start-work
name: เริ่มวันทำงาน
description: เปิดอีเมล เปิดหน้าตั้งค่า และปรับเสียง
keywords: เริ่มวันทำงาน
examples:
  - เริ่มวันทำงาน
  - เริ่มงานเช้านี้
  - เปิดของที่ใช้ทำงาน
permissions: run_actions
---
## ขั้นตอน
1. เปิดเว็บ gmail
2. ปรับเสียง 30
3. เปิดหน้า ตั้งค่า
"""
SAY_AI_SKILL = """---
id: idea-note
name: จดไอเดีย
description: บอกข้อความเตือนแล้วให้ AI ช่วยเรียบเรียงไอเดียที่พิมพ์มา
keywords: จดไอเดีย
examples:
  - จดไอเดีย ร้านกาแฟ
  - จดไอเดีย แอปสอนภาษา
  - จดไอเดีย ของขวัญ
---
## ขั้นตอน
1. บอก: อย่าลืมดื่มน้ำ
2. ถาม AI: เรียบเรียงไอเดียนี้เป็นข้อ ๆ
"""


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class StepSkillTest(unittest.TestCase):
    """สกิลแบบขั้นตอน (.md): แสดงทุกขั้น → ยืนยันครั้งเดียว → โค้ดทำตามลำดับ · ล้มขั้นไหนหยุดตรงนั้น."""

    def make(self, codes=None):
        from aipc.skills import manifest

        self.calls = []
        codes = list(codes or [])

        def runner(args):
            self.calls.append(args)
            return codes.pop(0) if codes else 0

        ex = actions.Executor(runner=runner, dry_run=False)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name)
        for name, text in (("start-work.md", STEP_SKILL), ("idea-note.md", SAY_AI_SKILL)):
            (d / name).write_text(text, encoding="utf-8")
        # llm_ready: สกิลที่ขั้นสุดท้ายเป็น "ถาม AI:" ต้องมี AI (ไม่มี = การ์ดบอกว่าต้องมีอะไรก่อน)
        s = SkillsController(executor=ex, reminders_path=d / "r.json", run_timer=False,
                             llm_ready=lambda: True)  # fmt: skip
        s._skills = [*s._skills, *manifest.load_dir(d)]
        return s

    def test_shows_every_step_and_waits_for_yes(self):
        s = self.make()
        card = s.handle("เริ่มวันทำงาน")
        self.assertEqual(card["kind"], "steps")
        self.assertEqual(card["title"], "จะทำ 3 ขั้นนี้ ใช่ไหม")
        self.assertEqual(card["lines"], ["1. เปิด Gmail", "2. ปรับเสียงเป็น 30%", "3. เปิดหน้าตั้งค่า"])
        self.assertEqual(card["chips"][0]["text"], "ความเสี่ยงกลาง", "ความเสี่ยงของขั้นที่สูงสุด (ปรับเสียง)")
        self.assertTrue(card["confirmToken"])
        self.assertEqual(self.calls, [], "ต้องไม่ทำก่อนผู้ใช้ตอบ")
        done = s.confirm(card["confirmToken"], True)
        self.assertEqual(done["title"], "ทำครบ 3 ขั้นแล้ว")
        self.assertEqual(self.calls, [["xdg-open", "https://mail.google.com"],
                                      ["wpctl", "set-volume", actions.SINK, "30%"]])  # fmt: skip
        self.assertEqual(done["page"], "settings")

    def test_stops_at_the_failing_step(self):
        s = self.make(codes=[0, 5])  # ขั้น 2 (ปรับเสียง) ล้ม
        card = s.handle("เริ่มวันทำงาน")
        done = s.confirm(card["confirmToken"], True)
        self.assertTrue(done["title"].startswith("หยุดที่ขั้น 2"))
        self.assertIn("ขั้นที่เหลือ 1 ขั้นไม่ได้ทำ", done["lines"])
        self.assertEqual(done["page"], "", "ขั้น 3 (เปิดหน้า) ต้องไม่ถูกทำ")

    def test_no_means_nothing_runs(self):
        s = self.make()
        card = s.handle("เริ่มวันทำงาน")
        self.assertEqual(s.confirm(card["confirmToken"], False)["title"], "ยกเลิกแล้ว ไม่ได้ทำอะไร")
        self.assertEqual(self.calls, [])

    def test_say_and_ask_ai_run_without_confirm(self):
        s = self.make()
        # ประโยคที่บอกวัน/เวลา (เช่น "วันนี้" "9 โมง") ไปสกิลนัดหมายก่อนเสมอ (router ข้อ 2) และคำอย่าง "ค้าง"
        # ชนกับสกิลถามเครื่อง (คะแนนเท่ากัน = ตัวที่โหลดก่อนชนะ · แก้ในงานข้อ ④) · จึงใช้ประโยคที่ไม่ชนสกิลอื่น
        card = s.handle("จดไอเดีย ทำแอปสอนภาษา")
        self.assertEqual(card["confirmToken"], "", "ไม่มีขั้นที่แตะเครื่อง = ไม่ต้องถาม")
        self.assertIn("อย่าลืมดื่มน้ำ", card["lines"])
        self.assertTrue(card["llm"])
        self.assertEqual(card["prompt"], "เรียบเรียงไอเดียนี้เป็นข้อ ๆ")
        self.assertEqual(card["llmText"], "จดไอเดีย ทำแอปสอนภาษา")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
