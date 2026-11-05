"""ตัววัดด่านตรวจสกิล (spikes.skill_gate · การ์ด 0074 S1) · ไม่ต่อเน็ต."""

import json
import tempfile
import unittest
from pathlib import Path

from aipc.skills import manifest
from aipc.spikes import skill_gate

ROOT = Path(__file__).resolve().parent.parent
GOOD = (ROOT / "docs/benchmarks/2026-09-30-skill-author/claude/s2.md").read_text(encoding="utf-8")
BAD = json.loads((ROOT / "tests/data/bad_skills.json").read_text(encoding="utf-8"))


class SkillGateTest(unittest.TestCase):
    def setUp(self):
        self.builtin = manifest.load_builtin()

    def test_same_verdict_as_the_import_button(self):
        self.assertEqual(skill_gate.check_import(GOOD, self.builtin), (True, []))
        ok, errors = skill_gate.check_import("โน้ตธรรมดา ไม่มีส่วนหัว", self.builtin)
        self.assertFalse(ok)
        self.assertTrue(errors)
        for it in BAD["items"]:  # ชุดสกิลเสียเดิม (การ์ด 0017) ยังไม่ผ่านทุกไฟล์
            self.assertFalse(skill_gate.check_import(it["skill_md"], self.builtin)[0], it["id"])

    def test_counts_bad_and_good_separately_by_category_and_type(self):
        items = [{"id": "g1", "label": "good", "category": None, "type": "steps", "md": GOOD},
                 {"id": "b1", "label": "bad", "category": "A", "type": "steps",
                  "md": BAD["items"][0]["skill_md"]},
                 {"id": "b2", "label": "bad", "category": "B", "type": "prompt",
                  "md": GOOD}]  # fmt: skip  # สกิลดีที่ติดป้ายเสีย = นับว่าหลุด
        res = skill_gate.evaluate(items, self.builtin)
        self.assertEqual((res["bad_accepted"], res["bad_total"]), (1, 2))
        self.assertEqual((res["good_accepted"], res["good_total"]), (1, 1))
        self.assertEqual(res["bad_by_group"]["category B"], [1, 1])
        self.assertEqual(res["bad_by_group"]["type steps"], [0, 1])
        self.assertIsNone(res["bad_accepted_upper95"], "มีหลุด = ไม่ใช้ขอบบนของ 0/N")

    def test_upper_bound_for_zero_of_n(self):
        self.assertAlmostEqual(skill_gate.upper95(40), 0.072, places=3)
        self.assertAlmostEqual(skill_gate.upper95(100), 0.0295, places=3)

    def test_main_writes_result(self):
        data = {"items": [{"id": "g1", "label": "good", "category": None, "type": "steps",
                           "md": GOOD}]}  # fmt: skip
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / "s1.json", Path(d) / "out.json"
            src.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(skill_gate.main(["--dataset", str(src), "--out", str(out)]), 0)
            res = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(res["good_accepted"], 1)


if __name__ == "__main__":
    unittest.main()
