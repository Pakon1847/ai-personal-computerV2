"""แกนของระบบใบหน้า (การ์ด 0005): ค่าตั้ง, quality gate, align, จับคู่ · ใช้ภาพสังเคราะห์ ไม่ต้องมีกล้อง/โมเดล."""

import json
import math
import tempfile
import unittest
from pathlib import Path

try:
    import numpy as np

    from aipc.vision import align, config, matching, quality
    from aipc.vision.quality import Face
except ImportError:  # pragma: no cover
    np = None

CFG = config.FaceConfig() if np is not None else None


def frontal(cx=320.0, cy=240.0, eye=60.0, yaw_shift=0.0, nose_down=0.57):
    """5 จุดของหน้าตรงขนาดตาห่าง `eye` px · yaw_shift = จมูกเลื่อนไปข้าง (เท่าของครึ่งระยะตา)."""
    ey, my = cy - 0.4 * eye, cy + 0.6 * eye
    nose = (cx + yaw_shift * eye / 2, ey + nose_down * (my - ey))
    eyes = ((cx - eye / 2, ey), (cx + eye / 2, ey))
    return (*eyes, nose, (cx - eye * 0.4, my), (cx + eye * 0.4, my))


def textured(h=480, w=640, level=128, amp=60, seed=0):
    """ภาพที่มีรายละเอียด (เหมือนผิว/ขน) · amp สูง = คม."""
    rng = np.random.default_rng(seed)
    img = level + rng.normal(0, amp, (h, w, 3))
    return np.clip(img, 0, 255).astype(np.uint8)


def blur(img, times=6):
    out = img.astype(np.float64)
    for _ in range(times):  # เบลอด้วยค่าเฉลี่ย 3×3 ซ้ำหลายรอบ (ไม่พึ่ง OpenCV)
        p = np.pad(out, ((1, 1), (1, 1), (0, 0)), mode="edge")
        h, w = out.shape[:2]
        out = sum(p[i : i + h, j : j + w] for i in range(3) for j in range(3)) / 9
    return out.astype(np.uint8)


def face(box=(220, 140, 200, 200), **kw):
    return Face(box, frontal(**kw))


