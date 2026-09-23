"""ตัวเลขประเมิน FAR/FRR/EER (การ์ด 0005) · ใช้ข้อมูลที่คำนวณคำตอบด้วยมือได้."""

import unittest

try:
    import numpy as np

    from aipc.vision import metrics
except ImportError:  # pragma: no cover
    np = None


@unittest.skipIf(np is None, "ไม่มี numpy")
class MetricsTest(unittest.TestCase):
    def test_hand_computed_rates(self):
        g = [0.9, 0.8, 0.7, 0.4]  # คนเดียวกัน
        i = [0.1, 0.2, 0.3, 0.75]  # คนละคน
        # ที่ 0.5: impostor 0.75 ผ่านเข้ามา 1/4 · genuine 0.4 ถูกปฏิเสธ 1/4
        self.assertEqual(metrics.rates_at(g, i, 0.5), (0.25, 0.25))
        self.assertEqual(metrics.rates_at(g, i, 0.76), (0.0, 0.5))
        self.assertEqual(metrics.rates_at(g, i, 0.0), (1.0, 0.0))

    def test_curve_matches_rates_at_every_threshold(self):
        rng = np.random.default_rng(0)
        g, i = rng.normal(0.6, 0.1, 300), rng.normal(0.2, 0.1, 500)
        c = metrics.curve(g, i)
        for k in range(0, len(c.thresholds) - 1, 37):
            self.assertEqual((c.far[k], c.frr[k]), metrics.rates_at(g, i, c.thresholds[k]))
        self.assertTrue(np.all(np.diff(c.far) <= 0), "FAR ต้องไม่เพิ่มเมื่อ threshold สูงขึ้น")
        self.assertTrue(np.all(np.diff(c.frr) >= 0))
        self.assertEqual((c.far[-1], c.frr[-1]), (0.0, 1.0))

    def test_perfect_separation_has_zero_eer(self):
        rate, t = metrics.eer(metrics.curve([0.8, 0.9, 0.95], [0.1, 0.2, 0.3]))
        self.assertAlmostEqual(rate, 0.0)
        self.assertTrue(0.3 <= t <= 0.8)

    def test_symmetric_overlap_eer(self):
        # สองกลุ่มกระจายสมมาตรรอบ 0.5 → EER ที่ threshold ≈ 0.5
        rng = np.random.default_rng(1)
        g = rng.normal(0.6, 0.1, 20000)
        i = rng.normal(0.4, 0.1, 20000)
        rate, t = metrics.eer(metrics.curve(g, i))
        self.assertAlmostEqual(t, 0.5, delta=0.01)
        # ทฤษฎี: EER = P(N(0.6, 0.1) < 0.5) = Φ(−1) ≈ 0.1587
        self.assertAlmostEqual(rate, 0.1587, delta=0.01)

    def test_threshold_at_far(self):
        i = np.linspace(0, 1, 1000, endpoint=False)  # impostor กระจายเท่า ๆ กัน 0–1
        g = np.full(10, 0.95)
        t, far, frr = metrics.at_far(metrics.curve(g, i), 0.001)
        self.assertLessEqual(far, 0.001)
        self.assertAlmostEqual(t, 0.999, places=6)
        self.assertEqual(frr, 1.0, "genuine 0.95 ต่ำกว่า threshold ทั้งหมด")

    def test_empty_input_rejected(self):
        with self.assertRaises(ValueError):
            metrics.curve([], [0.1])


if __name__ == "__main__":
    unittest.main()
