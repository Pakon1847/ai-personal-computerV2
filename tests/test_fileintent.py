"""ตัวแยกคำขอหาไฟล์ (aipc.skills.fileintent) · ชุดอิสระ: docs/benchmarks/2026-10-01-file-intent."""

import json
import unittest
from datetime import datetime
from pathlib import Path

from aipc.skills.fileintent import file_intent, file_time, time_range, topic

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

    def test_file_time_labels(self):
        cases = {"ขอดูไฟล์ที่แก้เมื่อวานหน่อย": "yesterday", "โน้ตที่เขียนสัปดาห์นี้": "this_week",
                 "หาเอกสารที่ทำอาทิตย์ที่แล้ว": "last_week", "ไฟล์ล่าสุดที่ฉันแก้": "latest",
                 "บันทึกนัดหมอเมื่อวานว่าอะไรนะ": None, "ไฟล์ล่าสุดของ Windows อัปเดตคืออะไร": None,
                 "ตั้งเตือนพรุ่งนี้เช้าให้ส่งเอกสาร": None}  # fmt: skip
        for t, want in cases.items():
            with self.subTest(t=t):
                self.assertEqual(file_time(t), want)

    def test_topic_drops_want_word(self):
        # พบ 2026-10-12: "อยากดูไฟล์ที่ทำสัปดาห์นี้ทั้งหมด" ได้หัวข้อ "อยาก" → กรองจนไม่พบไฟล์
        self.assertEqual(topic("อยากดูไฟล์ที่ทำสัปดาห์นี้ทั้งหมด"), "")
        self.assertEqual(topic("อยากดูไฟล์รายงานที่แก้เมื่อวาน"), "รายงาน")

    def test_time_range(self):
        now = datetime(2026, 10, 1, 15, 0)  # วันพฤหัส
        self.assertEqual(
            time_range("yesterday", now), (datetime(2026, 9, 30), datetime(2026, 10, 1))
        )
        self.assertEqual(time_range("this_week", now)[0], datetime(2026, 9, 28))  # จันทร์
        self.assertEqual(
            time_range("last_month", now), (datetime(2026, 9, 1), datetime(2026, 10, 1))
        )
        self.assertEqual(time_range("latest", now), (None, None))


if __name__ == "__main__":
    unittest.main()
