"""ขั้น B (aipc.spikes.presence): ตัวคิดตัวชี้วัดจากข้อมูลจำลอง · ไม่ใช้กล้อง."""

import re
import unittest
from pathlib import Path

from aipc.spikes import presence as pr


def rows(spec):
    """spec = [(ตั้งแต่ t, ถึง t, จำนวนหน้า, ความคล้ายเจ้าของ หรือ None)] · ทุก 0.5 วิ · cpu โต 0.02 วิ/แถว."""
    out, cpu = [], 0.0
    for a, b, faces, sim in spec:
        t = a
        while t < b:
            r = {"t": round(t, 2), "faces": faces, "cpu": round(cpu, 2), "temp": 60.0}
            if sim is not None and faces and int(t * 2) % 4 == 0:  # SFace ทุก 2 วิ
                r["owner_sim"] = sim
            out.append(r)
            t += 0.5
            cpu += 0.02
    return out


PHASES = {"present": [[15, 115]], "away": [115, 175], "stranger": [175, 205], "back": [205, 235]}


class PresenceAnalyzeTest(unittest.TestCase):
    def test_all_criteria_pass_on_clean_session(self):
        data = rows(
            [
                (0, 15, 1, None),
                (15, 60, 1, 0.7),
                (60, 75, 0, None),
                (75, 115, 1, 0.7),
                (115, 175, 0, None),
                (175, 205, 1, 0.1),
                (205, 235, 1, 0.7),
            ]
        )
        res = pr.analyze(data, PHASES)
        self.assertEqual(res["max_gap_present"], 15.0)  # ก้มหน้า 15 วิ ยังไม่ถึง 30
        self.assertEqual(res["gaps_present"][">=10s"], 1)
        self.assertEqual(res["absent_detected_after_s"], 30.0)
        self.assertLessEqual(res["stranger_detected_after_s"], 10)
        self.assertEqual(res["false_stranger_present"], 0)
        self.assertEqual(res["cpu_pct_one_core"], 4.0)
        self.assertTrue(all(res["pass"].values()), res["pass"])

    def test_long_look_away_and_misrecognized_owner_fail(self):
        data = rows([(15, 40, 1, 0.7), (40, 75, 0, None), (75, 115, 1, 0.2), (115, 175, 0, None)])
        res = pr.analyze(data, PHASES)
        self.assertFalse(res["pass"]["M1_no_gap_30s_while_present"])
        self.assertFalse(res["pass"]["M3_no_false_stranger"])
        self.assertFalse(res["pass"]["M3_stranger_within_10s"])  # ไม่มีช่วงคนอื่นในข้อมูล

    def test_recorder_never_writes_images(self):
        src = Path(pr.__file__).read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"imwrite|imencode|\.save\(|VideoWriter\(", src))
