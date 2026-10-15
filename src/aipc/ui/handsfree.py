"""สั่งด้วยเสียงไม่ใช้เมาส์ (การ์ด 0024): คีย์ลัดทั้งเครื่อง + เบราว์เซอร์ของผู้ช่วย.

- labwc กด F9 หรือ Alt+Space (การ์ด 0026) → `scripts/pi/session/aipc-voice-key` เขียนหนึ่งไบต์ลง FIFO
  `$XDG_RUNTIME_DIR/aipc/voice-key` → HotkeyListener ส่ง pressed()
  (FIFO ของผู้ใช้คนนี้ 0600 · บัญชีอื่นกดแทนไม่ได้)
- BrowserController ทำคำสั่งเว็บในเธรดแยก (หน้าเว็บโหลดหลายวินาที) แล้วส่ง finished(ประโยคสั้น, สำเร็จไหม)
- route() ตัดสินว่าคำพูดจากคีย์ลัดไปทางไหน (การ์ด 0027): สั่งงานอย่างเดียว ไม่ส่งให้ AI ในเครื่องคุย
"""

from __future__ import annotations

import math
import os
import shutil
import struct
import subprocess
import threading
import wave
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Property, QObject, QSocketNotifier, Signal, Slot


def runtime_dir() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}") / "aipc"


class HotkeyListener(QObject):
    pressed = Signal()

    def __init__(self, path: Path | None = None, active: bool = True):
        super().__init__()
        self._fd = -1
        self._notifier = None
        self.path = path
        if not active or not hasattr(os, "mkfifo"):  # หน้า Login / เทสต์ / Windows
            return
        self.path = path or runtime_dir() / "voice-key"
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists() and not self.path.is_fifo():
                self.path.unlink()
            if not self.path.exists():
                os.mkfifo(self.path, 0o600)
            # O_RDWR: ไม่มีคนเขียนก็ไม่ได้ EOF วนไม่หยุด (FIFO บน Linux เปิดแบบนี้ได้)
            self._fd = os.open(self.path, os.O_RDWR | os.O_NONBLOCK)
        except OSError:
            self._fd = -1
            return
        self._notifier = QSocketNotifier(self._fd, QSocketNotifier.Type.Read, self)
        self._notifier.activated.connect(self._read)

    @property
    def available(self) -> bool:
        return self._fd >= 0

    @Slot()
    def _read(self) -> None:
        try:
            data = os.read(self._fd, 64)
        except BlockingIOError:
            return
        except OSError:
            return
        if data:  # กดรัวหลายครั้งในจังหวะเดียว = ครั้งเดียว
            self.pressed.emit()

    def close(self) -> None:
        if self._notifier is not None:
            self._notifier.setEnabled(False)
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1


def beep(high: bool = True) -> None:
    """เสียง "ติ๊ก" บอกว่าเริ่มฟัง (สูง) / ฟังจบ (ต่ำ) · ไม่มี pw-play = เงียบ."""
    if not shutil.which("pw-play"):
        return
    path = runtime_dir() / ("beep-hi.wav" if high else "beep-lo.wav")
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            rate, freq, secs = 22050, 1320 if high else 660, 0.12
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                n = int(rate * secs)
                frames = b"".join(
                    struct.pack(
                        "<h",
                        int(9000 * math.sin(2 * math.pi * freq * i / rate) * min(1, (n - i) / 400)),
                    )  # fmt: skip
                    for i in range(n)
                )
                w.writeframes(frames)
        except OSError:
            return
    try:
        subprocess.Popen(["pw-play", str(path)], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)  # fmt: skip
    except OSError:
        pass


# ทางของคำพูดจากคีย์ลัด (การ์ด 0027 หัวข้อ 5) · ไม่มีทาง "ส่งให้ AI คุย" (BRIEF 5.6 ข้อ 1: คีย์ลัด = สั่งงาน)
BROWSER = "browser"  # คำสั่งเว็บ → เบราว์เซอร์ของผู้ช่วย
OPEN_BROWSER = "open_browser"  # "เปิดเบราว์เซอร์" → เบราว์เซอร์ของผู้ช่วย (ตัวที่เสียงคุมได้) แทนตัวธรรมดา
COMMAND = "command"  # คำสั่งเครื่อง (เปิดแอป ปรับเสียง หน้าในระบบ) → ทางเดิมของแชท ซึ่งทำคำสั่งก่อนถึง AI
NEEDS_BROWSER = "needs_browser"  # คำสั่งที่ต้องมีหน้าเว็บ แต่ยังไม่ได้เปิดเบราว์เซอร์ของผู้ช่วย
UNKNOWN = "unknown"  # ไม่ใช่คำสั่ง → บอกตรง ๆ ไม่ส่งให้ AI
SKILL = "skill"  # การ์ด 0028: ตรงเป๊ะกับประโยคของสกิลที่ทำด้วยโค้ด (เช่น สกิลที่ Claude สร้าง) → ทำสกิลนั้น


