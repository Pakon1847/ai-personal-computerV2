"""กฎคำขอแปล/สรุปก่อนถึง AI (Pakon เลือกข้อ ก. 2026-10-01).

ชุดอิสระวัดแยกใน docs/benchmarks/2026-10-01-lang-rule
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from aipc.skills import manifest, router
from aipc.skills.langintent import lang_intent
from aipc.spikes.lang_rule_eval import evaluate

DATA = Path(__file__).parent / "data"


class LangIntentTest(unittest.TestCase):
    def test_clear_requests(self):
        cases = {
            "แปลเป็นภาษาอังกฤษ: ขอบคุณที่มาร่วมงาน": "translate",
            "translate to Thai: The shop is closed": "translate",
            "คำว่า resilience แปลว่าอะไร": "translate",
            "ขอบคุณมาก พูดเป็นภาษาอังกฤษว่าอย่างไร": "translate",
            "สรุปให้หน่อย: เทศบาลแจ้งงดจ่ายน้ำวันเสาร์ ตั้งแต่เก้าโมงถึงบ่ายสาม": "summarize",
            "ข้อความนี้พูดถึงอะไร: บริษัทย้ายสำนักงานไปชั้นห้า พนักงานต้องย้ายของภายในศุกร์": "summarize",
        }  # fmt: skip
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(lang_intent(text), want)

    def test_look_alikes_go_to_ai(self):
        for text in ("แปลกใจที่รถไม่ติด", "แปลงไฟล์ PDF เป็น Word ยังไง", "สรุปแล้วพรุ่งนี้หยุดไหม",
                     "NASA ย่อมาจากอะไร", "ฝันว่าฟันหลุดแปลว่าอะไร", "Google Translate แม่นไหม",
                     "RPG หมายถึงอะไร", "แปล", "ช่วยสรุปหน่อย",
                     "แก้คำผิดให้หน่อย: วันนี้อากาสดีมาก ฉันเลยไปเดินเล่นที่สวนสาธารน"):  # fmt: skip
            with self.subTest(text=text):
                self.assertIsNone(lang_intent(text))

    def test_dev_sets_do_not_regress(self):
        # ชุดพัฒนา (ผู้ช่วยเห็นแล้ว) · ตัวเลขตอน commit กฎ 2026-10-01: 25/25 · 23/23 · ผิด 0/29
        res = evaluate(json.loads((DATA / "lang_rule_heldout.json").read_text("utf-8"))["items"])
        self.assertEqual(res["false"], 0)
        self.assertGreaterEqual(res["hit"]["translate"], 24)
        self.assertGreaterEqual(res["hit"]["summarize"], 22)

    def test_router_sends_clear_request_to_skill(self):
        skills = manifest.load_builtin()
        r = router.route_ai_first("แปลเป็นไทย: Please keep the door closed", skills)
        self.assertEqual((r.kind, r.skill.id), ("skill", "translate"))
        self.assertEqual(router.route_ai_first("ทำไมท้องฟ้าเป็นสีฟ้า", skills).kind, "chat")


if __name__ == "__main__":
    unittest.main()
