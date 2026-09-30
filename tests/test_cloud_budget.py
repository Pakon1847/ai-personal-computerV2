"""เพดานค่าใช้จ่าย Claude ต่อวัน (aipc.cloud.budget) · ไม่ต่อเน็ต."""

import tempfile
import unittest
from datetime import date
from pathlib import Path

from aipc.cloud import budget


class BudgetTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.path = Path(d.name) / "usage.json"
        self.day = date(2026, 10, 1)
        self.b = budget.Budget(self.path, today=lambda: self.day)

    def test_blocks_after_limit_and_resets_next_day(self):
        self.assertEqual(self.b.limit, budget.DEFAULT_LIMIT)
        self.b.record(0.6, "ask")
        self.assertTrue(self.b.allow())
        self.b.record(0.5, "skill")
        self.assertFalse(self.b.allow())
        self.assertIn("ครบเพดาน", self.b.blocked_message())
        self.assertEqual((self.b.spent(), self.b.calls()), (1.1, 2))
        self.day = date(2026, 10, 2)  # วันใหม่
        self.assertTrue(self.b.allow())
        self.assertEqual(self.b.spent(), 0.0)

    def test_limit_choice_persists_and_bad_values_ignored(self):
        self.b.set_limit(5.0)
        self.b.set_limit(999)  # ไม่อยู่ในตัวเลือก = ไม่เปลี่ยน
        again = budget.Budget(self.path, today=lambda: self.day)
        self.assertEqual(again.limit, 5.0)

    def test_broken_file_starts_fresh(self):
        self.path.write_text("{เสีย", encoding="utf-8")
        b = budget.Budget(self.path, today=lambda: self.day)
        self.assertEqual((b.spent(), b.limit), (0.0, budget.DEFAULT_LIMIT))
        b.record(0.1, "ask")
        self.assertEqual(budget.Budget(self.path, today=lambda: self.day).calls(), 1)

    def test_keeps_only_recent_days(self):
        for i in range(40):
            self.day = date(2026, 8, 1).fromordinal(date(2026, 8, 1).toordinal() + i)
            self.b.record(0.01, "ask")
        self.assertEqual(len(self.b._data["days"]), budget.KEEP_DAYS)

    def test_cloud_client_refuses_when_over_budget(self):
        from unittest import mock

        from aipc.ui import app

        self.b.record(5.0, "ask")
        with mock.patch("aipc.cloud.ask.find_claude", return_value="claude"), \
             mock.patch("aipc.cloud.ask.ask") as real:  # fmt: skip
            run = app._cloud_client(self.b)
            r = run("อากาศวันนี้", [])
        self.assertFalse(r.ok)
        self.assertIn("ครบเพดาน", r.error)
        real.assert_not_called()  # ไม่ส่งอะไรออกนอกเครื่องเลย


if __name__ == "__main__":
    unittest.main()
