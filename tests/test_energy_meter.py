"""มิเตอร์พลังงานต่อคำตอบ (Pakon เลือกข้อ ค 2026-10-07).

เกณฑ์: docs/benchmarks/2026-10-07-energy-meter-pi5 (ข้อ 3–4 วัดด้วยเทสต์นี้ · ข้อ 1–2 วัดบน Pi)
"""

import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from aipc.bench import energy
from aipc.chat import store
from tests.test_chat import ChatController, FakeLlama, ServerCase, pump

PMIC = "  VDD_CORE_A current(7)=2.00000000A\n  VDD_CORE_V volt(15)=1.00000000V\n"


class SummarizeTest(unittest.TestCase):
    def test_trapezoid(self):
        """เกณฑ์ข้อ 4: วัตต์คงที่ × เวลา = จูลที่คาด."""
        r = energy.summarize([(0.0, 5.0), (1.0, 5.0), (2.0, 5.0)])
        self.assertEqual(
            (r["joules"], r["seconds"], r["mean_w"], r["samples"]), (10.0, 2.0, 5.0, 3)
        )
        r = energy.summarize([(0.0, 4.0), (2.0, 6.0)])
        self.assertEqual(r["joules"], 10.0)

    def test_too_few_samples_shows_nothing(self):
        """เกณฑ์ข้อ 3: ได้ค่าน้อยกว่า 2 ครั้ง = ไม่แสดง."""
        self.assertIsNone(energy.summarize([]))
        self.assertIsNone(energy.summarize([(1.0, 5.0)]))
        self.assertIsNone(energy.summarize([(1.0, 5.0), (1.0, 6.0)]))


class MeterTest(unittest.TestCase):
    def test_runs_until_stopped_and_stops_fast(self):
        m = energy.Meter(period=0.01, reader=lambda: 4.0)
        m.start()
        time.sleep(0.08)
        t0 = time.monotonic()
        r = m.stop()
        self.assertLess(time.monotonic() - t0, 0.5)  # คำตอบจบ = หยุดทันที ไม่ค้างหน้าจอ
        self.assertGreaterEqual(r["samples"], 2)
        self.assertAlmostEqual(r["joules"], 4.0 * r["seconds"], delta=0.11)

    def test_unreadable_pmic_shows_nothing(self):
        m = energy.Meter(period=0.01, reader=lambda: None)
        m.start()
        time.sleep(0.03)
        self.assertIsNone(m.stop())

    def test_factory_only_where_pmic_reads(self):
        def missing(*a, **k):
            raise OSError("ไม่มี vcgencmd")  # วินโดวส์

        self.assertIsNone(energy.meter_factory(missing)())
        ok = energy.meter_factory(lambda *a, **k: SimpleNamespace(returncode=0, stdout=PMIC))
        self.assertIsInstance(ok(), energy.Meter)
        self.assertEqual(
            energy.read(lambda *a, **k: SimpleNamespace(returncode=0, stdout=PMIC)), 2.0
        )


class FakeMeter:
    def __init__(self, result):
        self.result, self.started = result, False

    def start(self):
        self.started = True

    def stop(self):
        return self.result


ENERGY = {"joules": 190.4, "seconds": 28.4, "mean_w": 6.7, "samples": 29}


@unittest.skipIf(ChatController is None, "ไม่มี PySide6")
class ChatEnergyTest(ServerCase):
    def make(self, meter, cloud=None):
        from PySide6.QtGui import QGuiApplication

        self.app = QGuiApplication.instance() or QGuiApplication([])
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        c = ChatController(target=self.target, store=store.ChatStore(Path(d.name)), poll_ms=100000,
                           cloud=cloud, meter=meter, auto_cloud=True)  # fmt: skip
        self.addCleanup(c.shutdown)
        pump(lambda: c.ready)
        rows = []
        c.finished.connect(lambda text, note: rows.append({r["k"]: r["v"] for r in c.lastTrace}))
        return c, rows

    def test_local_answer_shows_energy(self):
        meters = []
        c, rows = self.make(lambda: meters.append(FakeMeter(ENERGY)) or meters[-1])
        c.send("สวัสดี", "")
        pump(lambda: rows)
        self.assertTrue(meters[0].started)
        self.assertEqual(rows[0]["ไฟที่บอร์ดใช้ระหว่างตอบ"],
                         "≈ 190 J (28.4 วิ · เฉลี่ย 6.7 W · ทั้งบอร์ด ไม่รวมอะแดปเตอร์)")  # fmt: skip

    def test_no_meter_or_no_reading_shows_nothing(self):
        for meter in (lambda: None, lambda: FakeMeter(None)):
            c, seen = self.make(meter)
            c.send("สวัสดี", "")
            pump(lambda seen=seen: seen)
            self.assertNotIn("ไฟที่บอร์ดใช้ระหว่างตอบ", seen[0])

    def test_claude_answer_shows_no_energy(self):
        """เกณฑ์ข้อ 3: ไฟของเครื่องเราไม่ใช่พลังงานของคำตอบจาก Claude."""
        from aipc.cloud.ask import CloudReply

        FakeLlama.mode = "dunno"
        c, rows = self.make(lambda: FakeMeter(ENERGY), cloud=lambda q, h: CloudReply(True, "ข่าว …"))
        c.send("ข่าวเด่นวันนี้มีอะไร", "")
        pump(lambda: rows)
        self.assertEqual(rows[0]["ใครตอบ"], "Claude (cloud)")
        self.assertNotIn("ไฟที่บอร์ดใช้ระหว่างตอบ", rows[0])


if __name__ == "__main__":
    unittest.main()
