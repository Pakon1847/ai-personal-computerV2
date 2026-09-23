"""สรุปผลทดสอบใบหน้ากับคนจริง (aipc.vision.report) ด้วย log สังเคราะห์ที่นับคำตอบด้วยมือได้."""

import unittest

try:
    from aipc.vision import report
except ImportError:  # pragma: no cover
    report = None


def e(subject, account, reason="matched", ms=800.0):
    return {"subject": subject, "account": account, "reason": reason, "total_ms": ms}


@unittest.skipIf(report is None, "ไม่มี numpy")
class ReportTest(unittest.TestCase):
    def test_counts(self):
        log = [
            e("P01", "P01"), e("P01", "P01"), e("P01", None, "below_threshold"),
            e("P02", "P01"),  # ผิดคน
            e("P02", None, "spoof", 1200.0),
            {"account": "me", "reason": "matched"},  # ไม่มี subject = ใช้งานปกติ ไม่นับ
        ]  # fmt: skip
        s = report.summarize(log)
        self.assertEqual((s["attempts"], s["subjects"]), (5, 2))
        self.assertEqual(s["frr"], 0.4)  # ปฏิเสธ 2 จาก 5
        self.assertEqual(s["wrong_person"], 1)
        self.assertEqual(s["bpcer"], 0.2)
        self.assertEqual(s["per_subject"]["P01"]["correct"], 2)
        self.assertEqual(s["per_subject"]["P02"]["reason:spoof"], 1)
        self.assertEqual(s["time_ms"]["median"], 800.0)

    def test_verdict_needs_enough_data(self):
        s = report.summarize([e("P01", "P01")] * 10)
        v = report.verdicts(s)
        self.assertFalse(v["enough_data"], "1 คน 10 ครั้ง ยังไม่ถึง 5 คน × 50 ครั้ง")
        self.assertTrue(v["frr"] and v["wrong_person"] and v["time"])

    def test_full_pass(self):
        log = [e(f"P0{i}", f"P0{i}") for i in range(1, 6) for _ in range(50)]
        v = report.verdicts(report.summarize(log))
        self.assertTrue(all(v.values()), v)

    def test_one_wrong_person_fails(self):
        log = [e(f"P0{i}", f"P0{i}") for i in range(1, 6) for _ in range(50)] + [e("P01", "P02")]
        self.assertFalse(report.verdicts(report.summarize(log))["wrong_person"])


if __name__ == "__main__":
    unittest.main()
