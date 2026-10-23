"""ตัวช่วยสร้างบัญชี/กู้คืน (การ์ด 0012 ข้อ 8) · ระบบปลอม: ไม่มี useradd หรือ root จริง."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from aipc.accounts import helper

PW = "correct-horse-9"
PIN = "482917"
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

    def authenticate(self, user, password):
        return self.passwords.get(user) == password


def req(**kw):
    return json.dumps(kw).encode()


def create_req(**over):
    base = {"op": "create", "username": "namfon", "display_name": "น้ำฝน", "password": PW,
            "pin": PIN}  # fmt: skip
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
        self.assertNotIn("recovery_code", r)  # PIN ตั้งเอง ไม่มีรหัสให้จด
        self.assertTrue((self.sys.state / "recovery" / "namfon.json").exists())
        self.assertFalse((self.sys.state / "pending" / "namfon").exists())

    def test_new_account_never_gets_admin_rights(self):
        # เครื่องมีกลุ่ม sudo แต่บัญชีที่สมัครเองต้องไม่ได้ · ใส่ groups ในคำขอมาก็ไม่มีผล
        helper.handle(create_req(groups="sudo"), self.sys)
        add = self.useradd_calls()[0]
        self.assertEqual(add[add.index("--groups") + 1], "video,audio")
        self.assertTrue(all("sudo" not in arg for arg in add))

    def test_new_account_can_pick_wifi(self):  # การ์ด 0063 ทาง ก "ทุกบัญชี"
        self.sys.groups.add("netdev")
        helper.handle(create_req(), self.sys)
        add = self.useradd_calls()[0]
        self.assertEqual(add[add.index("--groups") + 1], "video,audio,netdev")

    def test_taken_username_is_refused(self):
        self.assertTrue(helper.handle(create_req(), self.sys)["ok"])
        r = helper.handle(create_req(password="another-pass-42"), self.sys)
        self.assertFalse(r["ok"])
        self.assertEqual(self.sys.passwords["namfon"], PW, "ห้ามเปลี่ยนรหัสของบัญชีที่มีอยู่แล้ว")
        self.assertEqual(len(self.useradd_calls()), 1)

    def test_rules_are_checked_again_by_the_helper(self):
        bad = [{"username": "root\n"}, {"username": "pakon"}, {"username": "Namfon"},
               {"password": "short"}, {"display_name": "a:b"}, {"display_name": ""},
               {"password": "line\nbreak-long-enough"}, {"pin": "123456"}, {"pin": "12345"},
               {"pin": "12ab56"}, {"pin": ""}]  # fmt: skip
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
        helper.handle(create_req(password=CANARY + "-password", pin="730519"), self.sys)
        for secret in (CANARY, "730519"):
            self.assertTrue(all(secret not in " ".join(c) for c in self.sys.calls))
            self.assertTrue(all(secret not in line for line in self.sys.logs))
        stored = (self.sys.state / "recovery" / "namfon.json").read_text()
        self.assertNotIn("730519", stored, "เก็บแค่ hash ของ PIN")

    # ---------- กู้คืน ----------
    def recover(self, pin, pw="new-password-99"):
        return helper.handle(req(op="recover", username="namfon", pin=pin,
                                 new_password=pw), self.sys)  # fmt: skip

    def test_recover_sets_new_password_and_keeps_pin(self):
        helper.handle(create_req(), self.sys)
        r = self.recover("๔๘๒ ๙๑๗")  # เลขไทยและช่องว่างก็ได้
        self.assertTrue(r["ok"], r)
        self.assertEqual(self.sys.passwords["namfon"], "new-password-99")
        self.assertNotIn("recovery_code", r)
        self.assertTrue(self.recover(PIN, pw="third-password-3")["ok"], "PIN เดิมใช้ต่อได้")
        self.assertEqual(self.sys.passwords["namfon"], "third-password-3")

    def test_recover_resets_login_keyring_as_the_user(self):
        """2026-10-06: keyring เข้ารหัสด้วยรหัสเก่า → Chromium/ระบบถามรหัสเก่าที่ลืมไปแล้ว ·
        ลบในนามผู้ใช้ (กัน symlink)."""
        helper.handle(create_req(), self.sys)
        self.sys.calls.clear()
        self.assertEqual(self.recover("000001")["message"], helper.RECOVER_FAIL)
        self.assertFalse([c for c in self.sys.calls if c[0] == "runuser"], "PIN ผิด = ไม่แตะ keyring")
        self.assertTrue(self.recover(PIN)["ok"])
        rm = [c for c in self.sys.calls if c[0] == "runuser"]
        self.assertEqual(len(rm), 1)
        self.assertEqual(rm[0][:6], ["runuser", "-u", "namfon", "--", "rm", "-f"])
        self.assertTrue(rm[0][6].replace("\\", "/").endswith(".local/share/keyrings/login.keyring"))
        self.sys.fail.add("runuser")
        self.assertTrue(self.recover(PIN)["ok"], "ล้าง keyring ไม่ได้ ไม่ทำให้กู้คืนล้ม")
        self.assertTrue(any("keyring" in x for x in self.sys.logs))

    def test_wrong_pins_make_you_wait(self):
        helper.handle(create_req(), self.sys)
        for _ in range(helper.FAIL_FREE):
            self.assertEqual(self.recover("000001")["message"], helper.RECOVER_FAIL)
        r = self.recover(PIN)
        self.assertFalse(r["ok"])
        self.assertIn("นาที", r["message"])  # แม้ PIN ถูกก็ต้องรอ
        self.sys.clock += helper.WAIT_BASE_S + 1
        self.assertTrue(self.recover(PIN)["ok"])

    def test_waits_grow_and_reset_after_success(self):
        helper.handle(create_req(), self.sys)
        path = self.sys.state / "recovery" / "namfon.json"
        waits = []
        for _ in range(helper.FAIL_FREE + 3):
            self.recover("000001")
            rec = json.loads(path.read_text())
            waits.append(rec["wait_until"] - self.sys.clock)
            self.sys.clock = max(self.sys.clock, rec["wait_until"]) + 1
        free = helper.FAIL_FREE - 1  # ผิดครั้งที่ 5 เริ่มรอ
        self.assertTrue(all(w <= 0 for w in waits[:free]))
        self.assertEqual(waits[free:], [helper.WAIT_BASE_S * 2**i for i in range(4)])  # 1 2 4 8 นาที
        self.assertTrue(self.recover(PIN)["ok"])
        self.assertEqual(json.loads(path.read_text())["failed"], 0)

    def test_unknown_user_or_no_pin_gives_the_same_message(self):
        self.assertEqual(self.recover("482917")["message"], helper.RECOVER_FAIL)

    @unittest.skipIf(sys.platform == "win32", "สิทธิ์ไฟล์ 0600 ตรวจได้บน Linux")
    def test_recovery_file_is_private(self):
        helper.handle(create_req(), self.sys)
        path = self.sys.state / "recovery" / "namfon.json"
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertNotIn("recovery_code", path.read_text())


class CheckPasswordTest(unittest.TestCase):
    """visiond ถามตัวช่วยก่อนเปิด/ปิดเข้าเครื่องด้วยใบหน้า (การ์ด 0015)."""

    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.sys = FakeSystem(Path(d.name))
        helper.handle(create_req(), self.sys)
        self.sys.who = "_aipcvision"

    def check(self, password, user="namfon"):
        return helper.handle(req(op="check-password", username=user, password=password), self.sys)

    def test_right_and_wrong_password(self):
        self.assertTrue(self.check(PW)["ok"])
        self.assertFalse(self.check("nope")["ok"])
        self.assertFalse(self.check(PW, user="ghost")["ok"])

    def test_visiond_can_only_check_passwords(self):
        self.assertFalse(helper.handle(create_req(username="evil"), self.sys)["ok"])
        self.assertNotIn("evil", self.sys.homes)
        self.sys.who = "_greetd"
        self.assertFalse(self.check(PW)["ok"], "หน้า Login ใช้ check-password ไม่ได้")

    def test_many_wrong_guesses_must_wait(self):
        for _ in range(helper.FAIL_FREE):
            self.assertFalse(self.check("nope")["ok"])
        r = self.check(PW)
        self.assertFalse(r["ok"])
        self.assertIn("รอ", r["message"])
        self.sys.clock += helper.WAIT_MAX_S + 1
        self.assertTrue(self.check(PW)["ok"])

    def test_password_is_never_logged(self):
        self.check(CANARY)
        self.assertFalse(any(CANARY in line for line in self.sys.logs))


if __name__ == "__main__":
    unittest.main()
