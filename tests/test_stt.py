"""กดค้างเพื่อพูด (aipc.voice.stt) · ตัวอัด/ตัวถอดปลอม · ไม่ต้องมีไมค์."""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from aipc.voice.stt import Listener, clean

# ตัวอัดปลอม: เขียนไฟล์แล้วรอจนถูกหยุด · ตัวถอดปลอม: พิมพ์ข้อความคงที่
FAKE_REC = [sys.executable, "-c",
            "import sys, time; open(sys.argv[1], 'wb').write(b'RIFF'); time.sleep(30)"]  # fmt: skip
FAKE_STT = [sys.executable, "-c", "import sys; print('[BLANK_AUDIO] เปิด ยูทูบ ')", "-f"]


class SttTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["XDG_RUNTIME_DIR"] = self.tmp.name
        self.done = threading.Event()
        self.result: list = []

        def on_done(text, err, secs):
            self.result.append((text, err))
            self.done.set()

        self.l = Listener(on_done, record_cmd=FAKE_REC, transcribe_cmd=FAKE_STT)

    def _files(self):
        d = Path(self.tmp.name) / "aipc-stt"
        return list(d.iterdir()) if d.exists() else []

    def test_clean_removes_tags(self):
        self.assertEqual(clean("[BLANK_AUDIO]  เปิด  (เสียงดนตรี) ยูทูบ\n"), "เปิด ยูทูบ")

    def test_hold_then_release_transcribes_and_deletes_audio(self):
        self.assertTrue(self.l.available)
        self.assertEqual(self.l.start(), "")
        self.assertTrue(self.l.listening)
        time.sleep(0.6)
        self.l.stop()
        self.assertFalse(self.l.listening)
        self.assertTrue(self.done.wait(15))
        self.assertEqual(self.result, [("เปิด ยูทูบ", "")])
        self.assertEqual(self._files(), [])  # ไม่เก็บไฟล์เสียง

    def test_tap_too_short_is_ignored(self):
        self.l.start()
        self.l.stop()
        self.assertTrue(self.done.wait(5))
        self.assertEqual(self.result[0][0], "")
        self.assertIn("กดค้าง", self.result[0][1])
        self.assertEqual(self._files(), [])

    def test_max_length_stops_by_itself(self):
        self.l._max_s = 0.7
        self.l.start()
        self.assertTrue(self.done.wait(15))
        self.assertFalse(self.l.listening)
        self.assertEqual(self.result[0][0], "เปิด ยูทูบ")

    def test_cancel_discards(self):
        self.l.start()
        time.sleep(0.3)
        self.l.cancel()
        self.assertFalse(self.done.wait(1))
        self.assertEqual(self._files(), [])

    def test_unavailable_without_recorder_or_model(self):
        missing = Listener(voice_dir=Path(self.tmp.name) / "none", record_cmd=FAKE_REC)
        self.assertFalse(missing.available)
        self.assertIn("ยังไม่ได้ติดตั้ง", missing.start())


if __name__ == "__main__":
    unittest.main()
