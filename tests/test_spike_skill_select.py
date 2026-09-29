"""ตัววัดการเลือกสกิล (spikes.skill_select) · AI ปลอม ไม่ต่อเน็ต."""

import json
import unittest

from aipc.skills import manifest
from aipc.spikes import skill_select


class SkillSelectTest(unittest.TestCase):
    def setUp(self):
        self.skills = manifest.load_builtin()
        self.asked = []

    def ai(self, answers):
        def fake(text, tools):
            self.asked.append((text, {t["function"]["name"] for t in tools}))
            return {"tool": answers.get(text, ""), "seconds": 1.0, "timings": {}}

        return fake

    def test_rules_first_then_ai_only_when_rules_find_nothing(self):
        items = [{"text": "เปิดยูทูบ", "expect": "system-command", "kind": "direct"},
                 {"text": "คอมหน่วงมาก", "expect": "machine-status", "kind": "paraphrase"},
                 {"text": "เล่ามุกหน่อย", "expect": "none", "kind": "general"},
                 {"text": "ขอแบบกระชับของเนื้อหานี้", "expect": "summarize-text",
                  "kind": "paraphrase"}]  # fmt: skip
        res = skill_select.evaluate(
            items,
            self.skills,
            self.ai(
                {
                    "คอมหน่วงมาก": "machine-status",
                    "เล่ามุกหน่อย": "rm-rf",
                    "ขอแบบกระชับของเนื้อหานี้": "summarize-text",
                }
            ),
        )
        self.assertEqual(
            [t for t, _ in self.asked], ["คอมหน่วงมาก", "เล่ามุกหน่อย", "ขอแบบกระชับของเนื้อหานี้"]
        )
        self.assertNotIn("system-command", self.asked[0][1], "AI ไม่มีเครื่องมือสั่งเครื่อง")
        self.assertEqual(res["correct"], 4, "ชื่อที่ไม่มีในรายการ (rm-rf) = คุยทั่วไป ถูกต้องตามแอปจริง")
        self.assertEqual(res["false_calls"], 0)
        self.assertEqual(res["ai_asked"], 3)

    def test_dataset_is_well_formed(self):
        data = json.loads(skill_select.DATASET.read_text(encoding="utf-8"))
        ids = {s.id for s in self.skills} | {"none"}
        kinds = {"direct", "paraphrase", "general", "trap"}
        for it in data["items"]:
            self.assertIn(it["expect"], ids, it["text"])
            self.assertIn(it["kind"], kinds, it["text"])
        self.assertEqual(len({it["text"] for it in data["items"]}), len(data["items"]), "ประโยคซ้ำ")
        self.assertEqual(data["criteria"]["correct_min"], 0.8)


if __name__ == "__main__":
    unittest.main()
