import json
import subprocess
import sys
import tempfile
import unittest
from itertools import count
from pathlib import Path

from aipc.bench import runner
from aipc.bench.machine import MachineInfo


def fake_sampler(throttled_values=None):
    ticks = count()
    values = iter(throttled_values or [])
    return runner.Sampler(
        temp=lambda: 50.0,
        throttled=lambda: next(values, 0),
        clock=lambda: float(next(ticks)),  # ทุกรอบใช้เวลา 1 วินาทีพอดี
    )


def info(board_class="pi5", dirty=False, commit="abc"):
    return MachineInfo(
        collected_at="2026-09-23T00:00:00+00:00",
        hostname="t",
        board_model="Raspberry Pi 5 Model B Rev 1.0" if board_class == "pi5" else None,
        board_class=board_class,
        ram_total_mb=8052,
        os="Debian",
        kernel="6.12",
        python="3.13",
        cpu_temp_c=50.0,
        throttled=0,
        git_commit=commit,
        git_dirty=dirty,
    )


class MeasureRulesTest(unittest.TestCase):
    def test_refuses_fewer_than_five_runs(self):
        with self.assertRaises(ValueError):
            runner.measure(lambda: None, runs=4, sampler=fake_sampler())

    def test_refuses_no_warmup(self):
        with self.assertRaises(ValueError):
            runner.measure(lambda: None, warmup=0, sampler=fake_sampler())

    def test_warmup_is_recorded_but_marked(self):
        records = runner.measure(lambda: None, sampler=fake_sampler())
        self.assertEqual([r.phase for r in records], ["warmup"] + ["measured"] * 5)
        self.assertTrue(all(r.seconds == 1.0 for r in records))

    def test_task_runs_warmup_plus_runs_times(self):
        calls = []
        runner.measure(lambda: calls.append(1), warmup=2, runs=6, sampler=fake_sampler())
        self.assertEqual(len(calls), 8)


class ThrottleJudgementTest(unittest.TestCase):
    def test_current_bit_means_throttled(self):
        self.assertTrue(runner.throttled_during(0, 0x4))

    def test_sticky_bit_already_set_before_is_not_blamed_on_run(self):
        self.assertFalse(runner.throttled_during(0x50000, 0x50000))

    def test_new_sticky_bit_means_it_happened_during_run(self):
        self.assertTrue(runner.throttled_during(0x0, 0x10000))

    def test_unknown_is_not_counted_as_throttled(self):
        self.assertFalse(runner.throttled_during(None, None))


class VerdictTest(unittest.TestCase):
    def records(self, throttled=None):
        return runner.measure(lambda: None, sampler=fake_sampler(throttled))

    def test_clean_pi5_run_is_level4(self):
        v = runner.judge(info(), self.records(), 0)
        self.assertTrue(v.evidence_level4)
        self.assertEqual(v.warnings, [])

    def test_pi4_is_never_level4(self):
        v = runner.judge(info("pi4"), self.records(), 0)
        self.assertFalse(v.evidence_level4)

    def test_throttle_during_any_run_invalidates(self):
        v = runner.judge(info(), self.records([0, 0, 0x4]), 0)
        self.assertFalse(v.evidence_level4)
        self.assertEqual(v.throttled_runs, [2])

    def test_sticky_bits_before_run_are_not_level4(self):
        """audit 2026-09-30 evidence-1: บิต "เคยเกิด" ติดก่อนวัด =
        throttle ที่เกิดแล้วหายระหว่างรอบมองไม่เห็น."""
        v = runner.judge(info(), self.records(), 0xE0000)
        self.assertEqual(v.throttled_runs, [])
        self.assertFalse(v.evidence_level4)
        self.assertTrue(any("รีบูต" in w for w in v.warnings))

    def test_dirty_tree_is_not_level4(self):
        self.assertFalse(runner.judge(info(dirty=True), self.records(), 0).evidence_level4)

    def test_unreadable_throttle_is_not_level4(self):
        records = runner.measure(
            lambda: None,
            sampler=runner.Sampler(
                temp=lambda: None, throttled=lambda: None, clock=count().__next__
            ),
        )
        v = runner.judge(info(), records, None)
        self.assertTrue(v.throttle_unknown)
        self.assertFalse(v.evidence_level4)


class ReportTest(unittest.TestCase):
    def test_writes_three_files_and_never_overwrites(self):
        records = runner.measure(lambda: None, sampler=fake_sampler())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            paths = runner.write_report(out, "x", info(), records, 0, {"threads": "4"}, {})
            self.assertEqual(sorted(p.suffix for p in paths.values()), [".csv", ".json", ".md"])
            rows = paths["csv"].read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(rows), 1 + 6)  # หัวตาราง + 6 รอบ
            data = json.loads(paths["json"].read_text(encoding="utf-8"))
            self.assertEqual(data["summary_seconds"]["n"], 5)
            self.assertEqual(data["meta"], {"threads": "4"})
            with self.assertRaises(FileExistsError):
                runner.write_report(out, "x", info(), records, 0, {}, {})

    def test_sha256_of_known_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "m.bin"
            p.write_bytes(b"abc")
            self.assertEqual(
                runner.sha256_file(p),
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            )

    def test_command_task_runs_real_command_without_shell(self):
        runner.command_task([sys.executable, "-c", "pass"])()
        with self.assertRaises(subprocess.CalledProcessError):
            runner.command_task([sys.executable, "-c", "raise SystemExit(3)"])()


if __name__ == "__main__":
    unittest.main()
