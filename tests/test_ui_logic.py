import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from aipc.ui import settings, thaidate


class ThaiDateTest(unittest.TestCase):
    def test_buddhist_era_and_names(self):
        dt = datetime(2026, 9, 23, 14, 32)  # วันพุธ
        self.assertEqual(thaidate.long_date(dt), "วันพุธที่ 23 กันยายน 2569")
        self.assertEqual(thaidate.short_date(dt), "พ. 23 ก.ย.")
        self.assertEqual(thaidate.clock(dt), "14:32")

    def test_every_month_and_day_has_a_name(self):
        self.assertEqual(len(thaidate.MONTHS), 12)
        self.assertEqual(len(thaidate.DAYS), 7)

    def test_greeting_boundaries(self):
        cases = {
            4: "ค่ำ",
            5: "เช้า",
            11: "เช้า",
            12: "บ่าย",
            16: "บ่าย",
            17: "เย็น",
            19: "เย็น",
            20: "ค่ำ",
            23: "ค่ำ",
        }
        for hour, part in cases.items():
            got = thaidate.greeting(datetime(2026, 9, 23, hour, 0))
            self.assertEqual(got, "สวัสดีตอน" + part, hour)


class SettingsTest(unittest.TestCase):
    def test_missing_file_gives_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(settings.load(Path(tmp) / "no.json"), settings.UiPrefs())

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a" / "ui.json"
            settings.save(settings.UiPrefs("dark", 1.5), p)
            self.assertEqual(settings.load(p), settings.UiPrefs("dark", 1.5))
            self.assertFalse(p.with_name("ui.json.tmp").exists())  # ไม่มีไฟล์ชั่วคราวค้าง
            # ตัวเลือกเสียง (การ์ด 0019) ไม่สลับช่องกัน
            voice = settings.UiPrefs("light", 1.0, speak_answers=False, speak_reminders=True)
            settings.save(voice, p)
            self.assertEqual(settings.load(p), voice)
            # สวิตช์ Claude (2026-10-05): ค่าเริ่มต้นเปิด · ปิดแล้วจำไว้ · ค่าแปลก ๆ ในไฟล์ = เปิด (ค่าเริ่มต้นที่ Pakon เลือก)
            self.assertTrue(settings.UiPrefs().use_claude)
            settings.save(settings.UiPrefs(use_claude=False), p)
            self.assertFalse(settings.load(p).use_claude)
            p.write_text(json.dumps({"use_claude": "no"}), encoding="utf-8")
            self.assertTrue(settings.load(p).use_claude)

    def test_broken_or_edited_file_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "ui.json"
            p.write_text("{not json", encoding="utf-8")
            self.assertEqual(settings.load(p), settings.UiPrefs())
            p.write_text(json.dumps({"theme": "neon", "font_scale": 9}), encoding="utf-8")
            self.assertEqual(settings.load(p), settings.UiPrefs())


if __name__ == "__main__":
    unittest.main()
