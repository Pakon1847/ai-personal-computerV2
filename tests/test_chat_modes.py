"""แชท 2 แบบ (การ์ด 0053 · เกณฑ์ M1–M5 ส่วนเทสต์) · llama-server ปลอม + Claude ปลอม ไม่ใช้เน็ต."""

import json
import tempfile
import unittest
from pathlib import Path

from aipc.chat import store
from aipc.cloud import ask
from aipc.cloud.ask import CloudReply
from aipc.skills import catalog, command
from tests.test_chat import ChatController, FakeLlama, ServerCase, pump

try:
    from PySide6.QtGui import QGuiApplication

    from aipc.ui.backend import UiSettings
except ImportError:  # pragma: no cover
    UiSettings = None

DATA = Path(__file__).parent / "data" / "chat_mode_dev.json"


@unittest.skipIf(ChatController is None, "ไม่มี PySide6")
class ChatModesTest(ServerCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def make(self, claude_on=True, cloud=True, model="sonnet"):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.asked, self.model = [], [model]
        on = [claude_on]
        self.on = on

        def fake(question, history, model=None):
            self.asked.append((question, model))
            return CloudReply(True, f"Claude ตอบ: {question}", model=f"claude-{model}-x")

        c = ChatController(target=self.target, store=store.ChatStore(Path(d.name)), poll_ms=100000,
                           cloud=fake if cloud else None, claude_on=lambda: on[0],
                           cloud_model=lambda: self.model[0])  # fmt: skip
        self.addCleanup(c.shutdown)
        pump(lambda: c.ready)
        done = []
        c.finished.connect(lambda text, note: done.append((text, note)))
        return c, done

    def ask_all(self, c, done, texts):
        for t in texts:
            n = len(done)
            self.assertTrue(c.send(t, ""), t)
            pump(lambda n=n: len(done) > n)

    def test_m1_general_never_sends_out(self):
        # 30 ข้อความ: คุยทั่วไป 10 · AI ในเครื่องตอบว่าไม่รู้ 10 · AI เลือก ask-cloud เอง 10 → ส่งออก 0 ครั้ง
        c, done = self.make()
        self.assertEqual(c.mode, "general")
        self.ask_all(c, done, [f"สวัสดี {i}" for i in range(10)])
        FakeLlama.mode = "dunno"
        self.ask_all(c, done, [f"ราคาทองวันนี้ {i}" for i in range(10)])
        self.assertTrue(all(note == c.WORK_HINT for _, note in done[-10:]))  # บอกทาง ไม่ส่งเอง
        FakeLlama.mode, FakeLlama.tool_name = "tool", catalog.ASK_CLOUD
        self.addCleanup(setattr, FakeLlama, "tool_name", "machine-status")
        for i in range(10):
            c.send(f"ข่าววันนี้ {i}", "")
            pump(lambda: not c.busy)
        self.assertEqual(self.asked, [])
        real = [b for b in FakeLlama.seen if b.get("max_tokens") != 1]
        names = {t["function"]["name"] for b in real for t in b.get("tools") or []}
        self.assertNotIn(catalog.ASK_CLOUD, names)  # AI ในเครื่องไม่เห็นเครื่องมือส่งออกเลย

    def test_m2_work_uses_chosen_model_for_each(self):
        c, done = self.make()
        self.assertTrue(c.setMode("work"))
        for m in ask.MODELS:
            self.model[0] = m
            self.ask_all(c, done, [f"{m} ข้อ {i}" for i in range(3)])
        self.assertEqual([m for _, m in self.asked], [m for m in ask.MODELS for _ in range(3)])
        self.assertIn("claude-opus-x", done[-1][1])  # ป้ายบอกโมเดลที่ตอบจริง
        rows = {r["k"]: r["v"] for r in c.lastTrace}
        self.assertIn("claude-opus-x", rows["ใครตอบ"])

    def test_work_does_not_need_local_ai(self):
        c, done = self.make()
        c.setMode("work")
        c._status = "down"  # AI ในเครื่องล่ม · แชทงานยังถามได้
        self.ask_all(c, done, ["สรุปข่าวให้หน่อย"])
        self.assertEqual(len(self.asked), 1)

    def test_m3_bad_model_never_sent(self):
        c, done = self.make()
        c.setMode("work")
        self.model[0] = "gpt-4; rm -rf"
        self.ask_all(c, done, ["ทดสอบ"])
        self.assertEqual(self.asked[-1][1], "sonnet")  # ค่าแปลก = ใช้ค่าเริ่มต้น ไม่ส่งค่าแปลก
        r = ask.ask("x", model="opus --dangerously", runner=lambda *a: self.fail("ต้องไม่รัน"))
        self.assertFalse(r.ok)

    def test_work_unavailable_is_refused_and_says_why(self):
        c, _ = self.make(cloud=False)
        self.assertFalse(c.setMode("work"))
        self.assertIn("Claude", c.workBlocked)
        c, _ = self.make(claude_on=False)
        self.assertFalse(c.setMode("work"))
        self.assertIn("ตั้งค่า", c.workBlocked)

    def test_switching_claude_off_in_work_goes_back_to_general(self):
        c, done = self.make()
        c.setMode("work")
        self.on[0] = False
        c.claudeChanged()
        self.assertEqual(c.mode, "general")
        self.assertFalse(c.send("ข่าววันนี้", "") and self.asked)

    def test_histories_are_separate_and_reopen_in_their_mode(self):
        c, done = self.make()
        self.ask_all(c, done, ["คุยในเครื่อง"])
        c.setMode("work")
        self.ask_all(c, done, ["คุยกับ Claude"])
        work = c.history
        self.assertEqual([h["title"] for h in work], ["คุยกับ Claude"])
        c.setMode("general")
        self.assertEqual([h["title"] for h in c.history], ["คุยในเครื่อง"])
        c.openChat(work[0]["id"])
        self.assertEqual(c.mode, "work")

    def test_no_file_in_work_chat(self):
        c, _ = self.make()
        c.setMode("work")
        self.assertIn("แชททั่วไป", c.attachFile(__file__))
        self.assertEqual(c.attachedFile, "")


class ChatModeCommandTest(unittest.TestCase):
    def test_m5_dev_set(self):
        data = json.loads(DATA.read_text(encoding="utf-8"))
        hits = 0
        for row in data["commands"]:
            cmd = command.parse(row["text"])
            if cmd and (cmd.plan.action, cmd.plan.params) == (row["action"], row["params"]):
                hits += 1
        self.assertGreaterEqual(hits / len(data["commands"]), 0.9, "M5 ≥ 90%")
        switch = ("chat_mode", "cloud_model")
        parsed = [(t, command.parse(t)) for t in data["not_commands"]]
        wrong = [t for t, c in parsed if c and c.plan.action in switch]
        self.assertEqual(wrong, [], "ไม่ใช่คำสั่ง = 0")


@unittest.skipIf(UiSettings is None, "ไม่มี PySide6")
class CloudModelSettingTest(unittest.TestCase):
    def test_remembered_and_validated(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ui.json"
            s = UiSettings(p)
            self.assertEqual(s.cloudModel, "sonnet")
            self.assertTrue(s.setCloudModel("opus"))
            self.assertFalse(s.setCloudModel("gpt"))
            self.assertEqual(UiSettings(p).cloudModel, "opus")


if __name__ == "__main__":
    unittest.main()
