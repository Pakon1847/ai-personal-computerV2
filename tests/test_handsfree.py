"""สั่งด้วยเสียงไม่ใช้เมาส์ (การ์ด 0024): โหมดคีย์ลัด · ตัวคุมเบราว์เซอร์ในแอป · FIFO ของคีย์ลัด."""

import os
import tempfile
import unittest
from pathlib import Path

try:
    from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

    from aipc.browser.control import Result
    from aipc.ui.backend import VoiceController
    from aipc.ui.handsfree import BrowserController, HotkeyListener, route
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
    available, current = True, -1

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
        v.toggleHandsFree()
        self.assertTrue(lis.listening)
        v._on_heard("ค้นหาราคาทอง", "", 1.9)
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
        """การ์ด 0028: ตรงเป๊ะกับสกิลที่ผู้ใช้มี = ทำสกิลนั้น (มาก่อนการแปลทั่วไป) ·
        ไม่ตรง = ทางเดิมของ 0027."""
        mine = {"เปิดโหมดประชุม": "meeting-mode", "ค้นหาสูตรอาหาร": "cook"}

        def skill(text):
            return mine.get(text, "")

        for running in (False, True):
            self.assertEqual(route("เปิดโหมดประชุม", running, skill=skill), "skill")
            self.assertEqual(route("ค้นหาสูตรอาหาร", running, skill=skill), "skill")  # ชนะคำสั่งเว็บ
            self.assertEqual(route("ค้นหาราคาทอง", running, skill=skill), "browser")
            self.assertEqual(route("เปิดโหมดประชม", running, skill=skill), "unknown")
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


if __name__ == "__main__":
    unittest.main()
