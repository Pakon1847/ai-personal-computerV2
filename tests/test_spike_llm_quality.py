"""ตัววัดคุณภาพภาษาไทยของ LLM (ADR-007 เกณฑ์ข้อ 1) · server ปลอม ไม่ต้องมีโมเดลจริง."""

import csv
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from aipc.spikes import llm_quality as q


class FakeLlamaServer(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        question = body["messages"][-1]["content"]
        reply = {
            "choices": [{"message": {"content": f"ตอบ: {question[:10]}"}}],
            "usage": {"completion_tokens": 5},
            "timings": {"predicted_per_second": 4.2},
        }
        data = json.dumps(reply, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class QuestionSetTest(unittest.TestCase):
    def test_thirty_questions_with_unique_ids(self):
        data = json.loads(q.QUESTIONS.read_text(encoding="utf-8"))
        ids = [x["id"] for x in data["questions"]]
        self.assertEqual(len(ids), 30)
        self.assertEqual(len(set(ids)), 30)
        self.assertEqual(data["criteria"]["mean_score_min"], 3.5)  # ตรงกับ ADR-007


class FlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aipc-llmq-"))
        self.srv = HTTPServer(("127.0.0.1", 0), FakeLlamaServer)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.shutdown)
        self.url = f"http://127.0.0.1:{self.srv.server_port}"

    def run_ask(self, label):
        return q.ask(self.url, label, q.QUESTIONS, self.tmp / f"{label}.json")

    def test_ask_records_every_answer_and_refuses_overwrite(self):
        res = self.run_ask("model-a")
        self.assertEqual(len(res["answers"]), 30)
        self.assertEqual(res["answers"][0]["timings"]["predicted_per_second"], 4.2)
        with self.assertRaises(FileExistsError):
            self.run_ask("model-a")

    def test_sheet_hides_model_names_and_score_uses_key(self):
        for label in ("typhoon", "qwen"):
            self.run_ask(label)
        out = self.tmp / "sheet"
        q.sheet([self.tmp / "typhoon.json", self.tmp / "qwen.json"], q.QUESTIONS, out)
        text = (out / "rate-me.csv").read_text(encoding="utf-8-sig")
        self.assertNotIn("typhoon", text)
        self.assertNotIn("qwen", text)
        page = (out / "rate-me.html").read_text(encoding="utf-8")  # หน้าให้คะแนนออฟไลน์ (2026-10-05)
        self.assertNotIn("typhoon", page)
        self.assertNotIn("__DATA__", page)
        self.assertIn('"choice": "B"', page)

        key = json.loads((out / "key.json").read_text(encoding="utf-8"))
        # ผู้ให้คะแนน 2 คน: ให้ typhoon 5 และ qwen 3 ทุกข้อ
        for rater in ("rater1", "rater2"):
            with (out / "rate-me.csv").open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            for r in rows:
                r["score"] = "5" if key[f"{r['id']}:{r['choice']}"] == "typhoon" else "3"
            with (out / f"{rater}.csv").open("w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
        res = q.score(out / "key.json", [out / "rater1.csv", out / "rater2.csv"])
        self.assertEqual(res["typhoon"]["mean"], 5)
        self.assertTrue(res["typhoon"]["passes"])
        self.assertEqual(res["qwen"]["mean"], 3)
        self.assertFalse(res["qwen"]["passes"])
        self.assertEqual(res["qwen"]["n"], 60)

    def test_blank_score_is_refused(self):
        self.run_ask("only")
        out = self.tmp / "s"
        q.sheet([self.tmp / "only.json"], q.QUESTIONS, out)
        with self.assertRaises(ValueError):
            q.score(out / "key.json", [out / "rate-me.csv"])


if __name__ == "__main__":
    unittest.main()
