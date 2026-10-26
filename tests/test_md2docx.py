"""ตัวแปลงเล่ม (docs/thesis/tools/md2docx.py) · Pakon 2026-10-26.

เลขอ้างอิงตามลำดับที่อ้างครั้งแรก + ตารางระยะเวลาแบบลูกศรตามแม่แบบ
"""

import importlib.util
import re
import sys
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "docs" / "thesis" / "tools" / "md2docx.py"
_spec = importlib.util.spec_from_file_location("md2docx", TOOL)
md2docx = importlib.util.module_from_spec(_spec)
sys.modules["md2docx"] = md2docx
_spec.loader.exec_module(md2docx)


class CitationTest(unittest.TestCase):
    def test_numbers_follow_first_use_across_chapters(self):
        ch1 = "ข้อมูลอ่อนไหว [R31] และบอร์ด [R1] <!-- [R9] ในคอมเมนต์ไม่นับ -->"
        ch2 = "อีกครั้ง [R1] แล้ว [R10] [R31]"
        order = md2docx.cite_order([ch1, ch2])
        self.assertEqual(order, {31: 1, 1: 2, 10: 3})
        self.assertEqual(md2docx.renumber_cites(ch2, order), "อีกครั้ง [2] แล้ว [3] [1]")

    def test_references_sorted_by_new_number_and_unused_kept_last(self):
        refs = "# บรรณานุกรม\n\n[1]\tหนึ่ง\n\n[9]\tเก้า\n\n[10]\tสิบ\n\n[31]\tสามสิบเอ็ด\n"
        out = md2docx.renumber_refs(refs, {31: 1, 1: 2, 10: 3})
        self.assertEqual(out, "# บรรณานุกรม\n\n[1]\tสามสิบเอ็ด\n\n[2]\tหนึ่ง\n\n[3]\tสิบ\n\n[4]\tเก้า\n")

    def test_cited_but_missing_reference_stops_the_build(self):
        with self.assertRaises(SystemExit):
            md2docx.renumber_refs("[1]\tหนึ่ง\n", {1: 1, 2: 2})


class GanttTest(unittest.TestCase):
    ROWS = [
        ["รายการ \\ เวลา", "2569/ก.ค.", "2569/ส.ค.", "2569/ก.ย.", "2569/ต.ค."],
        ["1. ศึกษา", "20–31", "↔", "1–22", ""],
        ["2. พัฒนา", "", "", "23–30", "1–26"],
        ["3. นำเสนอ", "", "", "", ""],
    ]

    def test_one_arrow_per_run_and_year_spans_all_months(self):
        xml = md2docx.gantt(self.ROWS)
        self.assertEqual(xml.count("<wp:anchor"), 2)
        self.assertEqual(xml.count('<w:gridSpan w:val="4"/>'), 1)
        self.assertIn("<w:tl2br", xml)  # ช่องหัวเส้นทแยง
        self.assertEqual(md2docx.TEXT_W, sum(map(int, re.findall(r'gridCol w:w="(\d+)"', xml))))

    def test_arrow_starts_and_ends_at_day_in_month(self):
        xml = md2docx.gantt(self.ROWS)
        col = int(re.findall(r'gridCol w:w="(\d+)"', xml)[1])
        offsets = [int(x) // 635 for x in re.findall(r"<wp:posOffset>(-?\d+)<", xml)[0::2]]
        widths = [int(x) // 635 for x in re.findall(r'<wp:extent cx="(\d+)"', xml)]
        # แถว 1: เริ่มวันที่ 20 ก.ค. จบวันที่ 22 ก.ย. (ช่องที่ 3)
        left = int(19 / 31 * col) + md2docx.ARROW_INSET
        self.assertAlmostEqual(offsets[0], left - md2docx.CELL_MARGIN, delta=1)
        self.assertAlmostEqual(
            widths[0], int((2 + 22 / 31) * col) - md2docx.ARROW_INSET - left, delta=1
        )
        # แถว 2: เริ่ม 23 ก.ย. ยาวข้ามไปถึง 26 ต.ค.
        self.assertGreater(widths[1], col)

    def test_short_task_still_draws_a_visible_arrow(self):
        rows = [self.ROWS[0], ["งานสั้น", "", "", "23–29", ""]]
        width = int(re.search(r'<wp:extent cx="(\d+)"', md2docx.gantt(rows)).group(1)) // 635
        self.assertEqual(width, md2docx.ARROW_MIN)

    def test_plain_tables_unchanged(self):
        md = "ตารางที่ 1.1 ทดสอบ\n\n| ก | ข |\n|---|---|\n| 1 | 2 |\n"
        body, _ = md2docx.convert(md, md2docx.Numbering())
        self.assertNotIn("<wp:anchor", body)
        self.assertNotIn("<w:tl2br", body)


if __name__ == "__main__":
    unittest.main()
