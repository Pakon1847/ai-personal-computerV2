"""ตัวแยกคำขอหาไฟล์ (aipc.skills.fileintent) · ชุดอิสระ: docs/benchmarks/2026-10-01-file-intent."""

import json
import unittest
from pathlib import Path

from aipc.skills.fileintent import file_intent

DATA = Path(__file__).parent / "data"


class FileIntentTest(unittest.TestCase):
    def test_find_requests(self):
        for t in ("หาไฟล์ใบเสร็จซ่อมแอร์ให้หน่อย", "สัญญาเช่าห้องอยู่ไหน", "ที่จดสูตรแกงไว้ไฟล์ไหน",
                  "มีโน้ตที่จดเรื่องรหัสวายฟายไหม", "ขอดูเอกสารที่จดเรื่องประกันหน่อย"):  # fmt: skip
            with self.subTest(t=t):
                self.assertTrue(file_intent(t))

    def test_look_alikes(self):
        for t in ("แปลงไฟล์ Word เป็น PDF ยังไง", "ไฟล์ zip คืออะไร", "สัญญาณเน็ตอยู่ไหนในห้อง",
                  "บันทึกนัดหมอพรุ่งนี้บ่ายสอง", "เปิดไฟล์รายงานให้หน่อย", "หาร้านซ่อมแอร์ใกล้ฉัน",
                  "บันทึกไว้ว่าพรุ่งนี้ต้องซื้อนม", "ช่วยลบไฟล์ขยะให้หน่อย"):  # fmt: skip
            with self.subTest(t=t):
                self.assertFalse(file_intent(t))

    def test_dev_set(self):
        # ชุดพัฒนา (ผู้ช่วยเห็นแล้ว) · ตอน commit กฎ: find 40/40 · other ผิด 0/43
        items = json.loads((DATA / "file_intent_dev.json").read_text("utf-8"))["items"]
        wrong = [i["text"] for i in items if file_intent(i["text"]) != (i["expect"] == "find")]
        self.assertLessEqual(len(wrong), 1, wrong)


if __name__ == "__main__":
    unittest.main()
