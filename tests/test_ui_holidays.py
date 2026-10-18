"""วันหยุดไทยจากปฏิทินสาธารณะของ Google (การ์ด 0033) · ไฟล์ตัวอย่างเลียนแบบรูปแบบจริง · ไม่ใช้เน็ตจริง."""

import os
import tempfile
import time
import unittest
from datetime import date, datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    from aipc.skills import agenda, gcal
    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None

NOW = datetime(2026, 10, 15, 9, 0).astimezone()  # พฤหัสบดี

PUBLIC = "วันหยุดนักขัตฤกษ์"
OBS = "วันสำคัญ\\nหากต้องการซ่อนวันสำคัญ ให้ไปที่การตั้งค่า Google ปฏิทิน"


def ev(uid, day, title, desc):
    nxt = date.fromisoformat(day).toordinal() + 1
    end = date.fromordinal(nxt).strftime("%Y%m%d")
    return (f"BEGIN:VEVENT\nDTSTART;VALUE=DATE:{day.replace('-', '')}\nDTEND;VALUE=DATE:{end}\n"
            f"UID:{uid}\nDESCRIPTION:{desc}\nSTATUS:CONFIRMED\nSUMMARY:{title}\nTRANSP:TRANSPARENT\n"
            "END:VEVENT\n")  # fmt: skip


HOLIDAY_ICS = (
    "BEGIN:VCALENDAR\nPRODID:-//Google Inc//Google Calendar 70.9054//EN\nVERSION:2.0\n"
    "X-WR-CALNAME:วันหยุดในไทย\nX-WR-TIMEZONE:UTC\n"
    + ev("h1", "2026-03-03", "วันมาฆบูชา", PUBLIC)  # ผ่านไปแล้ว · ปีหน้ายังไม่มี (เหมือนข้อมูลจริง)
    + ev("h2", "2026-10-23", "วันปิยมหาราช", PUBLIC)
    + ev("h3", "2026-10-31", "วันฮาโลวีน", OBS)
    + ev("h4", "2026-12-05", "วันคล้ายวันพระบรมราชสมภพ", PUBLIC)
    + ev("h5", "2026-12-07", "วันหยุดชดเชยวันคล้ายวันพระบรมราชสมภพ", PUBLIC)
    + ev("h6", "2026-12-10", "​วันรัฐธรรมนูญ", PUBLIC)
    + ev("h7", "2027-01-01", "วันขื้นปีใหม่", PUBLIC)
    + ev("h8", "2027-02-06", "วันตรุษจีน", OBS)
    + ev("h9", "2027-04-13", "วันสงกรานต์", PUBLIC)
    + ev("h10", "2027-04-14", "วันสงกรานต์", PUBLIC)
    + ev("h11", "2027-04-15", "วันสงกรานต์", PUBLIC)
    + "END:VCALENDAR\n"
).encode()


