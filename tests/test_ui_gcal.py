"""ปฏิทิน Google ในคำตอบนัด หน้าแรก เสียง และหน้าตั้งค่า (การ์ด 0014) · ตัวดึงปลอม ไม่ใช้เน็ตจริง."""

import os
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    from aipc.skills import gcal
    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None

from tests.test_skill_gcal import ICS, LINK

NOW = datetime(2026, 10, 15, 9, 0).astimezone()  # พฤหัสบดี · เขตเวลาของเครื่อง (แบบเดียวกับนัดในเครื่อง)


def wait_until(cond, timeout=5.0):
    # สร้างแบบมีหน้าจอ (QGuiApplication) ไม่ใช่ QCoreApplication: ไม่งั้นเทสต์หน้าจอที่รันต่อในโปรเซสเดียวกัน
    # สร้างหน้าต่างไม่ได้และโปรเซสหายเงียบ (พบ 2026-10-15 ตอนรันพ่วงกับ tests.test_ui_qml)
    app = QCoreApplication.instance() or QGuiApplication([])
    end = time.monotonic() + timeout
    while not cond() and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
    return cond()


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class GoogleAgendaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.now = NOW
        self.fetched = []
        self.records = []
        self.data = ICS
        self.cal = gcal.GoogleCalendar(root / "link.json", root / "events.json", fetcher=self.fetch,
                                       record=lambda sent, ok: self.records.append((sent, ok)),
                                       clock=lambda: self.now)  # fmt: skip
        self.reminders = root / "reminders.json"

    def fetch(self, link):
        self.fetched.append(link)
        if isinstance(self.data, Exception):
            raise self.data
        return self.data

    def make(self, connected=True, gcal_obj="default"):
        if connected:
            self.assertTrue(self.cal.connect(LINK).ok)
        g = self.cal if gcal_obj == "default" else gcal_obj
        return SkillsController(
            reminders_path=self.reminders, clock=lambda: self.now, run_timer=False, gcal=g
        )

    def test_agenda_merges_google_and_local_with_source_and_freshness(self):
        s = self.make()
        s.confirm(s.handle("เตือนส่งรายงานพรุ่งนี้บ่ายสาม")["confirmToken"], True)
        card = s.handle("พรุ่งนี้มีนัดอะไร")
        text = "\n".join(card["lines"])
        self.assertIn("มี 3 นัด", card["title"])  # ไปเชียงใหม่ (ทั้งวัน) + โทรหาหมอ + ส่งรายงาน (ในเครื่อง)
        self.assertIn("ทั้งวัน · ไปเชียงใหม่ · Google", text)
        self.assertIn("โทรหาหมอ · Google", text)
        self.assertIn("ส่งรายงาน", text)
        self.assertNotIn("ส่งรายงาน · Google", text)
        self.assertTrue(card["lines"][-1].startswith("ปฏิทิน Google: ข้อมูลเมื่อ"))
        self.assertIn("สำเนาปฏิทิน Google", card["badge"]["reason"])
        self.assertNotIn("private-", str(card))  # ลิงก์ลับไม่ขึ้นจอ

    def test_auto_sync_every_15_minutes_while_signed_in(self):
        # การ์ด 0051: ไม่ต้องเปิดเว็บ · ดึงเองตามรอบ · ครั้งที่ลองล่าสุดนับรอบ (ออฟไลน์ไม่ถี่ขึ้น)
        s = self.make()
        self.fetched.clear()
        s._gcal_tried = self.now
        s.tick()
        self.now += timedelta(minutes=14)
        s.tick()
        self.assertEqual(self.fetched, [])
        self.now += timedelta(minutes=1)
        s.tick()
        self.assertTrue(wait_until(lambda: len(self.fetched) == 1 and not s._gcal_busy))
        self.data = OSError("offline")
        self.now += timedelta(minutes=15)
        s.tick()
        self.assertTrue(wait_until(lambda: len(self.fetched) == 2 and not s._gcal_busy))
        self.now += timedelta(minutes=5)
        s.tick()
        self.assertEqual(len(self.fetched), 2)

    def test_auto_sync_needs_a_connected_calendar(self):
        s = self.make(connected=False)
        self.now += timedelta(hours=2)
        s.tick()
        self.assertEqual(self.fetched, [])

    def test_voice_update_calendar(self):
        s = self.make()
        self.assertTrue(wait_until(lambda: not s._gcal_busy))
        self.fetched.clear()
        card = s.handle("อัปเดตปฏิทินหน่อย")
        self.assertEqual(card["title"], "กำลังดึงปฏิทิน Google ใหม่")
        self.assertTrue(wait_until(lambda: self.fetched == [LINK]))
        card = SkillsController(reminders_path=self.reminders, clock=lambda: self.now,
                                run_timer=False, gcal=None).handle("ซิงค์ปฏิทิน")  # fmt: skip
        self.assertEqual(card["title"], "ยังไม่ได้เชื่อมต่อปฏิทิน Google")

    def test_voice_question_gets_google_events_without_ai(self):
        s = self.make()
        card = s.voiceAnswer("พรุ่งนี้มีนัดอะไร")
        self.assertIn("ไปเชียงใหม่ · Google", "\n".join(card["lines"]))

    def test_upcoming_and_next_include_google(self):
        s = self.make()
        up = s.upcoming
        self.assertTrue(
            any(u["what"] == "ไปเชียงใหม่" and u["when"].endswith("ทั้งวัน · Google") for u in up)
        )
        whens = [u["what"] for u in up]
        self.assertLess(whens.index("ไปเชียงใหม่"), whens.index("ประชุมทีม (ย้ายบ่าย)"))  # เรียงตามเวลา
        nxt = s.handle("นัดถัดไปของฉันคืออะไร")
        self.assertIn("ไปเชียงใหม่", "\n".join(nxt["lines"]))

    def test_google_events_cannot_be_cancelled_here(self):
        s = self.make()
        card = s.handle("ยกเลิกนัดโทรหาหมอ")
        self.assertIn("ปฏิทิน Google", card["title"])
        self.assertEqual(card["confirmToken"], "")  # ไม่มีอะไรให้ยืนยันลบ
        s.confirm(s.handle("เตือนส่งรายงานพรุ่งนี้บ่ายสาม")["confirmToken"], True)
        all_card = s.handle("ลบนัดทั้งหมด")
        self.assertIn("นัดจากปฏิทิน Google ไม่ถูกลบ", "\n".join(all_card["lines"]))
        s.confirm(all_card["confirmToken"], True)
        self.assertTrue(any(u["what"] == "โทรหาหมอ" for u in s.upcoming))  # นัด Google ยังอยู่
        self.assertFalse(any(u["what"] == "ส่งรายงาน" for u in s.upcoming))

    def test_not_connected_answers_like_before(self):
        s = self.make(connected=False)
        card = s.handle("พรุ่งนี้มีนัดอะไร")
        self.assertEqual(card["lines"], ["จดนัดได้เลย เช่น “เตือนส่งรายงานพรุ่งนี้บ่ายสอง”"])
        self.assertEqual(self.fetched, [])
        self.assertFalse(s.gcalConnected)
        no = self.make(connected=False, gcal_obj=None)
        self.assertFalse(no.gcalAvailable)
        self.assertEqual(no.handle("พรุ่งนี้มีนัดอะไร")["lines"], card["lines"])

    def test_stale_copy_refreshes_in_background_and_answers_now(self):
        s = self.make()
        n = len(self.fetched)
        self.now = NOW + timedelta(minutes=31)
        card = s.handle("พรุ่งนี้มีนัดอะไร")  # ตอบจากสำเนาทันที
        self.assertIn("ไปเชียงใหม่", "\n".join(card["lines"]))
        self.assertTrue(wait_until(lambda: not s.gcalBusy and len(self.fetched) == n + 1))
        self.assertEqual(self.records[-1][1], True)

    def test_offline_keeps_answering_from_copy(self):
        s = self.make()
        self.data = gcal.SyncError("ดึงปฏิทินไม่ได้ (ไม่มีอินเทอร์เน็ต?) · ใช้ข้อมูลที่ดึงไว้ล่าสุด")
        self.now = NOW + timedelta(hours=26)
        s.handle("พรุ่งนี้มีนัดอะไร")  # เก่ากว่า 30 นาที → ลองดึง (ล้ม)
        self.assertTrue(wait_until(lambda: not s.gcalBusy))
        tries = len(self.fetched)
        card = s.handle("วันนี้มีนัดอะไร")  # 16 ต.ค. · เพิ่งลองไป = ไม่ลองซ้ำ (สมุดบันทึกไม่รก)
        self.assertEqual(len(self.fetched), tries)
        self.assertFalse(s.gcalBusy)
        self.assertIn("ไปเชียงใหม่", "\n".join(card["lines"]))
        self.assertIn("เก่ากว่า 1 วัน", card["lines"][-1])
        self.assertIn("ดึงครั้งล่าสุดไม่สำเร็จ", card["lines"][-1])
        self.assertIn("ไม่มีอินเทอร์เน็ต", s.gcalStatus)
        self.now += timedelta(minutes=31)  # ผ่านไปอีกพัก = ลองใหม่ได้
        s.handle("วันนี้มีนัดอะไร")
        self.assertTrue(wait_until(lambda: not s.gcalBusy and len(self.fetched) == tries + 1))

    def test_settings_slots_connect_and_disconnect(self):
        s = self.make(connected=False)
        self.assertTrue(s.gcalConnect("https://evil.example/basic.ics"))
        self.assertTrue(wait_until(lambda: not s.gcalBusy))
        self.assertFalse(s.gcalConnected)
        self.assertIn("ไม่ใช่ที่อยู่ปฏิทินของ Google", s.gcalStatus)
        self.assertEqual(self.fetched, [])
        self.assertTrue(s.gcalConnect(LINK))
        self.assertTrue(wait_until(lambda: not s.gcalBusy))
        self.assertTrue(s.gcalConnected)
        self.assertEqual(s.gcalHint, "…cd12")
        self.assertIn("ดึงล่าสุด", s.gcalStatus)
        self.assertTrue(s.gcalSyncNow())
        self.assertTrue(wait_until(lambda: not s.gcalBusy))
        s.gcalDisconnect()
        self.assertFalse(s.gcalConnected)
        self.assertIn("เลิกเชื่อมต่อแล้ว", s.gcalStatus)
        self.assertFalse(any(u["what"] == "ไปเชียงใหม่" for u in s.upcoming))


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class GoogleAlertTest(unittest.TestCase):
    """การ์ด 0032: ตัวคุมเตือนนัด Google ผ่าน reminderDue เดียวกับนัดในเครื่อง."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = NOW
        self.minutes = 10
        self.got = []

    def make(self, ics=ICS):
        cal = gcal.GoogleCalendar(self.root / "link.json", self.root / "events.json",
                                  fetcher=lambda link: ics, clock=lambda: self.now)  # fmt: skip
        if not cal.connected:
            self.assertTrue(cal.connect(LINK).ok)
        s = SkillsController(
            reminders_path=self.root / "r.json",
            clock=lambda: self.now,
            run_timer=False,
            gcal=cal,
            gcal_alert_min=lambda: self.minutes,
        )
        s.reminderDue.connect(self.got.append)
        # tick ดึงปฏิทินเองตามรอบ (การ์ด 0051) · รอเธรดดึงจบก่อนลบโฟลเดอร์ชั่วคราว
        self.addCleanup(lambda: wait_until(lambda: not s._gcal_busy))
        return s, cal

    def test_alert_once_with_lead_title_and_source(self):
        s, cal = self.make()
        doctor = next(e for e in cal.between(date(2026, 10, 16), 1) if e.what == "โทรหาหมอ")
        self.now = doctor.when - timedelta(minutes=10, seconds=5)
        s.tick()
        self.assertEqual(self.got, [])
        self.now = doctor.when - timedelta(minutes=9, seconds=50)
        s.tick()
        s.tick()  # รอบถัดไป (30 วิ) ต้องไม่เตือนซ้ำ
        self.assertEqual(len(self.got), 1)
        r = self.got[0]
        self.assertEqual((r["what"], r["title"]), ("โทรหาหมอ", "อีก 10 นาที"))
        self.assertIn("ปฏิทิน Google", r["when"])
        again, _ = self.make()  # เข้าเครื่องใหม่
        self.now += timedelta(minutes=1)
        again.tick()
        self.assertEqual(len(self.got), 1)

    def test_broken_local_reminders_file_does_not_stop_google_alerts(self):
        """ตรวจทั้งระบบ 2026-10-18 ข้อ 3.9: ไฟล์นัดในเครื่องเสีย (ไม่มีสำรอง) เดิมทำให้เตือนนัด Google หยุดเงียบ."""
        (self.root / "r.json").write_text("{not json", "utf-8")
        s, cal = self.make()
        doctor = next(e for e in cal.between(date(2026, 10, 16), 1) if e.what == "โทรหาหมอ")
        self.now = doctor.when - timedelta(minutes=9)
        s.tick()
        self.assertEqual([r["what"] for r in self.got], ["โทรหาหมอ"])

    def test_off_means_no_alert(self):
        self.minutes = 0
        s, cal = self.make()
        doctor = next(e for e in cal.between(date(2026, 10, 16), 1) if e.what == "โทรหาหมอ")
        self.now = doctor.when - timedelta(minutes=5)
        s.tick()
        self.assertEqual(self.got, [])

    def test_many_at_once_are_capped(self):
        events = "".join(
            f"BEGIN:VEVENT\nUID:m{i}\nDTSTART:20261016T020000Z\nDTEND:20261016T030000Z\n"
            f"SUMMARY:ประชุม {i}\nEND:VEVENT\n"
            for i in range(5)
        )
        ics = f"BEGIN:VCALENDAR\nVERSION:2.0\n{events}END:VCALENDAR\n".encode()
        s, cal = self.make(ics)
        first = cal.between(date(2026, 10, 16), 1)[0]
        self.now = first.when - timedelta(minutes=5)
        s.tick()
        self.assertEqual(len(self.got), 4)  # 3 นัด + สรุปที่เหลือ
        self.assertIn("และอีก 2 นัด", self.got[-1]["what"])
        s.tick()
        self.assertEqual(len(self.got), 4)  # ทั้ง 5 นัดถูกจำว่าเตือนแล้ว


if __name__ == "__main__":
    unittest.main()
