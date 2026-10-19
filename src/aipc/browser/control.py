"""ทำคำสั่งเว็บจากเสียงกับเบราว์เซอร์ของผู้ช่วย (การ์ด 0024).

แอปเปิด Chromium เองด้วยโปรไฟล์แยก (`~/.local/share/aipc/browser`) และคุมทาง pipe (cdp.py) ·
ทุกคำสั่งตรวจผลจากหน้าเว็บจริง (URL / ตำแหน่งเลื่อน) แล้วตอบประโยคสั้น ๆ ให้อ่านออกเสียง ·
เรียกจากเธรดแยกเท่านั้น (รอหน้าโหลดได้หลายวินาที)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus, urlsplit

from aipc.browser import cdp
from aipc.skills.actions import SITES
from aipc.skills.browse import BrowseCommand

GOOGLE = "https://www.google.com/search?hl=th&q="
# Google ขอยืนยันว่าไม่ใช่บอต → DuckDuckGo · เดิม Bing (0024) แต่สำรวจบน Pi 2026-10-13 (2 รอบ × 4 คำค้นไทย):
# Bing ให้ผลไม่ตรงคำค้น 3/4 (ไข่เจียว → หน้าช่วยเหลือ Windows · อากาศเชียงใหม่ → แบบทดสอบ Harry Potter)
# DuckDuckGo ตรง 8/8 และลิงก์ชี้เว็บปลายทางตรง ๆ (Bing ผ่านตัวพาไป bing.com/ck/a)
DDG = "https://duckduckgo.com/?kl=th-th&q="
# คำสั่งที่ต้องมีหน้าเว็บเปิดอยู่ก่อน · เบราว์เซอร์ยังไม่เปิด = ไม่ใช่งานของเรา ส่งประโยคไปทางเดิมของแอป
NEEDS_PAGE = {"open", "back", "forward", "reload", "scroll", "close", "app", "media"}

# คุมเพลง/วิดีโอ (การ์ด 0035): สั่งตัวเล่น <video>/<audio> ของหน้าโดยตรง (ใช้ได้ทุกเว็บ รวมโฆษณา YouTube) ·
# ไม่อ่านเนื้อหาหน้า · คืนแค่สถานะ: none = หน้านี้ไม่มีตัวเล่น · idle = อยู่ในสภาพที่สั่งอยู่แล้ว
PAUSE_JS = r"""(() => {
  const m = [...document.querySelectorAll('video, audio')];
  if (!m.length) return 'none';
  const on = m.filter(e => !e.paused && !e.ended);
  on.forEach(e => e.pause());
  return on.length ? 'ok' : 'idle';
})()"""
PLAY_JS = r"""(async () => {
  const m = [...document.querySelectorAll('video, audio')];
  if (!m.length) return 'none';
  if (m.some(e => !e.paused && !e.ended)) return 'idle';
  const e = m.find(x => x.currentTime > 0 && !x.ended) || m[0];
  try { await e.play(); return 'ok'; } catch (err) { return 'blocked'; }
})()"""
# YouTube: ปุ่ม "ถัดไป" ของตัวเล่น (ทางสำรองเมื่อ Shift+N ไม่ได้ผล) · ซ่อนอยู่ = ไม่มีเพลงถัดไป
NEXT_BUTTON_JS = r"""(() => {
  const b = document.querySelector('.ytp-next-button');
  if (!b || b.offsetParent === null) return false;
  b.click();
  return true;
})()"""
# หน้าค้นของแต่ละบริการ (การ์ด 0036 หัวข้อ 3 · ตรวจลิงก์แล้ว 2026-10-15) · เขียนตายตัว คำค้นเข้ารหัส URL เสมอ
SITE_SEARCH = {
    "youtube": "https://www.youtube.com/results?search_query=",
    "maps": "https://www.google.com/maps/search/",
    "wikipedia": "https://th.wikipedia.org/w/index.php?search=",
    "drive": "https://drive.google.com/drive/search?q=",
    "gmail": "https://mail.google.com/mail/u/0/#search/",
}
MEDIA_SAY = {
    ("pause", "ok"): (True, "หยุดแล้ว"),
    ("pause", "idle"): (True, "ไม่มีเพลงหรือวิดีโอที่กำลังเล่นอยู่"),
    ("play", "ok"): (True, "เล่นต่อแล้ว"),
    ("play", "idle"): (True, "กำลังเล่นอยู่แล้ว"),
    ("play", "blocked"): (False, "เว็บไม่ยอมให้เล่นต่อ · กดเล่นที่หน้าจอเอง"),
}

# ลิงก์ที่ N = "อันที่เห็นบนจอ" (Pakon เลือก 2026-10-13 · รวมโฆษณา) เรียงจากบนลงล่าง ·
# หน้าผลค้นหา = หัวข้อผลค้นหา · หน้าอื่น = ลิงก์ที่มองเห็นในจอตอนนี้
LINKS_JS = r"""(() => {
  const host = location.hostname, seen = new Set(), out = [];
  let sel = null;
  if (/(^|\.)google\./.test(host) && location.pathname === '/search')
    sel = '#search a h3, #rso a h3, #tads a [role=heading], #tvcap a [role=heading], ' +
          '#bottomads a [role=heading]';
  else if (/(^|\.)bing\.com$/.test(host) && location.pathname === '/search')
    sel = 'li.b_algo h2 a, li.b_ad h2 a, .b_adTop h2 a';
  else if (/(^|\.)youtube\.com$/.test(host) && location.pathname === '/results')
    sel = 'a#video-title, a.yt-lockup-metadata-view-model__title, ' +
          'a.yt-lockup-metadata-view-model-wiz__title';  // คลิป ไม่ใช่โลโก้/เมนู (0025)
  else if (/duckduckgo\.com$/.test(host))
    sel = 'a.result__a, a[data-testid=result-title-a]';
  const push = (a) => {
    if (!a || !a.href || a.href.startsWith('javascript:') || seen.has(a.href)) return;
    const r = a.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    seen.add(a.href);
    const text = (a.innerText || '').trim().slice(0, 80);
    out.push({href: a.href, text, y: r.top + scrollY, x: r.left});
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


# ช่องค้นหาของเว็บที่เปิดอยู่ (find · 0025) · อันแรกที่มองเห็น
FIND_JS = r"""(() => {
  const sel = 'input[type=search], [role=searchbox], input[name=q], input[name=search_query], ' +
    'input[name=search], input[name=query], input[name=keyword], input[name=k], ' +
    'textarea[name=q], ' +
    'input[aria-label*=earch i], input[placeholder*=earch i], input[aria-label*=ค้นหา], ' +
    'input[placeholder*=ค้นหา], input[title*=ค้นหา], [role=combobox][aria-label*=earch i]';
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) continue;
    if (el.checkVisibility && !el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}))
      continue;
    el.scrollIntoView({block: 'center'});
    el.focus();
    if (el.select) el.select();
    return true;
  }
  return false;
})()"""

# รายการเลข n ที่ OBSERVE_JS ติดไว้ (aipc.browser.page) · ลิงก์เปิดในแท็บเดิม (target=_blank → ลบ)
CLICK_JS = r"""((n) => {
  const el = document.querySelector('[data-aipc-n="' + n + '"]');
  if (!el) return null;
  const a = el.closest('a');
  if (a) a.removeAttribute('target');
  el.scrollIntoView({block: 'center'});
  const label = (el.innerText || el.getAttribute('aria-label') || el.value || '')
    .replace(/\s+/g, ' ').trim().slice(0, 60);
  el.click();
  return label || ('รายการที่ ' + n);
})"""

TYPE_JS = r"""((n, text) => {
  const el = document.querySelector('[data-aipc-n="' + n + '"]');
  if (!el) return 'missing';
  const tag = el.tagName.toLowerCase(), type = (el.type || '').toLowerCase();
  if (type === 'password') return 'notfield';
  if (tag === 'select') {
    const opt = [...el.options].find(o => o.text.includes(text) || o.value === text);
    if (!opt) return 'nooption';
    el.value = opt.value;
    el.dispatchEvent(new Event('change', {bubbles: true}));
    return 'select';
  }
  const role = el.getAttribute('role') || '';
  const field = tag === 'textarea' || el.isContentEditable ||
    /^(textbox|searchbox|combobox)$/.test(role) ||
    (tag === 'input' &&
     !/^(submit|button|reset|image|checkbox|radio|file|range|color)$/.test(type));
  if (!field) return 'notfield';
  el.scrollIntoView({block: 'center'});
  el.focus();
  if (el.select) el.select(); else document.execCommand('selectAll');
  return 'ok';
})"""

# เปิดเว็บตามชื่อที่พูด (open · 0025) · ไม่รู้จักและไม่ใช่ที่อยู่เว็บ = ค้นแล้วเปิดผลแรก
KNOWN_SITES = {
    "youtube": "https://www.youtube.com", "ยูทูบ": "https://www.youtube.com",
    "pantip": "https://pantip.com",
    "พันทิป": "https://pantip.com", "wikipedia": "https://th.wikipedia.org",
    "วิกิพีเดีย": "https://th.wikipedia.org", "วิกิ": "https://th.wikipedia.org",
    "พีเดีย": "https://th.wikipedia.org",  # ถอดเสียงเพี้ยน "วิกฤติพีเดีย" (ชุดพัฒนา 0025)
    "google": "https://www.google.com", "กูเกิล": "https://www.google.com",
    "gmail": "https://mail.google.com", "จีเมล": "https://mail.google.com",
    "shopee": "https://shopee.co.th", "ช้อปปี้": "https://shopee.co.th",
    "lazada": "https://www.lazada.co.th", "ลาซาด้า": "https://www.lazada.co.th",
    "tiktok": "https://www.tiktok.com", "ติ๊กต็อก": "https://www.tiktok.com",
    "netflix": "https://www.netflix.com", "github": "https://github.com",
    "thairath": "https://www.thairath.co.th", "ไทยรัฐ": "https://www.thairath.co.th",
    "sanook": "https://www.sanook.com", "สนุก": "https://www.sanook.com",
    "duckduckgo": "https://duckduckgo.com",
}  # fmt: skip
_DOMAIN = re.compile(r"^(https?://)?([a-z0-9-]+\.)+[a-z]{2,}(/\S*)?$")


def site_url(name: str) -> str | None:
    """ชื่อที่พูด เช่น youtube.com / ยูทูบ / https://x.org/a → ที่อยู่เว็บ · ไม่รู้จัก = None."""
    key = re.sub(r"\s+", "", name.strip().lower())
    key = re.sub(r"^(เว็บไซต์|เว็บ|หน้า|เพจ)", "", key)
    if _DOMAIN.match(key):
        return key if key.startswith("http") else "https://" + key
    bare = re.sub(r"^(https?://)?(www\.)?", "", key).split("/")[0]
    for alias, url in KNOWN_SITES.items():
        if bare == alias or bare.startswith(alias + "."):
            return url
    for alias, url in KNOWN_SITES.items():
        if alias in key:
            return url
    return None


@dataclass
class Result:
    ok: bool
    say: str  # ประโยคสั้น ๆ ให้อ่านออกเสียง/แสดงในการ์ด
    handled: bool = True  # False = ไม่ใช่งานเบราว์เซอร์ตอนนี้ → ส่งประโยคไปทางเดิมของแอป
    url: str = ""


def default_profile() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "aipc" / "browser"


REMOVING = ".removing-"  # ชื่อชั่วคราวของโปรไฟล์ที่กำลังลบ (ออกจากบัญชีเว็บทั้งหมด · การ์ด 0031)


def profile_in_use(profile: Path) -> bool:
    """Chromium ตัวอื่นยังเปิดโปรไฟล์นี้อยู่ไหม.

    Chromium บน Linux ทำลิงก์ SingletonLock ชี้ไปที่ "<ชื่อเครื่อง>-<pid>" และลบเองตอนปิดปกติ ·
    ลิงก์ค้างจากไฟดับ = โปรเซสเลขนั้นไม่มีแล้ว = ไม่มีใครใช้
    """
    try:
        pid = int(os.readlink(profile / "SingletonLock").rsplit("-", 1)[1])
    except (OSError, ValueError, IndexError):
        return False
    return Path(f"/proc/{pid}").exists()


def remove_profile(profile: Path) -> threading.Thread | None:
    """ลบโปรไฟล์ทั้งโฟลเดอร์ (การเข้าสู่ระบบ คุกกี้ ประวัติ แคช) · การ์ด 0031.

    เปลี่ยนชื่อก่อน (เสร็จในคราวเดียว = ออกจากบัญชีทันที) แล้วค่อยลบเบื้องหลัง เพราะแคชหลายร้อย MB บน microSD
    ลบนานจนหน้าจอค้างได้ · ไฟดับระหว่างลบ = ชื่อเดิมว่างแล้ว เปิดครั้งหน้าได้โปรไฟล์ใหม่ · ของค้างถูกลบครั้งหน้า
    """
    if profile.exists():
        profile.rename(profile.with_name(f"{profile.name}{REMOVING}{time.time_ns()}"))
    return sweep_removed(profile)


def sweep_removed(profile: Path) -> threading.Thread | None:
    """ลบโฟลเดอร์ชื่อชั่วคราวที่ค้างอยู่ในเธรดเบื้องหลัง · คืนเธรดให้เทสต์รอได้ · ไม่มีของค้าง = None."""
    left = sorted(profile.parent.glob(profile.name + REMOVING + "*"))
    if not left:
        return None
    t = threading.Thread(
        target=lambda: [shutil.rmtree(p, ignore_errors=True) for p in left], daemon=True
    )
    t.start()
    return t


class BrowserControl:
    def __init__(
        self,
        profile: Path | None = None,
        chromium: str = "chromium",
        extra_args: list[str] | None = None,
        launcher=cdp.launch,
        load_timeout=12.0,
    ):
        self._profile = profile or default_profile()
        self._chromium, self._extra = chromium, list(extra_args or [])
        self._launch, self._load_timeout = launcher, load_timeout
        self._proc = self._cdp = None
        self._session = self._target = ""
        self._google_blocked = False
        self._lock = threading.Lock()  # ทีละคำสั่ง
        self._mark = 0
        self._google_blocked = False  # เจอ /sorry/ แล้ว = ค้นด้วย DuckDuckGo ตรง ๆ จนปิดเบราว์เซอร์

    # ---------- เปิด / ต่อ ----------
    @property
    def available(self) -> bool:
        """เครื่องมีโปรแกรม Chromium ไหม · ไม่มี = เปิดเว็บด้วยเบราว์เซอร์ปกติแทน (การ์ด 0031)."""
        return shutil.which(self._chromium) is not None

    @property
    def running(self) -> bool:
        return self._cdp is not None and not self._cdp.closed and self._proc.poll() is None

    def _start(self, url: str) -> None:
        self._profile.mkdir(parents=True, exist_ok=True)
        argv = [
            self._chromium,
            f"--user-data-dir={self._profile}",
            "--remote-debugging-pipe",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",
            *self._extra,
            url,
        ]
        if os.environ.get("WAYLAND_DISPLAY"):
            # Chromium บน Pi เลือก X11 เอง (hint=auto ก็ X11) · ไม่มี $DISPLAY = ปิดตัวทันที (พบ 2026-10-13)
            argv.insert(1, "--ozone-platform=wayland")
        self._proc, self._cdp = self._launch(argv)
        self._session = self._target = ""
        self._cdp.call("Browser.getVersion", timeout=30)  # รอจนพร้อม (เปิดครั้งแรกบน Pi ~1–3 วิ)

    def _page(self) -> str:
        """session ของแท็บที่ใช้อยู่ (แท็บล่าสุด) · แท็บเดิมปิดไปแล้ว = ต่อแท็บใหม่."""
        pages = [
            t for t in self._cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page"
        ]
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

    def _eval(self, js: str, **opts):
        """opts ส่งต่อให้ Runtime.evaluate (เช่น awaitPromise · userGesture ของคำสั่งเล่นต่อ การ์ด 0035)."""
        for _ in range(20):  # ระหว่างเปลี่ยนหน้า หน้าใหม่ยังไม่มี context ให้รันสคริปต์ (~0.1–1 วิ)
            try:
                r = self._cdp.call(
                    "Runtime.evaluate",
                    {"expression": js, "returnByValue": True, **opts},
                    session=self._page(),
                )
                return r.get("result", {}).get("value")
            except cdp.CdpError as e:
                if "context" not in str(e) or self._cdp.closed:
                    raise
                time.sleep(0.15)
        raise cdp.CdpError("หน้าเว็บยังไม่พร้อม")

    def _url(self) -> str:
        return self._eval("location.href") or ""

    def _go(self, url: str) -> str:
        return self._navigate("Page.navigate", {"url": url})

    def _navigate(self, method: str, params: dict | None = None) -> str:
        """เปลี่ยนหน้าแล้วรอจนหน้าใหม่โหลดเสร็จและ URL นิ่ง (หน้าเด้งต่อ เช่น Google → /sorry/).

        ทำเครื่องหมายเลขใหม่ไว้ในหน้าเดิมก่อน · ไม่เจอเลขนี้ = เป็นเอกสารใหม่แล้ว (ใช้ได้กับโหลดใหม่ที่ URL เดิม ·
        หน้าที่ย้อนกลับมาจากแคชของ Chromium มีเลขเก่า ไม่ใช่เลขนี้ · เดิมใช้ค่าเดียว ย้อนกลับรอจนหมดเวลา 12 วิ)
        """
        self._mark += 1
        token = self._mark
        self._eval(f"window.__aipcOld = {token}")
        self._cdp.call(method, params or {}, session=self._page())
        end = time.monotonic() + self._load_timeout
        last, since = None, time.monotonic()
        time.sleep(0.3)
        while time.monotonic() < end:
            try:
                state, url, old = self._eval(
                    f"[document.readyState, location.href, window.__aipcOld === {token}]"
                ) or ("", "", True)
            except cdp.CdpError:
                state, url, old = "", "", True
            if url != last:
                last, since = url, time.monotonic()
            if state == "complete" and not old and time.monotonic() - since >= 0.6:
                return url
            time.sleep(0.2)
        return last or ""

    def _front(self) -> None:
        """เบราว์เซอร์มาอยู่หน้าสุด (เคยย่อไว้ด้วย "กลับไปแอป")."""
        try:
            win = self._cdp.call("Browser.getWindowForTarget", {"targetId": self._target})
            self._cdp.call(
                "Browser.setWindowBounds",
                {"windowId": win["windowId"], "bounds": {"windowState": "maximized"}},
            )
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
            self._start("about:blank")
            self._page()
        self._page()
        if cmd.kind != "app":
            self._front()
        # ขั้น "เปิดเว็บ https://…" ของสกิล (ลิงก์ตายตัวในไฟล์ที่ผ่านประตูตรวจแล้ว · การ์ด 0031)
        if cmd.kind == "url":
            if not cmd.query.lower().startswith("https://"):
                return Result(False, "เปิดได้เฉพาะลิงก์ https")
            return Result(True, "เปิดเว็บแล้ว", url=self._go(cmd.query))
        if cmd.kind == "site_search":  # การ์ด 0036
            name = SITES[cmd.site][0]
            url = self._open_search(SITE_SEARCH[cmd.site] + quote_plus(cmd.query))
            return Result(True, f"ค้นหา {cmd.query} ใน {name} แล้ว", url=url)
        if cmd.kind in ("search", "site"):
            url = self._go(
                self._search_url(cmd.query) if cmd.kind == "search" else SITES[cmd.site][1]
            )
            return self._after_open(cmd, url)
        return getattr(self, "_do_" + cmd.kind)(cmd)

    def _open_search(self, url: str) -> str:
        """เปิดหน้าค้นของบริการ · ต่างจากหน้าปัจจุบันแค่หลัง # (ค้นในจีเมลขณะเปิดจีเมลอยู่) = เปลี่ยนในหน้าเดิม
        ไม่มีเอกสารใหม่ให้รอ → รอแค่ที่อยู่เปลี่ยน (ไม่งั้นรอจนหมดเวลา 12 วิ)."""
        if self._url().split("#")[0] != url.split("#")[0]:
            return self._go(url)
        before, token = self._marked()
        self._cdp.call("Page.navigate", {"url": url}, session=self._page())
        return self._wait_change(before, token)[0]

    def _search_url(self, query: str) -> str:
        return (DDG if self._google_blocked else GOOGLE) + quote_plus(query)

    def _after_open(self, cmd: BrowseCommand, url: str) -> Result:
        if cmd.kind == "site":
            return Result(True, f"เปิด {SITES[cmd.site][0]} แล้ว", url=url)
        if "/sorry/" in url:  # Google ขอยืนยันว่าไม่ใช่บอต (พบกับเน็ตมือถือ 2026-10-13) → DuckDuckGo
            self._google_blocked = True
            url = self._go(DDG + quote_plus(cmd.query))
            return Result(
                True, f"Google ขอยืนยันว่าไม่ใช่บอต จึงค้นด้วย DuckDuckGo แทน: {cmd.query}", url=url
            )
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
            return Result(
                False, "ย้อนกลับไม่ได้ นี่คือหน้าแรกแล้ว" if step < 0 else "ไปข้างหน้าไม่ได้ ไม่มีหน้าถัดไป"
            )
        url = self._navigate("Page.navigateToHistoryEntry", {"entryId": h["entries"][i]["id"]})
        return Result(True, "ย้อนกลับแล้ว" if step < 0 else "ไปข้างหน้าแล้ว", url=url)

    def _do_back(self, cmd: BrowseCommand) -> Result:
        return self._history(-1)

    def _do_forward(self, cmd: BrowseCommand) -> Result:
        return self._history(+1)

    def _do_reload(self, cmd: BrowseCommand) -> Result:
        return Result(True, "โหลดหน้านี้ใหม่แล้ว", url=self._navigate("Page.reload"))

    def _do_scroll(self, cmd: BrowseCommand) -> Result:
        sign = 1 if cmd.direction == "down" else -1
        before = self._eval("scrollY") or 0
        self._eval(f"window.scrollBy(0, {sign} * Math.round(innerHeight * 0.8))")
        time.sleep(0.3)
        after = self._eval("scrollY") or 0
        if after == before:
            return Result(False, "เลื่อนลงต่อไม่ได้ สุดหน้าแล้ว" if sign > 0 else "อยู่บนสุดแล้ว")
        return Result(True, "เลื่อนลงแล้ว" if sign > 0 else "เลื่อนขึ้นแล้ว")

    def _do_media(self, cmd: BrowseCommand) -> Result:
        """หยุด / เล่นต่อ / เพลงถัดไป (การ์ด 0035)."""
        if cmd.direction == "next":
            return self._media_next()
        # userGesture: นับเป็นการกดของผู้ใช้ (Chromium ไม่ยอมให้เล่นเสียงเองถ้าไม่มีคนสั่ง)
        state = self._eval(PAUSE_JS if cmd.direction == "pause" else PLAY_JS,
                           awaitPromise=True, userGesture=True)  # fmt: skip
        ok, say = MEDIA_SAY.get((cmd.direction, state), (False, "หน้านี้ไม่มีเพลงหรือวิดีโอ"))
        return Result(ok, say)

    def _media_next(self) -> Result:
        """YouTube เท่านั้น: กด Shift+N (คีย์ลัดเพลงถัดไป) · ที่อยู่ไม่เปลี่ยน = กดปุ่ม "ถัดไป" ของตัวเล่นแทน ·
        ข้อความบอกว่าได้ผลทางไหน (เกณฑ์ข้อ 3: บันทึกว่า Shift+N ใช้ได้ไหม)."""
        host = urlsplit(self._url()).hostname or ""
        if host != "youtube.com" and not host.endswith(".youtube.com"):
            return Result(False, "ข้ามเพลงได้เฉพาะใน YouTube")
        before, token = self._marked()
        # rawKeyDown = กดปุ่มโดยไม่พิมพ์ตัวอักษรลงช่องใด · modifiers 8 = Shift
        for kind in ("rawKeyDown", "keyUp"):
            key = {
                "type": kind,
                "key": "N",
                "code": "KeyN",
                "windowsVirtualKeyCode": 78,
                "modifiers": 8,
            }
            self._cdp.call("Input.dispatchKeyEvent", key, session=self._page())
        url, moved = self._wait_change(before, token)
        if moved:
            return Result(True, "เปิดเพลงถัดไปแล้ว", url=url)
        if self._eval(NEXT_BUTTON_JS):
            url, moved = self._wait_change(before, token)
            if moved:
                return Result(True, "กดปุ่มถัดไปให้แล้ว", url=url)
        return Result(False, "ข้ามไม่ได้ · หน้านี้ไม่มีเพลงถัดไป")

    def _do_close(self, cmd: BrowseCommand) -> Result:
        pages = [
            t for t in self._cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page"
        ]
        self._cdp.call("Target.closeTarget", {"targetId": self._target})
        self._session = self._target = ""
        if len(pages) <= 1:  # แท็บสุดท้าย = Chromium ปิดตัวเอง
            self.close()
        return Result(True, "ปิดแท็บแล้ว")

    def _do_app(self, cmd: BrowseCommand) -> Result:
        win = self._cdp.call("Browser.getWindowForTarget", {"targetId": self._target})
        self._cdp.call(
            "Browser.setWindowBounds",
            {"windowId": win["windowId"], "bounds": {"windowState": "minimized"}},
        )
        return Result(True, "ย่อเบราว์เซอร์แล้ว กลับมาที่แอป")

    # ---------- สำหรับผู้ช่วยที่ AI คิดเอง (การ์ด 0025 · aipc.browser.agent) ----------
    def current(self) -> dict:
        """ชื่อหน้า + ที่อยู่ (ขั้นวางแผนเห็นแค่นี้) · ยังไม่เปิด = {}."""
        if not self.running:
            return {}
        with self._lock:
            got = self._eval("[document.title, location.href]") or ["", ""]
        return {"title": got[0], "url": got[1]}

    def observe(self) -> dict:
        """ของบนจอติดเลข + ข้อความบนจอ (aipc.browser.page.OBSERVE_JS) · ยังไม่เปิด = {}."""
        from aipc.browser import page

        if not self.running:
            return {}
        with self._lock:
            return self._eval(page.OBSERVE_JS) or {}

    def where(self) -> tuple:
        """ที่อยู่ + ตำแหน่งเลื่อน · ใช้ดูว่าหน้าที่อ่านไว้ก่อนยังเป็นหน้าเดิมไหม."""
        if not self.running:
            return ()
        with self._lock:
            return tuple(self._eval("[location.href, Math.round(scrollY)]") or ())

    def tagged(self) -> bool:
        """ยังมีเลขที่ OBSERVE_JS ติดไว้ (หน้าเดิม ยังไม่ถูกสร้างใหม่)."""
        if not self.running:
            return False
        with self._lock:
            return bool(self._eval("!!document.querySelector('[data-aipc-n]')"))

    def act(self, step) -> Result:
        """ทำ 1 ขั้นจากแผนของ AI (aipc.browser.agent.Step) · ตรวจผลจากหน้าจริง."""
        simple = {
            "search": BrowseCommand("search", query=step.text),
            "result": BrowseCommand("open", n=step.n),
            "back": BrowseCommand("back"),
            "forward": BrowseCommand("forward"),
            "reload": BrowseCommand("reload"),
            "down": BrowseCommand("scroll", direction="down"),
            "up": BrowseCommand("scroll", direction="up"),
            "close": BrowseCommand("close"),
            "app": BrowseCommand("app"),
        }
        if step.action in simple:
            r = self.run(simple[step.action])
            return r if r.handled else Result(False, "ยังไม่ได้เปิดหน้าเว็บ", handled=False)
        with self._lock:
            try:
                return self._act(step)
            except cdp.CdpError as e:
                return Result(False, f"สั่งเบราว์เซอร์ไม่สำเร็จ: {e}")
            except OSError as e:
                return Result(False, f"เปิดเบราว์เซอร์ไม่ได้: {e.strerror or e}")

    def _act(self, step) -> Result:
        if step.action == "answer":  # ไม่แตะเบราว์เซอร์ · ผู้ช่วยพูดคำตอบ
            return Result(True, step.text)
        if not self.running:
            if step.action != "open":
                return Result(False, "ยังไม่ได้เปิดหน้าเว็บ", handled=False)
            self._start("about:blank")
        self._page()
        self._front()
        return getattr(self, "_step_" + step.action)(step)

    def _step_open(self, step) -> Result:
        url = site_url(step.text)
        if url is None:  # ชื่อที่ไม่รู้จัก → ค้นแล้วเปิดผลแรก
            self._go(DDG + quote_plus(step.text))
            r = self._do_open(BrowseCommand("open", n=1))
            if not r.ok:
                return r
            return Result(
                True, f"ค้นหา {step.text} แล้วเปิดผลแรก: " + r.say.split(": ")[-1], url=r.url
            )
        got = self._go(url)
        return Result(True, f"เปิด {urlsplit(got or url).hostname or url} แล้ว", url=got)

    def _wait_change(self, before: str, token: int, quiet: float = 2.5) -> tuple[str, bool]:
        """หลังคลิก/กด Enter: รอจนหน้าใหม่โหลดเสร็จ (หรือที่อยู่เปลี่ยนแบบ YouTube) และนิ่ง ·
        ไม่เปลี่ยนเลยใน quiet วิ = กดแล้วอยู่หน้าเดิม (ติ๊กตัวเลือก ฯลฯ)."""
        start = time.monotonic()
        end = start + self._load_timeout
        last, since, changed = before, start, False
        time.sleep(0.3)
        while time.monotonic() < end:
            try:
                state, url, old = self._eval(
                    f"[document.readyState, location.href, window.__aipcOld === {token}]"
                ) or ("", "", True)
            except cdp.CdpError:
                state, url, old, changed = "", last, True, True
            if url != last:
                last, since = url, time.monotonic()
            if not old or url != before:
                changed = True
            if changed and state == "complete" and time.monotonic() - since >= 0.6:
                return url, True
            if not changed and time.monotonic() - start >= quiet:
                return url, False
            time.sleep(0.2)
        return last, changed

    def _marked(self) -> tuple[str, int]:
        self._mark += 1
        return self._eval(f"window.__aipcOld = {self._mark}; location.href") or "", self._mark

    def _step_click(self, step) -> Result:
        before, token = self._marked()
        label = self._eval(f"({CLICK_JS})({int(step.n)})")
        if label is None:
            return Result(False, f"ไม่มีรายการที่ {step.n} ในหน้านี้แล้ว")
        url, moved = self._wait_change(before, token)
        host = urlsplit(url).hostname if moved else ""
        return Result(True, f"กด {label} แล้ว" + (f" → {host}" if host else ""), url=url)

    def _step_type(self, step) -> Result:
        got = self._eval(f"({TYPE_JS})({int(step.n)}, {json.dumps(step.text)})")
        if got == "missing":
            return Result(False, f"ไม่มีรายการที่ {step.n} ในหน้านี้แล้ว")
        if got in ("notfield", "nooption", None):
            return Result(False, f"รายการที่ {step.n} พิมพ์ไม่ได้")
        if got == "ok":
            self._cdp.call("Input.insertText", {"text": step.text}, session=self._page())
        return Result(True, f"พิมพ์ {step.text} แล้ว")

    def _press_enter(self) -> None:
        for kind in ("keyDown", "keyUp"):
            params = {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13}
            if kind == "keyDown":
                params["text"] = "\r"
            self._cdp.call("Input.dispatchKeyEvent", params, session=self._page())

    def _step_find(self, step) -> Result:
        if not self._eval(FIND_JS):
            host = urlsplit(self._url()).hostname or ""
            if not host:
                return Result(False, "หน้านี้ไม่มีช่องค้นหา")
            url = self._go(self._search_url(f"{step.text} site:{host}"))
            if "/sorry/" in url:
                self._google_blocked = True
                url = self._go(DDG + quote_plus(f"{step.text} site:{host}"))
            return Result(True, f"เว็บนี้ไม่มีช่องค้นหา จึงค้น {step.text} เฉพาะใน {host} แทน", url=url)
        self._cdp.call("Input.insertText", {"text": step.text}, session=self._page())
        before, token = self._marked()
        self._press_enter()
        url, _ = self._wait_change(before, token)
        return Result(True, f"ค้นหา {step.text} ในเว็บนี้แล้ว", url=url)

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
                # เก็บโปรเซสที่ฆ่าแล้ว · ค้างเป็น zombie = /proc/<pid> ยังอยู่
                # → profile_in_use คิดว่ายังมีคนใช้โปรไฟล์ (การ์ด 0031)
                try:
                    self._proc.wait(2)
                except Exception:  # noqa: BLE001
                    pass
        self._proc = self._cdp = None
        self._session = self._target = ""
        self._google_blocked = False
