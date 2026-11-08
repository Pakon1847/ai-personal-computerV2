"""แชร์สกิลด้วย QR (การ์ด 0080) · H1 (ผ่านด่านทุกครั้ง) · H2 ส่วนดิจิทัล (สร้างรูปแล้วอ่านกลับตรงทุกไบต์) · ไม่ต่อเน็ต.

H2 ตัวจริงต้องอ่านด้วยกล้อง Pi ( ยังไม่ได้วัด ) · ตรงนี้ตรวจว่ารูป PNG ที่ระบบสร้างอ่านกลับได้ตรงทุกไบต์
"""

import json
import tempfile
import unittest
import zlib
from pathlib import Path

from aipc.skills import share

ROOT = Path(__file__).resolve().parent.parent
SETS = sorted((ROOT / "tests/data").glob("skill_guard_*s1.json"))
ITEMS = [i for p in SETS for i in json.loads(p.read_text(encoding="utf-8"))["items"]]
GOOD = [i for i in ITEMS if i["label"] == "good"]
BAD = [i for i in ITEMS if i["label"] == "bad"]


class CodecTest(unittest.TestCase):
    def test_round_trip_and_size(self):
        md = (ROOT / "docs/benchmarks/2026-09-30-skill-author/claude/s2.md").read_text(
            encoding="utf-8"
        )
        text = share.encode(md)
        self.assertTrue(text.startswith(share.PREFIX))
        self.assertLess(len(text), len(md.encode("utf-8")), "บีบแล้วต้องเล็กกว่าไฟล์เดิม")
        self.assertEqual(share.decode(text), md)

    def test_too_big_for_one_qr(self):
        import os

        noise = os.urandom(4000).hex()  # บีบไม่ลง
        with self.assertRaises(share.ShareError) as ctx:
            share.encode("---\nid: x\n---\n" + noise)
        self.assertIn("ส่งออกเป็นไฟล์", str(ctx.exception))

    def test_bad_payloads_are_refused_with_reasons(self):
        for text, word in (("https://example.com", "ไม่ใช่สกิล"), (share.PREFIX + "!!!", "ข้อมูลเสีย"),
                           (share.PREFIX + "aGVsbG8=", "ข้อมูลเสีย")):  # fmt: skip
            with self.assertRaises(share.ShareError) as ctx:
                share.decode(text)
            self.assertIn(word, str(ctx.exception))
        import base64

        bomb = share.PREFIX + base64.urlsafe_b64encode(zlib.compress(b"a" * 10_000_000)).decode()
        with self.assertRaises(share.ShareError) as ctx:
            share.decode(bomb)
        self.assertIn("ใหญ่ผิดปกติ", str(ctx.exception))


class ImageTest(unittest.TestCase):
    def test_h2_digital_every_good_skill_reads_back_byte_exact(self):
        """สกิลดีทุกตัวจากชุดวัด 0074 (คนอื่นเขียน) → PNG → อ่านกลับ = ตรงทุกไบต์ · ใหญ่เกิน 1 QR นับแยก."""
        exact, too_big = 0, 0
        with tempfile.TemporaryDirectory() as d:
            for i, it in enumerate(GOOD):
                path = Path(d) / f"ภาพ-{i}.png"  # ชื่อไทย: วินโดวส์ต้องเขียน/อ่านได้
                try:
                    share.write_png(it["md"], path)
                except share.ShareError:
                    too_big += 1
                    continue
                exact += share.read_image(path) == it["md"]
        self.assertGreaterEqual(len(GOOD), 20)
        self.assertEqual(exact + too_big, len(GOOD), "ที่สร้าง QR ได้ต้องอ่านกลับตรงทุกตัว")
        self.assertEqual(too_big, 0, f"สกิลดีที่ใหญ่เกิน 1 QR: {too_big}")

    def test_image_without_qr(self):
        import cv2
        import numpy as np

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "blank.png"
            p.write_bytes(cv2.imencode(".png", np.full((200, 200), 255, np.uint8))[1].tobytes())
            with self.assertRaises(share.ShareError) as ctx:
                share.read_image(p)
            self.assertIn("ไม่พบ QR", str(ctx.exception))
            (Path(d) / "x.png").write_bytes(b"not an image")
            with self.assertRaises(share.ShareError):
                share.read_image(Path(d) / "x.png")


try:
    from PySide6.QtCore import QCoreApplication

    from aipc.skills import manifest, userskills
    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class ControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root = Path(d.name)
        self.store = userskills.UserSkills(self.root / "skills")
        self.s = SkillsController(reminders_path=self.root / "r.json", run_timer=False,
                                  llm_ready=lambda: True, user_skills=self.store)  # fmt: skip

    def test_h1_every_bad_skill_via_qr_still_meets_the_gate(self):
        """สกิลเสียทุกตัวของชุดวัด 0074 ส่งผ่าน QR → ทาง QR ต้องไม่รับตัวที่ด่านไม่รับ (ทางเดียวกับไฟล์ .md).

        อ่าน QR ไม่ได้ = ไม่ติดตั้ง (ปลอดภัย) · นับแยกไว้ (วัด 2026-11-07: 1 จาก 211 รูปของทุกชุด)
        """
        builtin = manifest.load_builtin()
        leaked, unreadable = [], []
        for i, it in enumerate(BAD):
            try:
                path = self.root / f"bad-{i}.png"
                share.write_png(it["md"], path)
            except share.ShareError:
                continue  # ใหญ่เกิน QR = แชร์ทางนี้ไม่ได้เลย
            msg = self.s.importSkill(str(path), False)
            if msg.startswith("ไม่พบ QR"):
                unreadable.append(it["id"])
            elif "กดอีกครั้ง" in msg and userskills.gate(it["md"], builtin)[0] is None:
                leaked.append(it["id"])
        self.assertEqual(leaked, [])
        self.assertLessEqual(len(unreadable), 2, unreadable)
        self.assertEqual(self.store.load_all(), [], "ดูก่อน (install=False) ต้องไม่ติดตั้งอะไร")

    def test_share_then_import_on_another_account(self):
        md = (ROOT / "docs/benchmarks/2026-09-30-skill-author/claude/l3.md").read_text(
            encoding="utf-8"
        )
        self.store.install(md, manifest.load_builtin(), request="คิดเมนู")
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"HOME": str(self.root), "USERPROFILE": str(self.root)}):
            r = self.s.shareSkillQr("fridge-menu")
        self.assertTrue(r["path"], r["message"])
        self.assertIn("ติดตั้งสกิลจาก QR", r["message"])
        friend = userskills.UserSkills(self.root / "friend")
        f = SkillsController(reminders_path=self.root / "r2.json", run_timer=False,
                             llm_ready=lambda: True, user_skills=friend)  # fmt: skip
        self.assertIn("กดอีกครั้ง", f.importSkill(r["path"], False))
        self.assertEqual(friend.load_all(), [])
        self.assertIn("ติดตั้งสกิล", f.importSkill(r["path"], True))
        self.assertEqual(friend.current_md("fridge-menu"), md)
        self.assertIn("แชร์ได้เฉพาะ", self.s.shareSkillQr("translate")["message"])


if __name__ == "__main__":
    unittest.main()
