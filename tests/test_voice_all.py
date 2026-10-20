"""คีย์ลัดเสียงใช้ได้กับทุกสกิล (การ์ด 0042) · เบราว์เซอร์จำลอง (ไม่เปิด Chromium จริง).

ตรวจ: คำใหม่ของเว็บ (รีเซ็ตหน้า · เลือกคลิป · เล่นวิดีโอ · เต็มจอ · ข้ามโฆษณา) · ตัวเล่นทำตามจริงและบอกผลตามจริง ·
ชุดพัฒนาของการ์ดผ่านครบ (ชุดทดสอบ held-out ไม่อยู่ในเทสต์นี้ · วัดครั้งเดียวด้วย aipc.spikes.voice_all_eval)
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aipc.browser import control
from aipc.browser.control import BrowserControl, Result
from aipc.skills import browse
from aipc.skills.browse import BrowseCommand
from tests.test_browser_control import FakeCdp, FakeProc

WATCH = "https://www.youtube.com/watch?v=aaa"
RESULTS = "https://www.youtube.com/results?search_query=cat"

PARSE = {
    "รีเซ็ตหน้า": BrowseCommand("reload"),
    "รีเซ็ตหน้าเว็บ": BrowseCommand("reload"),
    "เข้าวีดีโอ": BrowseCommand("open", n=1, direction="clip"),
    "เปิดวิดีโอแรก": BrowseCommand("open", n=1, direction="clip"),
    "ดูคลิปที่สอง": BrowseCommand("open", n=2, direction="clip"),
    "เข้าลิงก์ที่สาม": BrowseCommand("open", n=3),  # ลิงก์ทั่วไปไม่ใช่คลิป
    "เล่นวิดีโอ": BrowseCommand("media", direction="play"),
    "เต็มจอ": BrowseCommand("fullscreen"),
    "ออกจากเต็มจอ": BrowseCommand("fullscreen"),
    "ข้ามโฆษณา": BrowseCommand("skip_ad"),
}
# มีคำว่าคลิป/เต็ม/โฆษณา/รีเซ็ต แต่ไม่ใช่คำสั่งเว็บ
NOT_WEB = ["วิดีโอนี้ยาวมาก", "โฆษณานี้น่ารำคาญ", "หน้าจอมืดไปหน่อย", "เต็มที่", "รีเซ็ตรหัสผ่านยังไง",
           "เล่นเกม", "เปิดเพลง"]  # fmt: skip


class ParseTest(unittest.TestCase):
    def test_new_web_words(self):
        for text, want in PARSE.items():
            with self.subTest(text=text):
                self.assertEqual(browse.parse(text), [want])

    def test_near_misses_are_not_web_commands(self):
        for text in NOT_WEB:
            with self.subTest(text=text):
                self.assertEqual(browse.parse(text), [])


class PlayerCdp(FakeCdp):
    """ตัวเล่นจำลอง: f = สลับเต็มจอ (YouTube) · full_js / skip = สิ่งที่สคริปต์ของหน้าคืน."""

    def __init__(self, start, full_js="none", skip="none", f_works=True):
        super().__init__({}, start)
        self.full, self.full_js, self.skip, self.f_works = False, full_js, skip, f_works
        self.keys = []

    def call(self, method, params=None, session="", timeout=15.0):
        params = params or {}
        if method == "Input.dispatchKeyEvent":
            self.keys.append((params["type"], params["key"]))
            if params["type"] == "keyUp" and params["key"] == "f" and self.f_works:
                self.full = not self.full
            return {}
        return super().call(method, params, session, timeout)

    def evaluate(self, js):
        if js == "!!document.fullscreenElement":
            return self.full
        if js == control.FULLSCREEN_JS:
            return self.full_js
        if js == control.SKIP_AD_JS:
            return self.skip
        return super().evaluate(js)


def opened_at(url, **kw):
    cdp = PlayerCdp("about:blank", **kw)
    bc = BrowserControl(launcher=lambda argv: (FakeProc(), cdp), load_timeout=3)
    assert bc.run(BrowseCommand("url", query=url)).ok
    return bc, cdp


class PlayerTest(unittest.TestCase):
    def test_fullscreen_on_youtube_uses_player_key_and_checks_result(self):
        bc, cdp = opened_at(WATCH)
        self.assertEqual(bc.run(BrowseCommand("fullscreen")), Result(True, "เต็มจอแล้ว"))
        self.assertEqual(bc.run(BrowseCommand("fullscreen")), Result(True, "ออกจากเต็มจอแล้ว"))
        self.assertEqual(cdp.keys, [("rawKeyDown", "f"), ("keyUp", "f")] * 2)

    def test_fullscreen_elsewhere_or_without_video_tells_the_truth(self):
        bc, _ = opened_at("https://example.org/clip", full_js="on")
        self.assertEqual(bc.run(BrowseCommand("fullscreen")), Result(True, "เต็มจอแล้ว"))
        bc, _ = opened_at("https://example.org/news", full_js="none")
        self.assertEqual(bc.run(BrowseCommand("fullscreen")), Result(False, "หน้านี้ไม่มีวิดีโอให้เต็มจอ"))
        # คีย์ f ไม่ได้ผล (เช่นโฆษณาบัง) → ใช้ตัวเล่นของหน้าแทน
        bc, _ = opened_at(WATCH, f_works=False, full_js="blocked")
        r = bc.run(BrowseCommand("fullscreen"))
        self.assertFalse(r.ok)
        self.assertIn("กดปุ่มเต็มจอ", r.say)

    def test_skip_ad_only_when_the_button_is_there(self):
        bc, _ = opened_at(WATCH, skip="ok")
        self.assertEqual(bc.run(BrowseCommand("skip_ad")), Result(True, "ข้ามโฆษณาแล้ว"))
        bc, _ = opened_at(WATCH, skip="wait")
        r = bc.run(BrowseCommand("skip_ad"))
        self.assertFalse(r.ok)
        self.assertIn("รอปุ่มข้าม", r.say)
        bc, _ = opened_at(WATCH, skip="none")
        self.assertEqual(bc.run(BrowseCommand("skip_ad")), Result(False, "ตอนนี้ไม่มีโฆษณาให้ข้าม"))
        bc, _ = opened_at("https://example.org/clip", skip="ok")
        self.assertEqual(bc.run(BrowseCommand("skip_ad")), Result(False, "ข้ามโฆษณาได้เฉพาะใน YouTube"))

    def test_open_clip_while_watching_does_not_click_side_links(self):
        bc, _ = opened_at(WATCH)
        r = bc.run(BrowseCommand("open", n=1, direction="clip"))
        self.assertFalse(r.ok)
        self.assertIn("กำลังดูคลิปอยู่", r.say)
        self.assertEqual(bc.current().get("url", WATCH), WATCH)


class DevSetTest(unittest.TestCase):
    """ชุดพัฒนาของการ์ด 0042 (ประโยคที่ Pakon พูดจริง + ตัวอย่างในไฟล์สกิล) ผ่านครบ · ไม่ใช่คำสั่งไม่ถูกทำ."""

    def test_dev_set(self):
        from aipc.spikes import voice_all_eval

        _engine, skills = voice_all_eval.backend()
        res = voice_all_eval.score("dev", skills)
        self.assertEqual(res["wrong"], [])
        self.assertEqual(res["noncommands_acted"], 0)

    def test_editing_an_appointment_never_creates_a_new_one(self):
        """เกณฑ์ V3: "เลื่อน/ลบนัด…" (รวมที่ได้ยินเพี้ยน) ไม่ไปทางตั้งเตือนใหม่."""
        from aipc.spikes import voice_all_eval

        _engine, skills = voice_all_eval.backend()
        for text in ("เลื่อนนักประชุมไปพรุ่งนี้", "เลื่อนัดหมอฟันเป็นวันศุกร์", "ลบนัดประชุมพรุ่งนี้"):
            with self.subTest(text=text):
                self.assertEqual(skills.voiceIntent(text), "")


if __name__ == "__main__":
    unittest.main()
