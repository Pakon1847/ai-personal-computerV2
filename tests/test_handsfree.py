"""สั่งด้วยเสียงไม่ใช้เมาส์ (การ์ด 0024): โหมดคีย์ลัด · ตัวคุมเบราว์เซอร์ในแอป · FIFO ของคีย์ลัด."""

import os
import tempfile
import unittest
from pathlib import Path

try:
    from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

    from aipc.browser.control import Result
    from aipc.ui.backend import VoiceController
    from aipc.ui.handsfree import BrowserController, HotkeyListener, route, yes_no
except ImportError:  # pragma: no cover
    VoiceController = None


def pump(cond, ms=3000):
    loop, waited = QEventLoop(), 0
    while not cond() and waited < ms:
        QTimer.singleShot(20, loop.quit)
        loop.exec()
        waited += 20
    return cond()


class FakeListener:
    available = True

    def __init__(self):
        self.listening = False
        self.fast = []  # start(fast=…) ทุกครั้ง

    def start(self, fast=False):
        self.fast.append(fast)
        self.listening = True
        return ""

    def stop(self):
        self.listening = False


class FakeSpeaker:
    available, current, english_available = True, -1, False

    def __init__(self):
        self.said = []

    def say(self, text):
        self.said.append(text)
        self.current = len(self.said)
        return self.current

    def stop(self):
        pass

    def idle_check(self):
        pass


class FakeControl:
    def __init__(self, running=False):
        self.running, self.ran = running, []

    def run(self, cmd):
        self.ran.append(cmd.as_dict())
        self.running = True
        return Result(True, f"ทำ {cmd.kind} แล้ว")

    def close(self):
        self.running = False


class FakeLedger:
    def __init__(self):
        self.rows = []

    def record(self, kind, sent, cost_usd=0.0, ok=True, note=""):
        self.rows.append((kind, sent, ok))


