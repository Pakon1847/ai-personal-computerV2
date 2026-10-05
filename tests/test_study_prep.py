"""เตรียมบัญชีทดสอบกับผู้ใช้ (aipc.spikes.study_prep)."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from aipc.skills.reminders import ReminderStore
from aipc.spikes import study_prep as sp


class StudyPrepTest(unittest.TestCase):
    def test_seed_gives_t3_and_t5_answers(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            now = datetime(2026, 10, 12, 9, 0).astimezone()
            written = sp.seed(home, now)
            receipt = home / "Documents" / sp.RECEIPT_NAME
            self.assertIn(receipt, written)
            self.assertIn("รวมทั้งสิ้น 1,600 บาท", receipt.read_text(encoding="utf-8"))
            items = ReminderStore(home / ".local/share/aipc/reminders.json").items
            self.assertEqual([(r.what, r.when.date(), r.when.hour) for r in items],
                             [("รับยาที่โรงพยาบาล", now.date(), 18)])

    def test_create_sends_helper_request_like_signup_screen(self):
        seen = {}

        def run(argv, input, **kw):
            seen.update(argv=argv, req=json.loads(input))

            class R:
                stdout = '{"ok": true}'
                stderr = ""
            return R()

        self.assertTrue(sp.create("p1", "ผู้ร่วมทดสอบ P1", "pw-Long-123", "4821", run=run)["ok"])
        self.assertEqual(seen["argv"][-1], "/usr/local/sbin/aipc-accounts")
        self.assertEqual(seen["req"]["op"], "create")

    def test_dry_run_changes_nothing(self):
        self.assertEqual(sp.main(["p1", "p2"]), 0)
