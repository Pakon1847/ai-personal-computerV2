"""บันทึกสิ่งที่ส่งออกนอกเครื่อง (aipc.cloud.ledger) · ไม่ต่อเน็ต."""

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from aipc.cloud import ask, ledger


class LedgerTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)
        self.path = self.dir / "outbound.json"
        self.l = ledger.Ledger(self.path, now=lambda: datetime(2026, 10, 1, 14, 5))

    def test_records_newest_first_and_clears(self):
        self.l.record("ask", "คำถาม: อากาศวันนี้", 0.02)
        self.l.record("skill", "อยากได้โหมดทำงาน", 0.08, note="x")
        e = self.l.entries()
        self.assertEqual([x["kind"] for x in e], ["skill", "ask"])
        self.assertEqual(e[1]["sent"], "คำถาม: อากาศวันนี้")
        self.assertEqual(e[1]["chars"], len("คำถาม: อากาศวันนี้"))
        self.assertEqual(e[0]["time"], "2026-10-01T14:05:00")
        self.l.clear()
        self.assertEqual(self.l.entries(), [])

    def test_keeps_only_recent(self):
        for i in range(ledger.KEEP + 5):
            self.l.record("ask", f"q{i}")
        e = self.l.entries()
        self.assertEqual(len(e), ledger.KEEP)
        self.assertEqual(e[0]["sent"], f"q{ledger.KEEP + 4}")

    def test_broken_file_starts_fresh(self):
        self.path.write_text("{เสีย", encoding="utf-8")
        self.assertEqual(self.l.entries(), [])
        self.l.record("ask", "q")
        self.assertEqual(len(self.l.entries()), 1)

    @unittest.skipIf(sys.platform == "win32", "สิทธิ์ไฟล์แบบ POSIX")
    def test_file_is_private(self):
        self.l.record("ask", "q")
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    def test_cloud_client_records_exact_text_sent(self):
        from aipc.ui import app

        history = [{"role": "user", "content": "สวัสดี"}, {"role": "assistant", "content": "สวัสดีครับ"}]
        reply = ask.CloudReply(True, text="ตอบ", cost_usd=0.03)
        with mock.patch("aipc.cloud.ask.find_claude", return_value="claude"), \
             mock.patch("aipc.cloud.ask.ask", return_value=reply):  # fmt: skip
            run = app._cloud_client(self.l)
            run("อากาศวันนี้", history)
        e = self.l.entries()[0]
        self.assertEqual(e["sent"], ask.build_input("อากาศวันนี้", history))  # ตรงกับที่ส่งจริง
        self.assertEqual((e["kind"], e["cost_usd"], e["ok"]), ("ask", 0.03, True))

    def test_no_system_limit_however_much_is_used(self):
        """การ์ด 0084 C1: ค่าใช้จ่ายอ้างอิงเกิน $5 ในวันเดียว ยังถาม Claude และสร้างสกิลได้ทุกครั้ง."""
        from aipc.skills import forge
        from aipc.ui import app

        reply = ask.CloudReply(True, text="ตอบ", cost_usd=3.0)
        made = forge.Proposal(True, "สกิล", cost_usd=3.0)
        with mock.patch("aipc.cloud.ask.find_claude", return_value="claude"), \
             mock.patch("aipc.cloud.ask.ask", return_value=reply) as real, \
             mock.patch("aipc.skills.forge.forge", return_value=made) as real_forge, \
             mock.patch("aipc.skills.forge.run_process", return_value=(0, "2.1", "")):  # fmt: skip
            run, make = app._cloud_client(self.l), app._skill_forge(self.l)
            results = [run("อากาศ", []).ok for _ in range(3)] + [make("สกิล").ok for _ in range(3)]
        self.assertEqual(results, [True] * 6)
        self.assertEqual((real.call_count, real_forge.call_count), (3, 3))


if __name__ == "__main__":
    unittest.main()


class FileNeverLeavesTest(unittest.TestCase):
    """พบ 2026-10-05: ถามไฟล์ก่อน แล้วถามเรื่องที่ส่งต่อ Claude → เนื้อหาไฟล์ติดไปในบริบท."""

    def test_file_turn_and_its_answer_are_not_sent(self):
        history = [
            {"role": "user", "content": "สวัสดี"},
            {"role": "assistant", "content": "สวัสดีครับ"},
            {
                "role": "user",
                "content": "[ใบเสร็จ.pdf] ค่าซ่อมแอร์ 3,500 บาท เลขบัตร 1234\nคำถาม: จ่ายเท่าไร",
                "shown": "จ่ายเท่าไร",
                "file": "ใบเสร็จ.pdf",
            },
            {"role": "assistant", "content": "จ่ายไป 3,500 บาท"},
        ]
        sent = ask.build_input("ข่าววันนี้", history)
        for secret in ("ใบเสร็จ", "3,500", "1234"):
            self.assertNotIn(secret, sent)
        self.assertIn("สวัสดีครับ", sent)  # บทสนทนาอื่นยังเป็นบริบทได้
        self.assertIn("ข่าววันนี้", sent)
