"""ตัวช่วยสร้างบัญชี/กู้คืน (การ์ด 0012 ข้อ 8) · ระบบปลอม: ไม่มี PAM, useradd หรือ root จริง."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from aipc.accounts import helper, validation

PW = "correct-horse-9"
ADMIN_PW = "admin-secret-77"
CANARY = "CANARY-4bd1"  # ต้องไม่หลุดไปอยู่ใน argv หรือ log


class FakeSystem(helper.System):
    def __init__(self, tmp: Path):
        self.state = tmp / "state"
        self.homes = {"pakon": tmp / "home" / "pakon"}
        self.admins = {"pakon"}
        self.passwords = {"pakon": ADMIN_PW}
        self.groups = {"video", "audio"}  # ไม่มี render → ต้องไม่ใส่
        self.calls, self.stdins, self.logs = [], [], []
        self.fail = set()  # คำสั่งที่จะล้ม เช่น {"chpasswd"}
        self.who = "_greetd"
        self.clock = 1_000_000.0
        self.modes = {}

    def caller(self):
        return self.who

    def user_home(self, name):
        return self.homes.get(name)

    def group_exists(self, group):
        return group in self.groups

    def in_group(self, user, group):
        return group == "sudo" and user in self.admins

    def authenticate(self, user, password):
        return self.passwords.get(user) == password

    def run(self, argv, stdin=None):
        self.calls.append(argv)
        self.stdins.append(stdin)
        if argv[0] in self.fail:
            return 1
        if argv[0] == "useradd":
            self.homes[argv[-1]] = self.state.parent / "home" / argv[-1]
        elif argv[0] == "userdel":
            self.homes.pop(argv[-1], None)
        elif argv[0] == "chpasswd":
            name, pw = stdin.rstrip("\n").split(":", 1)
            self.passwords[name] = pw
        return 0

    def chmod(self, path, mode):
        self.modes[str(path)] = mode

    def now(self):
        return self.clock

    def log(self, text):
        self.logs.append(text)


def req(**kw):
    return json.dumps(kw).encode()


def create_req(**over):
    base = {"op": "create", "username": "namfon", "display_name": "น้ำฝน", "password": PW,
            "admin": "pakon", "admin_password": ADMIN_PW}  # fmt: skip
    base.update(over)
    return req(**base)


class HelperTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.sys = FakeSystem(Path(d.name))

    def useradd_calls(self):
        return [c for c in self.sys.calls if c[0] == "useradd"]

    # ---------- สมัคร ----------
    def test_create_with_admin_approval(self):
        r = helper.handle(create_req(), self.sys)
        self.assertTrue(r["ok"], r)
        self.assertEqual(self.sys.passwords["namfon"], PW)
        self.assertEqual(self.sys.modes[str(self.sys.homes["namfon"])], 0o700)
        add = self.useradd_calls()[0]
        self.assertIn("video,audio", add)  # เฉพาะกลุ่มที่เครื่องมี
        self.assertIn("น้ำฝน", add)
        code = r["recovery_code"]
        self.assertEqual(len(validation.normalize_recovery_code(code)), 24)
        self.assertFalse((self.sys.state / "pending" / "namfon").exists())

    def test_wrong_admin_password_never_runs_useradd(self):
        for over in ({"admin_password": "wrong"}, {"admin": ""}, {"admin": "somchai"}):
            with self.subTest(**over):
                r = helper.handle(create_req(**over), self.sys)
                self.assertFalse(r["ok"])
                self.assertEqual(r["message"], helper.ADMIN_FAIL)  # ข้อความเดียวกันทุกกรณี
        self.assertEqual(self.useradd_calls(), [])

    def test_non_admin_with_right_password_is_refused(self):
        self.sys.passwords["somchai"] = "somchai-pass-1"
        r = helper.handle(create_req(admin="somchai", admin_password="somchai-pass-1"), self.sys)
        self.assertEqual(r["message"], helper.ADMIN_FAIL)
        self.assertEqual(self.useradd_calls(), [])

    def test_rules_are_checked_again_by_the_helper(self):
        bad = [{"username": "root\n"}, {"username": "pakon"}, {"username": "Namfon"},
               {"password": "short"}, {"display_name": "a:b"}, {"display_name": ""},
               {"password": "line\nbreak-long-enough"}]  # fmt: skip
        for over in bad:
            with self.subTest(**over):
                self.assertFalse(helper.handle(create_req(**over), self.sys)["ok"])
        self.assertEqual(self.useradd_calls(), [])

    def test_bad_requests(self):
        cases = [b"{", b"[]", req(op="format"), req(op="create"), b"x" * (helper.REQUEST_MAX + 1)]
        for raw in cases:
            with self.subTest(raw=raw[:20]):
                self.assertFalse(helper.handle(raw, self.sys)["ok"])
        self.assertEqual(self.sys.calls, [])

    def test_only_the_login_screen_may_call(self):
        self.sys.who = "pakon"
        r = helper.handle(create_req(), self.sys)
        self.assertFalse(r["ok"])
        self.assertEqual(self.useradd_calls(), [])

    def test_failed_password_step_removes_the_account(self):
        self.sys.fail = {"chpasswd"}
        r = helper.handle(create_req(), self.sys)
        self.assertFalse(r["ok"])
        self.assertIn(["userdel", "-r", "namfon"], self.sys.calls)
        self.assertNotIn("namfon", self.sys.homes)
        self.assertFalse((self.sys.state / "pending" / "namfon").exists())

    def test_half_created_account_from_power_cut_is_removed_first(self):
        # ไฟดับหลัง useradd: มีบัญชี + ไฟล์งานค้าง แต่ไม่มีรหัสผ่าน
        self.sys.homes["namfon"] = self.sys.state.parent / "home" / "namfon"
        (self.sys.state / "pending").mkdir(parents=True)
        (self.sys.state / "pending" / "namfon").write_text("{}")
        r = helper.handle(create_req(), self.sys)
        self.assertTrue(r["ok"], r)  # สมัครชื่อเดิมใหม่ได้
        self.assertIn(["userdel", "-r", "namfon"], self.sys.calls)

    def test_passwords_and_codes_never_in_argv_or_log(self):
        helper.handle(create_req(password=CANARY + "-password"), self.sys)
        self.assertTrue(all(CANARY not in " ".join(c) for c in self.sys.calls))
        self.assertTrue(all(CANARY not in line for line in self.sys.logs))
        self.assertTrue(all(ADMIN_PW not in line for line in self.sys.logs))

    # ---------- กู้คืน ----------
    def recover(self, code, pw="new-password-99"):
        return helper.handle(req(op="recover", username="namfon", recovery_code=code,
                                 new_password=pw), self.sys)  # fmt: skip

    def test_recover_sets_new_password_and_rotates_code(self):
        code = helper.handle(create_req(), self.sys)["recovery_code"]
        r = self.recover(code.lower().replace("-", " "))  # พิมพ์ตัวเล็ก เว้นวรรค ก็ได้
        self.assertTrue(r["ok"], r)
        self.assertEqual(self.sys.passwords["namfon"], "new-password-99")
        self.assertNotEqual(r["recovery_code"], code)
        self.assertFalse(self.recover(code)["ok"], "รหัสเก่าต้องใช้ไม่ได้ทันที")
        self.assertTrue(self.recover(r["recovery_code"])["ok"])

    def test_wrong_codes_make_you_wait(self):
        code = helper.handle(create_req(), self.sys)["recovery_code"]
        for _ in range(helper.FAIL_FREE):
            self.assertEqual(self.recover("0000-0000-0000-0000-0000-0000")["message"],
                             helper.RECOVER_FAIL)  # fmt: skip
        r = self.recover(code)
        self.assertFalse(r["ok"])
        self.assertIn("นาที", r["message"])  # แม้รหัสถูกก็ต้องรอ
        self.sys.clock += helper.WAIT_BASE_S + 1
        self.assertTrue(self.recover(code)["ok"])

    def test_unknown_user_or_no_code_gives_the_same_message(self):
        self.assertEqual(self.recover("ABCD")["message"], helper.RECOVER_FAIL)

    @unittest.skipIf(sys.platform == "win32", "สิทธิ์ไฟล์ 0600 ตรวจได้บน Linux")
    def test_recovery_file_is_private(self):
        helper.handle(create_req(), self.sys)
        path = self.sys.state / "recovery" / "namfon.json"
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertNotIn("recovery_code", path.read_text())


class PamTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith("linux"), "PAM มีบน Linux เท่านั้น")
    def test_unknown_user_is_refused_without_crashing(self):
        from aipc.accounts import pam

        self.assertFalse(pam.authenticate("login", "aipc-no-such-user-xyz", "whatever"))


if __name__ == "__main__":
    unittest.main()
