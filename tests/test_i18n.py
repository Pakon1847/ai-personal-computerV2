"""ภาษาอังกฤษ (การ์ด 0039 ระยะ A) · ตารางแปล + ค่าภาษาในตั้งค่า."""

import json
import re
import tempfile
import unittest
from pathlib import Path

from aipc import i18n
from aipc.ui import settings

ROOT = Path(__file__).resolve().parents[1]
THAI = re.compile(r"[฀-๿]")


class TrTest(unittest.TestCase):
    def tearDown(self):
        i18n.set_lang("th")

    def test_thai_is_default_and_untranslated_falls_back_to_thai(self):
        self.assertEqual(i18n.lang(), "th")
        self.assertEqual(i18n.tr("ข้อความที่ไม่มีในตาราง"), "ข้อความที่ไม่มีในตาราง")
        i18n.set_lang("en")
        self.assertEqual(i18n.tr("ข้อความที่ไม่มีในตาราง"), "ข้อความที่ไม่มีในตาราง")  # ไม่มีช่องว่างโผล่
        i18n.set_lang("fr")  # ภาษาที่ไม่รองรับ = ไทย
        self.assertEqual(i18n.lang(), "th")

    def test_values_are_filled_after_translation(self):
        i18n.table.cache_clear()
        i18n.table()["อีก {n} วัน"] = "In {n} days"
        self.addCleanup(i18n.table.cache_clear)
        self.assertEqual(i18n.tr("อีก {n} วัน", n=3), "อีก 3 วัน")
        i18n.set_lang("en")
        self.assertEqual(i18n.tr("อีก {n} วัน", n=3), "In 3 days")

    def test_catalog_is_valid(self):
        data = json.loads((ROOT / "src/aipc/i18n/en.json").read_text(encoding="utf-8"))
        for th, en in data.items():
            self.assertTrue(THAI.search(th), f"กุญแจต้องเป็นข้อความไทย: {th!r}")
            self.assertFalse(THAI.search(en), f"คำแปลยังมีภาษาไทย: {th!r} → {en!r}")
            # ค่าแทรก {ชื่อ} ต้องครบเท่ากันทั้งสองภาษา (ไม่งั้น format พัง)
            self.assertEqual(
                sorted(re.findall(r"\{(\w+)\}", th)), sorted(re.findall(r"\{(\w+)\}", en)), th
            )


class LanguagePrefTest(unittest.TestCase):
    def test_saved_per_account_and_bad_value_is_thai(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ui.json"
            prefs = settings.load(path)
            self.assertEqual(prefs.language, "th")
            prefs.language = "en"
            settings.save(prefs, path)
            self.assertEqual(settings.load(path).language, "en")
            path.write_text('{"language": "xx"}', encoding="utf-8")
            self.assertEqual(settings.load(path).language, "th")


class AnswerLanguageTest(unittest.TestCase):
    """เกณฑ์ A3 ส่วนโค้ด: ถามอังกฤษ = สั่งให้ตอบอังกฤษ · ถามไทย = prompt เดิมทุกตัวอักษร (ภาษาไทยไม่ถอยหลัง)."""

    def test_question_language_is_decided_by_code(self):
        from aipc.skills import catalog

        for text in ("Why is the sky blue?", "what time is it", "OK thanks"):
            self.assertTrue(catalog.is_english(text), text)
        for text in ("ทำไมท้องฟ้าสีฟ้า", "เปิด YouTube", "แปลว่า hello", "123", ""):
            self.assertFalse(catalog.is_english(text), text)

    def test_thai_prompt_unchanged_and_english_prompt_says_english(self):
        from datetime import date

        from aipc.cloud import ask
        from aipc.skills import catalog

        d = date(2026, 10, 18)
        th = catalog.system_prompt(d, cloud=True, model="m", forge=True)
        self.assertIn("ตอบภาษาไทย", th)
        self.assertEqual(
            th, catalog.system_prompt(d, cloud=True, model="m", forge=True, english=False)
        )
        en = catalog.system_prompt(d, cloud=True, model="m", forge=True, english=True)
        self.assertNotIn("ตอบภาษาไทย", en)
        self.assertIn("Answer in English", en)
        self.assertEqual(ask.instructions(d), ask._instructions(d))
        self.assertIn("Answer in English", ask.instructions(d, english=True))


if __name__ == "__main__":
    unittest.main()
