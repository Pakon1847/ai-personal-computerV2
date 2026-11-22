"""visiond: ใครขออะไรได้ (ตาม uid ของผู้ต่อ) + aipc-face-pass ที่ PAM เรียก · ไม่มีกล้อง ไม่มี socket จริง."""

import tempfile
import threading
import unittest
from pathlib import Path

import numpy as np

from aipc.vision import daemon, face_pass, service, store
from tests.test_vision_service import FakeScanner, vec

GREETER, NAMFON, BOSS = 120, 1001, 1002


class HandlerTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.gallery = service.Gallery(Path(tmp.name) / "face-login", model_sha256="m1")
        self.gallery.folder.mkdir(parents=True)
        self.gallery.store("namfon").save(
            vec(1), 6, "x", store.Consent("2026-09-30T09:00:00+07:00")
        )
        self.scanner = FakeScanner("namfon")
        pw = {"namfon": "pw-namfon-1", "boss": "pw-boss-2"}
        self.face = service.FaceLogin(self.scanner, self.gallery, lambda u, p: pw.get(u) == p)
        uids = {"namfon": NAMFON, "boss": BOSS}
        self.h = daemon.Handler(self.face, lambda s: iter(()), GREETER, uid_of=uids.get)
        self.sent = []

    def pub(self, uid, **req):
        return self.h.public(req, uid, self.sent.append)

    def test_only_the_login_screen_can_identify(self):
        self.assertFalse(self.pub(NAMFON, op="identify")["ok"])
        self.assertEqual(self.scanner.scans, 0)
        r = self.pub(GREETER, op="identify")
        self.assertEqual((r["ok"], r["user"]), (True, "namfon"))

    def scan_handler(self, frames):
        asked = []

        def supply(seconds):
            asked.append(seconds)
            return iter(frames)

        h = daemon.Handler(self.face, supply, GREETER, uid_of={"namfon": NAMFON, "boss": BOSS}.get)
        return h, asked

    def test_scan_qr_returns_only_text_of_a_skill_qr(self):
        """การ์ด 0080 รอบ 2: ส่งกลับแค่ข้อความ · QR อื่นในห้องไม่ถึงโปรแกรมของผู้ใช้."""
        from aipc.skills import share

        blank = np.full((200, 200), 255, dtype=np.uint8)
        other = share._qr_bitmap("WIFI:S:home;P:secret;;")
        wanted = share._qr_bitmap("AIPC2:12345678")
        h, asked = self.scan_handler([blank, other, wanted])
        r = h.public(
            {"op": "scan_qr", "username": "namfon", "timeout_s": 999}, NAMFON, self.sent.append
        )
        self.assertEqual(r, {"ok": True, "state": "scanned", "text": "AIPC2:12345678"})
        self.assertEqual(asked, [daemon.SCAN_QR_MAX_S], "ขอนานแค่ไหน กล้องก็เปิดไม่เกินเพดาน")
        self.assertEqual(self.sent, [], "ไม่มีสถานะหรือภาพส่งระหว่างทาง")

    def test_scan_qr_ignores_other_qr_and_times_out_empty(self):
        from aipc.skills import share

        h, _ = self.scan_handler([share._qr_bitmap("https://example.com")])
        r = h.public({"op": "scan_qr", "username": "namfon"}, NAMFON, self.sent.append)
        self.assertEqual(r["text"], "")

    def test_r6_only_the_account_owner_may_scan(self):
        h, asked = self.scan_handler([])
        for uid in (BOSS, GREETER, 0):
            with self.subTest(uid=uid):
                r = h.public({"op": "scan_qr", "username": "namfon"}, uid, self.sent.append)
                self.assertFalse(r["ok"])
        self.assertEqual(asked, [], "ไม่ใช่เจ้าของบัญชี = กล้องต้องไม่เปิด")

    def test_only_root_can_use_a_ticket(self):
        self.pub(GREETER, op="identify")
        self.assertFalse(self.h.root({"op": "consume", "username": "namfon"}, NAMFON)["ok"])
        self.assertFalse(self.h.root({"op": "consume", "username": "namfon"}, GREETER)["ok"])
        self.assertTrue(self.h.root({"op": "consume", "username": "namfon"}, 0)["ok"])
        self.assertFalse(self.h.root({"op": "consume", "username": "namfon"}, 0)["ok"], "ครั้งเดียว")

    def test_manage_only_your_own_account(self):
        r = self.pub(BOSS, op="remove", username="namfon", password="pw-namfon-1")
        self.assertFalse(r["ok"], "รู้รหัสคนอื่นก็ไม่ได้ ถ้าไม่ได้ต่อมาจากบัญชีนั้นหรือหน้า Login")
        self.assertTrue(self.gallery.path("namfon").exists())
        self.assertEqual(self.pub(NAMFON, op="enabled", username="namfon")["state"], "enabled")
        self.assertEqual(
            self.pub(NAMFON, op="remove", username="namfon", password="pw-namfon-1")["state"],
            "removed",
        )
        self.assertEqual(self.pub(NAMFON, op="enabled", username="namfon")["state"], "disabled")

    def test_signup_can_enroll_from_the_login_screen(self):
        r = self.pub(GREETER, op="enroll", username="boss", password="pw-boss-2", consent_at="t")
        self.assertEqual(r["state"], "saved")
        r = self.pub(GREETER, op="enroll", username="boss", password="wrong", consent_at="t")
        self.assertEqual(r["state"], "bad-password")

    def test_root_uid_is_not_an_account_owner(self):
        r = self.pub(0, op="remove", username="namfon", password="pw-namfon-1")
        self.assertFalse(r["ok"])

    def test_one_camera_job_at_a_time(self):
        gate, started = threading.Event(), threading.Event()

        def slow_frames(_s):
            started.set()
            gate.wait(5)
            return iter(())

        self.h.frames = slow_frames
        t = threading.Thread(target=lambda: self.pub(GREETER, op="identify"))
        t.start()
        started.wait(5)
        self.assertEqual(self.pub(GREETER, op="identify")["state"], "busy")
        gate.set()
        t.join(5)

    def test_no_camera_is_reported_not_crashed(self):
        def broken(_s):
            raise RuntimeError("ไม่พบกล้อง")

        self.h.frames = broken
        r = self.pub(GREETER, op="identify")
        self.assertEqual(r["state"], "no-camera")
        self.assertEqual(self.pub(GREETER, op="identify")["state"], "no-camera", "ปล่อยกล้องแล้ว")

    def test_unknown_or_malformed_requests(self):
        self.assertFalse(self.pub(NAMFON, op="format-disk", username="namfon")["ok"])
        self.assertFalse(self.pub(NAMFON, op="remove", username="namfon")["ok"], "ไม่มีรหัสผ่าน")
        self.assertFalse(self.h.root({"op": "?"}, 0)["ok"])


