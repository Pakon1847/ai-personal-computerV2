"""ที่เก็บแม่แบบใบหน้า (การ์ด 0005 ข้อ 5): ความยินยอม, ไฟล์เสีย, โมเดลเปลี่ยน, ลบแล้วไม่เหลือ."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import numpy as np

    from aipc.vision import matching, store
except ImportError:  # pragma: no cover
    np = None

NOW = "2026-09-24T10:00:00+07:00"


@unittest.skipIf(np is None, "ไม่มี numpy")
class FaceStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "face-template.json"
        self.s = store.FaceStore(self.path, model_sha256="abc")
        self.vec = matching.l2_normalize(np.random.default_rng(3).normal(size=128))
        self.consent = store.Consent(NOW)

    def test_roundtrip(self):
        self.s.save(self.vec, 6, NOW, self.consent)
        got = self.s.load()
        self.assertTrue(np.allclose(got.vector, self.vec, atol=1e-6))
        self.assertEqual((got.frames, got.created), (6, NOW))
        self.assertEqual(got.consent.version, store.CONSENT_VERSION)

    def test_no_consent_no_save(self):
        with self.assertRaises(PermissionError):
            self.s.save(self.vec, 6, NOW, None)
        with self.assertRaises(PermissionError):
            self.s.save(self.vec, 6, NOW, store.Consent(""))
        self.assertFalse(self.path.exists())

    def test_file_has_no_image_and_is_private(self):
        self.s.save(self.vec, 6, NOW, self.consent)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        keys = {"version", "model_sha256", "vector_f32_b64", "frames", "created", "consent"}
        self.assertEqual(set(data), keys)
        self.assertLess(self.path.stat().st_size, 2000, "มีแค่ตัวเลข 128 ค่า ไม่ใช่ภาพ")
        if sys.platform != "win32":
            self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    def test_corrupt_file_falls_back_to_backup(self):
        self.s.save(self.vec, 6, NOW, self.consent)
        self.s.save(self.vec, 7, NOW, self.consent)  # รุ่นแรกไปอยู่ .bak
        self.path.write_text("{เสีย", encoding="utf-8")
        self.assertEqual(self.s.load().frames, 6)

    def test_both_corrupt_reports_problem(self):
        self.path.write_text("x", encoding="utf-8")
        self.assertIsNone(self.s.load())
        self.assertIn("เสีย", self.s.problem)

    def test_model_change_invalidates_template(self):
        self.s.save(self.vec, 6, NOW, self.consent)
        newer = store.FaceStore(self.path, model_sha256="def")
        self.assertIsNone(newer.load())
        self.assertIn("ลงทะเบียนใหม่", newer.problem)

    def test_delete_leaves_nothing(self):
        self.s.save(self.vec, 6, NOW, self.consent)
        self.s.save(self.vec, 6, NOW, self.consent)
        self.s.tmp.write_text("ค้าง", encoding="utf-8")
        self.assertTrue(self.s.delete())
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])
        self.assertIsNone(self.s.load())
        self.assertEqual(self.s.problem, "")
        self.assertFalse(self.s.delete(), "ลบซ้ำ = ไม่มีอะไรให้ลบ")

    def test_wrong_size_rejected(self):
        with self.assertRaises(ValueError):
            self.s.save(np.ones(64), 6, NOW, self.consent)


if __name__ == "__main__":
    unittest.main()
