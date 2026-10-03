"""ทำไมได้คำตอบนี้ (ข้อเสนอ 2026-10-03) · การ์ดจากสกิล · ตัวสั่งงาน/อากาศปลอม.

ส่วนคำตอบของ AI ในเครื่อง/Claude อยู่ใน tests/test_chat.py (ต้องมี llama ปลอม)
"""

import tempfile
import unittest
from pathlib import Path

from aipc.skills.weather import Weather
from tests.test_weather import FC, GEO

try:
    from aipc.skills import actions
    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None


def rows(card):
    return {r["k"]: r["v"] for r in card.get("why", [])}


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class WhyTest(unittest.TestCase):
    def setUp(self):
        self.t, self.sent = 1000.0, []
        weather = Weather(get=lambda url, params, timeout=10: GEO if "geocoding" in url else FC,
                          record=self.sent.append, now=lambda: self.t)  # fmt: skip
        ex = actions.Executor(runner=lambda a: 0, reader=lambda a: "Volume: 0.40", dry_run=False)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.s = SkillsController(executor=ex, reminders_path=Path(tmp.name) / "r.json",
                                  run_timer=False, weather=weather)  # fmt: skip

    def test_command_card_says_who_why_and_nothing_left(self):
        r = rows(self.s.handle("เปิดยูทูบ"))
        self.assertIn("สกิล", r["ใครตอบ"])
        self.assertTrue(r["ทำไมทางนี้"])
        self.assertEqual(r["ข้อมูลออกนอกเครื่อง"], "ไม่มี · ทำในเครื่องทั้งหมด")
        self.assertIn("วินาที", r["ใช้เวลา"])

    def test_weather_lists_exactly_what_was_sent_and_cache_sends_nothing(self):
        r = rows(self.s.handle("พรุ่งนี้เชียงใหม่ฝนตกไหม"))
        self.assertIn("Open-Meteo", r["ใครตอบ"])
        self.assertEqual(r["ข้อมูลออกนอกเครื่อง"],
                         "ส่งไป Open-Meteo: " + " · ".join(self.sent))  # fmt: skip
        self.assertEqual(len(self.sent), 2)
        again = rows(self.s.handle("วันนี้เชียงใหม่ร้อนไหม"))
        self.assertIn("ไม่มี", again["ข้อมูลออกนอกเครื่อง"])  # ใช้ผลที่จำไว้ ไม่ได้ส่งซ้ำ
        self.assertEqual(len(self.sent), 2)
        self.assertNotIn("_outbound", self.s.handle("อากาศวันนี้เป็นยังไง"))  # ถามชื่อเมือง ไม่มีคีย์ภายในหลุด

    def test_confirm_and_undo_cards_explain_too(self):
        card = self.s.handle("เสียง 70%")
        self.assertIn("ใครตอบ", rows(self.s.undo(card["undoToken"])))
        token = self.s.handle("เตือนส่งงานพรุ่งนี้บ่ายสอง")["confirmToken"]
        self.assertIn("ใครตอบ", rows(self.s.confirm(token, True)))

    def test_card_handed_to_ai_has_no_why_yet(self):
        s = SkillsController(run_timer=False, llm_ready=lambda: True)
        card = s.handle("เล่าเรื่องตลกหน่อย")
        self.assertTrue(card.get("llm"))
        self.assertNotIn("why", card)  # AI ตอบเสร็จแล้ว ChatController เป็นคนอธิบาย


if __name__ == "__main__":
    unittest.main()
