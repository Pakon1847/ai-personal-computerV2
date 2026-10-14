"""ตัวคุมเบราว์เซอร์ของผู้ช่วย (การ์ด 0024 · 0025): ขั้นที่ AI สั่ง กับเบราว์เซอร์จำลอง.

เบราว์เซอร์จริงทดสอบบน Pi (src/aipc/spikes/agent_e2e.py · browser_e2e.py) · ที่นี่ตรวจทางเดินของโค้ด:
รอหน้าโหลด · พิมพ์ด้วย Input.insertText · กด Enter · หน้าที่ไม่มีช่องค้นหา · Google ขอยืนยันว่าไม่ใช่บอต
"""

import os
import shutil
import sys
import unittest
from urllib.parse import parse_qs, urlsplit

from aipc.browser import cdp, control, page
from aipc.browser.agent import Step
from aipc.browser.control import BrowserControl


class FakeProc:
    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


class FakePage:
    """หน้าเว็บจำลอง: ที่อยู่ · รายการติดเลข (n → (ชนิด, ป้าย, href)) · มีช่องค้นหาไหม."""

    def __init__(self, url, items=None, search_box=False):
        self.url, self.items, self.search_box = url, items or {}, search_box


class FakeCdp:
    """ตอบ Runtime.evaluate ตามสคริปต์ที่ BrowserControl ส่ง (ไม่ได้รัน JS จริง)."""

    def __init__(self, pages: dict, start="about:blank"):
        self.pages, self.closed = pages, False
        self.cur = FakePage(start)
        self.marker = None
        self.typed, self.keys, self.calls = [], [], []
        self.focused = None

    def go(self, url):
        self.cur = self.pages.get(url.split("#")[0]) or FakePage(url)
        self.cur.url = url
        self.marker = None

    def call(self, method, params=None, session="", timeout=15.0):
        params = params or {}
        self.calls.append(method)
        if method == "Target.getTargets":
            return {"targetInfos": [{"type": "page", "targetId": "T1"}]}
        if method == "Target.attachToTarget":
            return {"sessionId": "S1"}
        if method == "Page.navigate":
            self.go(params["url"])
            return {}
        if method == "Input.insertText":
            self.typed.append(params["text"])
            return {}
        if method == "Input.dispatchKeyEvent":
            if (
                params["type"] == "keyDown"
                and params["key"] == "Enter"
                and self.focused == "search"
            ):
                q = self.typed[-1]
                self.go(f"https://{urlsplit(self.cur.url).hostname}/results?q={q}")
            return {}
        if method == "Browser.getWindowForTarget":
            return {"windowId": 1}
        if method == "Runtime.evaluate":
            return {"result": {"value": self.evaluate(params["expression"])}}
        return {}

    def evaluate(self, js):
        if js.startswith("window.__aipcOld = ") and js.endswith("; location.href"):
            self.marker = int(js.split("=")[1].split(";")[0])
            return self.cur.url
        if js.startswith("window.__aipcOld = "):
            self.marker = int(js.split("=")[1])
            return None
        if js.startswith("[document.readyState, location.href, window.__aipcOld === "):
            token = int(js.rsplit("=== ", 1)[1].rstrip("]"))
            return ["complete", self.cur.url, self.marker == token]
        if js == "location.href":
            return self.cur.url
        if js == "[document.title, location.href]":
            return ["หน้า", self.cur.url]
        if js == "[location.href, Math.round(scrollY)]":
            return [self.cur.url, 0]
        if js.startswith("(" + control.CLICK_JS):
            n = int(js.rsplit("(", 1)[1].rstrip(")"))
            if n not in self.cur.items:
                return None
            kind, label, href = self.cur.items[n]
            if href:
                self.go(href)
            return label
        if js.startswith("(" + control.TYPE_JS):
            n = int(js.rsplit("(", 1)[1].split(",")[0])
            if n not in self.cur.items:
                return "missing"
            if self.cur.items[n][0] != "ช่อง":
                return "notfield"
            self.focused = n
            return "ok"
        if js == control.FIND_JS:
            if self.cur.search_box:
                self.focused = "search"
            return self.cur.search_box
        if js == control.LINKS_JS:
            return [{"href": h, "text": t} for k, t, h in self.cur.items.values() if h]
        if js == page.OBSERVE_JS:
            return {
                "title": "หน้า",
                "url": self.cur.url,
                "items": [
                    {"n": n, "kind": k, "label": t} for n, (k, t, _) in self.cur.items.items()
                ],
            }
        raise AssertionError(f"สคริปต์ที่ไม่รู้จัก: {js[:80]}")

    def close(self):
        self.closed = True


def make(pages, start="about:blank"):
    cdp = FakeCdp(pages, start)
    bc = BrowserControl(launcher=lambda argv: (FakeProc(), cdp), load_timeout=3)
    return bc, cdp


GOOGLE_SORRY = "https://www.google.com/sorry/index"


