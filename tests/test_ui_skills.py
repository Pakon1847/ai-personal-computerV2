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
        self.assertFalse(ready["translate"])
        self.assertFalse(ready["what-is-this"])


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


if __name__ == "__main__":
    unittest.main()
