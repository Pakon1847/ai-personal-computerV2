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

    def test_cancel_reminder_by_typing_asks_then_deletes(self):
        # สำรวจบน Pi 5 2026-10-12: แอปไม่มีทางลบนัด (นัดซ้ำเลิกเตือนไม่ได้) · "ลบนัดทั้งหมด" ถูกส่งต่อ Claude
        for text in ("เตือนส่งรายงานพรุ่งนี้บ่ายสาม", "เตือนกินยาทุกวันตอน 8 โมงเช้า"):
            self.s.confirm(self.s.handle(text)["confirmToken"], True)
        card = self.s.handle("ยกเลิกนัดกินยาด้วยครับ")
        self.assertEqual(card["title"], "ลบนัด 1 รายการ ใช่ไหม")
        self.assertIn("กินยา", card["lines"][0])
        self.assertIn("ซ้ำ", card["lines"][0])
        self.assertEqual(len(self.s._store.items), 2)  # ยังไม่ลบจนกว่าจะยืนยัน
        no = self.s.confirm(card["confirmToken"], False)
        self.assertEqual(no["title"], "ยกเลิกแล้ว ไม่ได้ทำอะไร")
        self.assertEqual(len(self.s._store.items), 2)
        card = self.s.handle("ยกเลิกนัดกินยา")
        self.assertEqual(self.s.confirm(card["confirmToken"], True)["title"], "ลบนัดแล้ว 1 รายการ")
        self.assertEqual([r.what for r in self.s._store.items], ["ส่งรายงาน"])
        self.assertIn("ไม่พบนัด", self.s.handle("ลบนัดหมอฟัน")["title"])
        card = self.s.handle("ลบนัดทั้งหมด")
        self.s.confirm(card["confirmToken"], True)
        self.assertEqual(self.s._store.items, [])
        self.assertEqual(self.s.handle("ลบนัดทั้งหมด")["title"], "ยังไม่มีนัดให้ลบ")
        # ไม่ใช่คำขอลบนัด
        self.assertIsNone(self.s._cancel_card("ลบไฟล์รายงาน"))
        self.assertIsNone(self.s._cancel_card("ยกเลิกการประชุม"))

    def test_next_reminders_and_move_request_stay_local(self):
        # สำรวจบน Pi 5 2026-10-12: "นัดล่าสุดของฉันคืออะไร" → ส่งต่อ Claude ·
        # "เลื่อนนัดประชุมไปบ่ายสาม" → จดนัดใหม่ชื่อ "เลื่อนนัดประชุมไป"
        self.assertEqual(self.s.handle("นัดถัดไปของฉันคืออะไร")["title"], "ยังไม่มีนัดที่รออยู่")
        for text in ("เตือนประชุมพรุ่งนี้บ่ายสอง", "เตือนกินยาทุกวันตอน 8 โมงเช้า"):
            self.s.confirm(self.s.handle(text)["confirmToken"], True)
        card = self.s.handle("นัดล่าสุดของฉันคืออะไร")
        self.assertEqual(card["title"], "นัดที่ยังไม่ถึงเวลา 2 นัด")
        self.assertIn("กินยา", card["lines"][0])
        self.assertFalse(card.get("llm"))
        before = len(self.s._store.items)
        card = self.s.handle("เลื่อนนัดประชุมไปบ่ายสาม")
        self.assertEqual(card["title"], "ยังเลื่อนนัดให้ไม่ได้")
        self.assertEqual(card["confirmToken"], "")
        self.assertTrue(any("ประชุม" in line for line in card["lines"][1:]))
        self.assertEqual(len(self.s._store.items), before)

    def test_time_question_answered_by_clock_not_ai(self):
        # สำรวจบน Pi 5 2026-10-12: "ตอนนี้กี่โมง" AI ในเครื่องตอบว่าไม่รู้ → ส่งต่อ Claude
        for text in ("ตอนนี้กี่โมง", "กี่โมงแล้วครับ", "ตอนนี้เวลาเท่าไหร่", "what time is it"):
            card = self.s.handle(text)
            self.assertEqual(card["kind"], "clock", text)
            self.assertEqual(card["title"], "ตอนนี้ 10:00 น.")
            self.assertFalse(card.get("llm"))
            self.assertIn("โค้ดในเครื่อง", card["why"][0]["v"])
        # ถามเวลาของสิ่งอื่น = ไม่ใช่นาฬิกา
        for text in ("นัดพรุ่งนี้กี่โมง", "ร้านเปิดกี่โมง", "ตอนนี้ที่ญี่ปุ่นกี่โมง", "ราคาทองตอนนี้เท่าไหร่", "เท่าไหร่"):
            self.assertNotEqual(self.s.handle(text)["kind"], "clock", text)

    def test_agenda_question_lists_reminders_and_creates_nothing(self):
        # พบ 2026-10-01: "วันนี้มีนัดอะไร" เคยถูกตีเป็นคำขอจดนัดใหม่ชื่อ "มีนัดอะไร"
        for text in ("เตือนส่งรายงานวันนี้บ่ายสาม", "เตือนโทรหาแม่พรุ่งนี้หกโมงเย็น"):
            self.s.confirm(self.s.handle(text)["confirmToken"], True)
        before = len(self.s._store.items)
        card = self.s.handle("วันนี้มีนัดอะไร")
        self.assertEqual(card["title"][:6], "วันนี้")
        self.assertIn("มี 1 นัด", card["title"])
        self.assertIn("ส่งรายงาน", card["lines"][0])
        self.assertEqual(card["confirmToken"], "")
        card = self.s.handle("พรุ่งนี้มีอะไรบ้าง")
        self.assertIn("โทรหาแม่", card["lines"][0])
        self.assertIn("ยังไม่มีนัด", self.s.handle("มะรืนนี้ต้องทำอะไรบ้าง")["title"])
        self.assertIn("ส่งรายงาน", self.s.handleAs("reminder", "วันนี้ต้องทำอะไรบ้าง")["lines"][0])
        self.assertEqual(len(self.s._store.items), before, "ถามแล้วต้องไม่เกิดนัดใหม่")
        self.assertEqual(self.s.handle("เตือนประชุมพรุ่งนี้บ่ายสอง")["kind"], "reminder")  # จดนัดยังได้

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

    def test_repeating_reminder_fires_every_day(self):
        # นัดซ้ำ (docs/benchmarks/2026-10-02-repeat) · 23 ก.ย. 2569 = วันพุธ 10:00
        s = self.make()
        card = s.handle("เตือนกินยาทุกวันแปดโมงเช้า")
        self.assertIn("24 ก.ย. 2569 · 08:00", card["chips"][0]["text"])  # วันนี้ 8 โมงผ่านแล้ว
        self.assertEqual(card["chips"][1]["text"], "ซ้ำทุกวัน 08:00 น.")
        s.confirm(card["confirmToken"], True)
        self.assertIn("ซ้ำทุกวัน", s.upcoming[0]["when"])
        got = []
        s.reminderDue.connect(got.append)
        for day in (1, 2):
            self.now = datetime(2026, 9, 23 + day, 8, 0).astimezone()
            s.tick()
            s.tick()
        self.assertEqual([("24 ก.ย." in r["when"], "25 ก.ย." in r["when"]) for r in got],
                         [(True, False), (False, True)])  # fmt: skip
        self.assertIn("26 ก.ย. 2569 · 08:00", s.upcoming[0]["when"])  # ตั้งครั้งถัดไปเอง
        week = s.handle("สัปดาห์นี้มีนัดอะไร")
        self.assertGreaterEqual(sum("กินยา" in line for line in week["lines"]), 3)

    def test_repeating_without_time_asks_with_warning(self):
        card = self.make().handle("เตือนประชุมทีมทุกวันจันทร์")
        self.assertTrue(card["confirmToken"], "มีเวลา (เดา) → ถามยืนยัน ไม่ปฏิเสธ")
        self.assertEqual(card["chips"][1]["kind"], "warn")
        self.assertTrue(any("09:00" in line for line in card["lines"]))

    def test_repeat_missed_while_off_reports_once_then_moves_on(self):
        s = self.make()
        s.confirm(s.handle("เตือนกินยาทุกวันสองทุ่ม")["confirmToken"], True)
        self.now = datetime(2026, 9, 27, 9, 0).astimezone()  # ปิดเครื่องไป 3 วันกว่า
        later = self.make()
        self.assertEqual([r["what"] for r in later.missed], ["กินยา"])
        self.assertIn("27 ก.ย. 2569 · 20:00", later.upcoming[0]["when"])
        self.assertEqual(self.make().missed, [])

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
        card = s.handleAs("start-work", "เริ่มวันทำงาน")
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
        card = s.handleAs("start-work", "เริ่มวันทำงาน")
        done = s.confirm(card["confirmToken"], True)
        self.assertTrue(done["title"].startswith("หยุดที่ขั้น 2"))
        self.assertIn("ขั้นที่เหลือ 1 ขั้นไม่ได้ทำ", done["lines"])
        self.assertEqual(done["page"], "", "ขั้น 3 (เปิดหน้า) ต้องไม่ถูกทำ")

    def test_no_means_nothing_runs(self):
        s = self.make()
        card = s.handleAs("start-work", "เริ่มวันทำงาน")
        self.assertEqual(s.confirm(card["confirmToken"], False)["title"], "ยกเลิกแล้ว ไม่ได้ทำอะไร")
        self.assertEqual(self.calls, [])

    def test_say_and_ask_ai_run_without_confirm(self):
        s = self.make()
        # AI พร้อม = แบบผสม: AI เลือกสกิล (handleAs) แล้วทำทางเดียวกับที่กฎเลือก
        card = s.handleAs("idea-note", "จดไอเดีย ทำแอปสอนภาษา")
        self.assertEqual(card["confirmToken"], "", "ไม่มีขั้นที่แตะเครื่อง = ไม่ต้องถาม")
        self.assertIn("อย่าลืมดื่มน้ำ", card["lines"])
        self.assertTrue(card["llm"])
        self.assertEqual(card["prompt"], "เรียบเรียงไอเดียนี้เป็นข้อ ๆ")
        self.assertEqual(card["llmText"], "จดไอเดีย ทำแอปสอนภาษา")
        self.assertEqual(self.calls, [])


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class AiPicksSkillTest(unittest.TestCase):
    """AI ในเครื่องเลือกสกิล (อาจารย์ขอ · งานข้อ ④) · รายการสกิลสร้างจากไฟล์สกิล · AI ส่งได้แค่ชื่อ."""

    def make(self, llm=True):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.calls = []
        ex = actions.Executor(runner=lambda a: self.calls.append(a) or 0, dry_run=False)
        return SkillsController(executor=ex, reminders_path=Path(tmp.name) / "r.json",
                                run_timer=False, llm_ready=lambda: llm)  # fmt: skip

    def test_catalog_comes_from_skill_files(self):
        names = [t["function"]["name"] for t in self.make().tool_catalog()]
        self.assertIn("summarize-text", names)
        self.assertIn("machine-status", names)
        self.assertNotIn("system-command", names, "สั่งเครื่องต้องใช้ชื่อที่แน่นอน ให้กฎทำ")
        tool = self.make().tool_catalog()[0]
        self.assertEqual(tool["function"]["parameters"], {"type": "object", "properties": {}},
                         "ไม่มีพารามิเตอร์ = AI ส่งค่าให้สกิลไม่ได้")  # fmt: skip
        # ไม่มี AI = สกิลที่ต้องใช้ AI ไม่อยู่ในรายการ
        no_ai = [t["function"]["name"] for t in self.make(llm=False).tool_catalog()]
        self.assertNotIn("letter-writer", no_ai)

    def test_handle_as_goes_through_the_normal_path(self):
        s = self.make()
        card = s.handleAs("letter-writer", "อยากบอกหัวหน้าว่าขอทำงานที่บ้าน")
        self.assertTrue(card["llm"])
        self.assertTrue(card["prompt"])
        self.assertEqual(card["badge"]["reason"], "AI ในเครื่องเลือกสกิลนี้")
        machine = s.handleAs("machine-status", "คอมหน่วงมาก")
        self.assertEqual(machine["kind"], "skill")
        self.assertTrue(machine["title"])

    def test_unknown_or_forbidden_names_fall_back_to_chat(self):
        s = self.make()
        for name in ("rm-rf", "system-command"):
            card = s.handleAs(name, "เปิดทุกอย่าง")
            self.assertEqual((card["kind"], card["tools"]), ("chat", False), name)
        self.assertEqual(self.calls, [], "AI เลือกสกิลแล้วต้องไม่มีอะไรรันเอง")


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class TieTest(unittest.TestCase):
    """คะแนนเท่ากัน: เดิมตัวที่โหลดก่อนชนะเงียบ ๆ · ตอนนี้ถามผู้ใช้ (งานข้อ ④)
    ใช้เฉพาะตอน AI ในเครื่องยังไม่พร้อม (กฎก่อน) · AI พร้อม = AI เลือกเอง ไม่ผ่านกฎให้คะแนน."""

    def setUp(self):
        from aipc.skills import manifest

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name)
        # สกิลที่บอกข้อความอย่างเดียว = ไม่ต้องมี AI จึงชนกับสกิลถามเครื่องได้ตอนไม่มี AI
        text = SAY_AI_SKILL.replace("keywords: จดไอเดีย", "keywords: จดไอเดีย, ค้าง")
        text = text.replace("2. ถาม AI: เรียบเรียงไอเดียนี้เป็นข้อ ๆ\n", "")
        (d / "idea.md").write_text(text, encoding="utf-8")
        self.s = SkillsController(
            reminders_path=d / "r.json", run_timer=False, llm_ready=lambda: False
        )
        self.s._skills = [*self.s._skills, *manifest.load_dir(d)]

    def test_tie_asks_then_runs_the_confirmed_skill(self):
        from aipc.skills import router

        r = router.route("งานค้างเยอะ", self.s._skills, set())
        self.assertEqual(sorted(r.tied), ["idea-note", "machine-status"])
        card = self.s.handle("งานค้างเยอะ")
        self.assertTrue(card["confirmToken"])
        self.assertIn("ใช่ไหม", card["title"])
        self.assertEqual(len(card["chips"]), 2)
        self.assertEqual(
            self.s.confirm(card["confirmToken"], False)["title"], "ยกเลิกแล้ว ไม่ได้ทำอะไร"
        )
        card = self.s.handle("งานค้างเยอะ")
        done = self.s.confirm(card["confirmToken"], True)
        self.assertNotIn("ใช่ไหม", done["title"], "ยืนยันแล้ว = ทำเลย ไม่ถามซ้ำ")


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class HybridRouteTest(unittest.TestCase):
    """แบบผสม (ผู้ใช้เลือก 2026-09-30): AI พร้อม = คำสั่งเครื่องทำเลย ที่เหลือให้ AI เลือก ·
    ไม่พร้อม = กฎก่อนแบบเดิม."""

    def make(self, llm):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.calls = []
        ex = actions.Executor(runner=lambda a: self.calls.append(a) or 0, dry_run=False)
        return SkillsController(executor=ex, reminders_path=Path(tmp.name) / "r.json",
                                run_timer=False, llm_ready=lambda: llm)  # fmt: skip

    def test_commands_still_run_at_once_with_ai(self):
        card = self.make(llm=True).handle("เปิดยูทูบ")
        self.assertEqual(card["kind"], "command")
        self.assertEqual(len(self.calls), 1, "คำสั่งเครื่องที่แปลได้แน่นอน ไม่ต้องรอ AI")

    def test_keyword_traps_go_to_ai_not_to_a_skill(self):
        # ประโยคหลอกในชุดวัด: กฎคำสำคัญเลือกสกิลถามเครื่อง (คำว่า "เครื่อง") · แบบผสมให้ AI ตัดสิน
        text = "เครื่องบินลำแรกของโลกบินได้เมื่อไร"
        card = self.make(llm=True).handle(text)
        self.assertEqual(card["kind"], "chat")
        self.assertTrue(card["llm"])
        self.assertNotEqual(card.get("tools"), False, "ต้องส่งรายการสกิลให้ AI เลือก")
        self.assertEqual(self.make(llm=False).handle(text)["kind"], "skill", "ไม่มี AI = กฎก่อน")

    def test_skill_sentence_goes_to_ai_with_the_catalog(self):
        card = self.make(llm=True).handle("เตือนส่งรายงานพรุ่งนี้บ่ายสอง")
        self.assertEqual(card["kind"], "chat")
        self.assertEqual(card["prompt"], "", "prompt ว่าง = ChatController ส่งรายการสกิลไปด้วย")


if __name__ == "__main__":
    unittest.main()
