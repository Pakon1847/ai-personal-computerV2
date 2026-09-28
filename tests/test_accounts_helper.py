"""ตัวช่วยสร้างบัญชี/กู้คืน (การ์ด 0012 ข้อ 8) · ระบบปลอม: ไม่มี useradd หรือ root จริง."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from aipc.accounts import helper, validation

PW = "correct-horse-9"
CANARY = "CANARY-4bd1"  # ต้องไม่หลุดไปอยู่ใน argv หรือ log


class FakeSystem(helper.System):
    def __init__(self, tmp: Path):
        self.state = tmp / "state"
        self.homes = {"pakon": tmp / "home" / "pakon"}
        self.passwords = {}
        self.groups = {"video", "audio", "sudo"}  # ไม่มี render → ต้องไม่ใส่
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
    base = {"op": "create", "username": "namfon", "display_name": "น้ำฝน", "password": PW}
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
    def test_create_without_admin(self):  # สมัครเสรี (Pakon 2026-09-29)
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

    def test_new_account_never_gets_admin_rights(self):
        # เครื่องมีกลุ่ม sudo แต่บัญชีที่สมัครเองต้องไม่ได้ · ใส่ groups ในคำขอมาก็ไม่มีผล
        helper.handle(create_req(groups="sudo"), self.sys)
        add = self.useradd_calls()[0]
        self.assertEqual(add[add.index("--groups") + 1], "video,audio")
        self.assertTrue(all("sudo" not in arg for arg in add))

    def test_taken_username_is_refused(self):
        self.assertTrue(helper.handle(create_req(), self.sys)["ok"])
        r = helper.handle(create_req(password="another-pass-42"), self.sys)
        self.assertFalse(r["ok"])
        self.assertEqual(self.sys.passwords["namfon"], PW, "ห้ามเปลี่ยนรหัสของบัญชีที่มีอยู่แล้ว")
        self.assertEqual(len(self.useradd_calls()), 1)

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


if __name__ == "__main__":
    unittest.main()
