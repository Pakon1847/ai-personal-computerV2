"""ย้อนกลับคำสั่งล่าสุด (ข้อเสนอ 2026-10-03) · ตัวรัน/ตัวอ่านปลอม ไม่แตะเสียงจริง.

ที่มา: ผลวัดเสียง docs/benchmarks/2026-10-01-voice-noise · "เปิดวิกิ" ถอดเป็น "เปิดเสียง…" แล้วทำเลยโดยไม่ถาม
"""

import tempfile
import unittest
from pathlib import Path

from aipc.skills import actions
from aipc.skills.actions import Executor, Plan, parse_volume

try:
    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None


class FakeSink:
    """ลำโพงปลอม: จำระดับเสียงและสถานะปิดเสียงเหมือน wpctl."""

    def __init__(self, percent=40, muted=False, readable=True):
        self.percent, self.muted, self.readable, self.ran = percent, muted, readable, []

    def read(self, args):
        if not self.readable:
            return None
        return f"Volume: {self.percent / 100:.2f}" + (" [MUTED]" if self.muted else "") + "\n"

    def run(self, args):
        self.ran.append(args)
        if args[:2] == ["wpctl", "set-volume"]:
            v = args[-1]
            n = int(v.rstrip("%+-"))
            self.percent = (
                self.percent + n if v.endswith("+") else self.percent - n if v.endswith("-") else n
            )
            if "-l" in args:  # wpctl -l 1.0 = ไม่เกิน 100%
                self.percent = min(self.percent, 100)
        elif args[:2] == ["wpctl", "set-mute"]:
            self.muted = args[3] == "1"
        return 0


class ExecutorUndoTest(unittest.TestCase):
    def test_parse_volume(self):
        self.assertEqual(parse_volume("Volume: 0.40\n"), (40, False))
        self.assertEqual(parse_volume("Volume: 1.20 [MUTED]"), (120, True))
        self.assertIsNone(parse_volume(""))
        self.assertIsNone(parse_volume(None))

    def test_volume_change_can_be_undone_exactly(self):
        sink = FakeSink(percent=35, muted=True)
        ex = Executor(runner=sink.run, reader=sink.read, dry_run=False)
        out = ex.execute(Plan("unmute", {}, "เปิดเสียง"))
        out2 = ex.execute(Plan("change_volume", {"step": 10}, "เพิ่มเสียง"))
        self.assertEqual((sink.percent, sink.muted), (45, False))
        for p in out2.undo + out.undo:
            ex.execute(p)
        self.assertEqual((sink.percent, sink.muted), (35, True))

    def test_volume_up_stops_at_100(self):
        # พบบน Pi 5 2026-10-12: 100% + "เพิ่มเสียง" = 110% (เกินระดับปกติ เสียงแตกได้)
        sink = FakeSink(percent=100)
        ex = Executor(runner=sink.run, reader=sink.read, dry_run=False)
        ex.execute(Plan("change_volume", {"step": 10}, "เพิ่มเสียง"))
        self.assertEqual(sink.percent, 100)

    def test_no_undo_when_state_unknown_or_irreversible(self):
        sink = FakeSink(readable=False)
        ex = Executor(runner=sink.run, reader=sink.read, dry_run=False)
        self.assertEqual(
            ex.execute(Plan("set_volume", {"percent": 80}, "x")).undo, ()
        )  # ไม่เดาค่าเดิม
        ok = FakeSink()
        ex = Executor(runner=ok.run, reader=ok.read, dry_run=False)
        self.assertEqual(ex.execute(Plan("open_url", {"site": "youtube"}, "x")).undo, ())
        self.assertEqual(Executor(dry_run=True).execute(Plan("mute", {}, "x")).undo, ())
        failed = Executor(runner=lambda a: 1, reader=ok.read, dry_run=False)
        self.assertEqual(failed.execute(Plan("mute", {}, "x")).undo, ())


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class ControllerUndoTest(unittest.TestCase):
    def setUp(self):
        self.sink = FakeSink(percent=40)
        ex = actions.Executor(runner=self.sink.run, reader=self.sink.read, dry_run=False)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.s = SkillsController(
            executor=ex, reminders_path=Path(tmp.name) / "r.json", run_timer=False
        )

    def test_undo_restores_and_works_once(self):
        card = self.s.handle("เสียง 90%")
        self.assertEqual(self.sink.percent, 90)
        done = self.s.undo(card["undoToken"])
        self.assertEqual(done["title"], "ย้อนกลับแล้ว")
        self.assertIn("คืนระดับเสียงเป็น 40%", done["lines"])
        self.assertEqual(self.sink.percent, 40)
        self.assertIn("ไม่ได้แล้ว", self.s.undo(card["undoToken"])["title"])  # ครั้งเดียว

    def test_only_latest_command_can_be_undone(self):
        old = self.s.handle("เสียง 90%")
        new = self.s.handle("ปิดเสียง")
        self.assertIn("ไม่ได้แล้ว", self.s.undo(old["undoToken"])["title"])
        self.assertEqual(self.sink.percent, 90)  # คำสั่งเก่าไม่ถูกย้อนทับคำสั่งใหม่
        self.s.undo(new["undoToken"])
        self.assertEqual((self.sink.percent, self.sink.muted), (90, False))

    def test_opening_a_site_says_it_cannot_be_undone(self):
        card = self.s.handle("เปิดยูทูบ")
        self.assertEqual(card.get("undoToken", ""), "")
        self.assertTrue(any("ย้อนกลับไม่ได้" in line for line in card["lines"]))


if __name__ == "__main__":
    unittest.main()
