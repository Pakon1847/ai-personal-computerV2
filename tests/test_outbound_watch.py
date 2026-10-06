"""T6 แบบใหม่ (ร่างข้ออ้างรอบ 4 หัวข้อ 4): ตัวบันทึก/ตรวจการเชื่อมต่อขาออก ·
ใช้ผล ss ปลอมรูปแบบเดียวกับ Pi 5 จริง (2026-10-05)."""

import json
import tempfile
import unittest
from pathlib import Path

from aipc.cloud.ledger import Ledger
from aipc.spikes import outbound_watch as ow

SS = """udp 0      0      172.20.10.2:68    172.20.10.1:67
tcp 0      0      172.20.10.2:22    172.20.10.4:64631
tcp 0      0        127.0.0.1:8091    127.0.0.1:51854 users:(("llama-server",pid=5377,fd=4))
tcp 0      0      172.20.10.2:40112  160.79.104.10:443 users:(("claude",pid=901,fd=21))
tcp 0      0      172.20.10.2:40220  188.40.1.1:443 users:(("python",pid=777,fd=9))
"""
META = {"open_meteo_ips": {"api.open-meteo.com": ["188.40.1.1"]}}


class OutboundWatchTest(unittest.TestCase):
    def test_parse_and_drop_loopback(self):
        rows = [r for r in ow.parse_ss(SS) if ow.external(r)]
        self.assertEqual(len(rows), 5 - 1)
        self.assertEqual(rows[2]["procs"], ["claude"])

    def test_declared_paths_pass(self):
        rows = [r for r in ow.parse_ss(SS) if ow.external(r)]
        ledger = [{"kind": "ask", "sent": "คำถาม: ข่าววันนี้"}, {"kind": "weather", "sent": "เชียงใหม่"}]
        res = ow.check(rows, META, ledger, canary="CANARY-7Q4X")
        self.assertTrue(
            res["1_ours_only_to_declared"]
            and res["2_claude_has_ledger"]
            and res["3_canary_not_sent"]
        )
        self.assertIn("160.79.104.10:443", res["destinations"]["claude"])

    def test_our_process_to_unknown_host_fails(self):
        bad = SS + 'tcp 0 0 172.20.10.2:40300 93.184.216.34:443 users:(("python",pid=777,fd=10))\n'
        rows = [r for r in ow.parse_ss(bad) if ow.external(r)]
        res = ow.check(rows, META, [{"kind": "ask", "sent": "x"}], canary="C")
        self.assertFalse(res["1_ours_only_to_declared"])
        self.assertEqual(res["undeclared"][0]["peer"], "93.184.216.34:443")

    def test_claude_without_ledger_and_canary_leak_fail(self):
        rows = [r for r in ow.parse_ss(SS) if ow.external(r)]
        res = ow.check(rows, META, [], canary="C")
        self.assertFalse(res["2_claude_has_ledger"])
        res = ow.check(rows, META, [{"kind": "ask", "sent": "ใบเสร็จ C"}], canary="C")
        self.assertFalse(res["3_canary_not_sent"])

    def test_record_writes_meta_then_external_rows_and_check_reads_app_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "w.jsonl"
            t = iter([0.0, 0.0, 1.0, 5.0])
            n = ow.record(2, 1, out, run=lambda: SS, clock=lambda: next(t), sleep=lambda s: None)
            self.assertEqual(n, 4)
            meta, rows = ow.load_watch(out)
            self.assertIn("open_meteo_ips", meta)
            led = Ledger(Path(d) / "outbound.json")
            led.record("ask", "คำถาม: ข่าววันนี้")
            code = ow.main(["check", str(out), "--ledger", str(led.path), "--canary", "CANARY"])
            self.assertIn(
                code, (0, 1)
            )  # IP ของ Open-Meteo จริงไม่ตรงกับค่าปลอม · ตรวจแค่ว่าอ่านไฟล์ของแอปได้
            self.assertEqual(
                json.loads(out.read_text(encoding="utf-8").splitlines()[1])["proto"], "udp"
            )
