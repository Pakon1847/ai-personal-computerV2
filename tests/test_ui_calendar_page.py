"""หน้าปฏิทินตารางเดือน (การ์ด 0038) · ข้อมูลรายวันต้องตรงกับคำตอบ "วันนี้มีนัดอะไร" ทุกตัวอักษร."""

import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from aipc.skills import gcal
    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None

from tests.test_skill_gcal import ICS, LINK
from tests.test_ui_holidays import HOLIDAY_ICS

NOW = datetime(2026, 10, 15, 9, 0).astimezone()


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class MonthItemsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.now = NOW
        year = timedelta(days=365)  # ไม่ให้ดึงใหม่เบื้องหลังระหว่างเทสต์เลื่อนนาฬิกา
        self.cal = gcal.GoogleCalendar(root / "l.json", root / "e.json", fetcher=lambda link: ICS,
                                       clock=lambda: self.now, stale_after=year)  # fmt: skip
        self.hol = gcal.GoogleCalendar(root / "hl.json", root / "hc.json",
                                       fetcher=lambda link: HOLIDAY_ICS, clock=lambda: self.now,
                                       source="holidays", future=gcal.HOLIDAY_FUTURE,
                                       stale_after=year, classify=True)  # fmt: skip
        self.assertTrue(self.cal.connect(LINK).ok)
        self.assertTrue(self.hol.connect(gcal.HOLIDAYS_TH).ok)
        self.s = SkillsController(reminders_path=root / "r.json", clock=lambda: self.now,
                                  run_timer=False, gcal=self.cal, holidays=self.hol)  # fmt: skip
        self.s.confirm(self.s.handle("เตือนส่งรายงานวันที่ 20 ตุลาคม บ่ายสอง")["confirmToken"], True)

    def test_grid_shape_and_dots(self):
        m = self.s.monthItems(2026, 10)
        self.assertEqual(m["title"], "ตุลาคม 2569")
        cells = m["cells"]
        self.assertEqual(len(cells), 42)
        self.assertEqual(date.fromisoformat(cells[0]["iso"]).weekday(), 0)  # เริ่มวันจันทร์
        self.assertEqual(cells[0]["iso"], "2026-09-28")
        by = {c["iso"]: c for c in cells}
        self.assertTrue(by["2026-10-15"]["today"])
        self.assertTrue(by["2026-10-16"]["google"])
        self.assertTrue(by["2026-10-20"]["local"])
        self.assertTrue(by["2026-10-23"]["holiday"])  # วันปิยมหาราช (ไฟล์ตัวอย่าง)
        self.assertTrue(by["2026-10-31"]["observance"])  # วันฮาโลวีน
        self.assertFalse(by["2026-09-28"]["inMonth"])
        self.assertEqual(self.s.monthItems(0, 0)["month"], 10)  # 0 = เดือนนี้

    def test_every_day_matches_today_answer(self):
        for day in range(1, 32):
            self.now = datetime(2026, 10, day, 12, 0).astimezone()
            cell = next(c for c in self.s.monthItems(2026, 10)["cells"]
                        if c["iso"] == f"2026-10-{day:02d}")  # fmt: skip
            answer = self.s.handle("วันนี้มีนัดอะไร")["lines"]
            items = [x for x in answer if not x.startswith(("ปฏิทิน Google:", "จดนัดได้เลย"))]
            self.assertEqual(cell["lines"], items, f"วันที่ {day}")

    def test_note_when_month_beyond_google_copy(self):
        self.assertEqual(self.s.monthItems(2026, 11)["note"], "")
        self.assertIn("มีข้อมูลถึง", self.s.monthItems(2026, 12)["note"])  # สำเนา 15 ต.ค. มีถึง 14 ธ.ค.


try:
    from tests import test_ui_qml as qml
except ImportError:  # pragma: no cover
    qml = None


