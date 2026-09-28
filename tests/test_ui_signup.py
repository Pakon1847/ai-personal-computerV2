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
            return {"ok": True, "message": "สร้างแล้ว", "recovery_code": "AAAA-BBBB"}

        s, results = self.make(real=True, runner=runner)
        self.assertTrue(s.create("น้ำฝน ", "namfon", "correct-horse-9"))
        self.assertTrue(s.busy, "ระหว่างรอ หน้าจอต้องรู้ว่ากำลังทำ (ปุ่มปิด)")
        self.assertFalse(s.create("x", "y", "z"), "ห้ามส่งซ้ำระหว่างรอ")
        gate.set()
        wait_for(results)
        self.assertFalse(s.busy)
        self.assertEqual(results[0]["recovery_code"], "AAAA-BBBB")
        self.assertEqual(seen[0]["op"], "create")
        self.assertEqual(seen[0]["display_name"], "น้ำฝน")
        self.assertEqual(set(seen[0]), {"op", "display_name", "username", "password"})

    def test_dev_mode_is_clearly_simulated(self):
        s, results = self.make(dev=True)
        s.recover("namfon", "XXXX", "correct-horse-9")
        self.assertTrue(results[0]["simulated"])
        self.assertIn("จำลอง", results[0]["message"])
        self.assertIn("จำลอง", results[0]["recovery_code"])

    def test_plain_window_refuses(self):
        s, results = self.make()
        s.create("น้ำฝน", "namfon", "correct-horse-9")
        self.assertFalse(results[0]["ok"])

    def test_missing_helper_is_reported_not_crashed(self):
        # เครื่องที่ยังไม่ได้ติดตั้งตัวช่วย: sudo หาไม่เจอหรือตอบไม่ใช่ JSON → บอกเหตุผล ไม่พัง
        r = run_accounts_helper({"op": "create"}, timeout=10)
        self.assertFalse(r["ok"])
        self.assertTrue(r["message"])


if __name__ == "__main__":
    unittest.main()