def route(text: str, browser_running: bool, skill: Callable[[str], str] | None = None) -> str:
    """ใช้ตัวแปลแบบกฎล้วน ไม่มี LLM (H6).

    ลำดับ: เว็บ → เปิดเบราว์เซอร์ → คำสั่งเครื่อง → สกิลของผู้ใช้ (ตรงเป๊ะ) → ต้องเปิดเบราว์เซอร์ก่อน → ไม่รู้จัก ·
    skill(text) คืน id ของสกิล ("" = ไม่ตรง) · สกิลมาหลังคำสั่งเดิม = ตรงกับตอนพิมพ์ (แชทตรวจคำสั่งเครื่องก่อน
    router.repeat_of) และสกิลเปลี่ยนคำสั่งเดิมไม่ได้ · ประตูของการ์ด 0017 ไม่ได้กันประโยคสกิลชนคำสั่ง
    (พบ 2026-10-15: สกิล "เปิดแผนที่" ของ Claude มีตัวอย่าง "เปิดแผนที่ให้หน่อย" = คำสั่งเปิด Google Maps)
    """
    from aipc.browser.control import NEEDS_PAGE
    from aipc.skills import browse, command

    cmds = browse.parse(text)
    if cmds and (browser_running or not all(c.kind in NEEDS_PAGE for c in cmds)):
        return BROWSER
    cmd = command.parse(text)
    # สะกด/ได้ยินใกล้เคียง (ต้องยืนยัน) ไม่เข้าข้อนี้ → การ์ดยืนยันเดิมของคำสั่งเครื่อง (BRIEF 5.6 ข้อ 2)
    if cmd and cmd.plan.params.get("app") == "browser" and not cmd.needs_confirmation:
        return OPEN_BROWSER
    if cmd:
        return COMMAND
    if skill is not None and skill(text):
        return SKILL
    return NEEDS_BROWSER if cmds else UNKNOWN


