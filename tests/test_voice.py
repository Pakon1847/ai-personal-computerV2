"""อ่านออกเสียง (การ์ด 0019): ตัวแปลงข้อความเป็นคำอ่าน + Speaker กับตัวสังเคราะห์/ตัวเล่นปลอม."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from aipc.voice.speech_text import number_words, sentences, to_speech
from aipc.voice.tts import Speaker

DATA = Path(__file__).parent / "data" / "tts_normalize.json"

# ทำตามโปรโตคอลของ piper_worker แต่ไม่ใช้ piper · เขียนไฟล์ว่างแทนเสียง · ท่อนละ 0.05 วิ
FAKE_WORKER = r"""
import json, sys, threading, queue, time, os
jobs = queue.Queue(); cancelled = set()
def read():
    for line in sys.stdin:
        m = json.loads(line)
        if m["cmd"] == "cancel": cancelled.add(m["id"])
        else: jobs.put(m)
    jobs.put(None)
threading.Thread(target=read, daemon=True).start()
print(json.dumps({"ready": True}), flush=True)
while (j := jobs.get()) is not None:
    for i, t in enumerate(j["chunks"]):
        if j["id"] in cancelled: break
        time.sleep(0.05)
        p = os.path.join(j["dir"], f"{j['id']}-{i}.wav"); open(p, "w").write(t)
        last = i == len(j["chunks"]) - 1
        print(json.dumps({"id": j["id"], "i": i, "path": p, "last": last}), flush=True)
"""


class SpeechTextTest(unittest.TestCase):
    def test_dataset(self):
        # ชุดนี้เขียนก่อนโค้ด · เทียบหลังตัดช่องว่าง (Piper ไม่ได้ใช้ช่องว่างแบ่งคำไทย)
        items = json.loads(DATA.read_text(encoding="utf-8"))["items"]
        for it in items:
            with self.subTest(text=it["in"]):
                self.assertEqual(to_speech(it["in"]).replace(" ", ""), it["out"].replace(" ", ""))

    def test_number_words(self):
        cases = {0: "ศูนย์", 1: "หนึ่ง", 10: "สิบ", 11: "สิบเอ็ด", 20: "ยี่สิบ", 21: "ยี่สิบเอ็ด", 100: "หนึ่งร้อย",
                 101: "หนึ่งร้อยเอ็ด", 110: "หนึ่งร้อยสิบ", 1_000_001: "หนึ่งล้านเอ็ด",
                 2_500_000: "สองล้านห้าแสน", 12_000_000: "สิบสองล้าน", -3: "ลบสาม"}  # fmt: skip
        for n, words in cases.items():
            with self.subTest(n=n):
                self.assertEqual(number_words(n), words)

    def test_time_out_of_range_is_left_as_numbers(self):
        self.assertNotIn("นาฬิกา", to_speech("สกอร์ 30:45"))

    def test_sentences_short_first_chunk(self):
        text = " ".join(["คำ" * 5] * 60)
        parts = sentences(text)
        self.assertLessEqual(len(parts[0]), 60)
        self.assertTrue(all(len(p) <= 160 for p in parts))
        self.assertEqual(" ".join(parts), text)
        self.assertEqual(sentences(""), [])

    def test_long_answer_is_capped(self):
        self.assertLess(len(to_speech("ก" * 10_000)), 2000)


class SpeakerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        worker = Path(self.tmp.name) / "worker.py"
        worker.write_text(FAKE_WORKER, encoding="utf-8")
        self.played: list[str] = []
        play = [sys.executable, "-c", "import sys, time; time.sleep(0.05)"]
        self.states: list[tuple[int, bool, str]] = []
        self.done = threading.Event()

        def on_state(jid, speaking, err):
            self.states.append((jid, speaking, err))
            if not speaking:
                self.done.set()

        os.environ["XDG_RUNTIME_DIR"] = self.tmp.name
        self.sp = Speaker(on_state, play_cmd=play, worker_cmd=[sys.executable, str(worker)])
        self.addCleanup(self.sp.close)

    def _files(self):
        d = Path(self.tmp.name) / "aipc-tts"
        return list(d.glob("*.wav")) if d.exists() else []

    def test_speaks_to_the_end_and_cleans_up(self):
        self.assertTrue(self.sp.available)
        jid = self.sp.say("สวัสดีครับ วันนี้อากาศดี")
        self.assertTrue(self.done.wait(10))
        self.assertEqual(self.states[0], (jid, True, ""))
        self.assertEqual(self.states[-1], (jid, False, ""))
        self.assertEqual(self.sp.current, -1)
        time.sleep(0.1)
        self.assertEqual(self._files(), [])  # เล่นจบลบไฟล์เสียงทันที

    def test_stop_midway(self):
        jid = self.sp.say(" ".join(["ประโยคยาว"] * 200))  # หลายท่อน
        time.sleep(0.2)
        self.sp.stop()
        self.assertEqual(self.sp.current, -1)
        self.assertIn((jid, False, ""), self.states)
        time.sleep(0.5)
        self.assertEqual(self._files(), [])

    def test_nothing_to_say(self):
        self.assertEqual(self.sp.say("😀 **"), -1)
        self.assertEqual(self.states, [])

    def test_idle_closes_worker(self):
        self.sp._idle_s = 0
        self.sp.say("ทดสอบ")
        self.assertTrue(self.done.wait(10))
        self.assertTrue(self.sp.idle_check())
        self.assertIsNone(self.sp._proc)
        self.done.clear()
        self.sp.say("อีกครั้ง")  # เปิดใหม่เองได้
        self.assertTrue(self.done.wait(10))
        self.assertEqual(self.states[-1][2], "")

    def test_not_available_without_player(self):
        sp = Speaker(play_cmd=None)
        sp._play_cmd = None
        self.assertFalse(sp.available)


if __name__ == "__main__":
    unittest.main()
