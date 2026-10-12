"""ตัวแปลงเวลาไทย (การ์ดออกแบบ 0001) · ชุดประโยค 50 ข้อใน tests/data/reminder_sentences.json.

ชุดนี้คือชุดเดียวกับที่ใช้รายงานในบทที่ 4 · เกณฑ์ประกาศไว้ก่อนสร้าง:
- 40 ข้อที่รองรับ: ต้องถูก 100% (กฎตายตัว ผิดข้อเดียว = บั๊ก)
- 10 ข้อยาก: ห้ามได้วันเวลาออกมาโดยบอกว่า "มั่นใจ" แม้แต่ข้อเดียว
"""

import json
import unittest
from datetime import datetime, timedelta
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


class FoundOn20260928Test(unittest.TestCase):
    """บั๊กที่ตรวจเจอ 2026-09-28 (วินโดวส์) · ทุกข้อเคย "มั่นใจแต่ผิด" หรือทำโปรแกรมพัง."""

    def test_two_digit_year_is_buddhist_era(self):
        # เคยได้ปี 2069 · คนไทยเขียนปีย่อเป็น พ.ศ. (69 = 2569 = ค.ศ. 2026)
        r = when.parse("นัดหมอ 25/12/69 บ่ายสาม", NOW)
        self.assertEqual(r.at, datetime(2026, 12, 25, 15, 0))
        self.assertTrue(any("พ.ศ." in n for n in r.assumptions), "ต้องบอกว่าตีความปีเอง")

    def test_hours_and_minutes_together(self):
        # เคยบวกแค่ 1 ชั่วโมง แล้วเอา "30 นาที" ไปปนในชื่อนัด
        r = when.parse("อีก 1 ชั่วโมง 30 นาที เตือนกินยา", NOW)
        self.assertEqual(r.at, datetime(2026, 9, 23, 11, 30))
        self.assertEqual(r.what, "กินยา")

    def test_hours_and_a_half(self):
        r = when.parse("อีกสองชั่วโมงครึ่งเตือนปิดเตา", NOW)
        self.assertEqual(r.at, datetime(2026, 9, 23, 12, 30))
        self.assertEqual(r.what, "ปิดเตา")

    def test_leap_day_after_it_passed_does_not_crash(self):
        # เคยโยน ValueError ออกไปถึงหน้าจอ (ปีถัดไปไม่มีวันที่ 29 ก.พ.)
        after_leap_day = datetime(2028, 3, 1, 10, 0)
        for text in ("เตือนจ่ายค่าเช่า 29 ก.พ.", "29/2 จ่ายค่าเช่า"):
            with self.subTest(text=text):
                r = when.parse(text, after_leap_day)
                self.assertFalse(r.confident)
                self.assertTrue(r.problem)

    def test_money_is_not_a_time(self):
        # "1.50 บาท" เคยกลายเป็นเวลา 01:50
        r = when.parse("พรุ่งนี้โอนค่าน้ำ 1.50 บาท", NOW)
        self.assertEqual(r.at, datetime(2026, 9, 24, 9, 0))
        self.assertIn("1.50 บาท", r.what)

    def test_midnight_is_announced(self):
        r = when.parse("พรุ่งนี้เที่ยงคืนส่งงาน", NOW)
        self.assertEqual(r.at, datetime(2026, 9, 24, 0, 0))
        self.assertTrue(any("เที่ยงคืน" in n for n in r.assumptions), "ต้องบอกว่าเที่ยงคืนคือตอนไหน")

    def test_tomorrow_said_after_midnight_is_announced(self):
        just_after_midnight = datetime(2026, 9, 24, 0, 30)
        r = when.parse("พรุ่งนี้ 9 โมงประชุม", just_after_midnight)
        self.assertEqual(r.at, datetime(2026, 9, 25, 9, 0))
        self.assertTrue(any("เที่ยงคืน" in n for n in r.assumptions), "ต้องบอกว่า “พรุ่งนี้” คือวันไหน")

    def test_title_drops_leftover_part_of_day_words(self):
        # สำรวจบน Pi 5 2026-10-12: "พรุ่งนี้เช้า 9 โมงมีประชุม" ได้ชื่อนัด "เช้า มีประชุม"
        cases = {
            "พรุ่งนี้เช้า 9 โมงมีประชุม": "มีประชุม",
            "เย็นนี้ 6 โมงรดน้ำต้นไม้": "รดน้ำต้นไม้",
            "เตือนกินข้าวเย็นตอน 6 โมงเย็น": "กินข้าวเย็น",
            "คืนนี้ 4 ทุ่มโทรหาแม่": "โทรหาแม่",
            "จดไว้ว่าพรุ่งนี้ต้องซื้อนม": "ต้องซื้อนม",
        }
        for text, what in cases.items():
            self.assertEqual(when.parse(text, NOW).what, what, text)

    def test_monthly_is_not_turned_into_daily(self):
        # สำรวจบน Pi 5 2026-10-12: "เตือนจ่ายค่าไฟทุกวันที่ 5" เคยได้ "ทุกวัน 09:00" (จะเตือนทุกวัน)
        for text in ("เตือนจ่ายค่าไฟทุกวันที่ 5", "ทุกวันที่ห้าเตือนจ่ายค่าเน็ต", "เตือนจ่ายค่าห้องทุกสิ้นเดือน"):
            r = when.parse(text, NOW)
            self.assertIsNone(r.at, text)
            self.assertIn("รองรับนัดซ้ำแค่", r.problem)
        self.assertEqual(when.parse("ทุกวันเตือนกินยา 8 โมงเช้า", NOW).at.hour, 8)

    def test_chat_abbreviation_for_tomorrow(self):
        # สำรวจบน Pi 5 2026-10-12: "พน 10 โมงนัดหมอ" ได้ชื่อนัด "พน นัดหมอ"
        r = when.parse("พน 10 โมงนัดหมอ", NOW)
        self.assertEqual(
            (r.at.date(), r.at.hour, r.what), ((NOW + timedelta(days=1)).date(), 10, "นัดหมอ")
        )
        self.assertEqual(when.parse("เตือนประชุมพนักงาน 10 โมง", NOW).what, "ประชุมพนักงาน")


if __name__ == "__main__":
    unittest.main()
