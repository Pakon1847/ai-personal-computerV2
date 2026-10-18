"""กดค้างเพื่อพูด (aipc.voice.stt) · ตัวอัด/ตัวถอดปลอม · ไม่ต้องมีไมค์."""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from aipc.voice.stt import Endpointer, Listener, clean

# ตัวอัดปลอม: เขียนไฟล์แล้วรอจนถูกหยุด · ตัวถอดปลอม: พิมพ์ข้อความคงที่
FAKE_REC = [sys.executable, "-c",
            "import sys, time; open(sys.argv[1], 'wb').write(b'RIFF'); time.sleep(30)"]  # fmt: skip
FAKE_STT = [sys.executable, "-c", "import sys; print('[BLANK_AUDIO] เปิด ยูทูบ ')", "-f"]
# ตัวอัดปลอมแบบเวลาจริง: เขียน WAV เงียบ 0.4 วิ → เสียงดัง 0.6 วิ → เงียบไปเรื่อย ๆ (ทีละ 0.1 วิ)
TALKER = r"""
import math, struct, sys, time
f = open(sys.argv[1], "wb")
fmt = struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16)
f.write(b"RIFF" + struct.pack("<I", 0) + b"WAVEfmt " + fmt + b"data" + struct.pack("<I", 0))
f.flush()
for k in range(80):
    loud = 4 <= k < 10
    amp = 8000 if loud else 30
    f.write(b"".join(struct.pack("<h", int(amp * math.sin(i * 0.3))) for i in range(1600)))
    f.flush()
    time.sleep(0.1)
"""


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

    def test_tap_once_stops_by_itself_after_silence(self):
        talker = Path(self.tmp.name) / "talker.py"
        talker.write_text(TALKER, encoding="utf-8")
        lis = Listener(lambda t, e, s: (self.result.append((t, e)), self.done.set()),
                     record_cmd=[sys.executable, str(talker)], transcribe_cmd=FAKE_STT)  # fmt: skip
        self.assertEqual(lis.start(), "")
        t0 = time.monotonic()
        self.assertTrue(self.done.wait(15))
        self.assertEqual(self.result, [("เปิด ยูทูบ", "")])
        # พูด 0.4–1.0 วิ · เงียบ 1 วิ = หยุด → ราว 2 วิ (+ เวลาเปิดโปรแกรม/ถอด)
        self.assertLess(time.monotonic() - t0, 6)
        self.assertFalse(lis.listening)

    def test_no_speech_gives_up(self):
        talker = Path(self.tmp.name) / "quiet.py"
        talker.write_text(TALKER.replace("4 <= k < 10", "False"), encoding="utf-8")
        lis = Listener(lambda t, e, s: (self.result.append((t, e)), self.done.set()),
                     record_cmd=[sys.executable, str(talker)], transcribe_cmd=FAKE_STT,
                     endpointer=lambda: Endpointer(no_speech_s=0.8))  # fmt: skip
        lis.start()
        self.assertTrue(self.done.wait(15))
        self.assertEqual(self.result[0][0], "")
        self.assertIn("ไม่ได้ยินเสียงพูด", self.result[0][1])
        self.assertEqual(self._files(), [])

    def test_endpointer_keeps_listening_through_short_pause(self):
        import math
        import struct

        def tone(sec, amp):
            return b"".join(
                struct.pack("<h", int(amp * math.sin(i * 0.3))) for i in range(int(16000 * sec))
            )

        ep = Endpointer()
        audio = tone(0.4, 30) + tone(0.6, 8000) + tone(0.5, 30) + tone(0.6, 8000)
        self.assertIsNone(ep.feed(audio))  # เว้น 0.5 วิกลางประโยค ไม่ตัด
        self.assertEqual(ep.feed(tone(1.2, 30)), "end")

    def test_unavailable_without_recorder_or_model(self):
        missing = Listener(voice_dir=Path(self.tmp.name) / "none", record_cmd=FAKE_REC)
        self.assertFalse(missing.available)
        self.assertIn("ยังไม่ได้ติดตั้ง", missing.start())


class EnglishSttTest(unittest.TestCase):
    """การ์ด 0040: ภาษาตัวถอด = ภาษาหน้าจอ (โค้ดเลือก) · หน้าจอไทย = ทางเดิม ·
    คีย์ลัดอังกฤษไม่ใช้ Zipformer ไทย."""

    FAKE_EN = [sys.executable, "-c", "print('Open YouTube.')", "-f"]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["XDG_RUNTIME_DIR"] = self.tmp.name
        self.done = threading.Event()
        self.result: list = []
        self.lang = "en"

    def listener(self, en_cmd, fast=None):
        return Listener(lambda t, e, s: (self.result.append((t, e)), self.done.set()),
                        record_cmd=FAKE_REC, transcribe_cmd=FAKE_STT, en_transcribe_cmd=en_cmd,
                        fast=fast, language=lambda: self.lang)  # fmt: skip

    def run_once(self, lis, fast=False):
        self.assertEqual(lis.start(fast=fast), "")
        time.sleep(0.6)
        lis.stop()
        self.assertTrue(self.done.wait(15))
        self.done.clear()
        return self.result.pop()

    def test_english_screen_uses_english_model_thai_screen_unchanged(self):
        lis = self.listener(self.FAKE_EN)
        self.assertEqual(self.run_once(lis), ("Open YouTube.", ""))
        self.lang = "th"
        self.assertEqual(self.run_once(lis), ("เปิด ยูทูบ", ""))

    def test_hotkey_in_english_skips_thai_zipformer(self):
        class ThaiFast:
            available, used = True, 0

            def warm(self):
                pass

            def transcribe(self, path):
                ThaiFast.used += 1
                return "เปิดยูทูบ", ""

        lis = self.listener(self.FAKE_EN, fast=ThaiFast())
        self.assertEqual(self.run_once(lis, fast=True), ("Open YouTube.", ""))
        self.assertEqual(ThaiFast.used, 0)
        self.lang = "th"
        self.assertEqual(self.run_once(lis, fast=True), ("เปิดยูทูบ", ""))
        self.assertEqual(ThaiFast.used, 1)

    def test_missing_english_model_says_so(self):
        lis = Listener(record_cmd=FAKE_REC, voice_dir=Path(self.tmp.name), language=lambda: "en",
                       transcribe_cmd=FAKE_STT)  # fmt: skip
        self.assertEqual(lis.start(), "ยังไม่ได้ติดตั้งตัวถอดเสียงภาษาอังกฤษ")
        self.assertFalse(lis.listening)


if __name__ == "__main__":
    unittest.main()
