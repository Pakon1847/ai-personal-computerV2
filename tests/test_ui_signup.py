"""หน้าสมัคร/ลืมรหัสผ่านฝั่ง Python (การ์ด 0012) · ตัวช่วย root ปลอม ไม่เรียก sudo จริง."""

import os
import threading
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    from aipc.ui.backend import SignupController, run_accounts_helper
except ImportError:  # pragma: no cover
    SignupController = None


def wait_for(results, timeout=5.0):
    end = time.monotonic() + timeout
    while not results and time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)


@unittest.skipIf(SignupController is None, "ไม่มี PySide6")
class SignupControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def make(self, **kw):
        s = SignupController(**kw)
        results = []
        s.finished.connect(lambda r: results.append(dict(r)))
        return s, results

    def test_real_mode_sends_request_in_background(self):
        seen, gate = [], threading.Event()

        def runner(request):
            seen.append(request)
            gate.wait(2)
            return {"ok": True, "message": "สร้างแล้ว"}

        s, results = self.make(real=True, runner=runner)
        self.assertTrue(s.create("น้ำฝน ", "namfon", "correct-horse-9", "482917"))
        self.assertTrue(s.busy, "ระหว่างรอ หน้าจอต้องรู้ว่ากำลังทำ (ปุ่มปิด)")
        self.assertFalse(s.create("x", "y", "z", "1"), "ห้ามส่งซ้ำระหว่างรอ")
        gate.set()
        wait_for(results)
        self.assertFalse(s.busy)
        self.assertTrue(results[0]["ok"])
        self.assertEqual(seen[0]["op"], "create")
        self.assertEqual(seen[0]["display_name"], "น้ำฝน")
        self.assertEqual(set(seen[0]), {"op", "display_name", "username", "password", "pin"})

    def test_dev_mode_is_clearly_simulated(self):
        s, results = self.make(dev=True)
        s.recover("namfon", "482917", "correct-horse-9")
        self.assertTrue(results[0]["simulated"])
        self.assertIn("จำลอง", results[0]["message"])

    def test_delete_sends_only_what_is_needed(self):
        seen = []
        s, results = self.make(
            real=True, runner=lambda r: seen.append(r) or {"ok": True, "checks": []}
        )
        s.deleteAccount(" namfon ", "correct-horse-9", "namfon ")
        wait_for(results)
        self.assertEqual(seen[0], {"op": "delete", "username": "namfon",
                                   "password": "correct-horse-9", "confirm": "namfon"})  # fmt: skip

    def test_dev_delete_shows_a_simulated_certificate(self):
        s, results = self.make(dev=True)
        s.deleteAccount("namfon", "x", "namfon")
        self.assertTrue(results[0]["simulated"])
        self.assertFalse(results[0]["checks"][0]["gone"])  # จำลอง = ไม่บอกว่าลบแล้ว

    def test_plain_window_refuses(self):
        s, results = self.make()
        s.create("น้ำฝน", "namfon", "correct-horse-9", "482917")
        self.assertFalse(results[0]["ok"])

    def test_pin_check_for_the_form(self):
        s, _ = self.make()
        self.assertTrue(s.checkPin("482917", "482917")["ok"])
        self.assertFalse(s.checkPin("123456", "123456")["ok"])

    def test_missing_helper_is_reported_not_crashed(self):
        # เครื่องที่ยังไม่ได้ติดตั้งตัวช่วย: sudo หาไม่เจอหรือตอบไม่ใช่ JSON → บอกเหตุผล ไม่พัง
        r = run_accounts_helper({"op": "create"}, timeout=10)
        self.assertFalse(r["ok"])
        self.assertTrue(r["message"])


@unittest.skipIf(SignupController is None, "ไม่มี PySide6")
class SignupFaceTest(unittest.TestCase):
    """ขั้นใบหน้าตอนสมัคร (การ์ด 0015 หัวข้อ 11) · visiond ปลอม."""

    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_enroll_goes_to_visiond_with_password_and_consent_time(self):
        sent = []

        def face(req, on_progress):
            sent.append(req)
            on_progress({"state": "enrolling", "hint": "หันซ้าย", "poses": {"front": 2}})
            return {"ok": True, "state": "saved", "user": "namfon", "message": ""}

        s = SignupController(real=True, face=face)
        self.assertTrue(s.faceAvailable)
        progress, done = [], []
        s.faceProgress.connect(lambda h, p: progress.append((h, dict(p))))
        s.faceFinished.connect(lambda r: done.append(dict(r)))
        self.assertTrue(s.enrollFace(" namfon ", "correct-horse-9"))
        wait_for(done)
        self.assertEqual(done[0]["state"], "saved")
        self.assertEqual(progress[0], ("หันซ้าย", {"front": 2}))
        self.assertEqual(sent[0]["op"], "enroll")
        self.assertEqual(sent[0]["username"], "namfon")
        self.assertEqual(sent[0]["password"], "correct-horse-9")
        self.assertRegex(sent[0]["consent_at"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertFalse(s.busy)

    def test_without_visiond_the_step_is_skipped_honestly(self):
        s = SignupController(real=True, face=None)
        self.assertFalse(s.faceAvailable)
        done = []
        s.faceFinished.connect(lambda r: done.append(dict(r)))
        s.enrollFace("namfon", "x")
        self.assertFalse(done[0]["ok"])

    def test_dev_window_is_simulated(self):
        s = SignupController(dev=True)
        self.assertTrue(s.faceAvailable)
        done = []
        s.faceFinished.connect(lambda r: done.append(dict(r)))
        s.enrollFace("namfon", "x")
        self.assertTrue(done[0]["simulated"])


if __name__ == "__main__":
    unittest.main()
