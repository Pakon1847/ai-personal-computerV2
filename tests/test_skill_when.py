"""ตัวแปลงเวลาไทย (การ์ดออกแบบ 0001) · ชุดประโยค 50 ข้อใน tests/data/reminder_sentences.json.

ชุดนี้คือชุดเดียวกับที่ใช้รายงานในบทที่ 4 · เกณฑ์ประกาศไว้ก่อนสร้าง:
- 40 ข้อที่รองรับ: ต้องถูก 100% (กฎตายตัว ผิดข้อเดียว = บั๊ก)
- 10 ข้อยาก: ห้ามได้วันเวลาออกมาโดยบอกว่า "มั่นใจ" แม้แต่ข้อเดียว
"""

import json
import unittest
from datetime import datetime
from pathlib import Path

from aipc.skills import when

DATA = json.loads(
    (Path(__file__).parent / "data" / "reminder_sentences.json").read_text(encoding="utf-8")
)
NOW = datetime.fromisoformat(DATA["now"])


class SupportedSentencesTest(unittest.TestCase):
    def test_all_supported_sentences_are_exact(self):
        wrong = []
        for case in DATA["supported"]:
            r = when.parse(case["text"], NOW)
            got = r.at.strftime("%Y-%m-%dT%H:%M") if r.at else None
            if got != case["at"] or not r.confident:
                why = f"confident={r.confident}, {r.problem}"
                wrong.append(f"{case['text']}: ได้ {got} ({why}) ควรได้ {case['at']}")
        self.assertEqual(wrong, [], "\n".join(wrong))

    def test_what_is_extracted(self):
        wrong = []
        for case in DATA["supported"]:
            if case["what"] is None:
                continue
            got = when.parse(case["text"], NOW).what
            if got != case["what"]:
                wrong.append(f"{case['text']}: ได้ “{got}” ควรได้ “{case['what']}”")
        self.assertEqual(wrong, [], "\n".join(wrong))


class HardSentencesTest(unittest.TestCase):
    def test_never_silently_wrong(self):
        silent = []
        for case in DATA["hard"]:
            r = when.parse(case["text"], NOW)
            if r.at is not None and r.confident:
                silent.append(f"{case['text']}: ได้ {r.at} โดยบอกว่ามั่นใจ")
        self.assertEqual(silent, [], "\n".join(silent))

    def test_hard_sentences_explain_why(self):
        for case in DATA["hard"]:
            r = when.parse(case["text"], NOW)
            if r.at is None:
                self.assertTrue(r.problem, case["text"])


class AssumptionsTest(unittest.TestCase):
    """ทุกครั้งที่ตีความเอง ต้องบอกผู้ใช้ (H5)."""

    def test_default_time_is_announced(self):
        r = when.parse("พรุ่งนี้ส่งรายงาน", NOW)
        self.assertTrue(any("ไม่ได้บอกเวลา" in a for a in r.assumptions))

    def test_rollover_to_tomorrow_is_announced(self):
        r = when.parse("เตือนเก้าโมง", NOW)
        self.assertTrue(any("พรุ่งนี้" in a for a in r.assumptions))

    def test_ambiguous_hour_is_announced(self):
        r = when.parse("พรุ่งนี้สามโมง", NOW)
        self.assertTrue(any("15:00" in a for a in r.assumptions))

    def test_exact_sentence_has_no_assumptions(self):
        self.assertEqual(when.parse("พรุ่งนี้ 14:00 ประชุม", NOW).assumptions, [])


class EdgeTest(unittest.TestCase):
    def test_this_weekday_on_same_day_after_time_passed(self):
        # วันพุธ 10:00 พูดว่า "วันพุธนี้ 08:00" — เป็นวันนี้ซึ่งเวลาผ่านไปแล้ว ต้องไม่เงียบ
        r = when.parse("วันพุธนี้ 08:00 ประชุม", NOW)
        self.assertTrue(r.at is None or r.at > NOW or not r.confident or r.assumptions)

    def test_buddhist_year(self):
        self.assertEqual(when.parse("1 มกราคม 2570 ปีใหม่", NOW).at, datetime(2027, 1, 1, 9, 0))

    def test_invalid_times_rejected(self):
        for text in ("บ่ายเก้า", "เจ็ดทุ่ม", "25:00 ประชุม"):
            r = when.parse(text, NOW)
            self.assertFalse(r.at is not None and r.confident, text)


if __name__ == "__main__":
    unittest.main()
