"""การ์ด 0058: ฟังคำสั่งเสียงเฉพาะตอนหันหน้าเข้าจอ (G3 G5 ส่วนเทสต์) · ไม่มีกล้อง/ไมค์/socket จริง."""

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from aipc.vision import daemon, service
from aipc.voice import stt
from aipc.voice.stt import Listener
from tests.test_stt import TALKER

GREETER, NAMFON, BOSS = 120, 1001, 1002


class Yaws:
    """ตัวสแกนปลอม: face_yaws คืนมุมตามลำดับที่ตั้งไว้ (ภาพละรายการ)."""

    def __init__(self, seq):
        self.seq = iter(seq)

    def face_yaws(self, frame):
        return next(self.seq)


class FacingServiceTest(unittest.TestCase):
    def test_sends_only_count_and_facing(self):
        face = service.FaceLogin(Yaws([[3.0], [90.0], [], [-12.0, 80.0]]), None, lambda u, p: False)
        sent = []
        t = iter(range(10))
        out = face.facing(range(4), sent.append, every_s=0.0, clock=lambda: next(t))
        self.assertTrue(out.ok)
        self.assertEqual([m["facing"] for m in sent], [True, False, False, True])
        self.assertEqual([m["faces"] for m in sent], [1, 1, 0, 2])
        self.assertEqual(set(sent[0]), {"state", "faces", "facing"})  # ไม่มีภาพ/คะแนน/ชื่อ

    def test_only_the_session_owner_may_ask(self):
        face = service.FaceLogin(Yaws([]), None, lambda u, p: False)
        uids = {"namfon": NAMFON}
        h = daemon.Handler(face, lambda s: iter(()), GREETER, uid_of=uids.get)
        for uid in (BOSS, GREETER, 0):
            r = h.public({"op": "facing", "username": "namfon"}, uid, lambda m: None)
            self.assertFalse(r["ok"], uid)
        own = h.public({"op": "facing", "username": "namfon"}, NAMFON, lambda m: None)
        self.assertTrue(own["ok"])


def fake_facing(schedule):
    """visiond ปลอม: ส่ง {"facing": schedule(วินาทีตั้งแต่เริ่ม)} ทุก 0.05 วิ จน stop · บันทึกว่าถูกเรียกไหม."""
    calls = []

    def facing(on_seen, stop):
        calls.append(True)
        t0 = time.monotonic()
        while not stop.is_set():
            on_seen({"faces": 1, "facing": schedule(time.monotonic() - t0)})
            time.sleep(0.05)
        return {"ok": True, "state": "stopped"}

    return facing, calls


class ListenerFacingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["XDG_RUNTIME_DIR"] = self.tmp.name
        self.talker = Path(self.tmp.name) / "talker.py"
        self.talker.write_text(TALKER, encoding="utf-8")  # เงียบ 0.4 วิ → พูด 0.6 วิ → เงียบ
        self.done, self.result = threading.Event(), []

    def run_once(self, schedule, on=True):
        facing, calls = fake_facing(schedule)
        # ความยาวเสียงจากขนาดไฟล์ (ตัวอัดปลอมไม่เขียนขนาดในหัว WAV · อ่านด้วย wave ไม่ได้)
        code = "import os, sys; print((os.path.getsize(sys.argv[1]) - 44) / 32000)"
        lis = Listener(lambda t, e, s: (self.result.append((t, e)), self.done.set()),
                       record_cmd=[sys.executable, str(self.talker)],
                       transcribe_cmd=[sys.executable, "-c", code],
                       facing=facing, facing_on=lambda: on)  # fmt: skip
        self.assertEqual(lis.start(fast=True), "")
        self.assertTrue(self.done.wait(15))
        return self.result[0], calls

    def test_facing_the_screen_works_as_before(self):
        (text, err), calls = self.run_once(lambda t: True)
        self.assertEqual(err, "")
        self.assertTrue(calls)

    def test_never_facing_is_not_a_command(self):
        (text, err), _ = self.run_once(lambda t: False)
        self.assertEqual((text, err), ("", stt.NOT_FACING))

    def test_turning_away_cuts_the_rest(self):
        """G3: หันเข้าจอตอนเริ่มพูด แล้วหันออกที่ ~0.7 วิ → ถอดแค่ถึงตอนที่หัน (ไม่ใช่ทั้งไฟล์ ~2 วิ)."""
        (text, err), _ = self.run_once(lambda t: t < 0.7)
        self.assertEqual(err, "")
        self.assertLess(float(text), 1.0)
        self.assertGreater(float(text), 0.3)

    def test_setting_off_never_opens_the_camera(self):
        (text, err), calls = self.run_once(lambda t: False, on=False)
        self.assertEqual(err, "")  # ฟังแบบเดิม
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
