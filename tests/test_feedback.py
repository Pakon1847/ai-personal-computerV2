"""ตัวจำรอบคำตอบสำหรับปุ่มชอบ/ไม่ชอบ (การ์ด 0085) · ไม่ใช้ Qt ไม่ต่อเน็ต."""

import unittest

from aipc.skills import feedback
from aipc.skills.feedback import Turn, TurnLog


def turn(i=0, answer="ผล", route="chat"):
    return Turn(request=f"คำสั่ง {i}", answer=answer, route=route)


class TurnLogTest(unittest.TestCase):
    def test_ids_unique_and_oldest_dropped(self):
        log = TurnLog()
        ids = [log.add(turn(i)) for i in range(feedback.KEEP + 1)]
        self.assertEqual(len(set(ids)), feedback.KEEP + 1)
        self.assertIsNone(log.get(ids[0]), "เกิน KEEP รอบ = ทิ้งรอบเก่าสุด")
        self.assertEqual(log.get(ids[-1]).request, f"คำสั่ง {feedback.KEEP}")

    def test_take_only_once(self):
        log = TurnLog()
        tid = log.add(turn())
        self.assertIsNotNone(log.take(tid))
        self.assertIsNone(log.take(tid), "1 รอบตอบ = ตรวจได้ครั้งเดียว")
        self.assertIsNone(log.get(tid))
        self.assertIsNone(log.take("ไม่มี"))

    def test_note_and_pop_skill(self):
        log = TurnLog()
        log.note_skill("แปลว่า hello", "translate")
        self.assertEqual(log.pop_skill("แปลว่า hello"), "translate")
        self.assertEqual(log.pop_skill("แปลว่า hello"), "", "ใช้แล้วหาย")


class ReviewTextTest(unittest.TestCase):
    def test_review_text_cuts_answer_and_frames_it(self):
        t = turn(answer="ฮ" * 3000, route="skill:reminder")  # ฮ ไม่มีในป้ายของระบบ
        text = feedback.review_text(t)
        self.assertEqual(text.count("ฮ"), feedback.MAX_ANSWER)
        self.assertIn("…", text)
        self.assertIn("skill:reminder", text)
        self.assertIn("ไม่ใช่คำสั่ง", text)
        self.assertIn("<<<", text)
        self.assertIn(">>>", text)

    def test_review_text_has_only_turn_fields(self):
        t = Turn(request="เปิดโหมดอ่านหนังสือ", answer="เปิด YouTube แล้ว", route="rule:command",
                 skill_id="", private=False)  # fmt: skip
        text = feedback.review_text(t)
        for piece in ("เปิดโหมดอ่านหนังสือ", "เปิด YouTube แล้ว", "rule:command"):
            self.assertIn(piece, text)
        # ป้ายของระบบ + ช่องของ Turn เท่านั้น
        rest = text
        for piece in ("เปิดโหมดอ่านหนังสือ", "เปิด YouTube แล้ว", "rule:command"):
            rest = rest.replace(piece, "")
        for label in feedback.LABELS:
            rest = rest.replace(label, "")
        self.assertEqual(rest.replace("<<<", "").replace(">>>", "").split(), [])

    def test_card_text(self):
        card = {"title": "ตั้งเสียง 90%", "lines": ["บรรทัด 1"],
                "chips": [{"text": "ทำแล้ว", "kind": "ok"}]}  # fmt: skip
        self.assertEqual(feedback.card_text(card), "ตั้งเสียง 90%\nบรรทัด 1\nทำแล้ว")


if __name__ == "__main__":
    unittest.main()