def wait_until(cond, timeout=5.0):
    app = QCoreApplication.instance() or QGuiApplication([])
    end = time.monotonic() + timeout
    while not cond() and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
    return cond()


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class HolidayParseTest(unittest.TestCase):
    def test_kinds_and_zero_width(self):
        evs = gcal.expand(HOLIDAY_ICS, NOW, NOW.replace(year=2027, month=12), classify=True,
                          source="holidays")  # fmt: skip
        kinds = {e.what: e.kind for e in evs}
        self.assertEqual(kinds["วันปิยมหาราช"], "holiday")
        self.assertEqual(kinds["วันฮาโลวีน"], "observance")
        self.assertIn("วันรัฐธรรมนูญ", kinds)  # ตัด U+200B ออกแล้ว
        self.assertTrue(all(e.source == "holidays" for e in evs))
        plain = gcal.expand(HOLIDAY_ICS, NOW, NOW.replace(year=2027, month=12))
        self.assertTrue(all(e.kind == "event" for e in plain))  # ปฏิทินส่วนตัวไม่อ่านชนิดวัน

    def test_question_parsers(self):
        today = NOW.date()
        for t in ("วันหยุดถัดไปคือวันอะไร", "วันหยุดราชการครั้งหน้าวันไหน", "อีกกี่วันจะถึงวันหยุด",
                  "อีกกี่วันถึงวันหยุดครับ"):  # fmt: skip
            self.assertTrue(agenda.asks_next_holiday(t), t)
        for t in ("วันหยุดไปเที่ยวไหนดี", "พรุ่งนี้มีนัดอะไร", "อีกกี่วันจะถึงวันมาฆบูชา"):
            self.assertFalse(agenda.asks_next_holiday(t), t)
        q = agenda.holiday_range("สัปดาห์หน้ามีวันหยุดไหม", today)
        self.assertEqual((q.start, q.days), (date(2026, 10, 19), 7))
        self.assertEqual(agenda.holiday_range("พรุ่งนี้หยุดไหม", today).start, date(2026, 10, 16))
        self.assertIsNone(agenda.holiday_range("วันหยุดไปเที่ยวไหนดี", today))
        self.assertIsNone(agenda.parse("สัปดาห์หน้ามีวันหยุดไหม", today))  # ไม่ใช่ตารางนัด
        self.assertEqual(agenda.until_target("อีกกี่วันจะถึงวันมาฆบูชาครับ"), "วันมาฆบูชา")
        self.assertEqual(agenda.until_target("มาฆบูชาอีกกี่วัน"), "มาฆบูชา")
        self.assertEqual(agenda.until_target("กี่วันจะถึงสงกรานต์"), "สงกรานต์")
        self.assertIsNone(agenda.until_target("วันนี้วันอะไร"))
        self.assertEqual(agenda.holiday_key("วันขื้นปีใหม่"), "ขึ้นปีใหม่")


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class HolidayAnswerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = NOW
        self.fetched = []
        self.records = []

    def fetch(self, link):
        self.fetched.append(link)
        return HOLIDAY_ICS

    def make(self, on=True):
        hol = gcal.GoogleCalendar(
            self.root / "hol-link.json", self.root / "hol.json", fetcher=self.fetch,
            record=lambda sent, ok: self.records.append((sent, ok)), clock=lambda: self.now,
            source="holidays", future=gcal.HOLIDAY_FUTURE, stale_after=gcal.HOLIDAY_STALE,
            sent=gcal.HOLIDAY_SENT, classify=True,
        )  # fmt: skip
        if on:
            self.assertTrue(hol.connect(gcal.HOLIDAYS_TH).ok)
        s = SkillsController(reminders_path=self.root / "r.json", clock=lambda: self.now,
                             run_timer=False, holidays=hol)  # fmt: skip
        return s, hol

    def test_next_holiday_public_only(self):
        s, _ = self.make()
        card = s.handle("วันหยุดถัดไปคือวันอะไร")
        self.assertEqual(card["title"], "วันหยุดถัดไป: วันปิยมหาราช")
        self.assertIn("อีก 8 วัน", card["lines"][0])
        self.assertNotIn("ฮาโลวีน", "\n".join(card["lines"]))  # วันสำคัญไม่ใช่วันหยุด
        self.assertEqual(s.voiceAnswer("อีกกี่วันจะถึงวันหยุด")["title"], card["title"])  # ทางเสียงได้ด้วย

    def test_until_named_holiday_from_feed(self):
        s, _ = self.make()
        rc = s.handle("อีกกี่วันจะถึงวันรัฐธรรมนูญ")
        self.assertEqual(rc["title"], "อีก 56 วันถึงวันรัฐธรรมนูญ")  # มี U+200B ในไฟล์ก็ยังเจอ
        self.assertIn("วันหยุดราชการ", rc["lines"][0])
        self.assertEqual(s.handle("อีกกี่วันจะถึงวันตรุษจีน")["title"], "อีก 114 วันถึงวันตรุษจีน")
        self.assertIn("ไม่ได้หยุด", s.handle("อีกกี่วันจะถึงวันตรุษจีน")["lines"][0])
        # วันจริงมาก่อนวันชดเชยเสมอ · ไม่เอาวันชดเชยมาตอบชื่อวัน
        self.assertEqual(s.handle("อีกกี่วันถึงวันคล้ายวันพระบรมราชสมภพ")["title"],
                         "อีก 51 วันถึงวันคล้ายวันพระบรมราชสมภพ")  # fmt: skip
        self.now = datetime(2026, 12, 6, 9, 0).astimezone()  # ผ่านวันจริงแล้ว เหลือวันชดเชย
        self.assertIn("ยังไม่มีข้อมูล", s.handle("อีกกี่วันถึงวันคล้ายวันพระบรมราชสมภพ")["title"])

    def test_until_questions_that_are_not_holidays_keep_their_old_path(self):
        """ตรวจทั้งระบบ 2026-10-18 ข้อ 3.5: เปิดสวิตช์วันหยุดแล้ว "อีกกี่วัน…" ที่ไม่ใช่ชื่อวันหยุด ต้องไปทางเดิม
        เหมือนตอนปิดสวิตช์ (เดิม "…วันพระ" ได้วันคล้ายวันพระบรมราชสมภพ · "…นัด…" ได้ "ยังไม่มีข้อมูล")."""
        on, _ = self.make()
        off, _ = self.make(on=False)
        for q in ["อีกกี่วันจะถึงวันพระหน้า", "อีกกี่วันจะถึงนัดทำฟัน", "อีกกี่วันจะถึงวันที่ 28"]:
            a, b = on.handle(q), off.handle(q)
            self.assertEqual((a["kind"], a["title"]), (b["kind"], b["title"]), q)
            self.assertNotIn("ยังไม่มีข้อมูล", a["title"], q)

    def test_missing_data_is_said_not_guessed(self):
        s, _ = self.make()
        card = s.handle("อีกกี่วันจะถึงวันมาฆบูชา")  # ปีหน้ายังไม่มีในไฟล์
        self.assertEqual(card["title"], "ยังไม่มีข้อมูลวันมาฆบูชา")
        self.assertIn("ไม่เดา", card["lines"][0])
        self.assertIn("ยังไม่มีข้อมูล", s.handle("อีกกี่วันถึงวันเด็ก")["title"])
        # วันตายตัวยังตอบด้วยโค้ดเดิม (ไม่ต้องใช้ไฟล์)
        self.assertEqual(s.handle("อีกกี่วันจะถึงปีใหม่")["title"], "อีก 78 วันถึงปีใหม่")

    def test_ranges_and_agenda_labels(self):
        s, _ = self.make()
        week = s.handle("สัปดาห์หน้ามีวันหยุดไหม")  # 19–25 ต.ค.
        self.assertEqual(week["title"], "สัปดาห์หน้า (จ. 19 ต.ค.–อา. 25 ต.ค.) มีวันหยุด 1 วัน")
        self.assertIn("วันปิยมหาราช", week["lines"][0])
        self.assertIn("ไม่มีวันหยุดราชการ", s.handle("พรุ่งนี้หยุดไหม")["title"])
        self.now = datetime(2026, 10, 26, 9, 0).astimezone()
        agenda_card = s.handle("สัปดาห์นี้มีนัดอะไร")  # 26 ต.ค.–1 พ.ย. มีวันฮาโลวีน (วันสำคัญ)
        self.assertIn("วันฮาโลวีน · วันสำคัญ", "\n".join(agenda_card["lines"]))
        self.now = NOW
        self.assertFalse(any("ปิยมหาราช" in u["what"] for u in s.upcoming))  # วันหยุดไม่ใช่ "นัดถัดไป"

    def test_switch_off_by_default_and_cleanup(self):
        s, hol = self.make(on=False)
        self.assertFalse(s.holidaysOn)
        card = s.handle("วันหยุดถัดไปคือวันอะไร")
        self.assertEqual(card["title"], "ยังไม่ได้เปิดปฏิทินวันหยุดไทย")
        self.assertEqual(self.fetched, [])  # ปิดอยู่ = ไม่ออกเน็ต
        self.assertTrue(s.setHolidays(True))
        self.assertTrue(wait_until(lambda: not s.holidaysBusy))
        self.assertTrue(s.holidaysOn)
        self.assertIn("ดึงล่าสุด", s.holidaysStatus)
        self.assertIn("วันหยุดไทยสาธารณะ", self.records[-1][0])
        self.assertTrue(s.setHolidays(False))
        self.assertFalse(s.holidaysOn)
        self.assertFalse((self.root / "hol.json").exists())


if __name__ == "__main__":
    unittest.main()
