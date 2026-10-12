"""สั่งด้วยเสียงไม่ใช้เมาส์ (การ์ด 0024): คีย์ลัดทั้งเครื่อง + เบราว์เซอร์ของผู้ช่วย.

- labwc กด F9 → `scripts/pi/session/aipc-voice-key` เขียนหนึ่งไบต์ลง FIFO
  `$XDG_RUNTIME_DIR/aipc/voice-key` → HotkeyListener ส่ง pressed()
  (FIFO ของผู้ใช้คนนี้ 0600 · บัญชีอื่นกดแทนไม่ได้)
- BrowserController ทำคำสั่งเว็บในเธรดแยก (หน้าเว็บโหลดหลายวินาที) แล้วส่ง finished(ประโยคสั้น, สำเร็จไหม)
"""

from __future__ import annotations

import math
import os
import shutil
import struct
import subprocess
import threading
import wave
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


class BrowserController(QObject):
    """คำสั่งเว็บจากเสียง · ประโยคที่ไม่ใช่คำสั่งเว็บ handle() คืน False ให้หน้าจอส่งเข้าแชทตามเดิม."""

    finished = Signal(str, bool)
    busyChanged = Signal()  # noqa: N815
    _done = Signal(str, bool)

    def __init__(self, active: bool = True, control=None, ledger=None):
        super().__init__()
        self._active = active
        self._control = control
        self._ledger = ledger
        self._busy = False
        self._done.connect(self._on_done)

    def _ctl(self):
        if self._control is None:
            from aipc.browser.control import BrowserControl

            self._control = BrowserControl()
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
        self._busy = True
        self.busyChanged.emit()
        threading.Thread(target=self._work, args=(cmds,), daemon=True).start()
        return True

    def _work(self, cmds) -> None:
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
        self._done.emit(" · ".join(says) or "ทำไม่สำเร็จ", ok)

    @Slot(str, bool)
    def _on_done(self, say: str, ok: bool) -> None:
        self._busy = False
        self.busyChanged.emit()
        self.finished.emit(say, ok)

    @Slot()
    def close(self) -> None:
        if self._control is not None:
            self._control.close()
