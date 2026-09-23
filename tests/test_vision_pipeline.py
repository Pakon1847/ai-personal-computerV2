"""pipeline ใบหน้า (การ์ด 0005) ด้วยตัวตรวจหน้า/PAD/embedding ปลอม · ไม่ต้องมีกล้องหรือโมเดล."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import numpy as np

    from aipc.vision import matching, pipeline
    from aipc.vision.config import FaceConfig
    from tests.test_vision_core import frontal, textured
except ImportError:  # pragma: no cover
    np = None


def row(box=(220, 140, 200, 200), score=0.95, **kw):
    """แถวผลลัพธ์แบบ YuNet: x, y, w, h, 5×(x, y), score."""
    pts = [c for p in frontal(**kw) for c in p]
    return np.array([*box, *pts, score], dtype=np.float32)


class Scripted:
    """คืนค่าตามลำดับที่เตรียมไว้ทีละครั้ง (แทนโมเดลจริง)."""

    def __init__(self, values):
        self.values = list(values)
        self.calls = 0

    def next(self):
        self.calls += 1
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]


class FakeDetector(Scripted):
    def detect(self, frame):
        return self.next()


class FakeLiveness(Scripted):
    def score(self, frame, box):
        return self.next()


class FakeEmbedder(Scripted):
    def embed(self, aligned):
        assert aligned.shape == (112, 112, 3), "ต้องได้หน้าที่ align แล้ว"
        return self.next()


class Base(unittest.TestCase):
    """ของที่เทสต์สแกนและลงทะเบียนใช้ร่วมกัน (ไม่มีเทสต์ในตัว)."""

    def setUp(self):
        rng = np.random.default_rng(7)
        self.alice, self.bob = (matching.l2_normalize(rng.normal(size=128)) for _ in range(2))
        self.templates = {"alice": self.alice, "bob": self.bob}
        self.frame = textured()
        self.cfg = FaceConfig()

    def near(self, v, seed):
        return v + 0.03 * np.random.default_rng(seed).normal(size=v.shape)

    def scanner(self, rows, live=(0.99,), embs=None):
        embs = embs or [self.near(self.alice, s) for s in range(10)]
        fakes = FakeDetector(rows), FakeLiveness(live), FakeEmbedder(embs)
        return pipeline.FaceScanner(*fakes, self.cfg)


@unittest.skipIf(np is None, "ไม่มี numpy")
class PipelineTest(Base):
    def test_scan_matches_with_timings(self):
        s = self.scanner([[row()]])
        res = s.scan([self.frame] * 8, self.templates)
        self.assertEqual((res.account, res.reason), ("alice", "matched"))
        self.assertEqual(res.frames_used, 5)
        self.assertEqual(res.frames_seen, 5, "ครบ max_frames แล้วต้องหยุดอ่านเฟรม")
        for step in ("detect", "quality", "liveness", "align", "embed", "match"):
            self.assertIn(step, res.timings_ms)
        self.assertGreaterEqual(res.total_ms, 0)

    def test_spoof_rejects_immediately(self):
        s = self.scanner([[row()]], live=[0.99, 0.2, 0.99])
        res = s.scan([self.frame] * 8, self.templates)
        self.assertEqual((res.account, res.reason, res.frames_seen), (None, "spoof", 2))
        self.assertIn("ใช้รหัสผ่าน", res.advice)

    def test_not_enough_good_frames_gives_quality_advice(self):
        small = [row(box=(300, 200, 60, 60), eye=20)]
        s = self.scanner([[row()], [row()], small, small, small, small])
        res = s.scan([self.frame] * 6, self.templates)
        self.assertEqual((res.reason, res.frames_used), ("not_enough_frames", 2))
        self.assertIn("ยังได้ภาพที่ชัดไม่พอ", res.advice)
        self.assertEqual(res.last_advice, "ขยับเข้ามาใกล้อีกนิด")

    def test_second_big_face_is_refused(self):
        other = row(box=(20, 140, 180, 180), cx=110)
        r = self.scanner([[row(), other]]).process(self.frame)
        self.assertEqual((r.ok, r.reason), (False, "multiple_faces"))

    def test_small_face_far_behind_is_ignored(self):
        far = row(box=(20, 20, 40, 40), cx=40, cy=40, eye=12)
        self.assertTrue(self.scanner([[row(), far]]).process(self.frame).ok)

    def test_low_detector_score_counts_as_no_face(self):
        r = self.scanner([[row(score=0.3)]]).process(self.frame)
        self.assertEqual(r.reason, "no_face")

    def test_stranger_is_not_matched(self):
        rng = np.random.default_rng(99)
        stranger = [rng.normal(size=128) for _ in range(6)]
        res = self.scanner([[row()]], embs=stranger).scan([self.frame] * 6, self.templates)
        self.assertEqual((res.account, res.reason), (None, "below_threshold"))

    def test_embedding_is_unit_length(self):
        r = self.scanner([[row()]], embs=[np.full(128, 5.0)]).process(self.frame)
        self.assertAlmostEqual(float(np.linalg.norm(r.embedding)), 1.0, places=5)


@unittest.skipIf(np is None, "ไม่มี numpy")
class EnrollTest(Base):
    POSES = {"front": {}, "left": {"yaw_shift": -0.3}, "right": {"yaw_shift": 0.3}}

    def test_enroll_needs_front_left_right(self):
        order = ("front", "left", "right") * 2
        rows = [[row(**self.POSES[p])] for p in order]
        t = self.scanner(rows).enroll([self.frame] * 10)
        self.assertIsInstance(t, pipeline.Template)
        self.assertEqual(t.frames, 6)
        self.assertGreater(matching.cosine(t.vector, self.alice), 0.95)

    def test_missing_pose_is_rejected_with_advice(self):
        rows = [[row(**self.POSES[p])] for p in ("front", "left", "front", "left")]
        r = self.scanner(rows).enroll([self.frame] * 4)
        self.assertIsInstance(r, pipeline.Rejected)
        self.assertEqual(r.reasons, ("right",))
        self.assertIn("หันขวาเล็กน้อย", r.advice)

    def test_low_quality_frames_not_used(self):
        blurry_small = [row(box=(300, 200, 60, 60), eye=20)]
        r = self.scanner([blurry_small]).enroll([self.frame] * 5)
        self.assertIsInstance(r, pipeline.Rejected)
        self.assertIn("ขยับเข้ามาใกล้อีกนิด", r.advice)

    def test_spoof_during_enroll_cancels(self):
        r = self.scanner([[row()]], live=[0.99, 0.1]).enroll([self.frame] * 6)
        self.assertEqual(r.reasons, ("spoof",))


@unittest.skipIf(np is None, "ไม่มี numpy")
class ScanLogTest(unittest.TestCase):
    def test_log_has_no_image_or_embedding(self):
        res = pipeline.ScanResult("alice", "matched", 0.71234, 0.2, 5, 6, {"embed": 12.34}, 150.0)
        with tempfile.TemporaryDirectory() as d:
            log = pipeline.ScanLog(Path(d) / "scans.log")
            log.write(res)
            log.write(pipeline.ScanResult(None, "spoof", frames_seen=2))
            lines = [json.loads(x) for x in log.path.read_text(encoding="utf-8").splitlines()]
            if sys.platform != "win32":
                self.assertEqual(os.stat(log.path).st_mode & 0o777, 0o600)
        self.assertEqual(len(lines), 2)
        for entry in lines:
            self.assertEqual(set(entry), set(pipeline.ScanLog.FIELDS))
        self.assertEqual((lines[0]["result"], lines[0]["score"]), ("matched", 0.7123))
        self.assertEqual((lines[1]["result"], lines[1]["account"]), ("rejected", None))


if __name__ == "__main__":
    unittest.main()
