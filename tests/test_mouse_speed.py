"""การ์ด 0060: ความเร็วเมาส์ของแต่ละผู้ใช้ (M1) · ไม่มี labwc จริง."""

import tempfile
import unittest
from pathlib import Path

from aipc.ui import mouse, settings
from tests.test_session import LOOP

SESSION = LOOP.with_name("aipc-session")
RC = LOOP.parent / "labwc" / "rc.xml"


class MouseApplyTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        (self.dir / "rc.xml").write_text(RC.read_text(encoding="utf-8"), encoding="utf-8")
        self.ran = []

    def run_(self, args, **kw):
        self.ran.append(args)

    def test_writes_speed_and_reconfigures(self):
        self.assertTrue(mouse.apply(0.3, self.dir, run=self.run_))
        self.assertIn(
            "<pointerSpeed>0.30</pointerSpeed>", (self.dir / "rc.xml").read_text(encoding="utf-8")
        )
        self.assertEqual(self.ran, [["labwc", "--reconfigure"]])
        self.assertTrue(mouse.apply(5, self.dir, run=self.run_))  # เกินช่วง = 1.0
        self.assertIn(
            "<pointerSpeed>1.00</pointerSpeed>", (self.dir / "rc.xml").read_text(encoding="utf-8")
        )

    def test_not_in_our_session_does_nothing(self):
        self.assertFalse(mouse.apply(0.6, None, run=self.run_))  # ไม่มี AIPC_LABWC_DIR
        self.assertFalse(mouse.apply(0.6, self.dir / "none", run=self.run_))
        self.assertEqual(self.ran, [])

    def test_default_is_faster_and_bad_value_falls_back(self):
        self.assertIn(
            "<pointerSpeed>0.9</pointerSpeed>", RC.read_text(encoding="utf-8")
        )  # ก: 0.6 → 0.9
        self.assertEqual(settings.UiPrefs().mouse_speed, 0.9)
        self.assertEqual(settings.UiPrefs(mouse_speed=0.42).cleaned().mouse_speed, 0.9)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ui.json"
            prefs = settings.UiPrefs(mouse_speed=0.3)
            settings.save(prefs, path)
            self.assertEqual(settings.load(path).mouse_speed, 0.3)  # ปิดเครื่องแล้วยังจำค่า


class SessionScriptTest(unittest.TestCase):
    def test_session_uses_per_user_copy_and_logs_to_journal(self):
        s = SESSION.read_text(encoding="utf-8")
        self.assertIn('export AIPC_LABWC_DIR="$CFG"', s)
        self.assertIn('labwc -C "$CFG"', s)
        self.assertLess(s.index("systemd-cat -t aipc-session"), s.index("labwc -C"))
        g = LOOP.with_name("aipc-greeter").read_text(encoding="utf-8")
        self.assertLess(g.index("systemd-cat -t aipc-greeter"), g.index("exec cage"))


if __name__ == "__main__":
    unittest.main()
