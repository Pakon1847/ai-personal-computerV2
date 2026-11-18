"""ตัววัดวงจรเรียนรู้สกิล (การ์ด 0083) · ไม่ต่อ AI/Claude จริง."""

import unittest
from pathlib import Path

from aipc.spikes import skill_loop_eval as ev

DATA = Path(__file__).resolve().parent / "data"


class ParseTest(unittest.TestCase):
    def test_parses_blocks_and_skips_comments(self):
        text = ("# คำอธิบาย\n\nข้อ 1\nคำสั่ง: ทำ ก\nผลที่ถูก: ได้ ก\n\n"
                "# อีกบรรทัด\nข้อ 2\nคำสั่ง: ทำ ข\nผลที่ถูก: ได้ ข\n")  # fmt: skip
        self.assertEqual(ev.parse_items(text), [
            {"id": "1", "text": "ทำ ก", "expect": "ได้ ก"},
            {"id": "2", "text": "ทำ ข", "expect": "ได้ ข"},
        ])  # fmt: skip

    def test_empty_command_names_the_item(self):
        text = "ข้อ 1\nคำสั่ง: ทำ ก\nผลที่ถูก: ได้ ก\n\nข้อ 2\nคำสั่ง:\nผลที่ถูก: ได้ ข\n"
        with self.assertRaises(ValueError) as e:
            ev.parse_items(text)
        self.assertIn("ข้อ 2", str(e.exception))

    def test_partly_filled_file_names_the_empty_item(self):
        text = "ข้อ 1\nคำสั่ง: ทำ ก\nผลที่ถูก: ได้ ก\n\nข้อ 2\nคำสั่ง:\nผลที่ถูก:\n"
        with self.assertRaises(ValueError) as e:
            ev.parse_items(text)
        self.assertIn("ข้อ 2", str(e.exception))

    def test_unfilled_template_refuses(self):
        # รูปเดียวกับ skill_loop_test1.txt ตอนยังว่าง · ไม่เปิดไฟล์จริง (ชุดทดสอบของ Pakon · H9)
        text = "# วิธีกรอก\n\n" + "".join(f"ข้อ {n}\nคำสั่ง:\nผลที่ถูก:\n\n" for n in range(1, 21))
        with self.assertRaises(ValueError) as e:
            ev.parse_items(text)
        self.assertIn("ยังไม่ได้กรอก", str(e.exception))

    def test_dev_set_has_ten_items(self):
        items = ev.parse_items((DATA / "skill_loop_dev.txt").read_text(encoding="utf-8"))
        self.assertEqual(len(items), 10)
        self.assertTrue(all(i["text"] and i["expect"] for i in items))


if __name__ == "__main__":
    unittest.main()
