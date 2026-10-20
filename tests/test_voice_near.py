"""การ์ด 0045: ได้ยินใกล้เคียงคำสั่ง = ถาม "หมายถึง … ใช่ไหม" (BRIEF 5.6 ข้อ 2) · ใช่ = ทำคำสั่งนั้น."""

import unittest

from aipc.skills.voice_phrases import COMMANDS, near_command

try:
    from aipc.spikes import voice_all_eval
except ImportError:  # pragma: no cover
    voice_all_eval = None


class NearTest(unittest.TestCase):
    def test_close_mishearings_suggest_the_command(self):
        pairs = {"ปีกเสียง": "ปิดเสียง", "เปิดหมดมืด": "เปิดโหมดมืด", "เปิดมวดมืด": "เปิดโหมดมืด",
                 "ทำไมเครื่องชาร์จ": "ทำไมเครื่องช้า"}  # fmt: skip
        for heard, want in pairs.items():
            with self.subTest(heard=heard):
                self.assertEqual(near_command(heard), want)

    def test_everyday_sentences_do_not(self):
        for text in ("สวัสดีครับ", "วันนี้อากาศดีจัง", "ฉันหิวข้าว", "ขอบคุณมาก", "หน้าจอมืดไปหน่อย",
                     "เปิดใจคุยกัน", "ปิดประตูหน่อย", "เสียงดังจัง", "ก็"):  # fmt: skip
            with self.subTest(text=text):
                self.assertEqual(near_command(text), "")


@unittest.skipIf(voice_all_eval is None, "ไม่มี PySide6")
class FlowTest(unittest.TestCase):
    def test_every_phrase_is_a_real_command_and_yes_runs_it(self):
        _engine, skills = voice_all_eval.backend()
        for phrase in COMMANDS:  # ทุกประโยคในรายการต้องเป็นคำสั่งที่ตัวแปลรู้จัก
            with self.subTest(phrase=phrase):
                label = voice_all_eval.label(phrase, skills)
                self.assertNotIn(label, ("ask", "none"))
                self.assertFalse(label.startswith("near"))
        card = skills.voiceConfirm("ปีกเสียง")
        self.assertEqual(card["suggest"], "ปิดเสียง")
        done = skills.confirm(card["confirmToken"], True)
        self.assertEqual(done["redo"], "ปิดเสียง")
        card = skills.voiceConfirm("ปีกเสียง")
        self.assertNotIn("redo", skills.confirm(card["confirmToken"], False))  # ไม่ = ไม่ทำอะไร


if __name__ == "__main__":
    unittest.main()
