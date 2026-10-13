"""สั่งด้วยเสียงไม่ใช้เมาส์ (การ์ด 0024): คีย์ลัดทั้งเครื่อง + เบราว์เซอร์ของผู้ช่วย.

- labwc กด F9 → `scripts/pi/session/aipc-voice-key` เขียนหนึ่งไบต์ลง FIFO
  `$XDG_RUNTIME_DIR/aipc/voice-key` → HotkeyListener ส่ง pressed()
  (FIFO ของผู้ใช้คนนี้ 0600 · บัญชีอื่นกดแทนไม่ได้)
- BrowserController ให้ AI คิดเองว่าจะทำอะไรกับเบราว์เซอร์ (การ์ด 0025 · aipc.browser.agent) ในเธรดแยก
  แล้วส่ง finished(ประโยคสั้น, สำเร็จไหม) หรือ passToChat(ประโยค) เมื่อไม่ใช่งานเว็บ
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
    """ผู้ช่วยเว็บที่ AI คิดเอง (การ์ด 0025 · เดิม 0024 ใช้กฎ) · ทุกประโยคจากคีย์ลัด F9 มาที่นี่ (ยกเว้นตอบการ์ดยืนยัน)
    → AI วางแผน/ดูหน้า/ทำ ในเธรดแยก (aipc.browser.agent) → finished(ประโยคสั้น, สำเร็จไหม) ·
    AI บอกว่าไม่ใช่งานเว็บ → passToChat(ประโยค) ให้หน้าจอส่งเข้าแชทตามเดิม · progress(ข้อความ) ระหว่างทำ."""

    finished = Signal(str, bool)
    passToChat = Signal(str)  # noqa: N815
    progress = Signal(str)
    busyChanged = Signal()  # noqa: N815
    _done = Signal(object, str)

    WARM_DELAY_MS = 45_000  # หลัง AI พร้อม: ให้แชทอุ่นของตัวเองก่อน แล้วจึงอุ่นของผู้ช่วยเว็บ

    def __init__(self, active: bool = True, control=None, ledger=None, agent=None, cloud=None,
                 claude_on=None, chat_busy=None):  # fmt: skip
        super().__init__()
        self._chat_busy = chat_busy or (lambda: False)  # แชทกำลังใช้ AI = ไม่อ่านไว้ก่อน (ไม่แย่งคิว)
        self._warm_pending = False
        self._active = active
        self._control = control
        self._ledger = ledger
        self._agent = agent
        self._cloud = cloud  # (system, prompt) → CloudReply · None = ไม่มี Claude ในบัญชีนี้
        self._claude_on = claude_on or (lambda: True)  # สวิตช์ Claude ในหน้าตั้งค่า
        self._busy = False
        self._done.connect(self._on_done)

    def _ctl(self):
        if self._control is None:
            from aipc.browser.control import BrowserControl

            self._control = BrowserControl()
        return self._control

    def _get_agent(self):
        if self._agent is None:
            from aipc.browser.agent import Agent, Llm
            from aipc.chat.client import Target

            # Claude สำรอง · ไม่มี/ปิดสวิตช์ = ไม่ส่งอะไรออกเลย (การ์ด 0025 เกณฑ์ข้อ 7)
            self._agent = Agent(self._ctl(), Llm(Target.from_env()), cloud=self._cloud,
                                cloud_ready=self._claude_on, progress=self.progress.emit,
                                idle=lambda: not self._chat_busy() and not self._busy)  # fmt: skip
        return self._agent

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Slot()
    def warmSoon(self) -> None:  # noqa: N802
        """AI ในเครื่องเพิ่งพร้อม (login) → อีกสักพักอ่าน system prompt ของผู้ช่วยเว็บไว้ในแคชเบื้องหลัง
        · ไม่อุ่น = คำสั่งเสียงแรกรอเกือบ 3 นาที (Pi 5 2026-10-13) · อ่านเป็นช่วง ๆ เฉพาะตอนแชทว่าง."""
        if not self._active or self._warm_pending:
            return
        from PySide6.QtCore import QTimer

        self._warm_pending = True

        def go():
            self._warm_pending = False
            agent = self._get_agent()
            if agent.pre is not None and not agent.pre.warmed and not self._busy:
                agent.pre.warm()

        QTimer.singleShot(self.WARM_DELAY_MS, go)

    @Slot(str, result=bool)
    def handle(self, text: str) -> bool:
        """รับประโยคไปให้ AI ตัดสิน · False = ไม่รับ (ปิดอยู่ / กำลังทำคำสั่งก่อน) → หน้าจอส่งเข้าแชทเอง."""
        if not self._active or self._busy or not text.strip():
            return False
        self._busy = True
        self.busyChanged.emit()
        threading.Thread(target=self._work, args=(text,), daemon=True).start()
        return True

    def _work(self, text: str) -> None:
        out = self._get_agent().run(text)
        self._done.emit(out, text)

    @Slot(object, str)
    def _on_done(self, out, text: str) -> None:
        self._busy = False
        self.busyChanged.emit()
        if self._ledger is not None:
            for st in out.steps:
                act, _, arg = st.partition(" ")
                if act in ("search", "find"):  # คำค้นออกไปเว็บค้นหา/เว็บที่เปิด = ส่งออกนอกเครื่อง
                    self._ledger.record("web", f"ค้นเว็บ: {arg}", ok=out.ok,
                                        note="ผู้ช่วยเว็บ · สั่งด้วยเสียง")  # fmt: skip
        if not out.handled:
            self.passToChat.emit(text)
            return
        self.finished.emit(out.say or ("ทำแล้ว" if out.ok else "ทำไม่สำเร็จ"), out.ok)

    @Slot()
    def close(self) -> None:
        if self._agent is not None and self._agent.pre is not None:
            self._agent.pre.pause()
        if self._control is not None:
            self._control.close()