@unittest.skipIf(VoiceController is None, "ไม่มี PySide6")
class HandsFreeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_hotkey_text_goes_to_hands_free_not_input_box(self):
        lis, spk = FakeListener(), FakeSpeaker()
        v = VoiceController(speaker=spk, listener=lis, idle_poll_ms=10**6)
        typed, heard = [], []
        v.transcribed.connect(typed.append)
        v.heardHandsFree.connect(heard.append)
        self.assertFalse(v.handsFree)
        v.toggleHandsFree()
        self.assertTrue(lis.listening)
        self.assertTrue(v.handsFree)  # หน้าจอแสดงกล่องคำสั่งเสียง (Pakon 2026-10-20)
        v._on_heard("ค้นหาราคาทอง", "", 1.9)
        self.assertFalse(v.handsFree)
        self.assertEqual((typed, heard), ([], ["ค้นหาราคาทอง"]))
        # ปุ่มไมค์ในแอปคงเดิม (0019 ข้อ 9): ใส่ช่องพิมพ์ ไม่ทำเอง
        v.startListening()
        v._on_heard("สวัสดี", "", 1.0)
        self.assertEqual((typed, heard), (["สวัสดี"], ["ค้นหาราคาทอง"]))
        # การ์ด 0026: คีย์ลัดถอดด้วยตัวถอดเร็ว (Zipformer) · ปุ่มไมค์ใช้ whisper เดิม
        self.assertEqual(lis.fast, [True, False])

    def test_hotkey_with_nothing_heard_speaks_why(self):
        spk = FakeSpeaker()
        v = VoiceController(speaker=spk, listener=FakeListener(), idle_poll_ms=10**6)
        v.toggleHandsFree()
        v._on_heard("", "ไม่ได้ยินเสียงพูด", 0.0)
        self.assertEqual(spk.said, ["ไม่ได้ยินเสียงพูด"])

    def test_browser_takes_web_commands_only(self):
        ctl, ledger = FakeControl(), FakeLedger()
        b = BrowserController(control=ctl, ledger=ledger)
        done = []
        b.finished.connect(lambda say, ok: done.append((say, ok)))
        self.assertFalse(b.handle("ปรับเสียงเป็น 40"))  # ไม่ใช่คำสั่งเว็บ = แชทตามเดิม
        self.assertFalse(b.handle("ย้อนกลับ"))  # ยังไม่เปิดเบราว์เซอร์ = ไม่ใช่งานของเรา
        self.assertTrue(b.handle("ค้นหาราคาทองแล้วเข้าลิงก์แรก"))
        self.assertTrue(pump(lambda: done))
        self.assertEqual(
            ctl.ran, [{"kind": "search", "query": "ราคาทอง"}, {"kind": "open", "n": 1}]
        )
        self.assertEqual(done, [("ทำ search แล้ว · ทำ open แล้ว", True)])
        # คำค้นออกนอกเครื่อง = จดในบันทึกสิ่งที่ส่งออก
        self.assertEqual(ledger.rows, [("web", "ค้นเว็บ: ราคาทอง", True)])
        self.assertTrue(b.handle("ย้อนกลับ"))  # เปิดเบราว์เซอร์แล้ว = งานของเรา

    def test_error_mid_command_never_leaves_voice_stuck(self):
        """ตรวจทั้งระบบ 2.8: จดสมุดไม่ได้ (ดิสก์เต็ม) หรือเบราว์เซอร์พังกลางทาง = บอกผู้ใช้ + รับคำสั่งถัดไปได้."""

        class FullDisk(FakeLedger):
            def record(self, *a, **kw):
                raise OSError(28, "No space left on device")

        class Broken(FakeControl):
            def run(self, cmd):
                raise RuntimeError("pipe closed")

        for ctl, ledger, said in [(FakeControl(), FullDisk(), "จดลงสมุดสิ่งที่ส่งออกไม่ได้"),
                                  (Broken(), FakeLedger(), "ทำไม่สำเร็จ")]:  # fmt: skip
            b = BrowserController(control=ctl, ledger=ledger)
            done = []
            b.finished.connect(lambda say, ok, d=done: d.append((say, ok)))
            self.assertTrue(b.handle("ค้นหาราคาทอง"))
            self.assertTrue(pump(lambda d=done: d))
            self.assertIn(said, done[0][0])
            self.assertFalse(b.busy)  # ไม่ค้าง: รับคำสั่งถัดไปได้
            self.assertTrue(b.handle("ค้นหาราคาข้าว"))
            self.assertTrue(pump(lambda d=done: len(d) == 2))

    def test_login_screen_has_no_browser(self):
        b = BrowserController(active=False, control=FakeControl())
        self.assertFalse(b.handle("ค้นหาราคาทอง"))
        self.assertEqual(b.route("ค้นหาราคาทอง"), "unknown")
        self.assertFalse(b.openHome())

    def test_route_is_commands_only(self):
        """การ์ด 0027: คีย์ลัด = สั่งงานอย่างเดียว · ไม่มีทางไหนส่งให้ AI ในเครื่องคุย (BRIEF 5.6 ข้อ 1)."""
        for running in (False, True):
            self.assertEqual(route("ค้นหาราคาทองวันนี้", running), "browser")
            # เป็นทั้งคำสั่งเว็บและคำสั่งเครื่อง = เบราว์เซอร์ของผู้ช่วย
            self.assertEqual(route("เปิดยูทูบ", running), "browser")
            self.assertEqual(route("เปิดเบราว์เซอร์", running), "open_browser")
            self.assertEqual(route("ปิดเสียงหน่อย", running), "command")
            self.assertEqual(route("เปิดหน้าตั้งค่า", running), "command")
            for text in ("ตอนนี้กี่โมงแล้ว", "เตือนกินยาพรุ่งนี้แปดโมง", "สวัสดีครับ"):
                self.assertEqual(route(text, running), "unknown", text)
        # คำสั่งที่ต้องมีหน้าเว็บ: ยังไม่เปิดเบราว์เซอร์ของผู้ช่วย = บอกให้เปิดก่อน (เดิมหลุดไปแชท · Pi 5 2026-10-14)
        self.assertEqual(route("เลื่อนลง", False), "needs_browser")
        self.assertEqual(route("เลื่อนลง", True), "browser")
        # "กลับไปหน้าผู้ช่วย" ตอนไม่มีเบราว์เซอร์ = คำสั่งเปิดหน้าของแอปตามเดิม
        self.assertEqual(route("กลับไปหน้าผู้ช่วย", False), "command")
        # สะกดใกล้เคียง (ต้องยืนยัน) = การ์ดยืนยันเดิม ไม่เดาเปิดเอง
        self.assertEqual(route("เปิดเบราวเซอ", False), "command")

    def test_route_runs_exact_skill_phrase_first(self):
        """การ์ด 0028: ตรงเป๊ะกับสกิลที่ผู้ใช้มี = ทำสกิลนั้น · มาหลังคำสั่งเดิม (เหมือนตอนพิมพ์) ·
        ไม่ตรง = ทางเดิมของ 0027."""
        mine = {"เปิดโหมดประชุม": "meeting-mode", "ค้นหาสูตรอาหาร": "cook",
                "เปิดแผนที่ให้หน่อย": "maps", "เลื่อนลง": "scroll"}  # fmt: skip

        def skill(text):
            return mine.get(text, "")

        for running in (False, True):
            self.assertEqual(route("เปิดโหมดประชุม", running, skill=skill), "skill")
            # ชนคำสั่งเดิม = คำสั่งเดิมชนะ (พิมพ์ก็ได้ทางเดียวกัน)
            self.assertEqual(route("ค้นหาสูตรอาหาร", running, skill=skill), "browser")
            self.assertEqual(route("เปิดแผนที่ให้หน่อย", running, skill=skill), "command")
            self.assertEqual(route("เปิดโหมดประชม", running, skill=skill), "unknown")
        # เดิม "ต้องเปิดเบราว์เซอร์ก่อน" = สกิลของผู้ใช้รับได้ · เปิดเบราว์เซอร์แล้ว = คำสั่งเว็บชนะ
        self.assertEqual(route("เลื่อนลง", False, skill=skill), "skill")
        self.assertEqual(route("เลื่อนลง", True, skill=skill), "browser")
        b = BrowserController(control=FakeControl(), skill_match=skill)
        self.assertEqual(b.route("เปิดโหมดประชุม"), "skill")
        self.assertEqual(BrowserController(control=FakeControl()).route("เปิดโหมดประชุม"), "unknown")

    def test_open_home_opens_assistant_browser_at_google(self):
        ctl = FakeControl()
        b = BrowserController(control=ctl)
        done = []
        b.finished.connect(lambda say, ok: done.append(ok))
        self.assertEqual(b.route("เลื่อนลง"), "needs_browser")
        self.assertTrue(b.openHome())
        self.assertTrue(pump(lambda: done))
        self.assertEqual(ctl.ran, [{"kind": "site", "site": "google"}])
        self.assertEqual(b.route("เลื่อนลง"), "browser")  # เปิดแล้ว = เสียงคุมต่อได้


