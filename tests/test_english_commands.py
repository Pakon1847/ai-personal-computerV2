"""การ์ด 0039 ระยะ C: คำสั่งภาษาอังกฤษ → รูปไทยที่ตัวแปลเดิมเข้าใจ · ตัวอย่างชุดพัฒนา (ไม่ใช่ชุดวัด C1)."""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from aipc.skills import english

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None


class ToThaiTest(unittest.TestCase):
    def check(self, cases):
        for text, want in cases:
            with self.subTest(text=text):
                self.assertEqual(english.to_thai(text), want)

    def test_open_and_volume(self):
        self.check([
            ("Open YouTube", "เปิดยูทูบ"),
            ("Hey, open YouTube please", "เปิดยูทูบ"),
            ("go to my files", "เปิดหน้าไฟล์ของฉัน"),
            ("open the settings page", "เปิดหน้าตั้งค่า"),
            ("launch the terminal", "เปิดเทอร์มินัล"),
            ("mute", "ปิดเสียง"),
            ("turn the sound back on", "เปิดเสียง"),
            ("turn up the volume a bit", "เพิ่มเสียง"),
            ("lower the volume", "ลดเสียง"),
            ("set volume to 40%", "ปรับเสียงเป็น 40"),
        ])  # fmt: skip

    def test_questions(self):
        self.check([
            ("What time is it?", "ตอนนี้กี่โมง"),
            ("What do I have tomorrow?", "พรุ่งนี้มีนัดอะไร"),
            ("tomorrow's schedule", "พรุ่งนี้มีนัดอะไร"),
            ("any appointments next week", "สัปดาห์หน้ามีนัดอะไร"),
            ("am I busy on Friday", "วันศุกร์นี้มีนัดอะไร"),
            ("what's my next appointment", "นัดถัดไปคืออะไร"),
            ("show files I edited yesterday", "ไฟล์ที่แก้เมื่อวาน"),
        ])  # fmt: skip

    def test_reminders_keep_user_words(self):
        self.check([
            ("Remind me to call Mom tomorrow at 2 PM", "เตือน call Mom พรุ่งนี้ 14:00"),
            ("remind me at 7:30 am every weekday to take medicine",
             "เตือน take medicine วันธรรมดา 07:30"),
            ("remind me in 10 minutes to stretch", "เตือน stretch อีก 10 นาที"),
            ("remind me tonight at 9 to lock the door", "เตือน lock the door คืนนี้ 21:00"),
            ("set a reminder for October 25 at 3:30pm to see the dentist",
             "เตือน see the dentist 25 ตุลาคม 15:30"),
            ("remind me to water the plants every Monday at 8am",
             "เตือน water the plants ทุกวันจันทร์ 08:00"),
            ("remind me to stretch at 3:30", "เตือน stretch 15:30"),  # กติกาเดียวกับ "3 โมง"
            ("remind me to pay rent next Friday at noon", "เตือน pay rent วันศุกร์หน้า 12:00"),
            ("remind me to buy milk", "เตือน buy milk"),  # ไม่บอกเวลา = การ์ดขอให้ระบุเวลา
            ("cancel the meeting with Tom", "ยกเลิกนัด Tom"),
            ("cancel my dentist appointment", "ยกเลิกนัด dentist"),
            ("delete all my reminders", "ยกเลิกนัดทั้งหมด"),
        ])  # fmt: skip

    def test_not_commands(self):
        for text in (
            "I want to open a coffee shop",
            "remind me why the sky is blue",
            "What do I have to do to get a visa?",
            "How do I open a bank account?",
            "what time is the world cup final",
            "Why is the sky blue?",
            "remind me to",
        ):
            with self.subTest(text=text):
                self.assertIsNone(english.to_thai(text))

    def test_thai_is_never_converted(self):
        for text in ("เปิดยูทูบ", "เตือนประชุมพรุ่งนี้ 14:00", "open ยูทูบ", "พรุ่งนี้มี meeting ไหม"):
            with self.subTest(text=text):
                self.assertIsNone(english.to_thai(text))

    def test_when(self):
        self.assertEqual(english.when_th("at 2 pm tomorrow"), "พรุ่งนี้ 14:00")
        self.assertEqual(english.when_th("in half an hour"), "อีก 30 นาที")
        self.assertEqual(english.when_th("on the 5th of November at 9am"), "5 พฤศจิกายน 09:00")
        self.assertIsNone(english.when_th("at 25:00"))
        self.assertIsNone(english.when_th("sometime soon"))


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class ControllerTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        now = datetime(2026, 10, 21, 10, 0).astimezone()
        self.s = SkillsController(reminders_path=Path(tmp.name) / "r.json", clock=lambda: now,
                                  run_timer=False)  # fmt: skip

    def test_english_command_uses_thai_parsers_and_says_so(self):
        card = self.s.handle("Remind me to call Mom tomorrow at 2 pm")
        self.assertEqual(card["title"], "บันทึกนัด “call Mom” ใช่ไหม")
        self.assertTrue(card["confirmToken"])  # ยืนยันก่อนบันทึกเหมือนพิมพ์ไทย
        self.assertEqual(card["why"][1], {"k": "แปลงคำสั่งอังกฤษ", "v": "เตือน call Mom พรุ่งนี้ 14:00"})
        self.assertEqual(self.s.handle("what time is it")["kind"], "clock")

    def test_unconverted_english_goes_unchanged(self):
        card = self.s.handle("Why is the sky blue?")
        self.assertNotIn("แปลงคำสั่งอังกฤษ", [r["k"] for r in card.get("why", [])])


if __name__ == "__main__":
    unittest.main()
