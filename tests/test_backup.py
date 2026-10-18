"""สำรอง/กู้ลงไดรฟ์ USB (ฟีเจอร์ข้อ 7) · ใช้โฟลเดอร์ชั่วคราวแทนไดรฟ์จริง."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from aipc import backup


class BackupTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        root = Path(d.name)
        self.home, self.drive = root / "home", root / "usb"
        self.drive.mkdir()
        (self.home / ".local/share/aipc/chats").mkdir(parents=True)
        (self.home / ".local/share/aipc/chats/c1.json").write_text('{"m": "สวัสดี"}', "utf-8")
        (self.home / ".config/aipc").mkdir(parents=True)
        (self.home / ".config/aipc/ui.json").write_text('{"theme": "dark"}', "utf-8")
        (self.home / "เอกสาร").mkdir()
        (self.home / "เอกสาร/รายงาน.txt").write_text("งาน", "utf-8")
        (self.home / ".cache").mkdir()
        (self.home / ".cache/big.bin").write_bytes(b"x" * 100)
        (self.home / ".ssh").mkdir()
        (self.home / ".ssh/id").write_text("secret", "utf-8")
        # ลิงก์ลับปฏิทิน Google = กุญแจ · ไม่สำรองลง USB (ตรวจทั้งระบบ 2026-10-18 ข้อ 3.7)
        (self.home / ".config/aipc/gcal-link.json").write_text('{"link": "secret"}', "utf-8")

    def test_backup_contains_app_data_and_my_files_not_cache_or_keys(self):
        r = backup.backup(self.home, self.drive, "pakon1", datetime(2026, 10, 1, 3, 0))
        self.assertTrue(r.ok, r.message)
        files = json.loads((Path(r.path) / "manifest.json").read_text("utf-8"))["files"]
        self.assertEqual(
            sorted(files),
            [".config/aipc/ui.json", ".local/share/aipc/chats/c1.json", "เอกสาร/รายงาน.txt"],
        )
        self.assertEqual(backup.verify(Path(r.path)), [])
        self.assertEqual(backup.backups(self.drive, "pakon1"), [Path(r.path)])

    def test_restore_moves_old_app_data_aside_and_keeps_my_existing_files(self):
        r = backup.backup(self.home, self.drive, "pakon1", datetime(2026, 10, 1, 3, 0))
        (self.home / ".local/share/aipc/chats/c1.json").write_text('{"m": "ใหม่"}', "utf-8")
        (self.home / "เอกสาร/รายงาน.txt").write_text("แก้แล้ว", "utf-8")
        res = backup.restore(Path(r.path), self.home, datetime(2026, 10, 1, 4, 0))
        self.assertTrue(res.ok, res.message)
        self.assertIn("สวัสดี", (self.home / ".local/share/aipc/chats/c1.json").read_text("utf-8"))
        self.assertEqual((self.home / "เอกสาร/รายงาน.txt").read_text("utf-8"), "แก้แล้ว")  # ไม่ทับ
        old = list((self.home / ".local/share").glob("aipc-before-restore-*"))
        self.assertEqual(len(old), 1, "ของเดิมย้ายเก็บ ไม่ลบ")

    def test_corrupted_backup_is_refused(self):
        r = backup.backup(self.home, self.drive, "pakon1")
        (Path(r.path) / "home/เอกสาร/รายงาน.txt").write_text("เสีย", "utf-8")
        res = backup.restore(Path(r.path), self.home)
        self.assertFalse(res.ok)
        self.assertIn("เสีย", res.message)
        self.assertFalse(
            list((self.home / ".local/share").glob("aipc-before-restore-*")), "ไม่ได้แตะอะไร"
        )

    def test_partial_backup_is_not_listed(self):
        (self.drive / "AIPC-backup/pakon1/2026-10-01_0300.partial").mkdir(parents=True)
        self.assertEqual(backup.backups(self.drive, "pakon1"), [])

    def test_drives_from_proc_mounts(self):
        mounts = f"/dev/sda1 {self.drive} vfat rw 0 0\n/dev/mmcblk0p2 / ext4 rw 0 0\n"
        self.assertEqual(backup.drives(mounts), [])  # ไม่อยู่ใต้ /media
        self.assertEqual(
            backup.drives("/dev/sda1 /media/pakon1/USB\\040DISK vfat rw 0 0\n"), []
        )  # ไม่มีจริง


class MountTest(unittest.TestCase):
    def test_mounts_only_unmounted_usb_partitions(self):
        import subprocess

        tree = {
            "blockdevices": [
                {
                    "path": "/dev/mmcblk0",
                    "rm": False,
                    "tran": "mmc",
                    "type": "disk",
                    "fstype": None,
                    "mountpoints": [None],
                    "children": [
                        {
                            "path": "/dev/mmcblk0p2",
                            "rm": False,
                            "tran": None,
                            "type": "part",
                            "fstype": "ext4",
                            "mountpoints": ["/"],
                        }
                    ],
                },
                {
                    "path": "/dev/sda",
                    "rm": True,
                    "tran": "usb",
                    "type": "disk",
                    "fstype": None,
                    "mountpoints": [None],
                    "children": [
                        {
                            "path": "/dev/sda1",
                            "rm": True,
                            "tran": None,
                            "type": "part",
                            "fstype": "vfat",
                            "mountpoints": [None],
                        }
                    ],
                },
            ]
        }
        calls = []

        def run(args, **kw):
            calls.append(args)
            out = json.dumps(tree) if args[0] == "lsblk" else ""
            return subprocess.CompletedProcess(args, 0, out, "")

        self.assertEqual(backup.mount_usb(run), [])
        mounts = [c for c in calls if c[0] == "udisksctl"]
        self.assertEqual(
            mounts, [["udisksctl", "mount", "-b", "/dev/sda1", "--no-user-interaction"]]
        )


if __name__ == "__main__":
    unittest.main()
