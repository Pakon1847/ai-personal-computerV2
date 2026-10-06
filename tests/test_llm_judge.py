"""AI ผู้ให้คะแนนแบบปิดชื่อ (aipc.spikes.llm_judge) · ไม่เรียก Claude จริง."""

import csv
import tempfile
import unittest
from pathlib import Path

from aipc.skills.forge import Reply
from aipc.spikes import llm_judge as j

ROWS = [("q01", "ถามหนึ่ง", "A", "ตอบ ก"), ("q01", "ถามหนึ่ง", "B", "ตอบ ข"),
        ("q02", "ถามสอง", "A", "ตอบ ค"), ("q02", "ถามสอง", "B", "ตอบ ง")]


def write(path, rows, scores=None):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "question", "choice", "answer", "score"])
        for i, r in enumerate(rows):
            w.writerow([*r, "" if scores is None else scores[i]])


class JudgeTest(unittest.TestCase):
    def test_prompt_has_rubric_question_answers_but_no_model_names(self):
        p = j.build_prompt([{"id": "q01", "question": "ถามหนึ่ง", "choice": "A", "answer": "ตอบ ก"}])
        self.assertIn("ถามหนึ่ง", p)
        self.assertIn("คำตอบ A:", p)
        self.assertIn("5 =", p)
        for name in ("gemma", "typhoon", "qwen"):
            self.assertNotIn(name, p.lower())

    def test_parse_rejects_out_of_range_or_missing(self):
        self.assertEqual(j.parse_scores('{"A": 4, "B": 5}', ["A", "B"]), {"A": "4", "B": "5"})
        self.assertIsNone(j.parse_scores('{"A": 6, "B": 5}', ["A", "B"]))
        self.assertIsNone(j.parse_scores('{"A": 4}', ["A", "B"]))
        self.assertIsNone(j.parse_scores("ไม่ใช่ JSON", ["A", "B"]))

    def test_rate_retries_once_and_writes_sheet(self):
        replies = iter([Reply(True, "ผิดรูปแบบ"), Reply(True, '{"A": 3, "B": 5}', cost_usd=0.01),
                        Reply(True, '{"A": 2, "B": 4}', cost_usd=0.01)])
        with tempfile.TemporaryDirectory() as d:
            sheet, out = Path(d) / "s.csv", Path(d) / "judge.csv"
            write(sheet, ROWS)
            log = j.rate(sheet, out, ask=lambda prompt: next(replies))
            self.assertEqual(log["failed"], [])
            with out.open(encoding="utf-8-sig") as f:
                self.assertEqual([r["score"] for r in csv.DictReader(f)], ["3", "5", "2", "4"])
            with self.assertRaises(FileExistsError):
                j.rate(sheet, out, ask=lambda prompt: Reply(True, "{}"))

    def test_agreement(self):
        with tempfile.TemporaryDirectory() as d:
            h, a = Path(d) / "h.csv", Path(d) / "a.csv"
            write(h, ROWS, ["5", "3", "2", "4"])
            write(a, ROWS, ["5", "4", "1", "4"])
            r = j.agree(h, a)
            self.assertEqual((r["n"], r["exact"], r["within_1"]), (4, 0.5, 1.0))
            self.assertGreater(r["spearman"], 0.8)
