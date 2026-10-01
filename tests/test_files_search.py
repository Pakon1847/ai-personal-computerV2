"""ค้นไฟล์ด้วยเนื้อหา (aipc.files_search) · ชุดอิสระวัดแยกใน docs/benchmarks/2026-10-01-file-search."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aipc.files_search import HomeSearch, Index, candidates
from aipc.spikes.file_search_eval import evaluate

DATA = Path(__file__).parent / "data"


class IndexTest(unittest.TestCase):
    def test_dev_set_does_not_regress(self):
        # ชุดพัฒนา (ผู้ช่วยเห็นแล้ว) · ตอน commit ตัวค้น: R@1 17/20 · R@3 19/20
        res = evaluate(json.loads((DATA / "file_search_dev.json").read_text("utf-8")), "index")
        self.assertGreaterEqual(res["recall_at_1"], 17)
        self.assertGreaterEqual(res["recall_at_3"], 19)

    def test_snippet_from_best_chunk(self):
        long = "ก" * 400 + " ใบเสร็จค่าซ่อมแอร์ร้านช่างเอก 1,800 บาท " + "ข" * 400
        hits = Index([("a.txt", long), ("b.txt", "สูตรแกงเขียวหวานไก่")]).search("ซ่อมแอร์", 2)
        self.assertEqual(hits[0].name, "a.txt")
        self.assertIn("ซ่อมแอร์", hits[0].snippet)

    def test_no_match_returns_nothing(self):
        self.assertEqual(Index([("a.txt", "abc")]).search("ภาษาไทย"), [])


class HomeSearchTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root = Path(d.name)
        (self.root / "งาน").mkdir()
        (self.root / "งาน" / "receipt.txt").write_text("ใบเสร็จค่าซ่อมแอร์ 1,800 บาท", encoding="utf-8")
        (self.root / "recipe.md").write_text("สูตรแกงเขียวหวาน", encoding="utf-8")
        (self.root / ".cache").mkdir()
        (self.root / ".cache" / "secret.txt").write_text("ซ่อมแอร์ลับ", encoding="utf-8")
        (self.root / "photo.jpg").write_bytes(b"\xff\xd8")

    def test_skips_hidden_and_unsupported(self):
        paths, capped = candidates(self.root)
        names = sorted(p.name for p in paths)
        self.assertEqual(names, ["receipt.txt", "recipe.md"])
        self.assertFalse(capped)

    def test_search_and_cache(self):
        hs = HomeSearch(self.root)
        hits, n, _ = hs.search("ซ่อมแอร์อยู่ไหน")
        self.assertEqual((hits[0].name.replace(os.sep, "/"), n), ("งาน/receipt.txt", 2))
        with mock.patch("aipc.files_qa.extract", side_effect=AssertionError("อ่านซ้ำ")):
            hs.search("แกงเขียวหวาน")  # ไฟล์ไม่เปลี่ยน = ไม่อ่านใหม่


if __name__ == "__main__":
    unittest.main()
