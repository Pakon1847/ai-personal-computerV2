"""ตัวโหลดโมเดลใบหน้า (การ์ด 0005): sha256, กรอบของ PAD, โหลดได้จริงผ่าน OpenCV."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import cv2
    import numpy as np

    from aipc.vision import models
except ImportError:  # pragma: no cover
    models = None


@unittest.skipIf(models is None, "ไม่มี OpenCV")
class ModelFileTest(unittest.TestCase):
    def test_bundled_models_pass_sha256(self):
        for m in (models.YUNET, models.FAS_V2, models.FAS_V1SE):
            self.assertTrue(models.locate(m).exists())

    def test_tampered_file_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            fake = models.ModelFile("x.onnx", "0" * 64, url="https://example.invalid/x.onnx")
            (Path(d) / "x.onnx").write_bytes(b"not a model")
            with mock.patch.dict(os.environ, {"AIPC_MODEL_DIR": d}):
                with self.assertRaisesRegex(models.ModelError, "sha256"):
                    models.locate(fake)

    def test_shared_model_dir_is_used_when_user_has_none(self):
        with tempfile.TemporaryDirectory() as user, tempfile.TemporaryDirectory() as shared:
            fake = models.ModelFile(
                "x.onnx", models.sha256(Path(__file__)), url="https://x.invalid"
            )
            (Path(shared) / "x.onnx").write_bytes(Path(__file__).read_bytes())
            with mock.patch.dict(os.environ, {"AIPC_MODEL_DIR": user}):
                with mock.patch.object(models, "shared_dir", return_value=Path(shared)):
                    self.assertEqual(models.locate(fake), Path(shared) / "x.onnx")

    def test_missing_download_says_how_to_fetch(self):
        # ปิดที่เก็บกลางด้วย: บน Pi มีโมเดลจริงอยู่ที่ shared_dir → เดิมเทสต์นี้ล้มทุกครั้ง (หาเจอ ไม่ error)
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"AIPC_MODEL_DIR": d}):
            with mock.patch.object(models, "shared_dir", return_value=Path(d) / "none"):
                with self.assertRaisesRegex(models.ModelError, "fetch"):
                    models.locate(models.SFACE)

    def test_fetch_rejects_wrong_download_and_leaves_nothing(self):
        def fake_download(url, path):
            Path(path).write_bytes(b"evil")

        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"AIPC_MODEL_DIR": d}):
            with mock.patch("urllib.request.urlretrieve", fake_download):
                with self.assertRaises(models.ModelError):
                    models.fetch(models.SFACE)
            self.assertEqual(list(Path(d).iterdir()), [], "ห้ามทิ้งไฟล์ที่ไม่ผ่านไว้")


@unittest.skipIf(models is None, "ไม่มี OpenCV")
class FasBoxTest(unittest.TestCase):
    """กรอบของ PAD ต้องเหมือนต้นฉบับ (generate_patches._get_new_box)."""

    def test_centered_box_scaled(self):
        box = models.fas_box(1000, 1000, (450, 450, 100, 100), 2.7)
        self.assertEqual(box, (365, 365, 635, 635))

    def test_box_near_edge_is_shifted_not_shrunk(self):
        x0, y0, x1, y1 = models.fas_box(640, 480, (0, 0, 100, 100), 2.7)
        self.assertEqual((x0, y0), (0, 0))
        self.assertEqual((x1 - x0, y1 - y0), (270, 270))

    def test_scale_limited_by_image(self):
        x0, y0, x1, y1 = models.fas_box(300, 300, (100, 100, 100, 100), 4.0)
        self.assertLessEqual(x1, 299)
        self.assertGreaterEqual(x0, 0)


@unittest.skipIf(models is None, "ไม่มี OpenCV")
class LoadTest(unittest.TestCase):
    def test_detector_and_liveness_run_on_blank_frame(self):
        frame = np.full((240, 320, 3), 128, np.uint8)
        self.assertEqual(models.Detector().detect(frame), [], "ภาพว่างต้องไม่เจอหน้า")
        s = models.Liveness().score(frame, (100, 60, 120, 120))
        self.assertTrue(0.0 <= s <= 1.0)

    def test_embedder_if_downloaded(self):
        try:
            e = models.Embedder()
        except models.ModelError:
            self.skipTest("ยังไม่ได้ fetch SFace")
        v = e.embed(np.full((112, 112, 3), 128, np.uint8))
        self.assertEqual(v.shape, (128,))
        self.assertTrue(np.isfinite(v).all())
        self.assertIsNotNone(cv2)


@unittest.skipIf(models is None, "ไม่มี OpenCV")
class RescaleTest(unittest.TestCase):
    def test_coordinates_scaled_back_score_kept(self):
        row = np.array([10, 20, 30, 40, *range(10), 0.9], dtype=np.float32)
        (out,) = models.rescale([row], 0.5)
        self.assertEqual(out[:4].tolist(), [20, 40, 60, 80])
        self.assertEqual(out[4:14].tolist(), [v * 2 for v in range(10)])
        self.assertAlmostEqual(float(out[14]), 0.9, places=6)

    def test_large_frame_is_downscaled_for_detection(self):
        d = models.Detector(max_side=640)
        self.assertEqual(d.detect(np.full((720, 1280, 3), 128, np.uint8)), [])
        self.assertEqual(d._size, (640, 360), "หาหน้าบนภาพที่ย่อแล้ว")


if __name__ == "__main__":
    unittest.main()
