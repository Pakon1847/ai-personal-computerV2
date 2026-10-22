"""ตัวตรวจว่าเจ้าของยังอยู่ ใช้ใบหน้าที่ลงทะเบียนตอนสมัคร (การ์ด 0051 ทาง ก · เกณฑ์ F1 F5 ส่วนเทสต์).

ไม่มีกล้อง ไม่มี socket จริง: "ภาพ" ปลอม = รายการ embedding ของหน้าในภาพนั้น
"""

import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from aipc.ui import presence
from aipc.ui.presence import VisiondEyes
from aipc.vision import daemon, service, store
from tests.test_vision_service import FakeScanner, vec

GREETER, NAMFON, BOSS = 120, 1001, 1002


class WatchTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        gallery = service.Gallery(Path(tmp.name) / "face-login", model_sha256="m1")
        gallery.folder.mkdir(parents=True)
        gallery.store("namfon").save(vec(1), 6, "x", store.Consent("2026-09-30T09:00:00+07:00"))
        scanner = FakeScanner("namfon")
        scanner.embed_faces = lambda frame: frame
        face = service.FaceLogin(scanner, gallery, lambda u, p: False)
        frames = [[vec(1)], [], [vec(7)], [vec(7), vec(1)]]
        uids = {"namfon": NAMFON, "boss": BOSS}
        self.h = daemon.Handler(face, lambda s: iter(frames), GREETER, uid_of=uids.get)

    def watch(self, uid, user="namfon"):
        sent = []
        with mock.patch.object(service, "WATCH_EVERY_S", 0):  # ทุกภาพ (ของจริงทุก 2 วิ)
            r = self.h.public({"op": "watch", "username": user, "seconds": 5}, uid, sent.append)
        return r, sent

    def test_owner_gets_only_counts_and_yes_no(self):
        r, sent = self.watch(NAMFON)
        self.assertTrue(r["ok"])
        got = [(m["faces"], m["owner"]) for m in sent]
        self.assertEqual(got, [(1, True), (0, False), (1, False), (2, True)])  # เทียบทุกหน้าในภาพ
        for m in sent:
            self.assertEqual(set(m), {"state", "faces", "owner", "best"})  # ไม่มีภาพ แม่แบบ หรือชื่อคน

    def test_f5_only_the_account_owner_may_watch(self):
        for uid in (BOSS, GREETER, 0):
            r, sent = self.watch(uid)
            self.assertFalse(r["ok"], uid)
            self.assertEqual(sent, [], uid)

    def test_no_signup_face_says_so(self):
        r, sent = self.watch(BOSS, user="boss")
        self.assertEqual((r["ok"], r["state"]), (False, "no-templates"))

    def test_camera_released_after(self):
        self.watch(NAMFON)
        self.assertFalse(self.h._camera.locked())


class EyesTest(unittest.TestCase):
    def make(self, script):
        """script = ผลที่ visiond จะส่ง · ส่งครบแล้วรอจนถูกสั่งหยุด."""
        calls = []

        def watch(user, on_seen, stop, seconds=60.0):
            calls.append(user)
            for m in script:
                on_seen(m)
            stop.wait(2)
            return {"ok": True, "state": "stopped"}

        return VisiondEyes("namfon", watch=watch), calls

    def wait_seen(self, eyes, timeout=2.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            s = eyes.look(time.monotonic())
            if s is not None:
                return s
            time.sleep(0.01)
        return None

    def test_maps_messages_to_seen(self):
        eyes, calls = self.make([{"state": "seen", "faces": 2, "owner": False, "best": 0.1}])
        eyes.on()
        s = self.wait_seen(eyes)
        self.assertEqual((s.faces, s.owner, s.stranger), (2, False, True))
        self.assertIsNone(eyes.look(time.monotonic()))  # ผลเดียวใช้ครั้งเดียว
        eyes.off()
        self.assertEqual(calls, ["namfon"])

    def test_nobody_is_not_a_stranger(self):
        eyes, _ = self.make([{"state": "seen", "faces": 0, "owner": False, "best": None}])
        eyes.on()
        s = self.wait_seen(eyes)
        self.assertEqual((s.faces, s.stranger), (0, None))
        eyes.off()

    def test_visiond_error_becomes_camera_error(self):
        def watch(user, on_seen, stop, seconds=60.0):
            return {"ok": False, "state": "busy", "message": "กล้องกำลังใช้อยู่"}

        eyes = VisiondEyes("namfon", watch=watch)
        eyes.on()
        time.sleep(0.1)
        with self.assertRaisesRegex(RuntimeError, "กล้อง"):
            eyes.on()
        self.assertIsNone(eyes.cap)


class PickEyesTest(unittest.TestCase):
    def test_f1_signup_face_first_then_old_template(self):
        self.assertIsInstance(presence.pick_eyes("namfon", enabled=lambda u: True,
                                                 local=lambda: None), VisiondEyes)  # fmt: skip

        class Old:
            vector = vec(3)

        eyes = presence.pick_eyes("namfon", enabled=lambda u: False, local=lambda: Old())
        self.assertIsInstance(eyes, presence.Eyes)
        self.assertIsNone(presence.pick_eyes("namfon", enabled=lambda u: False, local=lambda: None))


if __name__ == "__main__":
    unittest.main()
