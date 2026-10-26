"""คุมเพลง/วิดีโอด้วยเสียง (การ์ด 0035 เกณฑ์ข้อ 1) · เบราว์เซอร์จำลอง (ไม่เปิด Chromium จริง).

ตรวจ: ประโยคแต่ละแบบ → คำสั่งถูก · ประโยคใกล้เคียงที่ไม่ใช่คำสั่งไม่เข้า · ไม่มีวิดีโอ = บอกตามจริง ·
เพลงถัดไป: Shift+N ก่อน · ไม่ได้ผล = ปุ่มถัดไป · ไม่ใช่ YouTube = บอก
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aipc.browser import control
from aipc.browser.control import BrowserControl, Result
from aipc.skills import browse, command
from aipc.skills.browse import BrowseCommand
from tests.test_browser_control import FakeCdp, FakeProc

try:
    from PySide6.QtGui import QGuiApplication

    from aipc.ui.handsfree import BROWSER, COMMAND, NEEDS_BROWSER, BrowserController, route
except ImportError:  # pragma: no cover
    BrowserController = None

PAUSE = ["หยุดเพลง", "หยุดวิดีโอ", "หยุดวีดีโอ", "หยุดคลิป", "หยุดชั่วคราว", "พักเพลง", "ช่วยหยุดเพลงหน่อย",
         "หยุดเพลงก่อน", "ปิดเพลง", "หยุด เพลง"]  # fmt: skip
PLAY = ["เล่นต่อ", "เล่นเพลงต่อ", "เล่นวิดีโอต่อ", "เปิดเพลงต่อ", "เล่นต่อเลย"]
NEXT = ["เพลงถัดไป", "คลิปถัดไป", "วิดีโอถัดไป", "ข้ามเพลง", "ไปเพลงถัดไป", "เพลงต่อไป", "ข้ามเพลงนี้"]
# ใกล้เคียงแต่ไม่ใช่คำสั่งคุมเพลง (การ์ดหัวข้อ 2 และ 6)
# "หยุด" เดี่ยว ๆ เคยอยู่ในรายการนี้ (การ์ด 0035) · Pakon เลือกเปลี่ยน 2026-10-26 (การ์ด 0065 ข้อ A) = หยุดคลิป ·
# ทดสอบที่ test_browse.ShortPauseTest · คำหยุดที่ไม่ใช่คลิป ("หยุดพูด" "หยุดอ่าน") ยังไม่เป็นคำสั่ง
NOT_MEDIA = ["หยุดเพลงตอนสามทุ่ม", "เพลงนี้ชื่ออะไร", "หยุดพูด", "ปิดเสียง", "เปิดเสียง", "เพิ่มเสียง", "เปิดเพลง",
             "เล่นเกม", "เพลงอะไรเพราะ"]  # fmt: skip


class MediaParseTest(unittest.TestCase):
    def test_each_phrase_maps_to_its_command(self):
        for direction, texts in (("pause", PAUSE), ("play", PLAY), ("next", NEXT)):
            for t in texts:
                with self.subTest(t=t):
                    self.assertEqual(browse.parse(t), [BrowseCommand("media", direction=direction)])

    def test_near_misses_are_not_media(self):
        for t in NOT_MEDIA:
            with self.subTest(t=t):
                self.assertFalse(any(c.kind == "media" for c in browse.parse(t)))
        # เสียงของเครื่องยังเป็นคำสั่งเดิม (การ์ด 0008)
        self.assertEqual(command.parse("ปิดเสียง").plan.action, "mute")
        self.assertEqual(command.parse("เพิ่มเสียง").plan.action, "change_volume")

    def test_media_with_another_step(self):
        self.assertEqual(browse.parse("หยุดเพลงแล้วเลื่อนลง"),
                         [BrowseCommand("media", direction="pause"),
                          BrowseCommand("scroll", direction="down")])  # fmt: skip


class MediaCdp(FakeCdp):
    """หน้าเว็บจำลองที่มีตัวเล่น · media = สถานะที่สคริปต์คืน · next_url = ที่อยู่หลังกด Shift+N ·
    button = ที่อยู่หลังกดปุ่มถัดไป (ว่าง = ไม่มีปุ่ม)."""

    def __init__(self, start, media=None, next_url="", button=""):
        super().__init__({}, start)
        self.media, self.next_url, self.button = media or {}, next_url, button
        self.evals, self.keys = [], []

    def call(self, method, params=None, session="", timeout=15.0):
        params = params or {}
        if method == "Runtime.evaluate":
            self.evals.append(params)
        if method == "Input.dispatchKeyEvent" and params.get("key") == "N":
            self.keys.append((params["type"], params.get("modifiers")))
            if params["type"] == "keyUp" and self.next_url:
                self.go(self.next_url)
            return {}
        return super().call(method, params, session, timeout)

    def evaluate(self, js):
        if js == control.PAUSE_JS:
            return self.media.get("pause", "none")
        if js == control.PLAY_JS:
            return self.media.get("play", "none")
        if js == control.NEXT_BUTTON_JS:
            if self.button:
                self.go(self.button)
            return bool(self.button)
        return super().evaluate(js)


WATCH = "https://www.youtube.com/watch?v=aaa"


def opened_at(url, **kw):
    cdp = MediaCdp("about:blank", **kw)
    bc = BrowserControl(launcher=lambda argv: (FakeProc(), cdp), load_timeout=3)
    assert bc.run(BrowseCommand("url", query=url)).ok
    return bc, cdp


class MediaControlTest(unittest.TestCase):
    def test_pause_and_play_tell_the_truth(self):
        bc, cdp = opened_at(WATCH, media={"pause": "ok", "play": "ok"})
        self.assertEqual(bc.run(BrowseCommand("media", direction="pause")), Result(True, "หยุดแล้ว"))
        self.assertEqual(bc.run(BrowseCommand("media", direction="play")), Result(True, "เล่นต่อแล้ว"))
        play = next(p for p in cdp.evals if p["expression"] == control.PLAY_JS)
        self.assertTrue(play["awaitPromise"] and play["userGesture"])  # นับเป็นการกดของผู้ใช้
        bc, _ = opened_at("https://example.org/news", media={"pause": "none"})
        r = bc.run(BrowseCommand("media", direction="pause"))
        self.assertEqual(r, Result(False, "หน้านี้ไม่มีเพลงหรือวิดีโอ"))
        bc, _ = opened_at(WATCH, media={"pause": "idle", "play": "blocked"})
        self.assertEqual(bc.run(BrowseCommand("media", direction="pause")).say,
                         "ไม่มีเพลงหรือวิดีโอที่กำลังเล่นอยู่")  # fmt: skip
        r = bc.run(BrowseCommand("media", direction="play"))
        self.assertFalse(r.ok)
        self.assertIn("ไม่ยอมให้เล่นต่อ", r.say)

    def test_next_uses_shift_n_first(self):
        bc, cdp = opened_at(WATCH, next_url="https://www.youtube.com/watch?v=bbb")
        r = bc.run(BrowseCommand("media", direction="next"))
        self.assertEqual(
            (r.ok, r.say, r.url), (True, "เปิดเพลงถัดไปแล้ว", "https://www.youtube.com/watch?v=bbb")
        )
        self.assertEqual(cdp.keys, [("rawKeyDown", 8), ("keyUp", 8)])  # 8 = Shift

    def test_next_falls_back_to_player_button(self):
        bc, _ = opened_at(WATCH, button="https://www.youtube.com/watch?v=ccc")
        r = bc.run(BrowseCommand("media", direction="next"))
        self.assertEqual((r.ok, r.say), (True, "กดปุ่มถัดไปให้แล้ว"))
        bc, _ = opened_at(WATCH)
        self.assertEqual(bc.run(BrowseCommand("media", direction="next")),
                         Result(False, "ข้ามไม่ได้ · หน้านี้ไม่มีเพลงถัดไป"))  # fmt: skip

    def test_next_outside_youtube_says_so(self):
        bc, cdp = opened_at("https://example.org/radio")
        r = bc.run(BrowseCommand("media", direction="next"))
        self.assertEqual(r, Result(False, "ข้ามเพลงได้เฉพาะใน YouTube"))
        self.assertEqual(cdp.keys, [])


class FakeControl:
    def __init__(self, running):
        self.running, self.ran, self.available = running, [], True

    def run(self, cmd):
        self.ran.append(cmd.as_dict())
        return Result(True, "หยุดแล้ว")

    def close(self):
        self.running = False


@unittest.skipIf(BrowserController is None, "ไม่มี PySide6")
class MediaRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_routes(self):
        self.assertEqual(route("หยุดเพลง", False), NEEDS_BROWSER)  # ยังไม่ได้เปิดเพลง
        self.assertEqual(route("หยุดเพลง", True), BROWSER)
        self.assertEqual(route("เพลงถัดไป", True), BROWSER)
        self.assertNotEqual(route("หยุดเพลงตอนสามทุ่ม", True), BROWSER)  # งานทีหลัง ไม่ทำตอนนี้
        self.assertEqual(route("ปิดเสียง", True), COMMAND)

    def test_hint_and_handle(self):
        b = BrowserController(control=FakeControl(running=False))
        self.assertIn("เปิดยูทูบ", b.hint("หยุดเพลง"))
        self.assertIn("เปิดเบราว์เซอร์", b.hint("เลื่อนลง"))  # ข้อความเดิมของ 0027
        self.assertFalse(b.handle("หยุดเพลง"))  # เบราว์เซอร์ยังไม่เปิด = ไม่ใช่งานของเรา
        ctl = FakeControl(running=True)
        self.assertTrue(BrowserController(control=ctl).handle("หยุดเพลง"))


try:
    from tests import test_ui_qml as qml
except ImportError:  # pragma: no cover
    qml = None


@unittest.skipIf(qml is None or qml.uiapp is None, "ไม่มี PySide6")
class MediaQmlTest(unittest.TestCase):
    open_shell = qml.ShellCardTest.open_shell if qml and qml.uiapp else None

    @classmethod
    def setUpClass(cls):
        qml.setUpModule()

    @classmethod
    def tearDownClass(cls):
        qml.tearDownModule()

    def test_media_before_any_music_says_open_music_first(self):
        engine, win, warnings = self.open_shell("workspace")
        engine._backends["browser"]._control = FakeControl(running=False)  # ไม่เปิด Chromium จริง
        page = qml.find_all(win, "workspace")[0]
        page.voiceCommand("หยุดเพลง")
        qml.settle(50)
        vc = qml.vc_of(page)  # ผลคำสั่งเสียงเด้งบนจอ ไม่ลงแชท (Pakon 2026-10-20)
        self.assertEqual(vc["heard"], "หยุดเพลง")
        self.assertIn("ยังไม่ได้เปิดเพลง", vc["text"])
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
