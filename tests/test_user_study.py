"""คิดคะแนนทดสอบกับผู้ใช้ (aipc.spikes.user_study) · SUS ตาม Brooke 1996."""

import csv
import unittest
from pathlib import Path

from aipc.spikes.user_study import summarize, sus

TEMPLATE = (
    Path(__file__).resolve().parent.parent / "docs" / "eval" / "user-study" / "results-template.csv"
)


class UserStudyTest(unittest.TestCase):
    def test_sus_bounds_and_example(self):
        self.assertEqual(sus([5, 1] * 5), 100.0)  # เห็นด้วยข้อดีทุกข้อ ไม่เห็นด้วยข้อเสียทุกข้อ
        self.assertEqual(sus([1, 5] * 5), 0.0)
        self.assertEqual(sus([3] * 10), 50.0)
        with self.assertRaises(ValueError):
            sus([3] * 9)

    def test_template_summarizes(self):
        with TEMPLATE.open(encoding="utf-8") as f:
            res = summarize(list(csv.DictReader(f)))
        g = res["groups"]["all"]
        self.assertEqual(g["people"], 1)
        self.assertEqual(g["task_ok_pct"], 75.0)  # 6 จาก 8
        # 4,2,4,3,4,2,3,2,4,3 → (3+3+3+2+3+3+2+3+3+2) × 2.5
        self.assertEqual(g["sus_mean"], 67.5)


if __name__ == "__main__":
    unittest.main()
