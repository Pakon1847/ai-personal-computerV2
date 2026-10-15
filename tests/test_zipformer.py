"""ตัวถอดเสียงของคีย์ลัด (การ์ด 0026 · aipc.voice.zipformer) · ตัวถอดปลอม ไม่ต้องมีโมเดล/sherpa-onnx."""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from aipc.voice import zipformer
from aipc.voice.stt import Listener
from aipc.voice.zipformer import Transcriber, tidy

# ตัวถอดปลอม: โปรโตคอลเดียวกับ zipformer_worker · ชื่อไฟล์บอกว่าจะตอบอะไร
FAKE_WORKER = r"""
import json, sys, time
print(json.dumps({"ready": True}), flush=True)
for line in sys.stdin:
    m = json.loads(line)
    wav = m["wav"]
    if "crash" in wav:
        sys.exit(1)
    if "hang" in wav:
        time.sleep(30)
    if "bad" in wav:
        print(json.dumps({"id": m["id"], "error": "ValueError: x"}), flush=True)
        continue
    text = "" if "silent" in wav else "ค้นหาวิธีลดน้ําหนัก ค้นหาวิธีลดน้ําหนัก"
    print(json.dumps({"id": m["id"], "text": text}), flush=True)
"""
FAKE_REC = [sys.executable, "-c",
            "import sys, time; open(sys.argv[1], 'wb').write(b'RIFF'); time.sleep(30)"]  # fmt: skip
FAKE_WHISPER = [sys.executable, "-c", "import sys; print('จาก whisper')", "-f"]


class TidyTest(unittest.TestCase):
    def test_nikhahit_plus_sara_aa_becomes_sara_am(self):
        self.assertEqual(tidy("วิธีลดน้ําหนัก"), "วิธีลดน้ำหนัก")

    def test_whole_sentence_said_twice_kept_once(self):
        self.assertEqual(tidy("ค้นหาร้านซ่อมรถใกล้ค้นหาร้านซ่อมรถใกล้"), "ค้นหาร้านซ่อมรถใกล้")
        self.assertEqual(tidy("ย้อนกลับ ย้อนกลับ"), "ย้อนกลับ")

    def test_partial_or_short_repeats_untouched(self):
        self.assertEqual(tidy("ค้นหานานา"), "ค้นหานานา")  # ทั้งประโยคไม่ได้ซ้ำ
        self.assertEqual(tidy("นานา"), "นานา")  # สั้นกว่า 4 ตัวอักษรต่อรอบ
        self.assertEqual(tidy("หาข่าว หาข่าวกีฬา"), "หาข่าว หาข่าวกีฬา")

    def test_spaces_collapsed(self):
        self.assertEqual(tidy("  เลื่อน   ลง \n"), "เลื่อน ลง")

    def test_hotwords_are_the_measured_list(self):
        """รายการต้องเท่ากับที่วัดบน Pi (spike ใช้ชุดเดียวกัน) · เปลี่ยน = ต้องวัดใหม่."""
        from aipc.spikes import voice_cands

        self.assertEqual(zipformer.HOTWORDS, voice_cands.SEARCH_STEMS + voice_cands.FIXED)
        # +7 = การ์ด 0031 (เปิดเฟซบุ๊ก ไอจี … เปิดปฏิทิน) · วัดใหม่ด้วยชุด H บน Pi = เกณฑ์ข้อ 2 ของการ์ด 0031
        self.assertEqual(len(zipformer.HOTWORDS), 7 + 24 + 15 + 3 + 10 + 7)
        self.assertEqual((zipformer.SCORE, zipformer.THREADS), (5.0, 4))


class TranscriberTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        script = Path(self.tmp.name) / "worker.py"
        script.write_text(FAKE_WORKER, encoding="utf-8")
        self.t = Transcriber(worker_cmd=[sys.executable, str(script)], idle_s=0.2)
        self.addCleanup(self.t.close)

    def wav(self, name):
        return Path(self.tmp.name) / f"{name}.wav"

    def test_transcribes_and_tidies(self):
        self.assertTrue(self.t.available)
        self.assertEqual(self.t.transcribe(self.wav("a")), ("ค้นหาวิธีลดน้ำหนัก", ""))
        self.assertEqual(self.t.transcribe(self.wav("b")), ("ค้นหาวิธีลดน้ำหนัก", ""))  # เปิดค้าง

    def test_warm_starts_before_first_use(self):
        self.t.warm()
        for _ in range(100):
            if self.t.running:
                break
            time.sleep(0.02)
        self.assertTrue(self.t.running)

    def test_worker_error_is_reported(self):
        self.assertEqual(self.t.transcribe(self.wav("bad")), ("", "ถอดเสียงไม่สำเร็จ"))
        self.assertEqual(self.t.transcribe(self.wav("ok"))[1], "")  # ยังใช้ต่อได้

    def test_crash_then_restarts(self):
        self.assertEqual(self.t.transcribe(self.wav("crash")), ("", "ตัวถอดเสียงหยุดทำงาน"))
        self.assertFalse(self.t.running)
        self.assertEqual(self.t.transcribe(self.wav("ok"))[1], "")

    def test_hang_times_out_and_kills(self):
        self.assertEqual(self.t.transcribe(self.wav("hang"), timeout_s=0.5),
                         ("", "ถอดเสียงนานเกินไป"))  # fmt: skip
        self.assertFalse(self.t.running)

    def test_skill_phrases_join_hotwords_and_restart_when_they_change(self):
        """การ์ด 0028 ทาง ข: ประโยคไทยของสกิลผู้ใช้เข้า hotwords ต่อท้าย (รายการคำสั่งเว็บเดิมไม่เปลี่ยน) ·
        สกิลเปลี่ยน = เริ่มตัวถอดใหม่ครั้งถัดไป · ไม่เปลี่ยน = ใช้ตัวเดิม (ไม่โหลดโมเดลซ้ำ)."""
        phrases = ["เปิดโหมดประชุม", "meeting mode", "  ขอโหมดประชุม\nหน่อย ", "เปิดโหมดประชุม", "ย้อนกลับ"]
        self.t.extra_hotwords = lambda: phrases
        self.assertEqual(self.t.hotwords(),
                         zipformer.HOTWORDS + ["เปิดโหมดประชุม", "ขอโหมดประชุม หน่อย"])  # fmt: skip
        self.t.transcribe(self.wav("a"))
        first = self.t._proc.pid
        self.t.transcribe(self.wav("b"))
        self.assertEqual(self.t._proc.pid, first)
        phrases.append("เปิดโหมดอ่านหนังสือ")  # สร้างสกิลใหม่
        self.t.transcribe(self.wav("c"))
        self.assertNotEqual(self.t._proc.pid, first)
        self.assertEqual(Transcriber(worker_cmd=["x"]).hotwords(), zipformer.HOTWORDS)  # ไม่มีสกิล

    def test_idle_closes_to_free_ram(self):
        self.t.transcribe(self.wav("a"))
        self.assertFalse(self.t.idle_check())  # เพิ่งใช้
        time.sleep(0.3)
        self.assertTrue(self.t.idle_check())
        self.assertFalse(self.t.running)

    def test_not_installed(self):
        t = Transcriber(base=Path(self.tmp.name) / "none")
        self.assertFalse(t.available)
        t.warm()  # ไม่ทำอะไร ไม่ล่ม
        self.assertFalse(t.running)


class ListenerFastPathTest(unittest.TestCase):
    """คีย์ลัด = ตัวถอดเร็ว · ล่ม = ถอยไปใช้ whisper (ไม่ทิ้งสิ่งที่ผู้ใช้พูด) · ปุ่มไมค์ = whisper."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["XDG_RUNTIME_DIR"] = self.tmp.name
        self.done = threading.Event()
        self.result: list = []

    def listener(self, fast):
        def on_done(text, err, secs):
            self.result.append((text, err))
            self.done.set()

        return Listener(on_done, record_cmd=FAKE_REC, transcribe_cmd=FAKE_WHISPER,
                        auto_stop=False, fast=fast)  # fmt: skip

    def run_once(self, lis, fast):
        self.assertEqual(lis.start(fast=fast), "")
        time.sleep(0.6)
        lis.stop()
        self.assertTrue(self.done.wait(15))
        files = list((Path(self.tmp.name) / "aipc-stt").glob("rec-*"))
        self.assertEqual(files, [])  # ไม่เก็บเสียงทั้งสองทาง
        return self.result[-1]

    def fake(self, body):
        script = Path(self.tmp.name) / "worker.py"
        script.write_text(body, encoding="utf-8")
        t = Transcriber(worker_cmd=[sys.executable, str(script)])
        self.addCleanup(t.close)
        return t

    def test_hotkey_uses_fast_transcriber(self):
        lis = self.listener(self.fake(FAKE_WORKER))
        self.assertEqual(self.run_once(lis, fast=True), ("ค้นหาวิธีลดน้ำหนัก", ""))

    def test_mic_button_still_uses_whisper(self):
        lis = self.listener(self.fake(FAKE_WORKER))
        self.assertEqual(self.run_once(lis, fast=False), ("จาก whisper", ""))

    def test_fast_broken_falls_back_to_whisper(self):
        lis = self.listener(self.fake("import sys; sys.exit(1)"))
        self.assertEqual(self.run_once(lis, fast=True), ("จาก whisper", ""))

    def test_fast_heard_nothing_says_so(self):
        body = FAKE_WORKER.replace('"silent" in wav', "True")
        lis = self.listener(self.fake(body))
        text, err = self.run_once(lis, fast=True)
        self.assertEqual(text, "")
        self.assertIn("ไม่ได้ยิน", err)

    def test_fast_not_installed_uses_whisper(self):
        lis = self.listener(Transcriber(base=Path(self.tmp.name) / "none"))
        self.assertEqual(self.run_once(lis, fast=True), ("จาก whisper", ""))


if __name__ == "__main__":
    unittest.main()
