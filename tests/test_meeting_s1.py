"""ตัววัด S1 ของการ์ด 0082: ตัวเลขต้องถูกก่อนจึงเชื่อผลได้ · ไม่ใช้เสียงจริง."""

import array
import unittest

from aipc.spikes import meeting_s1 as s


class CerTest(unittest.TestCase):
    def test_only_thai_letters_count(self):
        self.assertEqual(s.only_thai("สวัสดี 123, Hello!"), "สวัสดี")

    def test_perfect_and_wrong(self):
        self.assertEqual(s.cer("สวัสดีครับ", "สวัสดี ครับ."), 0.0)
        self.assertAlmostEqual(s.cer("กขคง", "กขจง"), 0.25)
        self.assertAlmostEqual(s.cer("กขคง", "กขค"), 0.25)
        self.assertAlmostEqual(s.cer("กขคง", ""), 1.0)

    def test_empty_reference_is_an_error(self):
        with self.assertRaises(ValueError):
            s.cer("123", "กข")

    def test_edit_distance_is_symmetric(self):
        self.assertEqual(s.edit_distance("กขค", "ขค"), s.edit_distance("ขค", "กขค"))
        self.assertEqual(s.edit_distance("", "กข"), 2)


def tone(seconds: float, level: int) -> array.array:
    n = int(seconds * s.RATE)
    return array.array("h", [level if i % 2 else -level for i in range(n)])


class SplitTest(unittest.TestCase):
    def spans(self, samples):
        return s.split_points(s.frame_levels(samples))

    def test_speech_separated_by_silence_makes_two_chunks(self):
        got = self.spans(tone(1, 0) + tone(2, 3000) + tone(1, 0) + tone(2, 3000) + tone(1, 0))
        self.assertEqual(len(got), 2)

    def test_silence_only_makes_no_chunk(self):
        self.assertEqual(self.spans(tone(3, 0)), [])
        self.assertEqual(s.split_points([]), [])

    def test_long_speech_is_cut_at_the_limit(self):
        got = self.spans(tone(65, 3000))
        limit = int(s.MAX_CHUNK_S / s.FRAME_S)
        self.assertGreaterEqual(len(got), 3)
        self.assertTrue(all(end - start <= limit for start, end in got))

    def test_no_speech_is_lost_between_chunks(self):
        got = self.spans(tone(65, 3000))
        for (_, end), (start, _) in zip(got, got[1:], strict=False):
            self.assertEqual(end, start)


if __name__ == "__main__":
    unittest.main()
