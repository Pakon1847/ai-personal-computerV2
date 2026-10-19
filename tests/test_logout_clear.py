"""การ์ด 0031 รอบ 3 เกณฑ์ L1: ออกจากบัญชีเว็บทุกครั้งที่ออกจากระบบ (ตัวล้าง + ค่าตั้ง + สคริปต์เซสชัน)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aipc.browser import control, logout_clear
from aipc.ui import settings

SESSION = Path(__file__).resolve().parents[1] / "scripts" / "pi" / "session"


class ClearTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.prof = self.root / "share" / "aipc" / "browser"
        (self.prof / "Default").mkdir(parents=True)
        (self.prof / "Default" / "Cookies").write_text("session=1", encoding="utf-8")
        self.normal = self.root / "config" / "chromium" / "Default"  # เบราว์เซอร์ธรรมดา
        self.normal.mkdir(parents=True)
        (self.root / "Downloads").mkdir()
        (self.root / "Downloads" / "งาน.pdf").write_text("pdf", encoding="utf-8")
        self.state = self.root / "state"
        self.closed = []

    def run_clear(self, enabled):
        return logout_clear.clear(self.prof, enabled, self.state, close=self.closed.append)

    def test_off_touches_nothing(self):
        self.assertEqual(self.run_clear(False), "off")
        self.assertTrue((self.prof / "Default" / "Cookies").exists())
        self.assertEqual(self.closed, [])

    def test_on_removes_profile_only(self):
        left = self.prof.with_name("browser" + control.REMOVING + "1")  # ค้างจากไฟดับครั้งก่อน
        left.mkdir()
        self.assertEqual(self.run_clear(True), "cleared")
        self.assertEqual(self.closed, [self.prof])  # ปิดเบราว์เซอร์ก่อนลบ
        self.assertEqual(list(self.prof.parent.glob("browser*")), [])  # ลบจนเสร็จ ไม่ทิ้งไว้เบื้องหลัง
        self.assertTrue(self.normal.exists())  # ไม่แตะเบราว์เซอร์ธรรมดา
        self.assertTrue((self.root / "Downloads" / "งาน.pdf").exists())
        self.assertEqual(self.run_clear(True), "none")  # ไม่มีอะไรให้ลบ = ไม่พัง

    def test_failure_is_flagged_not_raised(self):
        with mock.patch.object(Path, "rename", side_effect=OSError(13, "Permission denied")):
            result = self.run_clear(True)
        self.assertTrue(result.startswith("failed"))
        self.assertTrue((self.state / logout_clear.FAILED).exists())  # ครั้งหน้าหน้าจอบอกผู้ใช้
        self.assertEqual(self.run_clear(True), "cleared")
        self.assertFalse((self.state / logout_clear.FAILED).exists())

    def test_finds_only_this_profiles_browser(self):
        proc = self.root / "proc"
        for pid, cmd in [("10", f"chromium\0--user-data-dir={self.prof}\0"),
                         ("11", "chromium\0--user-data-dir=/home/x/.config/chromium\0"),
                         ("self", "x")]:  # fmt: skip
            (proc / pid).mkdir(parents=True)
            (proc / pid / "cmdline").write_bytes(cmd.encode())
        self.assertEqual(logout_clear.browser_pids(self.prof, proc), [10])


class SettingTest(unittest.TestCase):
    def test_default_off_and_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ui.json"
            self.assertFalse(settings.load(path).clear_web_on_logout)
            prefs = settings.UiPrefs(clear_web_on_logout=True)
            settings.save(prefs, path)
            self.assertTrue(settings.load(path).clear_web_on_logout)
            path.write_text(json.dumps({"clear_web_on_logout": "yes"}), encoding="utf-8")
            self.assertFalse(settings.load(path).clear_web_on_logout)  # ค่าเสีย = ปิด


class SessionScriptTest(unittest.TestCase):
    def test_session_clears_after_labwc_on_every_logout_path(self):
        text = (SESSION / "aipc-session").read_text(encoding="utf-8")
        self.assertNotIn("exec labwc", text)  # ต้องได้ทำงานต่อหลัง labwc จบ
        run_labwc = text.index('labwc -C "$HERE/labwc"')
        self.assertLess(run_labwc, text.index('"$HERE/aipc-logout-clear"'))
        helper = (SESSION / "aipc-logout-clear").read_text(encoding="utf-8")
        self.assertIn("timeout 20", helper)
        self.assertTrue(helper.rstrip().endswith("exit 0"))  # ไม่ขวางการออกจากระบบ


if __name__ == "__main__":
    unittest.main()