class BrowserStepTest(unittest.TestCase):
    def test_click_link_waits_for_new_page(self):
        bc, cdp = make({"https://news.example.com": FakePage("https://news.example.com", {
            1: ("ลิงก์", "ข่าวกีฬา", "https://news.example.com/sport")})})  # fmt: skip
        bc.act(Step("open", 0, "news.example.com"))
        r = bc.act(Step("click", 1))
        self.assertTrue(r.ok)
        self.assertEqual(r.say, "กด ข่าวกีฬา แล้ว → news.example.com")
        self.assertEqual(cdp.cur.url, "https://news.example.com/sport")

    def test_click_missing_item_fails(self):
        bc, _ = make({"https://a.example.com": FakePage("https://a.example.com", {})})
        bc.act(Step("open", 0, "a.example.com"))
        r = bc.act(Step("click", 7))
        self.assertFalse(r.ok)
        self.assertIn("ไม่มีรายการที่ 7", r.say)

    def test_type_uses_real_key_input_and_refuses_non_fields(self):
        bc, cdp = make({"https://form.example.com": FakePage("https://form.example.com", {
            1: ("ช่อง", "ชื่อ", ""), 2: ("ปุ่ม", "ส่ง", "")})})  # fmt: skip
        bc.act(Step("open", 0, "form.example.com"))
        r = bc.act(Step("type", 1, "สมชาย ใจดี"))
        self.assertTrue(r.ok)
        self.assertEqual(cdp.typed, ["สมชาย ใจดี"])
        self.assertFalse(bc.act(Step("type", 2, "x")).ok)
        self.assertEqual(cdp.typed, ["สมชาย ใจดี"], "ปุ่มพิมพ์ไม่ได้")

    def test_find_types_into_site_search_and_presses_enter(self):
        bc, cdp = make({"https://www.youtube.com": FakePage("https://www.youtube.com", {},
                                                           search_box=True)})  # fmt: skip
        bc.act(Step("open", 0, "ยูทูบ"))
        r = bc.act(Step("find", 0, "คาราบาว"))
        self.assertTrue(r.ok)
        self.assertEqual(cdp.cur.url, "https://www.youtube.com/results?q=คาราบาว")
        self.assertIn("Input.dispatchKeyEvent", cdp.calls)

    def test_find_without_search_box_searches_the_web_for_that_site(self):
        bc, cdp = make({"https://shop.example.com": FakePage("https://shop.example.com"),
                        GOOGLE_SORRY: FakePage(GOOGLE_SORRY)})  # fmt: skip
        bc.act(Step("open", 0, "shop.example.com"))
        real_go = cdp.go
        cdp.go = lambda url: real_go(GOOGLE_SORRY if "google.com/search" in url else url)
        r = bc.act(Step("find", 0, "หมวก"))
        self.assertTrue(r.ok)
        q = parse_qs(urlsplit(cdp.cur.url).query)["q"][0]
        self.assertTrue(cdp.cur.url.startswith(control.DDG.split("?")[0]))
        self.assertEqual(q, "หมวก site:shop.example.com")

    def test_google_bot_check_switches_to_duckduckgo_for_the_session(self):
        bc, cdp = make({GOOGLE_SORRY: FakePage(GOOGLE_SORRY)})
        real_go = cdp.go
        cdp.go = lambda url: real_go(GOOGLE_SORRY if "google.com/search" in url else url)
        r = bc.act(Step("search", 0, "ราคาทอง"))
        self.assertIn("DuckDuckGo", r.say)
        self.assertIn("duckduckgo.com", cdp.cur.url)
        cdp.calls.clear()
        bc.act(Step("search", 0, "ราคาเงิน"))
        self.assertEqual(cdp.calls.count("Page.navigate"), 1, "ครั้งต่อไปไป DuckDuckGo ตรง ๆ")

    def test_unknown_site_name_opens_first_search_result(self):
        ddg = control.DDG
        bc, cdp = make({})
        real_go = cdp.go

        def go(url):
            real_go(url)
            if url.startswith(ddg):
                cdp.cur.items = {1: ("ลิงก์", "ร้านป้าแดง", "https://padaeng.example.com/")}

        cdp.go = go
        r = bc.act(Step("open", 0, "ร้านป้าแดง"))
        self.assertTrue(r.ok, r.say)
        self.assertEqual(cdp.cur.url, "https://padaeng.example.com/")

    def test_page_steps_need_an_open_browser(self):
        bc, _ = make({})
        r = bc.act(Step("click", 1))
        self.assertFalse(r.ok)
        self.assertFalse(r.handled)
        self.assertEqual(bc.observe(), {})


# เบราว์เซอร์ปลอม: อ่านคำสั่งจาก fd 3 แล้วตอบทาง fd 4 แบบเดียวกับ Chromium --remote-debugging-pipe
FAKE_BROWSER = (
    "import json, os\n"
    "buf = b''\n"
    "while b'\\0' not in buf:\n"
    "    buf += os.read(3, 4096)\n"
    "msg = json.loads(buf.split(b'\\0')[0])\n"
    "os.write(4, json.dumps({'id': msg['id'], 'result': {'product': 'ปลอม'}}).encode() + b'\\0')\n"
)


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "pipe แบบ fd 3/4 มีเฉพาะ Linux")
class LaunchTest(unittest.TestCase):
    def test_pipe_reaches_browser_when_app_has_many_open_files(self):
        """แอปจริงเปิดไฟล์ไว้ ~28 ช่อง → os.pipe() ได้เลข ≥ 10 · dash (sh ของ Pi) รับเลข fd หลักเดียว
        ("Bad fd number") → เบราว์เซอร์ไม่เคยเปิด = "เบราว์เซอร์ปิดไปแล้ว" (Pi 5 2026-10-14)."""
        spare = [os.open(os.devnull, os.O_RDONLY) for _ in range(12)]
        self.addCleanup(lambda: [os.close(fd) for fd in spare])
        probe = os.open(os.devnull, os.O_RDONLY)
        os.close(probe)
        self.assertGreaterEqual(probe, 10)  # จำลองสภาพในแอปได้จริง
        proc, client = cdp.launch([sys.executable, "-c", FAKE_BROWSER])
        self.addCleanup(client.close)
        self.assertEqual(client.call("Browser.getVersion", timeout=10), {"product": "ปลอม"})
        proc.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
