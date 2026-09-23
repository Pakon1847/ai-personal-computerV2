"""การต่อสกิลเข้ากับหน้าแชท (SkillsController) · ใช้ตัวสั่งงานปลอม ไม่รันคำสั่งจริง."""

import unittest

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
        self.s = SkillsController(executor=ex)

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


if __name__ == "__main__":
    unittest.main()
