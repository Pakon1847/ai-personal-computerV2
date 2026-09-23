import unittest

from aipc.bench.stats import percentile_nearest_rank, summarize


class PercentileTest(unittest.TestCase):
    def test_p95_of_five_values_is_the_worst(self):
        # กฎที่ต้องเขียนในเล่ม: วัด 5 รอบ p95 = ค่าที่แย่ที่สุด
        self.assertEqual(percentile_nearest_rank([3, 1, 5, 2, 4], 95), 5)

    def test_p95_of_twenty_values_is_the_nineteenth(self):
        self.assertEqual(percentile_nearest_rank(list(range(1, 21)), 95), 19)

    def test_result_is_always_a_measured_value(self):
        values = [0.1, 0.7, 0.3, 0.9]
        self.assertIn(percentile_nearest_rank(values, 50), values)

    def test_rejects_empty_and_bad_pct(self):
        with self.assertRaises(ValueError):
            percentile_nearest_rank([], 95)
        with self.assertRaises(ValueError):
            percentile_nearest_rank([1], 0)


class SummarizeTest(unittest.TestCase):
    def test_median_ignores_one_outlier(self):
        s = summarize([1.0, 1.1, 0.9, 1.0, 50.0])
        self.assertEqual(s.median, 1.0)
        self.assertEqual(s.p95, 50.0)
        self.assertEqual((s.n, s.minimum, s.maximum), (5, 0.9, 50.0))


if __name__ == "__main__":
    unittest.main()
