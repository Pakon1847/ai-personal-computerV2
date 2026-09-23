import json
import tempfile
import unittest
from itertools import count
from pathlib import Path

from aipc.bench import runner
from aipc.spikes import llm
from tests.test_bench_runner import fake_sampler, info

# หน้าตาผล `llama-bench -o json` แบบย่อ (ฟิลด์อื่นตัดออก) — ต้องเทียบกับของจริงบน Pi อีกครั้ง
SAMPLE = json.dumps(
    [
        {"model_filename": "m.gguf", "n_prompt": 200, "n_gen": 0, "avg_ts": 40.0},
        {"model_filename": "m.gguf", "n_prompt": 0, "n_gen": 64, "avg_ts": 12.5},
    ]
)


class ParseTest(unittest.TestCase):
    def test_splits_prefill_and_generation(self):
        m = llm.parse_llama_bench_json(SAMPLE)
        self.assertEqual(m["pp_tok_s"], 40.0)
        self.assertEqual(m["tg_tok_s"], 12.5)
        self.assertEqual(m["prefill_s"], 5.0)  # 200 token ÷ 40 tok/s

    def test_unknown_format_stops_and_names_the_fields(self):
        with self.assertRaises(ValueError) as ctx:
            llm.parse_llama_bench_json(json.dumps([{"n_prompt": 200, "speed": 1}]))
        self.assertIn("avg_ts", str(ctx.exception))
        self.assertIn("speed", str(ctx.exception))

    def test_not_json(self):
        with self.assertRaises(ValueError):
            llm.parse_llama_bench_json("llama-bench: error")

    def test_bench_args_force_single_repetition_and_json(self):
        args = llm.bench_args("llama-bench", "m.gguf", 4, 200, 64)
        self.assertEqual(args[args.index("-r") + 1], "1")
        self.assertEqual(args[args.index("-o") + 1], "json")
        self.assertEqual(args[args.index("-p") + 1], "200")


class ReportWithMetricsTest(unittest.TestCase):
    def test_metrics_get_their_own_columns_and_summary(self):
        speeds = iter([10, 11, 12, 13, 14, 15])
        records = runner.measure(lambda: {"tg_tok_s": next(speeds)}, sampler=fake_sampler())
        with tempfile.TemporaryDirectory() as tmp:
            paths = runner.write_report(Path(tmp), "x", info(), records, 0, {}, {})
            header = paths["csv"].read_text(encoding="utf-8").splitlines()[0]
            self.assertIn("tg_tok_s", header)
            self.assertNotIn("metrics", header)
            data = json.loads(paths["json"].read_text(encoding="utf-8"))
            # warm-up (10) ไม่ถูกนับ → median ของ 11..15 = 13
            self.assertEqual(data["summary_metrics"]["tg_tok_s"]["median"], 13)
            self.assertIn("tg_tok_s", paths["md"].read_text(encoding="utf-8"))


class SoakTest(unittest.TestCase):
    def test_runs_until_time_is_up_and_records_each_round(self):
        ticks = count(0, 30)  # นาฬิกาปลอม: ทุกครั้งที่ถูกอ่าน เวลาเดินไป 30 วินาที
        speeds = iter([12.0, 11.0, 9.0, 8.0])

        def fake_run(args, parse):
            return lambda: {"tg_tok_s": next(speeds)}

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "soak.csv"
            rows = llm.soak(
                ["x"], 3, out, run=fake_run, clock=lambda: next(ticks),
                temp=lambda: 70.0, throttled=lambda: 0,
            )  # fmt: skip
            self.assertTrue(out.exists())
            with self.assertRaises(FileExistsError):
                llm.soak(["x"], 1, out, run=fake_run)
        self.assertEqual(len(rows), 3)  # อ่านนาฬิกา 2 ครั้งต่อรอบ → 3 รอบใน 3 นาที
        summary = llm.soak_summary(rows)
        self.assertIn("ลดลง", summary)
        self.assertIn("ไม่ throttle", summary)

    def test_summary_reports_throttle_time(self):
        rows = [
            {"elapsed_s": 10, "tg_tok_s": 12.0, "temp_c": 80.0, "throttled": 0},
            {"elapsed_s": 20, "tg_tok_s": 9.0, "temp_c": 86.0, "throttled": 0x4},
        ]
        self.assertIn("[20]", llm.soak_summary(rows))


if __name__ == "__main__":
    unittest.main()
