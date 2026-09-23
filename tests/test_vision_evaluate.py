"""ส่วนเตรียมคู่ภาพของ evaluate.py (การ์ด 0005) · ส่วนที่ต้องใช้โมเดลรันด้วยมือกับชุดข้อมูลจริง."""

import tempfile
import unittest
from pathlib import Path

try:
    from aipc.vision import evaluate
except ImportError:  # pragma: no cover
    evaluate = None


@unittest.skipIf(evaluate is None, "ไม่มี numpy")
class PairsTest(unittest.TestCase):
    IDS = {"a": [0, 1, 2], "b": [3, 4], "c": [5]}
    OWNER = {i: n for n, idx in IDS.items() for i in idx}

    def test_genuine_same_person_impostor_different(self):
        g, i = evaluate.make_pairs(self.IDS, 100, 10, seed=0)
        self.assertEqual(sorted(g), [(0, 1), (0, 2), (1, 2), (3, 4)])
        self.assertEqual(len(i), 10)
        for a, b in i:
            self.assertNotEqual(self.OWNER[a], self.OWNER[b])
        self.assertEqual(len(set(i)), len(i), "คู่ impostor ต้องไม่ซ้ำ")

    def test_same_seed_same_pairs(self):
        first = evaluate.make_pairs(self.IDS, 2, 5, seed=7)
        self.assertEqual(first, evaluate.make_pairs(self.IDS, 2, 5, seed=7))

    def test_caps_are_respected(self):
        g, i = evaluate.make_pairs(self.IDS, 2, 3, seed=1)
        self.assertEqual((len(g), len(i)), (2, 3))

    def test_impossible_impostor_count_stops(self):
        _, i = evaluate.make_pairs({"a": [0, 1], "b": [2]}, 10, 1000, seed=0)
        self.assertEqual(len(i), 2, "มีคู่ต่างคนได้แค่ 2 คู่ ต้องไม่วนไม่จบ")

    def test_list_people_skips_non_images(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "x").mkdir()
            (Path(d) / "x" / "1.jpg").write_bytes(b"")
            (Path(d) / "x" / "notes.txt").write_text("")
            (Path(d) / "empty").mkdir()
            people = evaluate.list_people(Path(d))
        self.assertEqual(list(people), ["x"])
        self.assertEqual([p.name for p in people["x"]], ["1.jpg"])


if __name__ == "__main__":
    unittest.main()
