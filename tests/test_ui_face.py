"""ใบหน้าในหน้าตั้งค่า (การ์ด 0006) · กล้องและ scanner ปลอม ไม่เปิดกล้องจริง."""

import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import numpy as np
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    from aipc.ui.face import FaceController
    from aipc.vision import matching, pipeline, store
except ImportError:  # pragma: no cover
    FaceController = None


class Cap:
    def __init__(self, n=50, fail_after=None):
        self.n, self.fail_after, self.reads, self.released = n, fail_after, 0, False

    def read(self):
        self.reads += 1
        if self.fail_after is not None and self.reads > self.fail_after:
            return False, None
        if self.reads > self.n:
            return False, None
        return True, np.zeros((4, 4, 3), np.uint8)

    def release(self):
        self.released = True


class Scanner:
    def __init__(self, enroll_result=None, scan_result=None, slow=0.0):
        self.enroll_result, self.scan_result, self.slow = enroll_result, scan_result, slow

    def enroll(self, frames, progress=None):
        # เหมือนของจริง: หยุดอ่านเมื่อได้ครบ (3 เฟรม) · slow = ทำช้าเพื่อทดสอบการยกเลิก
        for i, _ in enumerate(frames):
            if not self.slow and i >= 3:
                break
            time.sleep(self.slow)
            if progress:
                progress(
                    pipeline.FrameResult(False, "too_small"),
                    {"front": min(i, 2), "left": 0, "right": 0},
                )
        return self.enroll_result

    def scan(self, frames, templates, progress=None):
        self.templates = templates
        for i, _ in enumerate(frames):
            if i >= 3:
                break
        return self.scan_result


def settle(face, timeout=5.0):
    """รอเธรดงานจบ แล้วให้ event loop ส่งผลกลับเธรดหลัก."""
    face.wait(timeout)
    end = time.monotonic() + timeout
    while face.busy and time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)


@unittest.skipIf(FaceController is None, "ไม่มี PySide6/numpy")
class FaceControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # ต้องเป็น QGuiApplication: เทสต์หน้าจอที่รันต่อในโปรเซสเดียวกันใช้แอปตัวนี้ต่อ
        # (ถ้าเป็น QCoreApplication หน้าจอ QML จะล่มแบบ segfault)
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.fs = store.FaceStore(Path(d.name) / "face.json", model_sha256="m")
        self.vec = matching.l2_normalize(np.random.default_rng(0).normal(size=128))
        self.cap = Cap()
        self.opened = 0

    def make(self, scanner, cap=None):
        def open_camera():
            self.opened += 1
            return cap or self.cap

        return FaceController(fs=self.fs, open_camera=open_camera, build_scanner=lambda: scanner,
                              enroll_seconds=5, scan_seconds=5)  # fmt: skip

    def test_starts_as_none(self):
        self.assertEqual(self.make(Scanner()).state, "none")

    def test_no_consent_never_opens_camera(self):
        f = self.make(Scanner(pipeline.Template(self.vec, 6, "t")))
        self.assertFalse(f.startEnroll(False))
        self.assertEqual(self.opened, 0)
        self.assertIn("ไม่ได้ยินยอม", f.message)
        self.assertFalse(self.fs.path.exists())

    def test_enroll_success_saves_with_consent_and_releases_camera(self):
        f = self.make(Scanner(pipeline.Template(self.vec, 6, "2026-09-24T12:00:00+07:00")))
        results = []
        f.finished.connect(lambda ok, m: results.append((ok, m)))
        self.assertTrue(f.startEnroll(True))
        self.assertTrue(f.busy)
        settle(f)
        self.assertEqual(results[-1][0], True)
        self.assertEqual(f.state, "enrolled")
        self.assertTrue(self.fs.load().consent.given_at)
        self.assertTrue(self.cap.released, "ต้องปิดกล้องเมื่อเสร็จ")
        self.assertFalse(f.busy)

    def test_rejected_enroll_tells_why_saves_nothing(self):
        f = self.make(Scanner(pipeline.Rejected(("right",), "ต้องการภาพเพิ่ม: หันขวาเล็กน้อย")))
        f.startEnroll(True)
        settle(f)
        self.assertIn("หันขวาเล็กน้อย", f.message)
        self.assertEqual(f.state, "none")

    def test_cancel_saves_nothing(self):
        f = self.make(Scanner(pipeline.Template(self.vec, 6, "t"), slow=0.05), Cap(n=1000))
        f.startEnroll(True)
        time.sleep(0.15)
        f.cancel()
        settle(f)
        self.assertIn("ยกเลิก", f.message)
        self.assertFalse(self.fs.path.exists())

    def test_camera_unplugged_saves_nothing(self):
        f = self.make(Scanner(pipeline.Template(self.vec, 6, "t")), Cap(fail_after=3))
        f.startEnroll(True)
        settle(f)
        self.assertIn("กล้องหลุด", f.message)
        self.assertFalse(self.fs.path.exists())

    def test_missing_camera_or_model_is_reported(self):
        def boom():
            raise RuntimeError("ไม่พบกล้อง")

        f = FaceController(fs=self.fs, open_camera=boom, build_scanner=lambda: Scanner())
        f.startEnroll(True)
        settle(f)
        self.assertIn("ไม่พบกล้อง", f.message)
        self.assertFalse(f.busy)

    def test_progress_reaches_ui_state(self):
        f = self.make(Scanner(pipeline.Template(self.vec, 6, "t"), slow=0.05), Cap(n=1000))
        seen = []
        f.changed.connect(lambda: seen.append(f.advice))
        f.startEnroll(True)
        end = time.monotonic() + 2
        while "ขยับเข้ามาใกล้อีกนิด" not in seen and time.monotonic() < end:
            QCoreApplication.processEvents()
            time.sleep(0.01)
        f.cancel()
        settle(f)
        self.assertIn("ขยับเข้ามาใกล้อีกนิด", seen)

    def test_scan_and_delete(self):
        self.fs.save(self.vec, 6, "t", store.Consent("t"))
        res = pipeline.ScanResult("me", "matched", 0.91, -1, 5, 5, {}, 800.0)
        sc = Scanner(scan_result=res)
        f = self.make(sc)
        self.assertEqual(f.state, "enrolled")
        with tempfile.TemporaryDirectory() as d:
            from unittest import mock

            with mock.patch.dict(os.environ, {"XDG_STATE_HOME": d}):
                self.assertTrue(f.tryScan())
                settle(f)
        self.assertIn("รู้จัก", f.message)
        self.assertTrue(f.deleteTemplate())
        self.assertEqual(f.state, "none")
        self.assertFalse(self.fs.path.exists())

    def test_memory_returned_after_every_job(self):
        # วัดบน Pi 4: ไม่คืน = RSS ค้าง ~90 MB หลังใช้กล้อง (การ์ด 0006) → ต้องเรียกทุกครั้งที่งานจบ
        from unittest import mock

        with mock.patch("aipc.ui.face.release_memory") as release:
            face = self.make(Scanner(enroll_result=None))
            face.startEnroll(True)
            settle(face)
        release.assert_called_once()

    def test_inactive_in_greeter(self):
        f = FaceController(active=False)
        self.assertEqual(f.state, "unavailable")
        self.assertFalse(f.startEnroll(True))
        self.assertFalse(f.deleteTemplate())


if __name__ == "__main__":
    unittest.main()
