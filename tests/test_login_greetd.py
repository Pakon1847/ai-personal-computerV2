"""ตัวต่อ greetd (การ์ด 0003 ข้อ 9) · ใช้ greetd ปลอมผ่าน socketpair ไม่ต้องมี greetd จริง."""

import json
import socket
import struct
import threading
import unittest

from aipc.login import greetd as gd

PW = "s3cret-ไม่ควรโผล่"


OPEN: list[socket.socket] = []  # ปิดทุกตัวหลังจบแต่ละเทสต์


class FakeGreetd:
    """ตอบตามบทที่เขียนไว้ และจดทุกคำขอที่ได้รับ."""

    def __init__(self, script):
        self.script = list(script)  # [(type ที่คาดว่าจะได้รับ, คำตอบ dict | bytes ดิบ)]
        self.got: list[dict] = []
        self.client, self._srv = socket.socketpair()
        OPEN.extend((self.client, self._srv))
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _recv(self):
        head = self._srv.recv(4, socket.MSG_WAITALL)
        if len(head) < 4:
            return None
        (n,) = struct.unpack("=I", head)
        return json.loads(self._srv.recv(n, socket.MSG_WAITALL))

    def _run(self):
        for expect, reply in self.script:
            req = self._recv()
            if req is None:
                return
            self.got.append(req)
            assert req["type"] == expect, (req, expect)
            data = reply if isinstance(reply, bytes) else json.dumps(reply).encode()
            if isinstance(reply, bytes) and reply == b"":
                self._srv.close()
                return
            self._srv.sendall(struct.pack("=I", len(data)) + data)

    def types(self):
        self.thread.join(2)
        return [r["type"] for r in self.got]


OK = {"type": "success"}
SECRET = {"type": "auth_message", "auth_message_type": "secret", "auth_message": "Password: "}
AUTH_ERR = {"type": "error", "error_type": "auth_error", "description": "pam_authenticate: 7"}


def run(script, user="pakon", pw=PW):
    fake = FakeGreetd(script)
    result = gd.login(gd.Greetd(fake.client), user, pw, ["labwc"])
    return result, fake


class Base(unittest.TestCase):
    def tearDown(self):
        while OPEN:
            OPEN.pop().close()


class LoginFlowTest(Base):
    def test_success(self):
        r, fake = run(
            [("create_session", SECRET), ("post_auth_message_response", OK), ("start_session", OK)]
        )
        self.assertTrue(r.ok)
        self.assertEqual(
            fake.types(), ["create_session", "post_auth_message_response", "start_session"]
        )
        self.assertEqual(fake.got[0]["username"], "pakon")
        self.assertEqual(fake.got[1]["response"], PW)
        self.assertEqual(fake.got[2]["cmd"], ["labwc"])

    def test_wrong_password_is_generic_and_cancels(self):
        r, fake = run(
            [
                ("create_session", SECRET),
                ("post_auth_message_response", AUTH_ERR),
                ("cancel_session", OK),
            ]
        )
        self.assertFalse(r.ok)
        self.assertEqual(r.message, gd.GENERIC_FAIL)
        self.assertNotIn("pam_authenticate", r.message)  # ไม่เอารายละเอียดภายในมาโชว์
        self.assertEqual(fake.types()[-1], "cancel_session")

    def test_info_messages_are_shown_not_answered(self):
        info = {"type": "auth_message", "auth_message_type": "info", "auth_message": "เหลือ 2 ครั้ง"}
        r, fake = run(
            [
                ("create_session", info),
                ("post_auth_message_response", SECRET),
                ("post_auth_message_response", OK),
                ("start_session", OK),
            ]
        )
        self.assertTrue(r.ok)
        self.assertEqual(r.notes, ["เหลือ 2 ครั้ง"])
        self.assertIsNone(fake.got[1]["response"])
        self.assertEqual(fake.got[2]["response"], PW)

    def test_second_secret_prompt_is_not_guessed(self):
        # เช่น รหัสหมดอายุ ต้องตั้งใหม่ → ห้ามส่งรหัสเดิมซ้ำเป็น "รหัสใหม่"
        again = {
            "type": "auth_message",
            "auth_message_type": "secret",
            "auth_message": "New password: ",
        }
        r, fake = run(
            [
                ("create_session", SECRET),
                ("post_auth_message_response", again),
                ("cancel_session", OK),
            ]
        )
        self.assertFalse(r.ok)
        self.assertIn("New password", r.message)
        self.assertEqual(sum(1 for g in fake.got if g.get("response") == PW), 1)

    def test_visible_prompt_cancels(self):
        vis = {"type": "auth_message", "auth_message_type": "visible", "auth_message": "OTP: "}
        r, fake = run([("create_session", vis), ("cancel_session", OK)])
        self.assertFalse(r.ok)
        self.assertEqual(fake.types(), ["create_session", "cancel_session"])

    def test_empty_username_never_contacts_greetd(self):
        r, fake = run([], user="")
        self.assertFalse(r.ok)
        self.assertEqual(fake.types(), [])

    def test_start_failure_reported(self):
        bad = {"type": "error", "error_type": "error", "description": "no such file"}
        r, _ = run(
            [
                ("create_session", SECRET),
                ("post_auth_message_response", OK),
                ("start_session", bad),
                ("cancel_session", OK),
            ]
        )
        self.assertFalse(r.ok)
        self.assertIn("no such file", r.message)

    def test_password_never_in_result(self):
        for script in (
            [("create_session", SECRET), ("post_auth_message_response", OK), ("start_session", OK)],
            [
                ("create_session", SECRET),
                ("post_auth_message_response", AUTH_ERR),
                ("cancel_session", OK),
            ],
        ):
            r, _ = run(script)
            self.assertNotIn(PW, repr(r))


