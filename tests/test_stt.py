"""กดค้างเพื่อพูด (aipc.voice.stt) · ตัวอัด/ตัวถอดปลอม · ไม่ต้องมีไมค์."""

from __future__ import annotations

import math
import os
import struct
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


def tone(sec: float, amp: int) -> bytes:
    """PCM 16 kHz คลื่นไซน์ความดัง amp ยาว sec วิ (แทนเสียงพูด/เสียงรอบข้าง)."""
    n = int(16000 * sec)
    return b"".join(struct.pack("<h", int(amp * math.sin(i * 0.3))) for i in range(n))


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
        ep = Endpointer()
        audio = tone(0.4, 30) + tone(0.6, 8000) + tone(0.5, 30) + tone(0.6, 8000)
        self.assertIsNone(ep.feed(audio))  # เว้น 0.5 วิกลางประโยค ไม่ตัด
        self.assertEqual(ep.feed(tone(1.2, 30)), "end")

    def test_far_voice_does_not_keep_it_listening(self):
        """การ์ด 0056: พูดจบแล้วมีคนพูดเบา ๆ ห่างไมค์ (เบากว่าเรา 20 dB) ต่อ → จบเอง ·
        รุ่นเดิม (near_db=0) ฟังต่อ."""
        audio = tone(0.4, 30) + tone(0.6, 8000) + tone(1.2, 800)
        self.assertEqual(Endpointer().feed(audio), "end")
        self.assertIsNone(Endpointer(near_db=0).feed(audio))
        # คนข้าง ๆ ดังพอ ๆ กับเรา (เบากว่าแค่ 6 dB) = ยังนับเป็นเสียงพูด (ตัดไม่ได้ · H5)
        self.assertIsNone(Endpointer().feed(tone(0.4, 30) + tone(0.6, 8000) + tone(1.2, 4000)))

    def test_soft_tail_does_not_trigger_the_early_stop(self):
        """การ์ด 0056 (วัดบน Pi): หางเสียงเบาของท่อนแรก + เว้น 0.45 วิ · ประตูใกล้ไมค์นับเป็นเงียบ
        แต่ทางลัดจบเร็ว (quiet_s · การ์ด 0044) ต้องนับแค่เงียบจริง ไม่งั้นท่อนที่สองหาย."""
        ep = Endpointer()
        first = tone(0.4, 30) + tone(0.6, 8000) + tone(0.3, 700) + tone(0.45, 30)
        self.assertIsNone(ep.feed(first))
        self.assertLess(ep.quiet_s, 0.5)  # เงียบจริงแค่ 0.45 วิ (ไม่ใช่ 0.75)
        self.assertIsNone(ep.feed(tone(0.6, 8000)))  # ท่อนที่สอง = ยังฟังต่อ

    def test_speech_span_keeps_only_speech_plus_padding(self):
        ep = Endpointer()
        audio = tone(0.5, 30) + tone(0.6, 8000) + tone(1.2, 30)
        self.assertEqual(ep.feed(audio), "end")
        a, b = ep.speech_span(len(audio))
        self.assertAlmostEqual(a / 32000, 0.5 - 0.25, delta=0.05)  # เริ่มพูด − 0.25 วิ
        self.assertAlmostEqual(b / 32000, 1.1 + 0.3, delta=0.05)  # พูดจบ + 0.3 วิ

    def test_remembered_room_level_lets_you_speak_at_once(self):
        """การ์ด 0056: กดแล้วพูดทันที · ไม่มีค่าที่จำไว้ = 0.3 วิแรก (เสียงเรา) ถูกนับเป็นเสียงรอบข้าง → ไม่ได้ยิน."""
        audio = tone(0.6, 8000) + tone(1.2, 30)
        self.assertIsNone(Endpointer().feed(audio))
        ep = Endpointer()
        ep.use_noise(21.0)
        self.assertEqual(ep.feed(audio), "end")
        self.assertEqual(ep.start_frame, 0)
        self.assertLess(ep.noise_floor, 40)  # ระดับเงียบท้าย = จำไว้ครั้งหน้า

    def test_listener_transcribes_only_the_speech(self):
        """การ์ด 0056: ไฟล์ที่ส่งให้ตัวถอดเหลือแค่ช่วงพูด (ตัวถอดปลอมพิมพ์ความยาวไฟล์) · จำระดับเสียงรอบข้างไว้."""
        talker = Path(self.tmp.name) / "talker.py"
        talker.write_text(TALKER, encoding="utf-8")
        code = "import sys, wave; print(wave.open(sys.argv[1]).getnframes() / 16000)"
        length = [sys.executable, "-c", code]
        lis = Listener(lambda t, e, s: (self.result.append((t, e)), self.done.set()),
                       record_cmd=[sys.executable, str(talker)], transcribe_cmd=length)  # fmt: skip
        self.assertEqual(lis.start(), "")
        self.assertTrue(self.done.wait(15))
        seconds = float(self.result[0][0])
        self.assertAlmostEqual(seconds, 0.6 + 0.25 + 0.3, delta=0.1)  # ไม่ใช่ทั้งไฟล์ (~2 วิ)
        self.assertLess(lis._noise_floor, 100)

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

    def test_hotkey_is_bilingual_whatever_the_screen_language(self):
        """Pakon 2026-10-20: คีย์ลัดใช้ได้ทั้งไทยและอังกฤษ ไม่แยกตามภาษาหน้าจอ · ปุ่มไมค์ยังตามภาษาหน้าจอ."""

        class ThaiFast:
            available, used = True, 0

            def warm(self):
                pass

            def transcribe(self, path):
                ThaiFast.used += 1
                return "เปิดยูทูบ", ""

        for lang in ("en", "th"):
            self.lang = lang
            lis = self.listener(self.FAKE_EN, fast=ThaiFast())
            # พูดไทยได้ทั้งหน้าจอไทยและอังกฤษ
            self.assertEqual(self.run_once(lis, fast=True), ("เปิดยูทูบ", ""), lang)
        self.assertEqual(ThaiFast.used, 2)
        self.lang = "en"
        lis = self.listener(self.FAKE_EN, fast=ThaiFast())
        self.assertEqual(self.run_once(lis), ("Open YouTube.", ""))  # ปุ่มไมค์ = ภาษาหน้าจอ

    def test_thai_screen_hotkey_falls_back_to_english_command(self):
        """การ์ด 0040 หัวข้อ 13: หน้าจอไทย · Zipformer ได้คำไทยมั่ว → ลองอังกฤษ · ใช้เมื่อเป็นคำสั่งที่รู้จักเท่านั้น."""

        class Fast:
            available = True

            def __init__(self, text):
                self.text = text

            def warm(self):
                pass

            def transcribe(self, path):
                return self.text, ""

        self.lang = "th"
        tried = []

        def listener(thai, en_cmd):
            return Listener(lambda t, e, s: (self.result.append((t, e)), self.done.set()),
                            record_cmd=FAKE_REC, transcribe_cmd=FAKE_STT, en_transcribe_cmd=en_cmd,
                            fast=Fast(thai), language=lambda: self.lang,
                            try_english=lambda t: tried.append(t) or t == "วีเรียบร้อย",
                            use_english=lambda e: e.lower().startswith("open"))  # fmt: skip

        # ไทยมั่ว + อังกฤษเป็นคำสั่ง = ใช้อังกฤษ
        self.assertEqual(self.run_once(listener("วีเรียบร้อย", self.FAKE_EN), fast=True),
                         ("Open YouTube.", ""))  # fmt: skip
        # ไทยตรงคำสั่งอยู่แล้ว = ไม่ลองอังกฤษ
        self.assertEqual(self.run_once(listener("เปิดยูทูบ", self.FAKE_EN), fast=True),
                         ("เปิดยูทูบ", ""))  # fmt: skip
        # อังกฤษไม่ใช่คำสั่ง = ใช้ไทยเดิม (ไม่เดา)
        not_cmd = [sys.executable, "-c", "print('hello there')", "-f"]
        self.assertEqual(self.run_once(listener("วีเรียบร้อย", not_cmd), fast=True),
                         ("วีเรียบร้อย", ""))  # fmt: skip
        self.assertEqual(tried, ["วีเรียบร้อย", "เปิดยูทูบ", "วีเรียบร้อย"])

    def test_missing_english_model_says_so(self):
        lis = Listener(record_cmd=FAKE_REC, voice_dir=Path(self.tmp.name), language=lambda: "en",
                       transcribe_cmd=FAKE_STT)  # fmt: skip
        self.assertEqual(lis.start(), "ยังไม่ได้ติดตั้งตัวถอดเสียงภาษาอังกฤษ")
        self.assertFalse(lis.listening)


