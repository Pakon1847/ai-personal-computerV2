"""สวิตช์ "เข้าเครื่องด้วยใบหน้า" ในหน้าตั้งค่า (การ์ด 0015) · visiond ปลอม."""

import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QCoreApplication

    from aipc.ui.loginface import LoginFaceController
except ImportError:  # pragma: no cover
    LoginFaceController = None


class FakeVisiond:
    def __init__(self, enabled=False):
        self.enabled = enabled
        self.got = []

    def __call__(self, req, on_progress):
        self.got.append(req)
        if req["op"] == "enabled":
            return {"ok": True, "state": "enabled" if self.enabled else "disabled"}
        if req["password"] != "pw-1":
            return {"ok": False, "state": "bad-password", "message": "รหัสผ่านไม่ถูกต้อง"}
        if req["op"] == "enroll":
            on_progress({"state": "enrolling", "hint": "หันซ้าย"})
            self.enabled = True
            return {"ok": True, "state": "saved"}
        self.enabled = False
        return {"ok": True, "state": "removed"}


@unittest.skipIf(LoginFaceController is None, "ไม่มี PySide6")
class LoginFaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def settle(self, c):
        end = time.monotonic() + 3
        while c.busy and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()

    def test_enable_then_disable_for_own_account_only(self):
        v = FakeVisiond()
        c = LoginFaceController(face=v, user="namfon")
        self.assertEqual(c.state, "disabled")
        self.assertTrue(c.enable("pw-1"))
        self.settle(c)
        self.assertEqual(c.state, "enabled")
        enroll = next(r for r in v.got if r["op"] == "enroll")
        self.assertEqual(enroll["username"], "namfon")
        self.assertRegex(enroll["consent_at"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertTrue(c.disable("pw-1"))
        self.settle(c)
        self.assertEqual(c.state, "disabled")
        self.assertTrue(all(r["username"] == "namfon" for r in v.got))

    def test_wrong_password_keeps_the_state_and_says_why(self):
        c = LoginFaceController(face=FakeVisiond(enabled=True), user="namfon")
        c.disable("wrong")
        self.settle(c)
        self.assertEqual(c.state, "enabled")
        self.assertIn("รหัสผ่าน", c.message)

    def test_no_visiond(self):
        c = LoginFaceController(face=None, user="namfon")
        self.assertEqual(c.state, "unavailable")
        self.assertFalse(c.enable("pw-1"))


if __name__ == "__main__":
    unittest.main()
