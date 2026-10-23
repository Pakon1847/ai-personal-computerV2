"""ธีมหน้า Login = ธีมของผู้ใช้ที่เข้าล่าสุด (การ์ด 0051 ข้อ 4.2 · เกณฑ์ D3 ส่วนเทสต์)."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from aipc.accounts import helper
from tests.test_accounts_helper import FakeSystem


def ask(system, **req):
    return helper.handle(json.dumps({"op": "greeter-theme", **req}).encode(), system)


class GreeterThemeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.sys = FakeSystem(self.tmp)
        self.sys.homes["nok"] = self.tmp / "home" / "nok"

    def tearDown(self):
        self._tmp.cleanup()

    def set_theme(self, user, theme):
        f = self.sys.homes[user] / ".config" / "aipc" / "ui.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"theme": theme}), encoding="utf-8")
        return f

    def test_no_one_yet_is_dark(self):
        self.assertEqual(ask(self.sys), {"ok": True, "theme": "dark"})

    def test_follows_whoever_logged_in_last(self):
        self.set_theme("pakon", "light")
        self.set_theme("nok", "dark")
        for user, want in [("pakon", "light"), ("nok", "dark")] * 2:  # A→B→A→B (เกณฑ์ D3)
            self.assertEqual(ask(self.sys, user=user)["theme"], want, user)
            self.assertEqual(ask(self.sys)["theme"], want, f"เปิดหน้า Login ใหม่หลัง {user} ออก")

    def test_reads_current_theme_not_the_one_at_login(self):
        # เปลี่ยนธีมระหว่างใช้งาน → หน้า Login ครั้งถัดไปใช้ธีมใหม่
        self.set_theme("pakon", "dark")
        ask(self.sys, user="pakon")
        self.set_theme("pakon", "light")
        self.assertEqual(ask(self.sys)["theme"], "light")

    def test_bad_values_fall_back_to_dark(self):
        f = self.set_theme("pakon", "pink")
        self.assertEqual(ask(self.sys, user="pakon")["theme"], "dark")
        f.write_text("ไม่ใช่ JSON", encoding="utf-8")
        self.assertEqual(ask(self.sys)["theme"], "dark")
        big = {"theme": "light", "x": "a" * helper.THEME_FILE_MAX}
        f.write_text(json.dumps(big), encoding="utf-8")
        self.assertEqual(ask(self.sys)["theme"], "dark")  # ใหญ่เกิน = ไม่อ่าน

    @unittest.skipIf(os.name == "nt", "สร้าง symlink บนวินโดวส์ต้องใช้สิทธิ์พิเศษ")
    def test_link_out_of_home_is_not_followed(self):
        outside = self.tmp / "secret.json"
        outside.write_text(json.dumps({"theme": "light"}), encoding="utf-8")
        f = self.sys.homes["pakon"] / ".config" / "aipc" / "ui.json"
        f.parent.mkdir(parents=True)
        f.symlink_to(outside)
        self.assertEqual(ask(self.sys, user="pakon")["theme"], "dark")

    def test_bad_or_unknown_user(self):
        self.set_theme("pakon", "light")
        ask(self.sys, user="pakon")
        for bad in ("../root", "Pakon", 7, ""):
            self.assertFalse(ask(self.sys, user=bad)["ok"], bad)
        # ไม่มีบัญชีนี้ = ไม่จำ · ยังคืนธีมของคนล่าสุดที่มีจริง
        self.assertEqual(ask(self.sys, user="ghost")["theme"], "light")

    def test_only_login_screen_may_ask(self):
        self.sys.who = "_aipcvision"
        self.assertFalse(ask(self.sys)["ok"])
        self.sys.who = "pakon"
        self.assertFalse(ask(self.sys)["ok"])


if __name__ == "__main__":
    unittest.main()
