import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from aipc.ui import files


class FilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        (self.home / "เอกสาร").mkdir(parents=True)
        (self.home / "b.txt").write_text("x" * 2048, encoding="utf-8")
        (self.home / "A.pdf").write_text("x", encoding="utf-8")
        (self.home / ".secret").write_text("x", encoding="utf-8")
        (Path(self.tmp.name) / "outside.txt").write_text("x", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_folders_first_then_names_and_hidden_skipped(self):
        names = [e.name for e in files.list_dir(self.home)]
        self.assertEqual(names, ["เอกสาร", "A.pdf", "b.txt"])

    def test_sizes(self):
        by_name = {e.name: e for e in files.list_dir(self.home)}
        self.assertEqual(by_name["b.txt"].size_text, "2.0 KB")
        self.assertEqual(by_name["เอกสาร"].size_text, "")

    def test_cannot_leave_home_with_dotdot(self):
        with self.assertRaises(files.OutsideHome):
            files.list_dir(self.home, "..")
        with self.assertRaises(files.OutsideHome):
            files.list_dir(self.home, "เอกสาร/../../")

    @unittest.skipUnless(hasattr(os, "symlink") and os.name == "posix", "symlink บน Linux")
    def test_symlink_pointing_outside_is_hidden(self):
        (self.home / "link").symlink_to(Path(self.tmp.name) / "outside.txt")
        self.assertNotIn("link", [e.name for e in files.list_dir(self.home)])

    def test_modified_today_vs_other_day(self):
        now = datetime(2026, 9, 23, 15, 0)
        self.assertEqual(files.modified(datetime(2026, 9, 23, 9, 5).timestamp(), now), "วันนี้ 09:05")
        self.assertEqual(files.modified(datetime(2026, 9, 1).timestamp(), now), "1 ก.ย. 2569")


if __name__ == "__main__":
    unittest.main()
