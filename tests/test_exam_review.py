"""ตรวจคำตอบของ Claude ในชุดสอบไฮบริด (aipc.spikes.exam_review) · เกณฑ์ในหัวไฟล์ของโมดูล."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from aipc.spikes import exam_review as er

RESULT = {"date": "2026-10-05T20:46", "summary": {"auto_ok": 95}, "rows": [
    {"id": "A01", "by": "local", "q": "x", "expect": "answer"},
    {"id": "A08", "by": "cloud", "q": "แม่น้ำ", "expect": "answer", "text": "มูล", "local_text": "เจ้าพระยา",
     "escalated_by": "fallback"},
    {"id": "B03", "by": "cloud", "q": "ราคาทอง", "expect": "honest", "text": "ยืนยันไม่ได้", "escalated_by": "tool"},
    {"id": "B10", "by": "cloud", "q": "หุ้น", "expect": "honest", "text": "</script> ขึ้น", "escalated_by": "tool"},
]}


def write_review(path: Path, verdicts: dict) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "question", "verdict", "note"])
        for i, v in verdicts.items():
            w.writerow([i, "q", v, ""])


class ExamReviewTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.dir = Path(self.d.name)
        self.res = self.dir / "h.json"
        self.res.write_text(json.dumps(RESULT, ensure_ascii=False), encoding="utf-8")

    def test_sheet_has_only_cloud_items_and_escapes_script(self):
        page = er.sheet(self.res, self.dir / "out").read_text(encoding="utf-8")
        self.assertIn('"B10"', page)
        self.assertNotIn('"A01"', page)
        self.assertNotIn("</script> ขึ้น", page)  # ข้อความของ Claude ปิดแท็ก script ไม่ได้

    def test_score_rules(self):
        write_review(self.dir / "r1.csv", {"A08": "correct", "B03": "honest", "B10": "correct"})
        write_review(self.dir / "r2.csv", {"A08": "correct", "B03": "honest", "B10": "wrong"})
        s = er.score(self.res, [self.dir / "r1.csv", self.dir / "r2.csv"])
        self.assertEqual(s["cloud_passed"], 2)  # A08 ถูก · B03 บอกตรง ๆ ในข้อที่เฉลยคือบอกตรง ๆ
        self.assertEqual(s["disagree"], ["B10"])  # เห็นไม่ตรงกัน = ไม่ผ่าน
        self.assertEqual(s["hybrid_after_review"], 95 - 3 + 2)
        self.assertEqual(s["live_data_answered"], 0)

    def test_honest_on_answer_item_fails_and_incomplete_is_refused(self):
        write_review(self.dir / "r1.csv", {"A08": "honest", "B03": "correct", "B10": "correct"})
        s = er.score(self.res, [self.dir / "r1.csv"])
        self.assertEqual((s["cloud_passed"], s["live_data_answered"]), (2, 2))
        write_review(self.dir / "r2.csv", {"A08": "correct"})
        with self.assertRaises(ValueError):
            er.score(self.res, [self.dir / "r2.csv"])