@unittest.skipUnless(hasattr(os, "mkfifo") and VoiceController, "FIFO มีเฉพาะ Linux")
class HotkeyFifoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_key_script_poke_reaches_app_once(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        h = HotkeyListener(Path(d.name) / "aipc" / "voice-key")
        self.addCleanup(h.close)
        self.assertTrue(h.available)
        self.assertEqual(oct(h.path.stat().st_mode & 0o777), "0o600")
        hits = []
        h.pressed.connect(lambda: hits.append(1))
        script = Path(__file__).parents[1] / "scripts" / "pi" / "session" / "aipc-voice-key"
        import subprocess

        subprocess.run(["sh", str(script)], env={**os.environ, "XDG_RUNTIME_DIR": d.name},
                       check=True, timeout=5)  # fmt: skip
        self.assertTrue(pump(lambda: hits))
        self.assertEqual(hits, [1])

    def test_script_does_nothing_without_app(self):
        import subprocess

        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        script = Path(__file__).parents[1] / "scripts" / "pi" / "session" / "aipc-voice-key"
        r = subprocess.run(["sh", str(script)], env={**os.environ, "XDG_RUNTIME_DIR": d.name},
                           timeout=5)  # fmt: skip
        self.assertEqual(r.returncode, 0)


@unittest.skipIf(VoiceController is None, "ไม่มี PySide6")
class YesNoTest(unittest.TestCase):
    """ตอบการ์ดยืนยันด้วยเสียง · ตรวจทั้งระบบ 2026-10-18 ข้อ 2.1 (เดิมดูแค่คำแรก)."""

    def test_negation_anywhere_after_yes_word_means_no(self):
        no = ["ตกลงไม่ลบแล้ว", "โอเค ไม่เอาดีกว่า", "เอาเลยไม่ได้หรอก", "ใช่ อย่าเพิ่งลบ", "ไม่", "ยกเลิกครับ"]
        for text in no:
            self.assertEqual(yes_no(text), "no", text)

    def test_plain_yes_with_polite_endings(self):
        for text in ["ใช่", "ใช่ครับ", "ตกลงค่ะ", "โอเคเลย", "OK", "ยืนยัน.", "ใช่ ลบเลย"]:
            self.assertEqual(yes_no(text), "yes", text)

    def test_yes_word_with_other_words_asks_again(self):
        for text in ["ใช่ไหม", "ตกลงเปิดยูทูบ", "โอเคแล้วนัดพรุ่งนี้ล่ะ"]:
            self.assertEqual(yes_no(text), "unclear", text)

    def test_other_sentences_are_not_answers(self):
        for text in ["เปิดยูทูบ", "เลื่อนลง", "ถ้าไม่ว่างก็ช่างมัน", ""]:
            self.assertEqual(yes_no(text), "", text)

    def test_english_answers(self):
        """การ์ด 0040: หน้าจออังกฤษตอบด้วยเสียงอังกฤษ · กติกาเดียวกับไทย (ปฏิเสธชนะ · ยืนยันต้องไม่มีคำอื่น)."""
        for text, want in [("yes", "yes"), ("Yes please.", "yes"), ("okay, go ahead", "yes"),
                           ("no", "no"), ("No, cancel", "no"), ("yes but not now", "no"),
                           ("don't", "no"), ("yes and open youtube", "unclear"),
                           ("open youtube", ""), ("nobody knows", ""), ("notice", "")]:  # fmt: skip
            self.assertEqual(yes_no(text), want, text)

    def test_english_commands_route_like_thai(self):
        from aipc.ui.handsfree import route

        for running in (False, True):
            self.assertEqual(route("open youtube", running), route("เปิดยูทูบ", running))
            self.assertEqual(route("Mute the sound", running), "command")
            self.assertEqual(route("Why is the sky blue?", running), "unknown")


if __name__ == "__main__":
    unittest.main()
