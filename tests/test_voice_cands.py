"""การ์ด 0026: ตัวสร้างตัวเลือกและตัวตัดสินใจ (โค้ดล้วน · คะแนนในเทสต์เป็นค่าสมมติ)."""

import unittest

from aipc.spikes.voice_cands import candidates, decide, looped, meaning


class CandidatesTest(unittest.TestCase):
    def test_fixes_misheard_stem_and_keeps_query(self):
        self.assertIn("ค้นหาราคาทองหน่อย", candidates("คนหาราคาทองหน่อย"))

    def test_fixed_command_from_misheard(self):
        self.assertIn("เข้าลิงก์แรก", candidates("เข้าหลิงแรก"))
        self.assertIn("กลับไปแอป", candidates("กลับไปแอค"))

    def test_only_parseable_and_not_heard(self):
        heard = "ค้นหาแมวแล้วข้าวหลิงแรก"
        got = candidates(heard)
        self.assertNotIn(heard, got)
        self.assertIn("ค้นหาแมวแล้วเข้าลิงก์แรก", got)
        self.assertTrue(all(meaning(c) for c in got))

    def test_keep_limits_count(self):
        self.assertLessEqual(len(candidates("ตอนนี้ขี่โมงแล้ว", keep=2)), 2 * 5)


class DecideTest(unittest.TestCase):
    def test_free_text_command_counts(self):
        d = decide("ย้อนกลับ", -1.0, [("ถอยกลับ", -9.0)], ts=6, tc=12, m=2)
        self.assertEqual((d.what, d.commands), ("do", [{"kind": "back"}]))

    def test_far_from_heard_is_chat(self):
        d = decide("ตอนนี้ขี่โมงแล้ว", -1.3, [("เลื่อนขึ้น", -36.6)], ts=6, tc=12, m=2)
        self.assertEqual(d.what, "chat")

    def test_search_threshold_stricter(self):
        scored = [("ค้นหาขี่โมงแล้ว", -9.0)]
        self.assertEqual(decide("ตอนนี้ขี่โมงแล้ว", -1.0, scored, 6, 12, 2).what, "chat")
        self.assertEqual(decide("ตอนนี้ขี่โมงแล้ว", -1.0, scored, 10, 12, 2).what, "do")

    def test_close_second_meaning_asks(self):
        d = decide("เป๊ก", -7.0, [("ปิดแท็บ", -10.0), ("รีเฟรช", -11.0)], ts=6, tc=12, m=2)
        self.assertEqual((d.what, d.commands), ("ask", [{"kind": "close"}]))

    def test_dropping_spoken_words_not_counted(self):
        heard = "ยอนกลับเมื่อกี้ที่ปรับเสียง"
        self.assertNotIn("ย้อนกลับ", candidates(heard))
        self.assertEqual(decide(heard, -1.7, [("ย้อนกลับ", -13.2)], 6, 14, 2).what, "chat")

    def test_loop_acts_only_when_command_beats_loop(self):
        heard = "กดลิงที่สอง สิ่งสิ่งสิ่งสิ่งสิ่ง"
        d = decide(heard, -23.7, [("กดลิงก์ที่สอง", -8.8), ("กดลิงก์ที่สาม", -21.7)], 6, 14, 2)
        self.assertEqual((d.what, d.commands), ("do", [{"kind": "open", "n": 2}]))

    def test_loop_never_acts(self):
        self.assertTrue(looped("ปิดเสียง ปิดเสียง ปิดเสียง"))
        d = decide("ย้อน ย้อน ย้อน ย้อน", -3.0, [("ย้อนกลับ", -5.0)], ts=6, tc=12, m=2)
        self.assertEqual(d.what, "ask")


if __name__ == "__main__":
    unittest.main()
