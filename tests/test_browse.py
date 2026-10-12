"""ตัวแปลคำสั่งเว็บด้วยเสียง (การ์ด 0024)."""

import json
import unittest
from pathlib import Path

from aipc.skills import browse

DATA = Path(__file__).parent / "data"


def parsed(text):
    return [c.as_dict() for c in browse.parse(text)]


class BrowseParseTest(unittest.TestCase):
    def test_pakon_example(self):
        # ตัวอย่างของ Pakon 2026-10-13: "ค้นหาราคาทองหน่อยเข้าลิ้งค์แรก" · "ย้อนกลับ"
        want = [{"kind": "search", "query": "ราคาทอง"}, {"kind": "open", "n": 1}]
        self.assertEqual(parsed("ค้นหาราคาทองหน่อยเข้าลิ้งค์แรก"), want)
        self.assertEqual(parsed("ย้อนกลับ"), [{"kind": "back"}])

    def test_numbers_and_spellings(self):
        for text, n in [("เข้าลิงก์ที่สอง", 2), ("เปิดลิงค์ที่ 3", 3), ("คลิกอันที่สี่", 4),
                        ("เข้าลิ้งแรก", 1), ("เปิดเว็บที่สิบ", 10)]:  # fmt: skip
            self.assertEqual(parsed(text), [{"kind": "open", "n": n}], text)

    def test_whisper_style_text(self):
        # whisper ถอดมามีวรรคตอน/คำลงท้าย/ตัวพิมพ์ใหญ่
        self.assertEqual(
            parsed("ค้นหา Raspberry Pi 5 ครับ."), [{"kind": "search", "query": "raspberry pi 5"}]
        )
        self.assertEqual(parsed(" เลื่อนลงหน่อยค่ะ "), [{"kind": "scroll", "direction": "down"}])

    def test_local_work_is_not_web(self):
        # หาไฟล์/โน้ตในเครื่อง · เลื่อนนัด · ย้อนงานเดิม · ต้นคำ "หา" อื่น ๆ = ไปทางเดิมของแอป
        for text in ["ค้นหาไฟล์รายงาน", "หาโน้ตที่จดไว้วันนี้ให้หน่อย", "หาใบเสร็จค่าซ่อมรถ",
                     "เลื่อนนัดประชุมไปพรุ่งนี้", "ย้อนกลับเมื่อกี้ที่ปรับเสียง", "หากต้องการสอบถาม",
                     "หาดใหญ่", "หาค่าเฉลี่ยของ 4 6 8", "กูเกิลก่อตั้งปีไหน", "ปิดเสียง", ""]:  # fmt: skip
            self.assertEqual(parsed(text), [], text)

    def test_v1_dev_set(self):
        items = json.loads((DATA / "browse_v1.json").read_text(encoding="utf-8"))["items"]
        wrong = [it["text"] for it in items if parsed(it["text"]) != it["expect"]]
        # 1 ข้อที่ยอมพลาด: "กูเกิลวิธีทำไข่เจียว" (กูเกิล + คำค้นตรง ๆ ชนกับ "กูเกิลก่อตั้งปีไหน" ในชุดเดิม)
        self.assertEqual(wrong, ["กูเกิลวิธีทำไข่เจียว"])

    def test_v2_non_commands_never_caught(self):
        items = json.loads((DATA / "browse_v2.json").read_text(encoding="utf-8"))["items"]
        caught = [it["text"] for it in items if not it["expect"] and parsed(it["text"])]
        self.assertEqual(caught, [])


if __name__ == "__main__":
    unittest.main()