class BrowserController(QObject):
    """คำสั่งเว็บจากเสียง · route() บอกหน้าจอว่าคำพูดจากคีย์ลัดไปทางไหน (การ์ด 0027)."""

    finished = Signal(str, bool)
    # การ์ด 0031: เปิดจากปุ่ม/สกิล ไม่ใช่คำสั่งเสียง → ไม่ไปแก้ข้อความล่าสุดในแชท (เดิมแชทรับ finished ทุกครั้ง)
    opened = Signal(str, bool)
    busyChanged = Signal()  # noqa: N815
    _done = Signal(str, bool, bool)

    def __init__(self, active: bool = True, control=None, ledger=None, skill_match=None,
                 profile=None):  # fmt: skip
        super().__init__()
        self._active = active
        self._control = control
        # โฟลเดอร์โปรไฟล์ของเบราว์เซอร์ของผู้ช่วย · None = ค่าเริ่มต้น (เทสต์ใส่โฟลเดอร์ชั่วคราว)
        self._profile = profile
        self._ledger = ledger
        self._skill_match = skill_match  # การ์ด 0028: SkillsController.voiceSkill (app.py ต่อให้)
        self._busy = False
        self._done.connect(self._on_done)

    def _ctl(self):
        if self._control is None:
            from aipc.browser.control import BrowserControl, default_profile, sweep_removed

            self._control = BrowserControl(profile=self._profile)
            # ของค้างจากกด "ออกจากบัญชีเว็บทั้งหมด" แล้วไฟดับระหว่างลบ (การ์ด 0031) · ลบเบื้องหลัง
            sweep_removed(self._profile or default_profile())
        return self._control

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Slot(str, result=bool)
    def handle(self, text: str) -> bool:
        from aipc.browser.control import NEEDS_PAGE
        from aipc.skills import browse

        if not self._active or self._busy:
            return False
        cmds = browse.parse(text)
        if not cmds:
            return False
        ctl = self._ctl()
        if not ctl.running and all(c.kind in NEEDS_PAGE for c in cmds):
            return False  # ยังไม่เปิดเบราว์เซอร์ เช่น "กลับไปหน้าแชท" = คำสั่งเดิมของแอป
        return self._start(cmds)

    @Slot(str, result=str)
    def route(self, text: str) -> str:
        if not self._active:  # หน้าเข้าสู่ระบบไม่มีเบราว์เซอร์และไม่มีแชท
            return UNKNOWN
        return route(text, self._ctl().running, self._skill_match)

    @Slot(str, result=str)
    def hint(self, text: str) -> str:
        """คำบอกเมื่อสั่งงานที่ต้องมีหน้าเว็บ แต่ยังไม่ได้เปิดเบราว์เซอร์ของผู้ช่วย (route = needs_browser)."""
        from aipc.skills import browse

        if any(c.kind == "media" for c in browse.parse(text)):  # การ์ด 0035
            return 'ยังไม่ได้เปิดเพลงในเบราว์เซอร์ของผู้ช่วย · พูดว่า "เปิดยูทูบ" แล้วเลือกเพลงก่อน'
        return 'ยังไม่ได้เปิดเบราว์เซอร์ของผู้ช่วย พูดว่า "เปิดเบราว์เซอร์" ก่อน'

    @Slot(result=bool)
    def openHome(self) -> bool:  # noqa: N802
        """พูด "เปิดเบราว์เซอร์" → เปิดเบราว์เซอร์ของผู้ช่วยที่หน้า Google (คำสั่งเปิดเว็บตัวเดิมของ 0024)."""
        from aipc.skills.browse import BrowseCommand

        if not self._active or self._busy:
            return False
        return self._start([BrowseCommand(kind="site", site="google")])

    def open_web(self, site: str, url: str) -> bool:
        """ตัวสั่งงาน (actions.Executor) ส่งงานเปิดเว็บมาที่นี่ · การ์ด 0031.

        มาจาก: ปุ่มหน้าแรก · พิมพ์ "เปิด…" · ขั้น "เปิดเว็บ" ของสกิล

        True = เริ่มเปิดในเบราว์เซอร์ของผู้ช่วยแล้ว (ผลจริงมาทางสัญญาณ opened) ·
        False = ให้ตัวสั่งงานเปิดด้วยเบราว์เซอร์ปกติแทน (หน้า Login · กำลังทำคำสั่งอื่น · เครื่องไม่มี Chromium)
        """
        from aipc.skills.browse import BrowseCommand

        if not self._active or self._busy or not self._ctl().available:
            return False
        cmd = BrowseCommand("site", site=site) if site else BrowseCommand("url", query=url)
        return self._start([cmd], quiet=True)

    @Slot(result=str)
    def signOutAll(self) -> str:  # noqa: N802
        """ออกจากบัญชีเว็บทั้งหมดในเครื่องนี้ของผู้ใช้คนนี้ (การ์ด 0031).

        ปิดเบราว์เซอร์ของผู้ช่วย → ลบโฟลเดอร์โปรไฟล์ · backend ตรวจเอง (H7):
        หน้า Login ไม่มีเจ้าของเซสชัน = ไม่ทำ · Chromium ตัวอื่นยังใช้โปรไฟล์ = ไม่ลบ (H1) ·
        ไม่แตะไฟล์ดาวน์โหลด (อยู่นอกโปรไฟล์)
        """
        from aipc.browser import control

        if not self._active:
            return "ทำไม่ได้ในหน้าเข้าสู่ระบบ"
        if self._busy:
            return "เบราว์เซอร์ของผู้ช่วยกำลังทำงาน · รอสักครู่แล้วกดใหม่"
        if self._control is not None:
            self._control.close()
        profile = self._profile or control.default_profile()
        if control.profile_in_use(profile):
            return "ยังมีหน้าต่างเบราว์เซอร์ของผู้ช่วยเปิดค้างอยู่ · ปิดหน้าต่างนั้นก่อนแล้วกดใหม่"
        try:
            control.remove_profile(profile)
        except OSError as e:
            return f"ลบไม่สำเร็จ: {e.strerror or e} · การเข้าสู่ระบบเว็บยังอยู่"
        return "ออกจากบัญชีเว็บทั้งหมดในเครื่องนี้แล้ว · ลบการเข้าสู่ระบบ คุกกี้ และประวัติของเบราว์เซอร์ของผู้ช่วย"

    def _start(self, cmds, quiet: bool = False) -> bool:
        self._busy = True
        self.busyChanged.emit()
        threading.Thread(target=self._work, args=(cmds, quiet), daemon=True).start()
        return True

    def _work(self, cmds, quiet: bool = False) -> None:
        says, ok = [], True
        for c in cmds:
            r = self._ctl().run(c)
            if c.kind == "search" and self._ledger is not None:
                # คำค้นออกไป Google/Bing = ส่งออกนอกเครื่อง (แผงความเป็นส่วนตัวนับด้วย)
                self._ledger.record("web", f"ค้นเว็บ: {c.query}", ok=r.ok,
                                    note="เบราว์เซอร์ของผู้ช่วย · สั่งด้วยเสียง")  # fmt: skip
            if r.say:
                says.append(r.say)
            if not r.ok:
                ok = False
                break
        self._done.emit(" · ".join(says) or "ทำไม่สำเร็จ", ok, quiet)

    @Slot(str, bool, bool)
    def _on_done(self, say: str, ok: bool, quiet: bool) -> None:
        self._busy = False
        self.busyChanged.emit()
        (self.opened if quiet else self.finished).emit(say, ok)

    @Slot()
    def close(self) -> None:
        if self._control is not None:
            self._control.close()