class EnrollStatusTest(unittest.TestCase):
    """ภาพย่อ + ท่าถัดไประหว่างลงทะเบียน (Pakon ขอให้เห็นหน้าตัวเอง 2026-09-30)."""

    def test_status_has_mirror_preview_next_pose_and_reach(self):
        import base64
        from types import SimpleNamespace

        r = SimpleNamespace(
            advice="", box=(10, 10, 50, 60), quality=SimpleNamespace(yaw=8.0, pitch=0.0)
        )
        msg = daemon.enroll_status(
            r, {"front": 2}, object(), lambda f, b: (b"JPEGDATA", [0.1, 0.2, 0.3, 0.4])
        )
        self.assertEqual(msg["pose"], "left")
        self.assertEqual(msg["hint"], "หันซ้ายเล็กน้อย")
        self.assertEqual(msg["reach"], 1.0)
        self.assertEqual(base64.b64decode(msg["jpeg"]), b"JPEGDATA")
        self.assertEqual(msg["box"], [0.1, 0.2, 0.3, 0.4])

    def test_no_preview_function_means_no_image(self):
        from types import SimpleNamespace

        r = SimpleNamespace(advice="แสงน้อยไป", box=None, quality=None)
        msg = daemon.enroll_status(r, {}, object(), None)
        self.assertNotIn("jpeg", msg)
        self.assertEqual(msg["hint"], "แสงน้อยไป")


class FacePassTest(unittest.TestCase):
    """pam_exec: มีตั๋ว = 0 (เข้าได้) · อย่างอื่นทั้งหมด = 1 (PAM ไปถามรหัสผ่าน)."""

    def test_ticket_means_success(self):
        asked = []

        def ask(req):
            asked.append(req)
            return {"ok": True}

        self.assertEqual(face_pass.run({"PAM_TYPE": "auth", "PAM_USER": "namfon"}, ask), 0)
        self.assertEqual(asked, [{"op": "consume", "username": "namfon"}])

    def test_every_failure_falls_back_to_password(self):
        def down(req):
            raise OSError("visiond ไม่ตอบ")

        env = {"PAM_TYPE": "auth", "PAM_USER": "namfon"}
        self.assertEqual(face_pass.run(env, lambda r: {"ok": False}), 1)
        self.assertEqual(face_pass.run(env, down), 1)
        self.assertEqual(face_pass.run(env, lambda r: {"ok": "yes"}), 1, "ต้องเป็น true จริง ๆ")
        self.assertEqual(face_pass.run({"PAM_TYPE": "auth"}, lambda r: {"ok": True}), 1)
        self.assertEqual(
            face_pass.run({"PAM_TYPE": "account", "PAM_USER": "x"}, lambda r: {"ok": True}), 1
        )

    def test_session_open_resets_lockout_and_never_blocks_login(self):
        def down(req):
            raise OSError

        self.assertEqual(face_pass.run({"PAM_TYPE": "open_session"}, down), 0)
        sent = []
        face_pass.run({"PAM_TYPE": "open_session"}, lambda r: sent.append(r) or {})
        self.assertEqual(sent, [{"op": "login-ok"}])


if __name__ == "__main__":
    unittest.main()
