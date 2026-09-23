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

    def test_broken_or_edited_file_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "ui.json"
            p.write_text("{not json", encoding="utf-8")
            self.assertEqual(settings.load(p), settings.UiPrefs())
            p.write_text(json.dumps({"theme": "neon", "font_scale": 9}), encoding="utf-8")
            self.assertEqual(settings.load(p), settings.UiPrefs())


if __name__ == "__main__":
    unittest.main()