@unittest.skipIf(qml is None or qml.uiapp is None, "ไม่มี PySide6")
class CalendarPageQmlTest(unittest.TestCase):
    open_shell = qml.ShellCardTest.open_shell if qml and qml.uiapp else None

    @classmethod
    def setUpClass(cls):
        qml.setUpModule()

    @classmethod
    def tearDownClass(cls):
        qml.tearDownModule()

    def test_page_navigation_and_day_list(self):
        engine, win, warnings = self.open_shell("calendar")
        skills = engine._backends["skills"]
        tmp = Path(os.environ["XDG_DATA_HOME"])
        # ล็อกนาฬิกา: ดึงนัดได้แค่ตั้งแต่ "ตอนนี้ − 1 วัน" · ใช้นาฬิกาจริงแล้วนัด 16 ต.ค. หลุดเมื่อวันที่ผ่านไป
        skills._gcal = gcal.GoogleCalendar(tmp / "l.json", tmp / "e.json", fetcher=lambda link: ICS,
                                           clock=lambda: NOW)  # fmt: skip
        self.assertTrue(skills._gcal.connect(LINK).ok)
        skills.remindersChanged.emit()  # หน้าวาดใหม่
        qml.settle(80)
        cells = qml.find_items(win, "calendarCell")
        self.assertEqual(len(cells), 42)
        title = qml.find_items(win, "calendarMonthTitle")[0]
        before = title.property("text")
        qml.find_items(win, "calendarNext")[0].clicked.emit()
        qml.settle(50)
        self.assertNotEqual(title.property("text"), before)
        qml.find_items(win, "calendarPrev")[0].clicked.emit()
        qml.settle(50)
        self.assertEqual(title.property("text"), before)
        page = qml.find_items(win, "calendarPage")[0]
        page.setProperty("year", 2026)  # เดือนที่ไฟล์ตัวอย่างมีนัด (ไม่ขึ้นกับวันที่ของเครื่องที่รันเทสต์)
        page.setProperty("month", 10)
        skills.remindersChanged.emit()
        qml.settle(50)
        self.assertEqual(title.property("text"), "ตุลาคม 2569")
        page.setProperty("selected", "2026-10-16")  # เหมือนกดช่องวันศุกร์ 16
        qml.settle(50)
        lines = [x.property("text") for x in qml.find_items(win, "calendarDayLine")]
        self.assertTrue(any("โทรหาหมอ · Google" in x for x in lines), lines)
        self.assertEqual(warnings, [])

    def test_connect_banner_takes_you_to_the_calendar_card(self):
        """การ์ด 0067 G2: ยังไม่เชื่อมปฏิทิน Google = แถบ + ปุ่มพาไปการ์ดเชื่อมในหน้าตั้งค่า · เชื่อมแล้ว = แถบหาย."""
        engine, win, warnings = self.open_shell("calendar")
        skills = engine._backends["skills"]
        tmp = Path(os.environ["XDG_DATA_HOME"])
        skills._gcal = gcal.GoogleCalendar(tmp / "l2.json", tmp / "e2.json",
                                           fetcher=lambda link: ICS, clock=lambda: NOW)  # fmt: skip
        skills.gcalChanged.emit()
        qml.settle(50)
        banner = qml.find_items(win, "gcalBanner")[0]
        self.assertTrue(banner.property("visible"))
        qml.find_items(win, "gcalConnectFromCalendar")[0].clicked.emit()
        qml.settle(80)
        settings = qml.find_items(win, "settingsPage")[0]
        self.assertEqual(settings.property("section"), "ai")  # หมวดที่มีการ์ดปฏิทิน Google
        self.assertTrue(settings.property("visible"))
        self.assertTrue(skills._gcal.connect(LINK).ok)
        skills.gcalChanged.emit()
        qml.settle(50)
        self.assertFalse(banner.property("visible"))
        self.assertEqual(warnings, [])

    def test_large_font_and_dark_theme_have_no_warnings(self):
        engine, win, warnings = self.open_shell("calendar")
        ui = engine._backends["uiSettings"]
        ui.setFontScale(2.0)
        ui.setTheme("dark")
        qml.settle(80)
        self.assertEqual(len(qml.find_items(win, "calendarCell")), 42)
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
