"""ลบบัญชีพร้อมใบยืนยัน (ข้อเสนอ 2026-10-03) · ระบบปลอม: ไม่มี userdel หรือ root จริง.

ลองกับบัญชีจริงบน Pi แยก (ต้องมี root · docs/runbooks/pi5-account-delete.md)
"""

import json
import tempfile
import unittest
from pathlib import Path

from aipc.accounts import helper
from tests.test_accounts_helper import PIN, PW, FakeSystem, create_req, req


class DeleteSystem(FakeSystem):
    def __init__(self, tmp: Path):
        super().__init__(tmp)
        self.vision_dir = tmp / "vision" / "face-login"
        self.vision_dir.mkdir(parents=True)
        self.sys_dir = tmp / "var"
        self.uids = {"pakon": 1000}
        self.admins = {"pakon"}
        self.running = set()
        self.leftovers: dict[Path, int] = {}

    def run(self, argv, stdin=None):
        code = super().run(argv, stdin)
        if argv[0] == "useradd":
            self.uids[argv[-1]] = 1001
            self.homes[argv[-1]].mkdir(parents=True, exist_ok=True)
        elif argv[0] == "userdel":
            self.uids.pop(argv[-1], None)  # ตัวปลอม: ไม่ลบโฟลเดอร์ home (ให้ตัวช่วยตามลบเอง)
        return code

    def uid_of(self, name):
        return self.uids.get(name)

    def in_group(self, name, group):
        return group == "sudo" and name in self.admins

    def has_processes(self, uid):
        return uid in self.running

    def system_files(self, name):
        return [self.sys_dir / "cron" / name, self.sys_dir / "mail" / name]

    def owned_by(self, uid):
        return [p for p, u in self.leftovers.items() if u == uid and p.exists()]


def delete_req(user="namfon", password=PW, confirm=None):
    return req(op="delete", username=user, password=password,
               confirm=user if confirm is None else confirm)  # fmt: skip


class DeleteTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.tmp = Path(d.name)
        self.sys = DeleteSystem(self.tmp)
        self.assertTrue(helper.handle(create_req(), self.sys)["ok"])
        self.home = self.sys.homes["namfon"]
        # ข้อมูลของบัญชีในทุกที่ที่ระบบเก็บ
        (self.home / ".local" / "share" / "aipc").mkdir(parents=True)
        (self.home / ".local" / "share" / "aipc" / "reminders.json").write_text("{}")
        for n in ("namfon.json", "namfon.json.bak"):
            (self.sys.vision_dir / n).write_text("{}")
        (self.sys.vision_dir / "pakon.json").write_text("{}")  # ของคนอื่น ต้องไม่หาย
        cron = self.sys.sys_dir / "cron" / "namfon"
        cron.parent.mkdir(parents=True)
        cron.write_text("x")
        tmpdir = self.tmp / "tmp" / "namfon-cache"
        tmpdir.mkdir(parents=True)
        (tmpdir / "a").write_text("x")
        self.sys.leftovers = {tmpdir: 1001, tmpdir / "a": 1001}

    def test_deletes_everywhere_and_certifies_each_place(self):
        r = helper.handle(delete_req(), self.sys)
        self.assertTrue(r["ok"], r)
        self.assertEqual(len(r["checks"]), 7)
        self.assertTrue(all(c["gone"] for c in r["checks"]))
        self.assertFalse(self.home.exists())
        self.assertEqual(sorted(p.name for p in self.sys.vision_dir.iterdir()), ["pakon.json"])
        self.assertFalse((self.sys.state / "recovery" / "namfon.json").exists())
        self.assertFalse((self.tmp / "tmp" / "namfon-cache").exists())
        self.assertNotIn("namfon", self.sys.uids)
        self.assertTrue(r["limits"], "ใบยืนยันต้องบอกข้อจำกัด (microSD · ข้อมูลที่ส่งออกไปแล้ว · สำรอง)")
        self.assertFalse((self.sys.state / "deleting" / "namfon").exists())

    def test_wrong_password_or_confirm_deletes_nothing(self):
        for bad in (delete_req(password="nope"), delete_req(confirm="namfo"),
                    delete_req(user="ghost")):  # fmt: skip
            self.assertFalse(helper.handle(bad, self.sys)["ok"])
        self.assertTrue(self.home.exists())
        self.assertNotIn(["userdel", "-r", "namfon"], self.sys.calls)
        self.assertEqual(helper.handle(delete_req(password="nope"), self.sys)["message"],
                         helper.handle(delete_req(user="ghost"), self.sys)["message"])  # fmt: skip

    def test_guessing_passwords_through_delete_must_wait(self):
        for _ in range(helper.FAIL_FREE):
            helper.handle(delete_req(password="nope"), self.sys)
        self.assertFalse(helper.handle(delete_req(), self.sys)["ok"])  # ถูกแล้วก็ยังต้องรอ
        self.assertTrue(self.home.exists())

    def test_admin_and_logged_in_accounts_are_refused(self):
        self.sys.passwords["pakon"] = PW
        self.assertIn("ผู้ดูแล", helper.handle(delete_req(user="pakon"), self.sys)["message"])
        self.sys.running.add(1001)
        self.assertIn("ออกจากระบบ", helper.handle(delete_req(), self.sys)["message"])
        self.assertTrue(self.home.exists())

    def test_only_the_login_screen_may_delete(self):
        self.sys.who = "_aipcvision"
        self.assertFalse(helper.handle(delete_req(), self.sys)["ok"])
        self.assertTrue(self.home.exists())

    def test_power_cut_mid_delete_is_finished_next_time(self):
        marker = self.sys.state / "deleting" / "namfon"
        helper._write_private(marker, {"uid": 1001, "home": str(self.home)})
        self.sys.run(["userdel", "-r", "namfon"])  # ไฟดับหลัง userdel · ที่เหลือยังไม่ได้ลบ
        helper.handle(req(op="recover", username="x", pin=PIN, new_password=PW), self.sys)
        self.assertFalse(self.home.exists())
        self.assertFalse(any(self.sys.vision_dir.glob("namfon.json*")))
        self.assertFalse(marker.exists())

    def test_password_never_logged(self):
        helper.handle(delete_req(password="CANARY-77"), self.sys)
        self.assertFalse(any("CANARY-77" in line for line in self.sys.logs))
        self.assertFalse(any("CANARY-77" in json.dumps(c) for c in self.sys.calls))


if __name__ == "__main__":
    unittest.main()
