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


class LoginWindowTest(unittest.TestCase):
    """“เข้าสู่ระบบยูทูบ”: ปิดเบราว์เซอร์ที่ถูกคุม แล้วเปิดหน้า Google แบบไม่คุมด้วยโปรไฟล์เดียวกัน."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        from unittest import mock

        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.profile = Path(self.dir.name) / "browser"
        self.started = []

        class LoginProc:
            alive = True

            def poll(self):
                return None if self.alive else 0

        self.proc = LoginProc()

        def popen(argv, **kw):
            self.started.append(argv)
            return self.proc

        patcher = mock.patch.object(control.subprocess, "Popen", side_effect=popen)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.b = BrowserControl(
            profile=self.profile, launcher=lambda argv: (FakeProc(), FakeCdp({}))
        )

    def test_login_opens_uncontrolled_window_with_same_profile(self):
        self.b._start("about:blank")
        r = self.b.run(control.BrowseCommand("login", site="google"))
        self.assertTrue(r.ok)
        self.assertFalse(self.b.running)  # เบราว์เซอร์ที่ถูกคุมปิดแล้ว (ปล่อยโปรไฟล์)
        argv = self.started[0]
        self.assertIn(f"--user-data-dir={self.profile}", argv)
        self.assertNotIn("--remote-debugging-pipe", argv)
        self.assertEqual(argv[-1], control.LOGIN_URL)

    def test_after_sign_in_goes_to_the_google_account_page_not_youtube(self):
        """Pakon 2026-10-27: "เข้าสู่ระบบกูเกิล" แล้วไปหน้า YouTube เอง → ไปหน้าบัญชี Google แทน."""
        from urllib.parse import parse_qs, urlsplit

        q = parse_qs(urlsplit(control.LOGIN_URL).query)
        self.assertEqual(q["continue"], ["https://myaccount.google.com/"])
        self.assertNotIn("youtube", control.LOGIN_URL)

    def test_other_commands_wait_for_login_window(self):
        self.b.run(control.BrowseCommand("login", site="google"))
        r = self.b.run(control.BrowseCommand("site", site="youtube"))
        self.assertFalse(r.ok)
        self.assertIn("ปิดหน้าต่าง", r.say)
        again = self.b.run(control.BrowseCommand("login", site="google"))
        self.assertEqual(len(self.started), 1)  # ไม่เปิดหน้าต่างซ้อน
        self.assertTrue(again.ok)
        self.proc.alive = False  # ผู้ใช้ปิดหน้าต่างแล้ว → เปิดเบราว์เซอร์ของผู้ช่วยได้ตามเดิม
        self.assertFalse(self.b.logging_in)
        self.assertTrue(self.b.run(control.BrowseCommand("site", site="youtube")).ok)


class GoogleLoginPageTest(unittest.TestCase):
    """การ์ด 0064: Gmail ในเบราว์เซอร์ของผู้ช่วย · ยังไม่เข้าสู่ระบบ = เด้งไปหน้า Google →
    บอกทางเข้าสู่ระบบ ไม่บอก "เปิดแล้ว"."""

    LOGIN = (
        "https://accounts.google.com/v3/signin/identifier?continue=https%3A%2F%2Fmail.google.com"
    )

    def browser(self, redirect: bool):
        cdp_ = FakeCdp({})
        go = cdp_.go

        def go_redirect(url):
            go(self.LOGIN if redirect and "google.com" in url and "accounts." not in url else url)

        cdp_.go = go_redirect
        return BrowserControl(launcher=lambda argv: (FakeProc(), cdp_))

    def test_not_signed_in_says_how_to_sign_in(self):
        r = self.browser(redirect=True).run(control.BrowseCommand("site", site="gmail"))
        self.assertFalse(r.ok)  # H5
        self.assertIn("เข้าสู่ระบบกูเกิล", r.say)
        r = self.browser(redirect=True).run(
            control.BrowseCommand("site_search", query="ใบเสร็จ", site="gmail")
        )
        self.assertFalse(r.ok)
        self.assertIn("เข้าสู่ระบบกูเกิล", r.say)

    def test_signed_in_opens_normally(self):
        r = self.browser(redirect=False).run(control.BrowseCommand("site", site="gmail"))
        self.assertTrue(r.ok)
        self.assertEqual(r.say, "เปิด Gmail แล้ว")

    def test_only_the_google_sign_in_host_counts(self):
        self.assertTrue(control.google_login_page(self.LOGIN))
        for url in ["https://mail.google.com/mail/u/0/", "https://www.youtube.com/",
                    "https://example.org/?next=accounts.google.com", "about:blank"]:  # fmt: skip
            self.assertFalse(control.google_login_page(url), url)


class TabsCdp(FakeCdp):
    """หลายแท็บ: แต่ละแท็บมีหน้าของตัวเอง · front = แท็บที่ผู้ใช้เห็น (การ์ด 0065)."""

    def __init__(self, first="about:blank"):
        super().__init__({})
        self.tabs = {"T1": FakePage(first)}
        self.front, self.sessions, self.n = "T1", {}, 1

    def call(self, method, params=None, session="", timeout=15.0):
        params = params or {}
        if method == "Target.getTargets":
            self.calls.append(method)
            return {"targetInfos": [{"type": "page", "targetId": t, "url": p.url}
                                    for t, p in reversed(self.tabs.items())]}  # fmt: skip
        if method == "Target.attachToTarget":
            sid = f"S-{params['targetId']}-{len(self.sessions)}"
            self.sessions[sid] = params["targetId"]
            return {"sessionId": sid}
        if method == "Target.createTarget":
            self.n += 1
            t = f"T{self.n}"
            self.tabs[t] = FakePage(params["url"])
            self.front = t
            return {"targetId": t}
        if method == "Target.activateTarget":
            self.front = params["targetId"]
            return {}
        if method == "Target.closeTarget":
            del self.tabs[params["targetId"]]
            self.front = next(reversed(self.tabs), "")
            return {}
        if session in self.sessions:
            target = self.sessions[session]
            if method == "Runtime.evaluate" and params["expression"] == "document.visibilityState":
                return {"result": {"value": "visible" if target == self.front else "hidden"}}
            self.cur = self.tabs[target]
        return super().call(method, params, session, timeout)

    def go(self, url):
        self.cur.url = url
        self.marker = None


class NewTabTest(unittest.TestCase):
    """การ์ด 0065: เปิดเว็บไม่ทับหน้าเดิม · เว็บเดิม = สลับไปแท็บนั้น · คำสั่งตามแท็บที่ผู้ใช้เห็น."""

    def setUp(self):
        self.cdp = TabsCdp()
        self.b = BrowserControl(launcher=lambda argv: (FakeProc(), self.cdp))

    def site(self, name):
        return self.b.run(control.BrowseCommand("site", site=name))

    def urls(self):
        return {t: p.url for t, p in self.cdp.tabs.items()}

    def test_first_site_uses_the_blank_tab(self):
        self.assertTrue(self.site("youtube").ok)
        self.assertEqual(len(self.cdp.tabs), 1)

    def test_second_site_opens_a_new_tab_and_keeps_the_first(self):
        self.site("youtube")
        self.cdp.tabs["T1"].url = "https://www.youtube.com/watch?v=abc"  # กำลังดูคลิป
        r = self.site("gmail")
        self.assertTrue(r.ok)
        self.assertEqual(len(self.cdp.tabs), 2)
        self.assertEqual(self.cdp.tabs["T1"].url, "https://www.youtube.com/watch?v=abc")  # H2
        self.assertTrue(self.cdp.tabs["T2"].url.startswith("https://mail.google.com"))
        self.assertEqual(self.cdp.front, "T2")

    def test_open_site_that_is_already_open_switches_without_reloading(self):
        self.site("youtube")
        self.cdp.tabs["T1"].url = "https://www.youtube.com/watch?v=abc"
        self.site("gmail")
        r = self.site("youtube")
        self.assertTrue(r.ok)
        self.assertEqual(r.say, "สลับไปแท็บ YouTube แล้ว")
        self.assertEqual(len(self.cdp.tabs), 2)  # ไม่เปิดแท็บที่ 3
        self.assertEqual(self.cdp.front, "T1")
        self.assertEqual(self.cdp.tabs["T1"].url, "https://www.youtube.com/watch?v=abc")  # คลิปไม่หาย

    def test_commands_follow_the_tab_the_user_clicked(self):
        self.site("youtube")
        self.site("gmail")
        self.cdp.front = "T1"  # ผู้ใช้คลิกกลับไปแท็บ YouTube เอง
        self.b.run(control.BrowseCommand("reload"))
        self.assertEqual(self.b._target, "T1")

    def test_search_stays_in_the_current_tab(self):
        self.site("youtube")
        self.b.run(control.BrowseCommand("search", query="ข่าว"))
        self.assertEqual(len(self.cdp.tabs), 1)

    def test_full_does_not_open_or_close_tabs(self):
        for i in range(control.MAX_TABS):
            self.cdp.tabs[f"X{i}"] = FakePage(f"https://site{i}.example/")
        self.cdp.tabs.pop("T1")
        self.cdp.front = "X0"
        r = self.site("youtube")
        self.assertFalse(r.ok)
        self.assertIn("ปิดแท็บ", r.say)
        self.assertEqual(len(self.cdp.tabs), control.MAX_TABS)  # ไม่ปิดแท็บของผู้ใช้เอง

    def test_another_tab_of_the_same_site_when_asked(self):
        """Pakon 2026-10-26: "เปิดยูทูบอีกแท็บ" = แท็บใหม่แม้ YouTube เปิดอยู่ · ไม่ทับแท็บที่ดูอยู่."""
        self.site("youtube")
        self.site("gmail")
        r = self.b.run(control.BrowseCommand("site", site="youtube", direction="newtab"))
        self.assertTrue(r.ok)
        self.assertEqual(len(self.cdp.tabs), 3)
        self.assertTrue(self.cdp.tabs["T2"].url.startswith("https://mail.google.com"))  # ไม่ทับ

    def test_close_all_closes_the_browser(self):
        self.site("youtube")
        self.site("gmail")
        r = self.b.run(control.BrowseCommand("close", direction="all"))
        self.assertEqual((r.ok, r.say), (True, "ปิดแท็บทั้งหมดแล้ว"))
        self.assertFalse(self.b.running)

    def test_same_site(self):
        self.assertTrue(
            control.same_site("https://www.youtube.com/watch?v=1", "https://youtube.com")
        )
        self.assertFalse(control.same_site("https://mail.google.com", "https://drive.google.com"))
        self.assertFalse(control.same_site("about:blank", "about:blank"))


class YoutubeClipSelectorTest(unittest.TestCase):
    """S0 ข้อ 2 (การ์ด 0064 · Pi 5 2026-10-26): หน้าแรก YouTube ที่เข้าสู่ระบบแล้วใช้ class แบบใหม่ ·
    ตัวเลือกเดิมเจอ 0 ลิงก์ ("หน้านี้ไม่มีคลิปให้เลือก") · เพิ่มแล้วเจอ 22 (yt_links_probe.py) ·
    JS รันจริงได้บน Pi เท่านั้น ที่นี่กันไม่ให้ชื่อใดชื่อหนึ่งหายไปตอนแก้ครั้งหน้า."""

    def test_both_old_and_new_title_classes_are_kept(self):
        for cls in ("a.yt-lockup-metadata-view-model__title", "a.ytLockupMetadataViewModelTitle"):
            self.assertIn(cls, control.LINKS_JS)


if __name__ == "__main__":
    unittest.main()