if __name__ == "__main__":
    unittest.main()


# การ์ด 0044: พูด 0.6 วิ → เงียบ (ถอดล่วงหน้า + จบเร็ว) · TALK_AGAIN = พูด เงียบ 0.4 วิ แล้วพูดต่อ
TALK_AGAIN = TALKER.replace("loud = 4 <= k < 10", "loud = 4 <= k < 10 or 14 <= k < 20")


class SpeculativeTest(unittest.TestCase):
    """การ์ด 0044: ถอดล่วงหน้าระหว่างรอเงียบ · คำสั่งครบ = จบเร็ว · พูดต่อ = ทิ้งผลล่วงหน้า."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["XDG_RUNTIME_DIR"] = self.tmp.name
        self.done = threading.Event()
        self.result: list = []

    def listen(self, script, complete):
        calls = []

        class Fast:
            available = True

            def warm(self):
                pass

            def transcribe(self, path):
                import wave

                with wave.open(str(path)) as w:
                    calls.append(w.getnframes() / 16000)
                return "เปิดยูทูบ", ""

        talker = Path(self.tmp.name) / "talker.py"
        talker.write_text(script, encoding="utf-8")

        def on_done(t, e, s):
            self.result.append((t, e, time.monotonic()))
            self.done.set()

        lis = Listener(on_done, record_cmd=[sys.executable, str(talker)], transcribe_cmd=FAKE_STT,
                       fast=Fast(), complete=complete)  # fmt: skip
        t0 = time.monotonic()
        self.assertEqual(lis.start(fast=True), "")
        self.assertTrue(self.done.wait(15))
        return calls, self.result[-1][2] - t0

    def test_complete_command_ends_early_and_reuses_the_early_result(self):
        calls, early = self.listen(TALKER, complete=lambda t: True)
        self.assertEqual(self.result[-1][:2], ("เปิดยูทูบ", ""))
        self.assertEqual(len(calls), 1, "ใช้ผลที่ถอดล่วงหน้า ไม่ถอดซ้ำ")
        self.done.clear()
        _, normal = self.listen(TALKER, complete=lambda t: False)
        self.assertLess(early, normal - 0.2, "คำสั่งครบ = ไม่ต้องรอเงียบครบ 1 วิ")
        self.assertEqual(list(Path(self.tmp.name, "aipc-stt").iterdir()), [])  # ไม่เก็บไฟล์เสียง

    def test_speaking_again_discards_the_early_result(self):
        calls, _ = self.listen(TALK_AGAIN, complete=lambda t: False)
        self.assertGreaterEqual(len(calls), 2)
        self.assertGreater(calls[-1], calls[0] + 0.5, "ผลสุดท้ายต้องรวมเสียงที่พูดต่อ")
