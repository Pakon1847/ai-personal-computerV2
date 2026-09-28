"""เส้นทางจริงของผู้ใช้: ข้อความ → ตัวคัดสกิล → สกิลที่หน้าจอใช้ (router.route ตัวเดียวกับ SkillsController).

พบ 2026-09-28: ชุดประโยคนัดหมาย 40 ข้อผ่านตัวแปลงวันเวลาครบ 40/40 แต่พอป้อนผ่านตัวคัดสกิล
ถึงสกิลนัดหมายแค่ 13 ข้อ (ไปแชท 22 · ไปสกิลถามเครื่อง 5 เพราะคำว่า "ช้า" อยู่ในคำว่า "เช้า")
และคำว่า "เสียง" ที่อยู่ในประโยคนัดหรือประโยคปฏิเสธถูกสั่งทันที · เทสต์นี้ล็อกเส้นทางที่ผู้ใช้เจอจริง
"""

import json
import unittest
from pathlib import Path

from aipc.skills import command, manifest, router

DATA = json.loads(
    (Path(__file__).parent / "data" / "reminder_sentences.json").read_text(encoding="utf-8")
)


def route(text):
    return router.route(text, manifest.load_builtin(), set())


def skill_of(text):
    r = route(text)
    return r.kind if r.kind in ("command", "chat") else r.skill.id


class ReminderSentencesReachReminderSkillTest(unittest.TestCase):
    def test_every_supported_sentence_reaches_the_reminder_skill(self):
        wrong = [f"{c['text']} → {skill_of(c['text'])}" for c in DATA["supported"]
                 if skill_of(c["text"]) != "reminder"]  # fmt: skip
        self.assertEqual(wrong, [], "\n".join(wrong))

    def test_morning_is_not_slow(self):
        # "เช้า" มี "ช้า" อยู่ข้างใน แต่เป็นคนละคำ (สระเอนำหน้า = อยู่พยางค์เดียวกัน)
        self.assertEqual(skill_of("เตือนประชุมพรุ่งนี้ตอนเช้า"), "reminder")

    def test_washing_machine_reminder_is_a_reminder(self):
        self.assertEqual(skill_of("อีก 2 ชั่วโมงเตือนเอาผ้าออกจากเครื่อง"), "reminder")


class MachineQuestionsStillWorkTest(unittest.TestCase):
    def test_machine_questions(self):
        for text in ("ทำไมเครื่องช้า", "เครื่องร้อนไปไหม", "พื้นที่เหลือเท่าไร", "ทำไมเครื่องช้าตอนเช้า"):
            with self.subTest(text=text):
                self.assertEqual(skill_of(text), "machine-status")

    def test_hotel_is_not_ram(self):
        # "โรงแรม" มีคำว่า "แรม" อยู่ข้างใน
        self.assertNotEqual(skill_of("โรงแรมที่ไปพักพรุ่งนี้ชื่ออะไร"), "machine-status")

    def test_questions_about_time_are_not_reminders(self):
        for text in ("พรุ่งนี้วันอะไร", "พรุ่งนี้ประชุมกี่โมง"):
            with self.subTest(text=text):
                self.assertNotEqual(skill_of(text), "reminder")


class VolumeWordsInsideOtherSentencesTest(unittest.TestCase):
    """คำสั่งเสียงลำโพงต้องไม่ถูกทำทันที เมื่อประโยคเป็นนัดหมาย ปฏิเสธ หรือพูดถึงเรื่องอื่น."""

    def test_reminders_about_volume_are_reminders(self):
        for text in ("อีก 10 นาทีเตือนให้ลดเสียง", "สองทุ่มเตือนเปิดเสียง",
                     "พรุ่งนี้บ่ายสามเตือนปิดเสียงก่อนประชุม"):  # fmt: skip
            with self.subTest(text=text):
                self.assertIsNone(command.parse(text))
                self.assertEqual(skill_of(text), "reminder")

    def test_negation_is_not_a_command(self):
        for text in ("อย่าปิดเสียงนะ", "ไม่ต้องเปิดเสียง", "ห้ามปิดเสียง"):
            with self.subTest(text=text):
                self.assertIsNone(command.parse(text))

    def test_recording_is_not_volume(self):
        self.assertIsNone(command.parse("อัดเสียง 10 นาที"))

    def test_real_volume_commands_still_work(self):
        cases = {
            "ปิดเสียง": ("mute", {}),
            "ช่วยเปิดเสียงหน่อยครับ": ("unmute", {}),
            "เสียง 30": ("set_volume", {"percent": 30}),
            "ปรับเสียงเป็น 50": ("set_volume", {"percent": 50}),
            "ลดเสียงหน่อย": ("change_volume", {"step": -10}),
            "เสียงดังไป": ("change_volume", {"step": -10}),
        }
        for text, (action, params) in cases.items():
            with self.subTest(text=text):
                cmd = command.parse(text)
                self.assertIsNotNone(cmd)
                self.assertEqual((cmd.plan.action, cmd.plan.params), (action, params))


if __name__ == "__main__":
    unittest.main()