@unittest.skipIf(np is None, "ไม่มี numpy")
class ConfigTest(unittest.TestCase):
    def test_defaults_are_valid(self):
        self.assertEqual(config.FaceConfig().validate().min_face_px, 112)

    def test_file_overrides_only_given_values(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "face.json"
            p.write_text(json.dumps({"match_threshold": 0.5, "max_frames": 4}), encoding="utf-8")
            c = config.load(p)
        self.assertEqual((c.match_threshold, c.max_frames, c.min_frames), (0.5, 4, 3))

    def test_unknown_or_invalid_values_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "face.json"
            p.write_text(json.dumps({"match_treshold": 0.5}), encoding="utf-8")  # พิมพ์ผิด
            with self.assertRaises(ValueError):
                config.load(p)
            p.write_text(json.dumps({"min_frames": 6, "max_frames": 3}), encoding="utf-8")
            with self.assertRaises(ValueError):
                config.load(p)

    def test_missing_file_is_default(self):
        self.assertEqual(config.load(Path("/nonexistent/face.json")), config.FaceConfig())

    def test_template_poses_from_file_and_must_keep_front(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "face.json"
            p.write_text(json.dumps({"template_poses": ["front", "left", "right", "up"]}), "utf-8")
            self.assertEqual(config.load(p).template_poses, ("front", "left", "right", "up"))
            for bad in (["left", "right"], ["front", "sideways"]):
                p.write_text(json.dumps({"template_poses": bad}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    config.load(p)


@unittest.skipIf(np is None, "ไม่มี numpy")
class QualityGateTest(unittest.TestCase):
    def test_good_frontal_face_passes(self):
        q = quality.check(textured(), face(), CFG)
        self.assertTrue(q.ok, q.reasons)
        self.assertEqual(q.advice, "")

    def test_no_face(self):
        q = quality.check(textured(), None, CFG)
        self.assertEqual(q.reasons, ("no_face",))
        self.assertIn("ไม่พบใบหน้า", q.advice)

    def test_too_small(self):
        q = quality.check(textured(), face(box=(300, 200, 80, 80), eye=24), CFG)
        self.assertIn("too_small", q.reasons)
        self.assertEqual(q.advice, "ขยับเข้ามาใกล้อีกนิด")

    def test_exactly_112_is_enough(self):
        q = quality.check(textured(), face(box=(260, 180, 112, 112)), CFG)
        self.assertNotIn("too_small", q.reasons)

    def test_too_dark_and_too_bright(self):
        dark = quality.check(textured(level=25, amp=20), face(), CFG)
        self.assertEqual(dark.advice, "แสงน้อยเกินไป · หาที่สว่างขึ้น")
        bright = quality.check(textured(level=240, amp=20), face(), CFG)
        self.assertIn("too_bright", bright.reasons)

    def test_blurry(self):
        q = quality.check(blur(textured()), face(), CFG)
        self.assertIn("blurry", q.reasons)
        self.assertLess(q.sharpness, CFG.min_sharpness)

    def test_turned_left_right_up_down(self):
        for kw in ({"yaw_shift": 0.6}, {"yaw_shift": -0.6}, {"nose_down": 0.1}, {"nose_down": 0.8}):
            with self.subTest(**kw):
                self.assertIn("turned", quality.check(textured(), face(**kw), CFG).reasons)

    def test_small_turn_still_passes(self):
        # หันเล็กน้อย (ใช้ตอนลงทะเบียนมุมซ้าย/ขวา) ต้องยังผ่าน
        q = quality.check(textured(), face(yaw_shift=0.25), CFG)
        self.assertTrue(q.ok, q.reasons)
        self.assertGreater(q.yaw, 5)

    def test_face_outside_frame(self):
        q = quality.check(textured(), face(box=(560, 140, 200, 200), cx=660), CFG)
        self.assertEqual(q.reasons[0], "outside")

    def test_reasons_ordered_most_useful_first(self):
        small = face(box=(300, 200, 60, 60), eye=20)
        q = quality.check(blur(textured(level=25, amp=10)), small, CFG)
        self.assertEqual(q.reasons[:2], ("too_small", "too_dark"))

    def test_pose_symmetry(self):
        yaw, pitch = quality.estimate_pose(frontal())
        self.assertAlmostEqual(yaw, 0, places=6)
        self.assertAlmostEqual(pitch, 0, places=6)
        self.assertAlmostEqual(quality.estimate_pose(frontal(yaw_shift=0.3))[0],
                               -quality.estimate_pose(frontal(yaw_shift=-0.3))[0])  # fmt: skip

    def test_from_yunet_row(self):
        row = [10, 20, 150, 160, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 0.93]
        f = Face.from_yunet(row)
        self.assertEqual(f.box, (10, 20, 150, 160))
        self.assertEqual(f.landmarks[2], (5, 6))
        self.assertAlmostEqual(f.score, 0.93)


@unittest.skipIf(np is None, "ไม่มี numpy")
class AlignTest(unittest.TestCase):
    def test_landmarks_land_on_template(self):
        for kw in ({}, {"cx": 100, "cy": 400, "eye": 150}, {"eye": 30}):
            with self.subTest(**kw):
                pts = frontal(**kw)
                moved = align.apply(align.transform(pts), pts)
                # จุดตาต้องใกล้ตำแหน่งมาตรฐาน (หน้าสังเคราะห์ไม่ใช่สัดส่วนเดียวกับ template เป๊ะ)
                self.assertLess(np.abs(moved[:2] - align.TEMPLATE[:2]).max(), 6)

    def test_rotated_face_is_straightened(self):
        pts = np.array(frontal())
        ang = math.radians(30)
        rot = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
        tilted = (pts - pts.mean(0)) @ rot.T + pts.mean(0)
        moved = align.apply(align.transform(tilted), tilted)
        self.assertLess(abs(moved[0, 1] - moved[1, 1]), 1.0, "ตาสองข้างต้องอยู่ระดับเดียวกัน")

    def test_crop_is_112(self):
        self.assertEqual(align.crop(textured(), frontal()).shape, (112, 112, 3))

    def test_degenerate_points_rejected(self):
        with self.assertRaises(ValueError):
            align.transform([(5, 5)] * 5)


@unittest.skipIf(np is None, "ไม่มี numpy")
class MatchingTest(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(1)
        self.a, self.b, self.c = (matching.l2_normalize(rng.normal(size=128)) for _ in range(3))

    def near(self, v, noise=0.03, seed=2):
        # noise ต่อช่อง · 128 ช่อง × 0.03 → cosine กับตัวจริงราว 0.95 (คนเดียวกัน คนละเฟรม)
        return matching.l2_normalize(v + noise * np.random.default_rng(seed).normal(size=v.shape))

    def test_l2_normalize(self):
        self.assertAlmostEqual(float(np.linalg.norm(matching.l2_normalize([3, 4]))), 1.0, places=6)
        with self.assertRaises(ValueError):
            matching.l2_normalize([0, 0, 0])
        with self.assertRaises(ValueError):
            matching.l2_normalize([np.nan, 1])

    def test_average_is_unit_and_between(self):
        frames = [self.near(self.a, noise=0.06, seed=s) for s in (3, 4, 5, 6)]
        avg = matching.average(frames)
        self.assertAlmostEqual(float(np.linalg.norm(avg)), 1.0, places=5)
        # เฉลี่ยหลายเฟรม → นอยส์หักล้างกัน → ใกล้หน้าจริงกว่าเฟรมไหน ๆ (เหตุผลที่ทำ multi-frame)
        best_single = max(matching.cosine(f, self.a) for f in frames)
        self.assertGreater(matching.cosine(avg, self.a), best_single)

    def test_average_rejects_empty_or_mixed(self):
        with self.assertRaises(ValueError):
            matching.average([])
        with self.assertRaises(ValueError):
            matching.average([self.a, self.a[:64]])

    def test_match_right_person(self):
        m = matching.match(self.near(self.a), {"a": self.a, "b": self.b, "c": self.c}, 0.363, 0.05)
        self.assertEqual((m.account, m.reason), ("a", "matched"))
        self.assertGreater(m.score, m.second)

    def test_stranger_is_rejected(self):
        m = matching.match(self.c, {"a": self.a, "b": self.b}, 0.363, 0.05)
        self.assertEqual((m.account, m.reason), (None, "below_threshold"))

    def test_lookalikes_are_ambiguous(self):
        twin = self.near(self.a, noise=0.01, seed=9)
        m = matching.match(self.near(self.a), {"a": self.a, "twin": twin}, 0.363, 0.05)
        self.assertEqual((m.account, m.reason), (None, "ambiguous"))

    def test_no_templates(self):
        self.assertEqual(matching.match(self.a, {}, 0.363, 0.05).reason, "no_templates")

    def test_threshold_is_configurable(self):
        q = self.near(self.a, noise=0.08)
        self.assertTrue(matching.match(q, {"a": self.a}, 0.5, 0.05).ok)
        self.assertFalse(matching.match(q, {"a": self.a}, 0.9999, 0.05).ok)

    def test_select_best(self):
        best = matching.select_best([5, 1, 4, 3, 9, 2], key=lambda x: x, k_min=3, k_max=4)
        self.assertEqual(best, [9, 5, 4, 3])
        self.assertEqual(matching.select_best([5, 1], key=lambda x: x, k_min=3, k_max=5), [])


if __name__ == "__main__":
    unittest.main()
