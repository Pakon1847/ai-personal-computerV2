"""การ์ด 0044: ลองฟังอังกฤษเฉพาะที่ควร · คำสั่งครบแล้วจบเร็ว · แก้ข้อความจาก Zipformer."""

import unittest

from aipc.voice.zipformer import tidy

try:
    from aipc.ui import backend
except ImportError:  # pragma: no cover
    backend = None


class TidyTest(unittest.TestCase):
    def test_thai_digits_and_fillers(self):
        self.assertEqual(tidy("เตือนกินยา๒ทุ่ม"), "เตือนกินยา2ทุ่ม")
        self.assertEqual(tidy("ก็เพิ่มเสียง"), "เพิ่มเสียง")
        self.assertEqual(tidy("เอ่อ เปิดยูทูบ"), "เปิดยูทูบ")
        self.assertEqual(tidy("ก็อปปี้ไฟล์"), "ก็อปปี้ไฟล์")  # "ก็" ไม่ได้นำหน้าคำสั่ง = ไม่แตะ
        self.assertEqual(tidy("ก็ดีนะ"), "ก็ดีนะ")


@unittest.skipIf(backend is None, "ไม่มี PySide6")
class EnglishGateTest(unittest.TestCase):
    def test_try_english_only_for_short_unknown_non_questions(self):
        self.assertTrue(backend._thai_missed("โทรแบ็ค"))  # อังกฤษที่ถอดเป็นไทยเพี้ยน
        self.assertFalse(backend._thai_missed("เปิดยูทูบ"))  # คำสั่งที่รู้จัก
        self.assertFalse(backend._thai_missed("ตอนนี้กี่โมง"))  # คำถามไทย
        self.assertFalse(backend._thai_missed("ช่วยคิดเมนูอาหารเย็นให้หน่อย"))  # ยาว = ไทยแน่
        self.assertFalse(backend._thai_missed("เปิดโหมดมืด"))  # ค่าตั้งของแอป
        reminder = lambda t: "reminder" if t.startswith("เตือน") else ""  # noqa: E731
        self.assertFalse(backend._thai_missed("เตือนกินยา", intent=reminder))

    def test_complete_commands(self):
        self.assertTrue(backend._command_complete("เปิดยูทูบ"))
        self.assertTrue(backend._command_complete("ปิดเสียง"))
        self.assertTrue(backend._command_complete("เปิดโหมดมืด"))
        self.assertFalse(backend._command_complete("อากาศพรุ่งนี้เป็นยังไง"))
        reminder = lambda t: "reminder" if t.startswith("เตือน") else ""  # noqa: E731
        self.assertFalse(backend._command_complete("เตือนประชุม", intent=reminder))  # อาจพูดต่อ


if __name__ == "__main__":
    unittest.main()
