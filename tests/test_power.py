"""ปิด/รีสตาร์ตเครื่อง (การ์ด 0052 · เกณฑ์ P4 P5 ส่วนเทสต์) · ไม่สั่งเครื่องจริง."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aipc.skills import actions, command  # noqa: E402

try:
    from aipc.ui.backend import PowerController, SkillsController
except ImportError:  # pragma: no cover
    PowerController = None

# P4: ประโยคทั่วไปที่มีคำว่า "ปิด" หรือ "เครื่อง" 20 ประโยค → ต้องไม่เป็นคำสั่งปิด/รีสตาร์ต (ชุดพัฒนา · Claude เขียน)
NOT_POWER = [
    "ปิดเสียง", "ปิดไฟห้องนอนยังไง", "ปิดเครื่องดูดฝุ่น", "ปิดเครื่องปรับอากาศ", "ปิดเครื่องตอนกี่โมงดี",
    "ทำไมเครื่องปิดเอง", "อย่าปิดเครื่องนะ", "ปิดเครื่องอีก 10 นาที", "เตือนให้ปิดเครื่องตอนสี่ทุ่ม",
    "ปิดยูทูบ", "ปิดแท็บนี้", "เครื่องร้อนไหม", "ปิดหน้าต่าง", "วิธีปิดเครื่องที่ถูกต้อง",
    "รีสตาร์ตแล้วยังช้าอยู่", "ปิดคอมแล้วข้อมูลหายไหม", "ช่วยสรุปเรื่องการปิดเครื่อง", "ปิดกล้อง",
    "ทุกครั้งที่ปิดเครื่องให้สำรองไฟล์", "ปิดเครื่องได้ไหมตอนอัปเดต",
]  # fmt: skip


class ParseTest(unittest.TestCase):
    def test_power_commands_always_need_confirmation(self):
        for text, action in (("ปิดเครื่อง", "power_off"), ("ช่วยปิดคอมให้หน่อย", "power_off"),
                             ("ปิดเครื่องเลย", "power_off"), ("Shut down", "power_off"),
                             ("รีสตาร์ตเครื่อง", "reboot"), ("รีบูตที", "reboot"),
                             ("เริ่มเครื่องใหม่", "reboot"), ("restart", "reboot")):  # fmt: skip
            c = command.parse(text)
            self.assertEqual(c.plan.action, action, text)
            self.assertTrue(c.needs_confirmation, text)  # ความเสี่ยงสูง = ถามเสมอแม้ได้ยินชัด

    def test_p4_other_sentences_are_not_power(self):
        parsed = [(t, command.parse(t)) for t in NOT_POWER]
        wrong = [t for t, c in parsed if c and c.plan.action in ("power_off", "reboot")]
        self.assertEqual(wrong, [])

    def test_command_is_a_fixed_list(self):
        self.assertEqual(actions.command_for(actions.Plan("power_off")), ["systemctl", "poweroff"])
        self.assertEqual(actions.command_for(actions.Plan("reboot")), ["systemctl", "reboot"])


@unittest.skipIf(PowerController is None, "ไม่มี PySide6")
class ControllerTest(unittest.TestCase):
    def test_runs_systemctl_once_and_blocks_double_press(self):
        calls = []
        p = PowerController(True, runner=lambda a: calls.append(a) or 0)
        self.assertTrue(p.request("reboot"))
        self.assertFalse(p.request("reboot"))
        self.assertEqual(calls, [["systemctl", "reboot"]])

    def test_failure_is_shown_and_can_retry(self):
        p = PowerController(True, runner=lambda a: 1)
        self.assertFalse(p.request("power_off"))
        self.assertIn("ไม่สำเร็จ", p.error)
        self.assertFalse(p.busy)

    def test_dev_window_never_powers_off(self):
        calls = []
        p = PowerController(False, runner=lambda a: calls.append(a) or 0)
        self.assertFalse(p.request("power_off"))
        self.assertEqual(calls, [])
        self.assertIn("จำลอง", p.error)
        self.assertFalse(PowerController(True, runner=lambda a: 0).request("rm -rf /"))


@unittest.skipIf(PowerController is None, "ไม่มี PySide6")
class VoiceCardTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.calls = []
        ex = actions.Executor(runner=lambda a: self.calls.append(a) or 0, dry_run=False)
        self.s = SkillsController(executor=ex, reminders_path=Path(tmp.name) / "r.json",
                                  run_timer=False)  # fmt: skip

    def test_asks_first_and_no_means_nothing(self):
        card = self.s.handle("ปิดเครื่อง")
        self.assertTrue(card["power"])
        self.assertIn("10 วินาที", card["lines"][0])
        self.assertEqual(self.calls, [])
        self.s.confirm(card["confirmToken"], False)
        self.assertEqual(self.calls, [])
        card = self.s.handle("รีสตาร์ตเครื่อง")
        self.s.confirm(card["confirmToken"], True)
        self.assertEqual(self.calls, [["systemctl", "reboot"]])

    def test_old_token_cannot_be_reused(self):
        card = self.s.handle("ปิดเครื่อง")
        self.s.confirm(card["confirmToken"], False)
        self.s.confirm(card["confirmToken"], True)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()


# ใช้ตัวเปิดหน้าจอเดียวกัน · import ทั้งโมดูล ไม่ให้เทสต์ของมันถูกรันซ้ำที่นี่
from tests import test_ui_qml as uiq  # noqa: E402


@unittest.skipIf(PowerController is None or uiq.uiapp is None, "ไม่มี PySide6")
class DialogQmlTest(unittest.TestCase):
    open_shell = uiq.ShellCardTest.open_shell

    def test_sidebar_button_asks_then_dev_window_says_simulated(self):
        engine, win, warnings = self.open_shell("workspace")
        uiq.find_all(win, "powerOffButton")[0].clicked.emit()
        uiq.settle()
        dlg = uiq.find_all(win, "powerDialog")[0]
        self.assertTrue(dlg.property("opened"))
        self.assertEqual(dlg.property("action"), "power_off")
        uiq.find_all(win, "powerConfirm")[0].clicked.emit()  # หน้าต่างพัฒนา = ไม่ปิดจริง
        uiq.settle()
        self.assertIn("จำลอง", engine._backends["power"].error)
        self.assertEqual(warnings, [])