class ProtocolErrorTest(Base):
    def test_garbage_json(self):
        fake = FakeGreetd([("create_session", b"{not json")])
        with self.assertRaises(gd.ProtocolError):
            gd.Greetd(fake.client).create_session("pakon")

    def test_unknown_type(self):
        fake = FakeGreetd([("create_session", {"type": "hello"})])
        with self.assertRaises(gd.ProtocolError):
            gd.Greetd(fake.client).create_session("pakon")

    def test_connection_closed(self):
        fake = FakeGreetd([("create_session", b"")])
        with self.assertRaises(gd.ProtocolError):
            gd.Greetd(fake.client).create_session("pakon")

    def test_oversized_length_rejected(self):
        a, b = socket.socketpair()
        OPEN.extend((a, b))
        b.sendall(struct.pack("=I", gd.MAX_MESSAGE + 1))
        with self.assertRaises(gd.ProtocolError):
            gd.Greetd(a)._recv()

    def test_connect_without_env(self):
        import os

        old = os.environ.pop("GREETD_SOCK", None)
        try:
            with self.assertRaises(gd.ProtocolError):
                gd.Greetd.connect()
        finally:
            if old is not None:
                os.environ["GREETD_SOCK"] = old


try:
    from aipc.ui.backend import LoginController
except ImportError:  # pragma: no cover
    LoginController = None


@unittest.skipIf(LoginController is None, "ไม่มี PySide6")
class GreeterModeTest(Base):
    """LoginController ในโหมด greeter ส่งงานให้ greetd จริง ไม่ผ่านเองเด็ดขาด."""

    def make(self, script):
        self.fake = FakeGreetd(script)
        return LoginController(
            False, None, greeter_session=["labwc"], connect=lambda: gd.Greetd(self.fake.client)
        )

    def test_wrong_password_shows_generic_message(self):
        c = self.make(
            [
                ("create_session", SECRET),
                ("post_auth_message_response", AUTH_ERR),
                ("cancel_session", OK),
            ]
        )
        self.assertEqual(c.signIn("pakon", PW), gd.GENERIC_FAIL)
        self.assertTrue(c.greeterMode)

    def test_success_returns_empty(self):
        c = self.make(
            [("create_session", SECRET), ("post_auth_message_response", OK), ("start_session", OK)]
        )
        self.assertEqual(c.signIn(" pakon ", PW), "")
        self.assertEqual(self.fake.got[0]["username"], "pakon")  # ตัดช่องว่างที่พิมพ์เกิน

    def test_greetd_unreachable_points_to_fallback(self):
        def boom():
            raise OSError("no socket")

        c = LoginController(False, None, greeter_session=["labwc"], connect=boom)
        self.assertIn("Ctrl+Alt+F2", c.signIn("pakon", PW))

    def test_non_greeter_non_dev_still_refuses(self):
        self.assertNotEqual(LoginController(False).signIn("pakon", PW), "")


if __name__ == "__main__":
    unittest.main()
