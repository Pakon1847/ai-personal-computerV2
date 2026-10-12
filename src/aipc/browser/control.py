"""ทำคำสั่งเว็บจากเสียงกับเบราว์เซอร์ของผู้ช่วย (การ์ด 0024).

แอปเปิด Chromium เองด้วยโปรไฟล์แยก (`~/.local/share/aipc/browser`) และคุมทาง pipe (cdp.py) ·
ทุกคำสั่งตรวจผลจากหน้าเว็บจริง (URL / ตำแหน่งเลื่อน) แล้วตอบประโยคสั้น ๆ ให้อ่านออกเสียง ·
เรียกจากเธรดแยกเท่านั้น (รอหน้าโหลดได้หลายวินาที)
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus, urlsplit

from aipc.browser import cdp
from aipc.skills.actions import SITES
from aipc.skills.browse import BrowseCommand

GOOGLE = "https://www.google.com/search?hl=th&q="
BING = "https://www.bing.com/search?setlang=th&q="
# คำสั่งที่ต้องมีหน้าเว็บเปิดอยู่ก่อน · เบราว์เซอร์ยังไม่เปิด = ไม่ใช่งานของเรา ส่งประโยคไปทางเดิมของแอป
NEEDS_PAGE = {"open", "back", "forward", "reload", "scroll", "close", "app"}

# ลิงก์ที่ N = "อันที่เห็นบนจอ" (Pakon เลือก 2026-10-13 · รวมโฆษณา) เรียงจากบนลงล่าง ·
# หน้าผลค้นหา = หัวข้อผลค้นหา · หน้าอื่น = ลิงก์ที่มองเห็นในจอตอนนี้
LINKS_JS = r"""(() => {
  const host = location.hostname, seen = new Set(), out = [];
  let sel = null;
  if (/(^|\.)google\./.test(host) && location.pathname === '/search')
    sel = '#search a h3, #rso a h3, #tads a [role=heading], #tvcap a [role=heading], #bottomads a [role=heading]';
  else if (/(^|\.)bing\.com$/.test(host) && location.pathname === '/search')
    sel = 'li.b_algo h2 a, li.b_ad h2 a, .b_adTop h2 a';
  else if (/duckduckgo\.com$/.test(host))
    sel = 'a.result__a, a[data-testid=result-title-a]';
  const push = (a) => {
    if (!a || !a.href || a.href.startsWith('javascript:') || seen.has(a.href)) return;
    const r = a.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    seen.add(a.href);
    out.push({href: a.href, text: (a.innerText || '').trim().slice(0, 80), y: r.top + scrollY, x: r.left});
  };
  if (sel) {
    for (const el of document.querySelectorAll(sel)) push(el.closest('a') || el);
  } else {
    for (const a of document.querySelectorAll('a[href]')) {
      const r = a.getBoundingClientRect();
      if (r.bottom < 0 || r.top > innerHeight || (a.innerText || '').trim().length < 2) continue;
      push(a);
    }
  }
  return out.sort((p, q) => (p.y - q.y) || (p.x - q.x));
})()"""


@dataclass
class Result:
    ok: bool
    say: str  # ประโยคสั้น ๆ ให้อ่านออกเสียง/แสดงในการ์ด
    handled: bool = True  # False = ไม่ใช่งานเบราว์เซอร์ตอนนี้ → ส่งประโยคไปทางเดิมของแอป
    url: str = ""


def default_profile() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "aipc" / "browser"


class BrowserControl:
    def __init__(self, profile: Path | None = None, chromium: str = "chromium",
                 extra_args: list[str] | None = None, launcher=cdp.launch, load_timeout=12.0):  # fmt: skip
        self._profile = profile or default_profile()
        self._chromium, self._extra = chromium, list(extra_args or [])
        self._launch, self._load_timeout = launcher, load_timeout
        self._proc = self._cdp = None
        self._session = self._target = ""
        self._lock = threading.Lock()  # ทีละคำสั่ง

    # ---------- เปิด / ต่อ ----------
    @property
    def running(self) -> bool:
        return self._cdp is not None and not self._cdp.closed and self._proc.poll() is None

    def _start(self, url: str) -> None:
        self._profile.mkdir(parents=True, exist_ok=True)
        argv = [self._chromium, f"--user-data-dir={self._profile}", "--remote-debugging-pipe",
                "--no-first-run", "--no-default-browser-check", "--start-maximized",
                *self._extra, url]  # fmt: skip
        self._proc, self._cdp = self._launch(argv)
        self._session = self._target = ""
        self._cdp.call("Browser.getVersion", timeout=30)  # รอจนพร้อม (เปิดครั้งแรกบน Pi ~1–3 วิ)

    def _page(self) -> str:
        """session ของแท็บที่ใช้อยู่ (แท็บล่าสุด) · แท็บเดิมปิดไปแล้ว = ต่อแท็บใหม่."""
        pages = [t for t in self._cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page"]
        if not pages:
            created = self._cdp.call("Target.createTarget", {"url": "about:blank"})
            pages = [{"targetId": created["targetId"]}]
        target = pages[0]["targetId"]
        if target != self._target or not self._session:
            self._session = self._cdp.call(
                "Target.attachToTarget", {"targetId": target, "flatten": True}
            )["sessionId"]
            self._target = target
        return self._session

    def _eval(self, js: str):
        r = self._cdp.call("Runtime.evaluate", {"expression": js, "returnByValue": True},
                           session=self._page())  # fmt: skip
        return r.get("result", {}).get("value")

    def _url(self) -> str:
        return self._eval("location.href") or ""

    def _go(self, url: str) -> str:
        self._cdp.call("Page.navigate", {"url": url}, session=self._page())
        return self._wait_load()

    def _wait_load(self, before: str = "") -> str:
        end = time.monotonic() + self._load_timeout
        time.sleep(0.3)
        while time.monotonic() < end:
            try:
                state, url = self._eval("[document.readyState, location.href]") or ("", "")
            except cdp.CdpError:  # ระหว่างเปลี่ยนหน้า context เดิมหายชั่วคราว
                state, url = "", ""
            if state in ("interactive", "complete") and url and url != before:
                return url
            time.sleep(0.25)
        return self._url()

    def _front(self) -> None:
        """เบราว์เซอร์มาอยู่หน้าสุด (เคยย่อไว้ด้วย "กลับไปแอป")."""
        try:
            win = self._cdp.call("Browser.getWindowForTarget", {"targetId": self._target})
            self._cdp.call("Browser.setWindowBounds",
                           {"windowId": win["windowId"], "bounds": {"windowState": "maximized"}})  # fmt: skip
        except cdp.CdpError:
            pass
        self._cdp.call("Page.bringToFront", session=self._page())

    # ---------- คำสั่ง ----------
    def run(self, cmd: BrowseCommand) -> Result:
        with self._lock:
            try:
                return self._run(cmd)
            except cdp.CdpError as e:
                return Result(False, f"สั่งเบราว์เซอร์ไม่สำเร็จ: {e}")
            except OSError as e:
                return Result(False, f"เปิดเบราว์เซอร์ไม่ได้: {e.strerror or e}")

    def _run(self, cmd: BrowseCommand) -> Result:
        if not self.running:
            if cmd.kind in NEEDS_PAGE:
                return Result(False, "", handled=False)
            first = self._search_url(cmd.query) if cmd.kind == "search" else SITES[cmd.site][1]
            self._start(first)
            self._page()
            url = self._wait_load()
            return self._after_open(cmd, url)
        self._page()
        if cmd.kind != "app":
            self._front()
        if cmd.kind in ("search", "site"):
            url = self._go(self._search_url(cmd.query) if cmd.kind == "search" else SITES[cmd.site][1])
            return self._after_open(cmd, url)
        return getattr(self, "_do_" + cmd.kind)(cmd)

    @staticmethod
    def _search_url(query: str) -> str:
        return GOOGLE + quote_plus(query)

    def _after_open(self, cmd: BrowseCommand, url: str) -> Result:
        if cmd.kind == "site":
            return Result(True, f"เปิด {SITES[cmd.site][0]} แล้ว", url=url)
        if "/sorry/" in url:  # Google ขอยืนยันว่าไม่ใช่บอต (พบกับเน็ตมือถือ 2026-10-13) → Bing
            url = self._go(BING + quote_plus(cmd.query))
            return Result(True, f"Google ขอยืนยันว่าไม่ใช่บอต จึงค้นด้วย Bing แทน: {cmd.query}", url=url)
        return Result(True, f"ค้นหา {cmd.query} แล้ว", url=url)

    def links(self) -> list[dict]:
        return self._eval(LINKS_JS) or []

    def _do_open(self, cmd: BrowseCommand) -> Result:
        links = self.links()
        if not links:
            return Result(False, "หน้านี้ไม่มีลิงก์ให้เลือก")
        if cmd.n > len(links):
            return Result(False, f"หน้านี้มีลิงก์ให้เลือก {len(links)} ลิงก์")
        link = links[cmd.n - 1]
        url = self._go(link["href"])
        site = urlsplit(url).hostname or url
        return Result(True, f"เข้าลิงก์ที่ {cmd.n} แล้ว: {site}", url=url)

    def _history(self, step: int) -> Result:
        h = self._cdp.call("Page.getNavigationHistory", session=self._page())
        i = h["currentIndex"] + step
        if not 0 <= i < len(h["entries"]):
            return Result(False, "ย้อนกลับไม่ได้ นี่คือหน้าแรกแล้ว" if step < 0 else "ไปข้างหน้าไม่ได้ ไม่มีหน้าถัดไป")
        before = self._url()
        self._cdp.call("Page.navigateToHistoryEntry", {"entryId": h["entries"][i]["id"]},
                       session=self._page())  # fmt: skip
        url = self._wait_load(before)
        return Result(True, "ย้อนกลับแล้ว" if step < 0 else "ไปข้างหน้าแล้ว", url=url)

    def _do_back(self, cmd: BrowseCommand) -> Result:
        return self._history(-1)

    def _do_forward(self, cmd: BrowseCommand) -> Result:
        return self._history(+1)

    def _do_reload(self, cmd: BrowseCommand) -> Result:
        self._cdp.call("Page.reload", session=self._page())
        return Result(True, "โหลดหน้านี้ใหม่แล้ว", url=self._wait_load())

    def _do_scroll(self, cmd: BrowseCommand) -> Result:
        sign = 1 if cmd.direction == "down" else -1
        before = self._eval("scrollY") or 0
        self._eval(f"window.scrollBy(0, {sign} * Math.round(innerHeight * 0.8))")
        time.sleep(0.3)
        after = self._eval("scrollY") or 0
        if after == before:
            return Result(False, "เลื่อนลงต่อไม่ได้ สุดหน้าแล้ว" if sign > 0 else "อยู่บนสุดแล้ว")
        return Result(True, "เลื่อนลงแล้ว" if sign > 0 else "เลื่อนขึ้นแล้ว")

    def _do_close(self, cmd: BrowseCommand) -> Result:
        pages = [t for t in self._cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page"]
        self._cdp.call("Target.closeTarget", {"targetId": self._target})
        self._session = self._target = ""
        if len(pages) <= 1:  # แท็บสุดท้าย = Chromium ปิดตัวเอง
            self.close()
        return Result(True, "ปิดแท็บแล้ว")

    def _do_app(self, cmd: BrowseCommand) -> Result:
        win = self._cdp.call("Browser.getWindowForTarget", {"targetId": self._target})
        self._cdp.call("Browser.setWindowBounds",
                       {"windowId": win["windowId"], "bounds": {"windowState": "minimized"}})  # fmt: skip
        return Result(True, "ย่อเบราว์เซอร์แล้ว กลับมาที่แอป")

    def close(self) -> None:
        """ออกจากระบบ / แอปปิด = ปิดเบราว์เซอร์ของผู้ช่วย."""
        if self._cdp is not None:
            try:
                if not self._cdp.closed:
                    self._cdp.call("Browser.close", timeout=3)
            except cdp.CdpError:
                pass
            self._cdp.close()
        if self._proc is not None:
            try:
                self._proc.wait(5)
            except Exception:  # noqa: BLE001
                self._proc.kill()
        self._proc = self._cdp = None
        self._session = self._target = ""
