"""แชท 2 แบบ (การ์ด 0053 · เกณฑ์ M1–M5 ส่วนเทสต์) · llama-server ปลอม + Claude ปลอม ไม่ใช้เน็ต."""

import json
import tempfile
import unittest
from pathlib import Path

from aipc.chat import store
from aipc.cloud import ask
from aipc.cloud.ask import CloudReply
from aipc.skills import command
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

    def make(self, claude_on=True, cloud=True, model="sonnet", auto=False, effort=None):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.asked, self.model, self.effort, self.efforts = [], [model], [effort], []
        on = [claude_on]
        self.on = on

        def fake(question, history, model=None, **kw):
            self.asked.append((question, model))
            self.efforts.append(kw.get("effort"))
            return CloudReply(True, f"Claude ตอบ: {question}", model=f"claude-{model}-x")

        c = ChatController(target=self.target, store=store.ChatStore(Path(d.name)), poll_ms=100000,
                           cloud=fake if cloud else None, claude_on=lambda: on[0],
                           cloud_model=lambda: self.model[0], auto_cloud=auto,
                           cloud_effort=lambda: self.effort[0])  # fmt: skip
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

    def test_m1_general_keeps_hybrid(self):
        # หัวข้อ 8 (Pakon 2026-10-22): แชททั่วไป = ไฮบริดเดิม
        # ไม่รู้ = ส่งต่อ Claude ด้วยโมเดลเดิม (ไม่ใช่ที่เลือกในแชทงาน)
        c, done = self.make(auto=True, model="opus")
        self.ask_all(c, done, ["สวัสดี"])
        self.assertEqual(self.asked, [])  # ตอบได้เอง = ไม่ส่ง
        FakeLlama.mode = "dunno"
        self.ask_all(c, done, ["ราคาทองวันนี้"])
        self.assertEqual(self.asked, [("ราคาทองวันนี้", None)])
        self.assertEqual(done[-1][1], c.CLOUD_NOTE)

    def test_m1_general_with_claude_off_sends_nothing(self):
        c, done = self.make(auto=True, claude_on=False)
        FakeLlama.mode = "dunno"
        self.ask_all(c, done, [f"ราคาทองวันนี้ {i}" for i in range(10)])
        self.assertEqual(self.asked, [])

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

    def test_effort_is_sent_only_when_valid(self):
        # Pakon 2026-10-22: เลือกระดับความคิด low/medium/high/xhigh/max ได้ในแชทงาน
        c, done = self.make(effort="max")
        c.setMode("work")
        self.ask_all(c, done, ["ข้อ 1"])
        self.effort[0] = "ultra; rm"  # ค่าแปลก = ไม่ส่ง effort เลย
        self.ask_all(c, done, ["ข้อ 2"])
        self.assertEqual(self.efforts, ["max", None])
        rows = {r["k"]: r["v"] for r in c.lastTrace}
        self.assertNotIn("ultra", str(rows))

    def test_ask_builds_effort_flag_and_refuses_unknown(self):
        seen = []

        def runner(args, text, cwd, timeout):
            seen.append(args)
            return 0, '{"result": "ok", "modelUsage": {"claude-x": {}}}', ""

        r = ask.ask("x", model="haiku", effort="xhigh", claude="claude", runner=runner)
        self.assertTrue(r.ok)
        i = seen[0].index("--effort")
        self.assertEqual(seen[0][i : i + 2], ["--effort", "xhigh"])
        self.assertFalse(ask.ask("x", effort="extreme", claude="claude", runner=runner).ok)
        ask.ask("x", claude="claude", runner=runner)
        self.assertNotIn("--effort", seen[-1])  # ไม่เลือก = ไม่ส่ง (แชททั่วไป/ไฮบริดเดิม)
        self.assertEqual(len(seen), 2)

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
            self.assertEqual(s.cloudEffort, "medium")
            self.assertTrue(s.setCloudEffort("xhigh"))
            self.assertFalse(s.setCloudEffort("extra"))
            self.assertEqual(UiSettings(p).cloudEffort, "xhigh")


if __name__ == "__main__":
    unittest.main()


# ใช้ตัวเปิดหน้าจอเดียวกัน · import ทั้งโมดูล ไม่ให้เทสต์ของมันถูกรันซ้ำที่นี่
from tests import test_ui_qml as uiq  # noqa: E402


@unittest.skipIf(UiSettings is None or uiq.uiapp is None, "ไม่มี PySide6")
class SegmentedQmlTest(unittest.TestCase):
    open_shell = uiq.ShellCardTest.open_shell

    def test_effort_switch_shows_only_in_work_and_saves(self):
        engine, win, warnings = self.open_shell("workspace")
        chat, ui = engine._backends["chat"], engine._backends["uiSettings"]
        effort = uiq.find_all(win, "effortSwitch")[0]
        self.assertFalse(effort.property("visible"))  # แชททั่วไป = ไม่มีตัวเลือกของ Claude
        chat._cloud = lambda q, h, model=None, effort=None: None
        chat.modeChanged.emit()
        self.assertTrue(chat.setMode("work"))
        uiq.settle()
        self.assertTrue(effort.property("visible"))
        effort.picked.emit("max")
        self.assertEqual(ui.cloudEffort, "max")
        self.assertEqual(warnings, [])
