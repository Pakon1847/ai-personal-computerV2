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

    def test_parse_lfw_pairs(self):
        rows = ["2 1", "A 1 2", "B 1 C 2", "D 3 4", "E 1 F 1"]
        pairs = evaluate.parse_lfw_pairs(chr(10).join(r.replace(" ", chr(9)) for r in rows))
        self.assertEqual(pairs[0], ("A/A_0001.jpg", "A/A_0002.jpg", True, 0))
        self.assertEqual(pairs[1], ("B/B_0001.jpg", "C/C_0002.jpg", False, 0))
        self.assertEqual([p[3] for p in pairs], [0, 0, 1, 1])

    def test_parse_lfw_pairs_wrong_count(self):
        with self.assertRaises(ValueError):
            evaluate.parse_lfw_pairs(chr(10).join(["2 1", "A 1 2"]))

    def test_parse_lfw_pairs_bad_line(self):
        with self.assertRaises(ValueError):
            evaluate.parse_lfw_pairs(chr(10).join(["1 1", "A 1 2", "B 1 3 C 2"]))

if __name__ == "__main__":
    unittest.main()
