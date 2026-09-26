"""ขั้นตอนของเครื่องมือกล้อง (การ์ด 0005) ด้วยกล้องปลอมและ scanner ปลอม · ไม่เปิดกล้องจริง."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import numpy as np

    from aipc.vision import camera, matching, pipeline, store
except ImportError:  # pragma: no cover
    np = None


class FakeCap:
    def __init__(self, n):
        self.n = n

    def read(self):
        if self.n <= 0:
            return False, None
        self.n -= 1
        return True, np.zeros((4, 4, 3), np.uint8)


class FakeScanner:
    def __init__(self, enroll_result=None, scan_result=None):
        self.enroll_result, self.scan_result = enroll_result, scan_result
        self.frames_read = 0

    def enroll(self, frames):
        self.frames_read = sum(1 for _ in frames)
        return self.enroll_result

    def scan(self, frames, templates):
        self.templates = templates
        self.frames_read += sum(1 for _ in frames)
        return self.scan_result

    def process(self, frame):
        return pipeline.FrameResult(False, "no_face")


@unittest.skipIf(np is None, "ไม่มี numpy")
class CameraFlowTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)
        self.fs = store.FaceStore(self.dir / "face.json", model_sha256="m")
        self.vec = matching.l2_normalize(np.random.default_rng(0).normal(size=128))
        self.out = []
        # ห้ามเขียน log ลง home จริงของคนที่รันเทสต์ · เทสต์ที่ต้องอ่าน log จะ patch ทับเอง
        for name in ("log_path", "enroll_log_path"):
            patcher = mock.patch.object(camera, name, return_value=self.dir / f"{name}.log")
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_frames_stop_when_camera_fails(self):
        self.assertEqual(sum(1 for _ in camera.frames(FakeCap(3), seconds=60)), 3)

    def test_enroll_without_consent_saves_nothing(self):
        sc = FakeScanner(pipeline.Template(self.vec, 6, "t"))
        rc = camera.cmd_enroll(FakeCap(10), sc, self.fs, 5, ask=lambda _: "ไม่", out=self.out.append)
        self.assertEqual(rc, 1)
        self.assertEqual(sc.frames_read, 0, "ไม่ยินยอม = ไม่เปิดอ่านภาพเลย")
        self.assertFalse(self.fs.path.exists())

    def test_enroll_with_consent_saves_template_and_consent(self):
        sc = FakeScanner(pipeline.Template(self.vec, 6, "2026-09-24T10:00:00+07:00"))
        rc = camera.cmd_enroll(FakeCap(10), sc, self.fs, 5, ask=lambda _: " ยินยอม ",
                               out=self.out.append)  # fmt: skip
        self.assertEqual(rc, 0)
        got = self.fs.load()
        self.assertEqual(got.frames, 6)
        self.assertTrue(got.consent.given_at)

    def test_rejected_enroll_tells_why(self):
        sc = FakeScanner(pipeline.Rejected(("right",), "ต้องการภาพเพิ่ม: หันขวาเล็กน้อย"))
        yes = lambda _: "ยินยอม"  # noqa: E731
        rc = camera.cmd_enroll(FakeCap(10), sc, self.fs, 5, ask=yes, out=self.out.append)
        self.assertEqual(rc, 1)
        self.assertIn("หันขวาเล็กน้อย", self.out[-1])
        self.assertFalse(self.fs.path.exists())

    def test_scan_without_template(self):
        rc = camera.cmd_scan(FakeCap(10), FakeScanner(), self.fs, 1, 5, out=self.out.append)
        self.assertEqual(rc, 1)
        self.assertIn("enroll", self.out[0])

    def test_scan_logs_every_attempt(self):
        self.fs.save(self.vec, 6, "t", store.Consent("t"))
        res = pipeline.ScanResult("me", "matched", 0.8, -1.0, 5, 5, {}, 300.0)
        with mock.patch.object(camera, "log_path", return_value=self.dir / "scans.log"):
            rc = camera.cmd_scan(FakeCap(100), FakeScanner(scan_result=res), self.fs, 3, 5,
                                 out=self.out.append)  # fmt: skip
        self.assertEqual(rc, 0)
        self.assertEqual(len((self.dir / "scans.log").read_text(encoding="utf-8").splitlines()), 3)
        self.assertIn("รู้จัก: me", self.out[0])

    def test_enroll_writes_enroll_log(self):
        sc = FakeScanner(pipeline.Rejected(("left",), "ต้องการภาพเพิ่ม", "too_dark"))
        with mock.patch.object(camera, "enroll_log_path", return_value=self.dir / "enroll.log"):
            camera.cmd_enroll(
                FakeCap(10), sc, self.fs, 5, ask=lambda _: "ยินยอม", out=self.out.append
            )
        entry = json.loads((self.dir / "enroll.log").read_text(encoding="utf-8"))
        self.assertEqual((entry["result"], entry["common_reason"]), ("rejected", "too_dark"))

    def compare(self, s5_offset, times=4):
        """แม่แบบ 3 ท่าได้ alice · ท่าเงย/ก้มเป็นเวกเตอร์ที่ห่างออกไปตาม s5_offset."""
        rng = np.random.default_rng(1)
        alice = self.vec
        other = matching.l2_normalize(rng.normal(size=128))
        up = matching.l2_normalize(alice + s5_offset * other)
        by_pose = {"front": [alice], "left": [alice], "right": [alice], "up": [up], "down": [up]}
        sc = FakeScanner(pipeline.Template(alice, 6, "t", by_pose=by_pose),
                         pipeline.ScanResult("me", "matched", 0.9, probe=alice))  # fmt: skip
        with mock.patch.object(camera, "log_path", return_value=self.dir / "compare.log"):
            rc = camera.cmd_compare(FakeCap(1000), sc, camera.config.FaceConfig(), times, 5,
                                    ask=lambda _: "ยินยอม", out=self.out.append)  # fmt: skip
        entry = json.loads((self.dir / "compare.log").read_text(encoding="utf-8"))
        return rc, entry

    def test_compare_scores_same_scan_against_both_templates(self):
        rc, entry = self.compare(s5_offset=2.0)
        self.assertEqual(rc, 0)
        self.assertEqual(len(entry["scans"]), 4)
        self.assertGreater(entry["summary"]["3"]["mean"], entry["summary"]["5"]["mean"])
        self.assertFalse(entry["five_not_worse"])  # 5 ท่าแย่กว่า → ใช้ 3 ท่าต่อ
        self.assertNotIn("probe", json.dumps(entry))  # log ไม่มีเวกเตอร์หน้า

    def test_compare_saves_no_template(self):
        self.compare(s5_offset=0.0)
        self.assertFalse(self.fs.path.exists())

    def test_compare_needs_all_five_poses(self):
        by_pose = {"front": [self.vec], "left": [self.vec], "right": [self.vec]}
        sc = FakeScanner(pipeline.Template(self.vec, 6, "t", by_pose=by_pose))
        rc = camera.cmd_compare(FakeCap(10), sc, camera.config.FaceConfig(), 3, 5,
                                ask=lambda _: "ยินยอม", out=self.out.append)  # fmt: skip
        self.assertEqual(rc, 1)
        self.assertIn("5 ท่า", self.out[-1])

    def test_check_summarises_advice(self):
        rc = camera.cmd_check(FakeCap(4), FakeScanner(), 60, out=self.out.append)
        self.assertEqual(rc, 0)
        self.assertIn("อ่าน 4 เฟรม", self.out[0])
        self.assertIn("ไม่พบใบหน้า", self.out[1])

    def test_find_camera_skips_soc_nodes(self):
        root = self.dir
        nodes = {"video10": "bcm2835-codec-decode", "video2": "Web Camera: Web Camera",
                 "video3": "Web Camera: Web Camera"}  # fmt: skip
        for dev, name in nodes.items():
            (root / "sys/class/video4linux" / dev).mkdir(parents=True)
            (root / "sys/class/video4linux" / dev / "name").write_text(name + "\n")
        self.assertEqual(camera.find_camera(root), 2, "video2 ต้องมาก่อน video10 (เรียงเป็นตัวเลข)")

    def test_find_camera_none_when_only_soc(self):
        d = self.dir / "sys/class/video4linux/video10"
        d.mkdir(parents=True)
        (d / "name").write_text("bcm2835-isp\n")
        self.assertIsNone(camera.find_camera(self.dir))

    def test_scan_against_participants_logs_subject(self):
        folder = self.dir / "participants"
        for pid, seed in (("P01", 1), ("P02", 2)):
            v = matching.l2_normalize(np.random.default_rng(seed).normal(size=128))
            store.FaceStore(folder / f"{pid}.json").save(v, 6, "t", store.Consent("t"))
        (folder / "P03.json").write_text("{", encoding="utf-8")  # ไฟล์เสีย ต้องข้ามพร้อมบอก
        templates = camera.load_templates(folder, out=self.out.append)
        self.assertEqual(sorted(templates), ["P01", "P02"])
        self.assertIn("P03.json", self.out[0])
        sc = FakeScanner(scan_result=pipeline.ScanResult("P02", "matched", 0.7, 0.1, 5, 5, {}, 1.0))
        log = self.dir / "scans.log"
        with mock.patch.object(camera, "log_path", return_value=log):
            camera.cmd_scan(FakeCap(50), sc, self.fs, 2, 5, out=self.out.append,
                            templates=templates, subject="P01")  # fmt: skip
        self.assertEqual(sorted(sc.templates), ["P01", "P02"])
        lines = log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn('"subject": "P01"', lines[0])

    def test_self_scan_uses_who_as_template_name(self):
        self.fs.save(self.vec, 6, "t", store.Consent("t"))
        sc = FakeScanner(scan_result=pipeline.ScanResult("P00", "matched", 0.9, -1, 5, 5, {}, 1.0))
        with mock.patch.object(camera, "log_path", return_value=self.dir / "s.log"):
            camera.cmd_scan(FakeCap(10), sc, self.fs, 1, 5, out=self.out.append, subject="P00")
        self.assertEqual(list(sc.templates), ["P00"])


class TickClock:
    """นาฬิกาปลอม: เดินทีละ step ทุกครั้งที่ถูกอ่าน · ใช้คุมจำนวนเฟรมในช่วงอุ่นเครื่อง/วัด."""

    def __init__(self, step):
        self.t, self.step = 0.0, step

    def __call__(self):
        self.t += self.step
        return self.t


class LitCap(FakeCap):
    """กล้องปลอมที่ให้ภาพความสว่างคงที่ขนาด 640×480."""

    def __init__(self, n, level):
        super().__init__(n)
        self.level = level

    def read(self):
        ok, _ = super().read()
        return (ok, np.full((480, 640, 3), self.level, np.uint8) if ok else None)

    def release(self):
        self.released = True


@unittest.skipIf(np is None, "ไม่มี numpy")
class CameraTestCommandTest(unittest.TestCase):
    """การ์ด 0011: camera test ไม่ต้องมีโมเดล · ไม่เขียนดิสก์ถ้าไม่สั่ง --snap."""

    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)
        self.out = []

    def run_test(self, cap, snap=None):
        return camera.cmd_test(cap, 1.0, snap, out=self.out.append, clock=TickClock(0.1))

    def test_reports_size_fps_and_skips_warmup(self):
        self.assertEqual(self.run_test(LitCap(100, 128)), 0)
        text = "\n".join(self.out)
        self.assertIn("640×480", text)
        self.assertRegex(text, r"ทิ้ง \d+ เฟรมแรก")
        self.assertRegex(text, r"อ่าน \d+ เฟรม")
        self.assertIn("128/255", text)
        self.assertNotIn("มืด", text)
        self.assertEqual(list(self.dir.iterdir()), [], "ไม่มี --snap = ไม่เขียนดิสก์")

    def test_warns_when_dark_or_bright(self):
        self.run_test(LitCap(100, 20))
        self.assertIn("มืดไป", self.out[-1])
        self.out.clear()
        self.run_test(LitCap(100, 240))
        self.assertIn("สว่างเกิน", self.out[-1])

    def test_no_frames_fails(self):
        self.assertEqual(self.run_test(LitCap(0, 128)), 1)
        self.assertIn("ไม่ได้ภาพ", self.out[0])

    def test_frames_only_in_warmup_fails(self):
        self.assertEqual(self.run_test(LitCap(3, 128)), 1, "ได้แค่ช่วงอุ่นเครื่อง = ยังไม่ผ่าน")

    def test_snap_writes_one_image(self):
        snap = self.dir / "snap.jpg"
        self.assertEqual(self.run_test(LitCap(100, 128), snap), 0)
        self.assertEqual(list(self.dir.iterdir()), [snap])
        self.assertGreater(snap.stat().st_size, 0)

    def test_snap_failure_still_reports(self):
        rc = self.run_test(LitCap(100, 128), self.dir / "no-such-dir" / "snap.jpg")
        self.assertEqual(rc, 0, "ผลวัดยังใช้ได้แม้บันทึกภาพไม่ได้")
        self.assertIn("บันทึกภาพไม่ได้", self.out[-1])
        self.assertTrue(any("ภาพ/วิ" in line for line in self.out))

    def test_main_test_does_not_load_models(self):
        cap = LitCap(0, 0)
        with mock.patch.object(camera, "open_camera", return_value=cap), \
             mock.patch.object(camera, "build_scanner") as build, \
             contextlib.redirect_stdout(io.StringIO()):  # fmt: skip
            rc = camera.main(["test", "--seconds", "0.01"])
        build.assert_not_called()
        self.assertEqual(rc, 1)
        self.assertTrue(cap.released, "จบแล้วต้องปิดกล้อง")


if __name__ == "__main__":
    unittest.main()
