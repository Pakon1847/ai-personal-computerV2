"""ถามนัดละเอียดขึ้น: วันในสัปดาห์ · วันที่ · เดือน · ค้นชื่อนัด (การ์ด 0037) · ใช้ปฏิทินตัวอย่างของเทสต์ ไม่ใช้ชุดวัด."""

import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from aipc.skills import agenda, gcal
    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None

from tests.test_skill_gcal import ICS, LINK
from tests.test_ui_gcal import wait_until

NOW = datetime(2026, 10, 15, 9, 0).astimezone()  # พฤหัสบดี
TODAY = NOW.date()


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class DetailParseTest(unittest.TestCase):
    def q(self, text, today=TODAY):
        r = agenda.parse(text, today)
        return None if r is None else (r.start, r.days)

    def test_weekdays_and_the_sunday_trap(self):
        self.assertEqual(self.q("วันศุกร์นี้มีนัดอะไร"), (date(2026, 10, 16), 1))
        self.assertEqual(self.q("วันพฤหัสมีนัดอะไร"), (TODAY, 1))  # วันนี้เป็นวันพฤหัส = วันนี้
        self.assertEqual(self.q("วันจันทร์หน้ามีนัดไหม"), (date(2026, 10, 19), 1))
        # "อาทิตย์" แปลได้ทั้งวันอาทิตย์และสัปดาห์: มี "วัน" นำหน้า = วันอาทิตย์
        self.assertEqual(self.q("วันอาทิตย์นี้มีนัดอะไร"), (date(2026, 10, 18), 1))
        self.assertEqual(self.q("วันอาทิตย์หน้ามีนัดไหม"), (date(2026, 10, 25), 1))
        self.assertEqual(self.q("อาทิตย์นี้มีนัดอะไร"), (TODAY, 4))  # กฎเดิม: สัปดาห์นี้

    def test_dates_months_and_invalid(self):
        self.assertEqual(self.q("วันที่ 20 มีนัดอะไร"), (date(2026, 10, 20), 1))
        self.assertEqual(self.q("วันที่ 3 มีนัดอะไร"), (date(2026, 11, 3), 1))  # ผ่านแล้ว = เดือนหน้า
        self.assertEqual(self.q("วันที่ 3 พฤศจิกายนมีนัดไหม"), (date(2026, 11, 3), 1))
        self.assertEqual(self.q("5 ม.ค. มีนัดอะไรบ้าง"), (date(2027, 1, 5), 1))
        self.assertEqual(self.q("10 ต.ค.มีนัดไหม"), (date(2027, 10, 10), 1))  # ผ่านแล้วปีนี้ = ปีหน้า
        self.assertEqual(self.q("วันที่ 31 พฤศจิกายนมีนัดไหม")[1], 0)  # ไม่มีวันนี้
        self.assertEqual(self.q("วันที่ 31 มีนัดอะไร", date(2026, 11, 15))[1], 0)  # 31 พ.ย. ไม่มี
        self.assertEqual(self.q("เดือนนี้มีนัดอะไรบ้าง"), (TODAY, 17))
        self.assertEqual(self.q("เดือนหน้ามีนัดอะไร"), (date(2026, 11, 1), 30))
        self.assertEqual(self.q("เดือนหน้ามีนัดอะไร", date(2026, 12, 20)), (date(2027, 1, 1), 31))

    def test_weekday_with_date_uses_the_date(self):
        """ตรวจทั้งระบบ 2026-10-18 ข้อ 3.6: วันที่ชัดเจนมาก่อนวันในสัปดาห์ (เดิม "วันศุกร์ที่ 20 พ.ย." = ศุกร์นี้)."""
        self.assertEqual(self.q("วันอังคารที่ 17 พฤศจิกายนมีนัดอะไร"), (date(2026, 11, 17), 1))
        self.assertEqual(self.q("วันเสาร์ที่ 24 มีนัดไหม"), (date(2026, 10, 24), 1))
        self.assertEqual(self.q("วันที่ 1/12 มีนัดอะไร"), (date(2026, 12, 1), 1))
        self.assertEqual(self.q("วันที่ 9 เดือนหน้ามีนัดไหม"), (date(2026, 11, 9), 1))
        for text in ("วันพุธที่แล้วมีนัดอะไร", "สัปดาห์ที่แล้วมีนัดอะไรบ้าง"):  # ย้อนหลัง ไม่ใช่นัดที่จะถึง
            self.assertIsNone(agenda.parse(text, TODAY), text)
        # วันจันทร์ (19) ถาม "อาทิตย์หน้าวันอังคาร" = อังคารของสัปดาห์หน้า (27) ไม่ใช่พรุ่งนี้
        monday = date(2026, 10, 19)
        self.assertEqual(self.q("อาทิตย์หน้าวันอังคารมีนัดอะไร", monday), (date(2026, 10, 27), 1))

    def test_not_schedule_questions(self):
        for text in ("วันศุกร์นี้อากาศเป็นยังไง", "วันที่ 20 คือวันอะไร", "เดือนหน้าจะไปเที่ยวไหนดี"):
            self.assertIsNone(agenda.parse(text, TODAY), text)

    def test_title_query(self):
        self.assertEqual(agenda.title_query("นัดหมอวันไหน"), ("หมอ", True))
        self.assertEqual(agenda.title_query("มีนัดกับหมอไหมครับ"), ("หมอ", True))
        self.assertEqual(agenda.title_query("ประชุมทีมครั้งหน้าเมื่อไหร่"), ("ประชุมทีม", False))
        for text in ("นัดถัดไปของฉันวันไหน", "นัดต่อไปของแมนซิตี้เจอใคร", "มีนัดอะไรไหม", "นัดวันไหน"):
            self.assertIsNone(agenda.title_query(text), text)


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class DetailAnswerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.now = NOW
        self.cal = gcal.GoogleCalendar(root / "l.json", root / "e.json", fetcher=lambda link: ICS,
                                       clock=lambda: self.now)  # fmt: skip
        self.assertTrue(self.cal.connect(LINK).ok)
        self.s = SkillsController(reminders_path=root / "r.json", clock=lambda: self.now,
                                  run_timer=False, gcal=self.cal)  # fmt: skip

    def text(self, card):
        return "\n".join(card["lines"])

    def test_weekday_and_date_answers(self):
        fri = self.s.handle("วันศุกร์นี้มีนัดอะไร")
        self.assertEqual(fri["route"], "agenda")
        self.assertIn("ไปเชียงใหม่", self.text(fri))
        self.assertIn("โทรหาหมอ", self.text(fri))
        sun = self.s.handle("วันอาทิตย์นี้มีนัดอะไร")
        self.assertIn("ไปเชียงใหม่", self.text(sun))  # ทั้งวันหลายวันถึง 18 ต.ค.
        self.assertNotIn("โทรหาหมอ", self.text(sun))
        bad = self.s.handle("วันที่ 31 พฤศจิกายนมีนัดไหม")
        self.assertEqual(bad["title"], "ไม่มีวันที่ 31 พ.ย.")
        self.assertEqual(self.s.voiceAnswer("วันศุกร์นี้มีนัดอะไร")["title"], fri["title"])

    def test_month_beyond_google_copy_says_so(self):
        self.now = NOW + timedelta(days=36)  # 20 พ.ย. · สำเนาดึงเมื่อ 15 ต.ค. มีถึง 14 ธ.ค.
        card = self.s.handle("เดือนหน้ามีนัดอะไร")
        self.assertIn("มีข้อมูลถึง", card["lines"][-1])
        # สำเนาเก่า = ดึงใหม่เบื้องหลัง · รอให้จบก่อนลบโฟลเดอร์ชั่วคราว (วินโดวส์ลบไฟล์ที่เปิดอยู่ไม่ได้)
        self.assertTrue(wait_until(lambda: not self.s.gcalBusy))

    def test_title_search(self):
        meet = self.s.handle("นัดประชุมทีมวันไหน")
        self.assertEqual(meet["route"], "agenda")
        self.assertIn("ประชุมทีม (ย้ายบ่าย)", self.text(meet))
        self.assertLessEqual(sum("ประชุมทีม" in x for x in meet["lines"]), 10)
        none = self.s.handle("มีนัดกับทันตแพทย์ไหม")
        self.assertEqual(none["title"], "ไม่พบนัด “กับทันตแพทย์” ที่ยังไม่ถึง".replace("กับ", ""))
        other = self.s.handle("ทีมชาติไทยแข่งครั้งหน้าเมื่อไหร่")  # ไม่มีนัดชื่อนี้ = ไม่ใช่คำถามนัด
        self.assertNotEqual(other.get("route"), "agenda")


if __name__ == "__main__":
    unittest.main()
