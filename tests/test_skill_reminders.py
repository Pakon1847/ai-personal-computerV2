import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from aipc.skills import reminders as rm

NOW = datetime(2026, 9, 23, 10, 0).astimezone()
DISK_FULL = OSError(28, "No space left on device")


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "aipc" / "reminders.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip(self):
        s = rm.ReminderStore(self.path)
        s.add(rm.Reminder("ส่งรายงาน", NOW + timedelta(days=1)), NOW)
        again = rm.ReminderStore(self.path)
        self.assertEqual([r.what for r in again.items], ["ส่งรายงาน"])
        self.assertEqual(again.items[0].when, NOW + timedelta(days=1))
        self.assertFalse(self.path.with_name("reminders.json.tmp").exists())

    def test_corrupt_file_recovers_from_backup(self):
        s = rm.ReminderStore(self.path)
        s.add(rm.Reminder("หนึ่ง", NOW + timedelta(hours=1)), NOW)
        s.add(rm.Reminder("สอง", NOW + timedelta(hours=2)), NOW)  # .bak = รุ่นที่มี "หนึ่ง"
        self.path.write_text("{เสีย", encoding="utf-8")
        again = rm.ReminderStore(self.path)
        self.assertTrue(again.recovered_from_backup)
        self.assertEqual([r.what for r in again.items], ["หนึ่ง"])

    def test_both_broken_refuses_to_overwrite(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{เสีย", encoding="utf-8")
        self.path.with_name("reminders.json.bak").write_text("{เสียด้วย", encoding="utf-8")
        s = rm.ReminderStore(self.path)
        self.assertTrue(s.broken)
        with self.assertRaises(rm.Unreadable):
            s.add(rm.Reminder("ใหม่", NOW), NOW)
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{เสีย")  # ไม่ถูกเขียนทับ

    def test_file_is_plain_json_with_timezone(self):
        s = rm.ReminderStore(self.path)
        s.add(rm.Reminder("ส่งรายงาน", NOW), NOW)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], 1)
        self.assertIn("+", data["reminders"][0]["when"][19:] + "+")  # มีเขตเวลา

    def test_delete(self):
        s = rm.ReminderStore(self.path)
        r = s.add(rm.Reminder("ลบฉัน", NOW), NOW)
        self.assertTrue(s.delete(r.id, NOW))
        self.assertEqual(rm.ReminderStore(self.path).items, [])

    def test_failed_add_is_not_kept(self):
        """พบ 2026-09-28: บันทึกไม่สำเร็จ (ดิสก์เต็ม) แต่นัดยังอยู่ในหน่วยความจำ → หน้าจอบอกว่าไม่สำเร็จ แต่ยังเตือน."""
        s = rm.ReminderStore(self.path)
        with mock.patch.object(s, "save", side_effect=DISK_FULL):
            with self.assertRaises(OSError):
                s.add(rm.Reminder("ไม่ควรค้าง", NOW + timedelta(hours=1)), NOW)
        self.assertEqual(s.items, [])

    def test_recovery_keeps_the_good_backup(self):
        """พบ 2026-09-28: หลังกู้จาก .bak การบันทึกครั้งถัดไปคัดไฟล์หลักที่เสียทับ .bak ที่ดี
        ถ้าการเขียนครั้งนั้นล้มด้วย = เสียทั้งคู่ ข้อมูลหายหมด."""
        s = rm.ReminderStore(self.path)
        s.add(rm.Reminder("หนึ่ง", NOW + timedelta(hours=1)), NOW)
        s.add(rm.Reminder("สอง", NOW + timedelta(hours=2)), NOW)  # .bak = รุ่นที่มี "หนึ่ง"
        self.path.write_text("{เสีย", encoding="utf-8")
        again = rm.ReminderStore(self.path)
        self.assertTrue(again.recovered_from_backup)
        with mock.patch.object(rm.os, "replace", side_effect=DISK_FULL):
            with self.assertRaises(OSError):
                again.add(rm.Reminder("สาม", NOW + timedelta(hours=3)), NOW)
        after = rm.ReminderStore(self.path)
        self.assertFalse(after.broken, ".bak ที่ดีต้องยังอยู่")
        self.assertEqual([r.what for r in after.items], ["หนึ่ง"])


class SchedulerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = rm.ReminderStore(Path(self.tmp.name) / "r.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_fires_once_at_time(self):
        self.s.add(rm.Reminder("กินยา", NOW + timedelta(minutes=30)), NOW)
        self.assertEqual(rm.tick(self.s, NOW + timedelta(minutes=29)).due, [])
        due = rm.tick(self.s, NOW + timedelta(minutes=30)).due
        self.assertEqual([r.what for r in due], ["กินยา"])
        self.assertEqual(rm.tick(self.s, NOW + timedelta(minutes=31)).due, [])  # ไม่เตือนซ้ำ

    def test_remind_before(self):
        self.s.add(rm.Reminder("ประชุม", NOW + timedelta(hours=1), remind_before_min=30), NOW)
        self.assertEqual(len(rm.tick(self.s, NOW + timedelta(minutes=30)).due), 1)

    def test_missed_while_logged_out(self):
        self.s.add(rm.Reminder("ส่งงาน", NOW + timedelta(hours=1)), NOW)
        later = NOW + timedelta(hours=5)  # เปิดเครื่องใหม่หลังเลยเวลา
        self.assertEqual([r.what for r in rm.missed_since_last_session(self.s, later)], ["ส่งงาน"])

    def test_clock_went_back(self):
        self.s.add(rm.Reminder("อะไรก็ได้", NOW + timedelta(days=1)), NOW)
        wrong_clock = NOW - timedelta(days=365)  # ไฟดับแล้วนาฬิกากลับไปปีก่อน
        self.assertTrue(rm.tick(self.s, wrong_clock).clock_went_back)
        self.assertFalse(rm.tick(self.s, NOW + timedelta(minutes=1)).clock_went_back)

    def test_idle_ticks_do_not_write_every_time(self):
        # รอบตรวจทุก 30 วิ ต้องไม่เขียน microSD ทุกรอบ (H4) · เขียนเมื่อมีนัดถึงเวลา หรือห่างเกิน SEEN_EVERY
        self.s.add(rm.Reminder("ไกลมาก", NOW + timedelta(days=30)), NOW)
        path = self.s.path
        before = path.stat().st_mtime_ns
        for i in range(1, 19):  # 9 นาที
            rm.tick(self.s, NOW + timedelta(seconds=30 * i))
        self.assertEqual(path.stat().st_mtime_ns, before)
        rm.tick(self.s, NOW + rm.SEEN_EVERY)
        self.assertEqual(rm.ReminderStore(path).last_seen, NOW + rm.SEEN_EVERY)

    def test_due_always_saved_immediately(self):
        self.s.add(rm.Reminder("กินยา", NOW + timedelta(minutes=1)), NOW)
        rm.tick(self.s, NOW + timedelta(minutes=1))
        self.assertTrue(rm.ReminderStore(self.s.path).items[0].fired)

    def test_save_failure_does_not_lose_the_alert(self):
        """พบ 2026-09-28: ทำเครื่องหมายว่าเตือนแล้วก่อนบันทึก · บันทึกล้ม = ไม่มีการเตือนเลย
        ต้องเตือนตอนนี้ และเมื่อบันทึกไม่ได้ ครั้งหน้าที่เข้าใช้ต้องรายงานว่า "พลาดไป" (ไม่หายเงียบ)."""
        self.s.add(rm.Reminder("กินยา", NOW + timedelta(minutes=1)), NOW)
        due_at = NOW + timedelta(minutes=1)
        with mock.patch.object(self.s, "save", side_effect=DISK_FULL):
            t = rm.tick(self.s, due_at)
        self.assertEqual([r.what for r in t.due], ["กินยา"])
        self.assertTrue(t.save_failed)
        again = rm.tick(self.s, due_at + timedelta(seconds=30))
        self.assertEqual(again.due, [], "ไม่เตือนซ้ำในเซสชันเดียวกัน")
        on_disk = rm.ReminderStore(self.s.path)
        missed = rm.missed_since_last_session(on_disk, due_at + timedelta(hours=1))
        self.assertEqual([r.what for r in missed], ["กินยา"])

    def test_upcoming_sorted(self):
        self.s.add(rm.Reminder("สอง", NOW + timedelta(hours=2)), NOW)
        self.s.add(rm.Reminder("หนึ่ง", NOW + timedelta(hours=1)), NOW)
        self.assertEqual([r.what for r in self.s.upcoming(NOW)], ["หนึ่ง", "สอง"])


if __name__ == "__main__":
    unittest.main()
