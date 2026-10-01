"""อ่านคำตอบออกเสียง (การ์ด 0019) · แอปคุยกับ piper_worker ที่เปิดค้าง แล้วเล่นทีละท่อนด้วย pw-play.

- เปิดตัวสังเคราะห์เมื่อกดอ่านครั้งแรก (ไม่โหลดตอนเข้าเครื่อง: ขณะทำงานใช้ RAM ~670 MB · วัดบน Pi 5)
- ไม่ได้ใช้ IDLE_S วินาที → ปิดตัวสังเคราะห์คืน RAM
- ไฟล์เสียงอยู่ใน $XDG_RUNTIME_DIR (tmpfs ของผู้ใช้ 0700) · เล่นจบลบทันที · ไม่มีอะไรออกนอกเครื่อง
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

from aipc.voice.speech_text import sentences, to_speech

VOICE_DIR = Path(os.environ.get("AIPC_VOICE_DIR", "/opt/aipc-voice"))
MODEL = "th_TH-tsync2-medium.onnx"
WORKER = Path(__file__).with_name("piper_worker.py")
PLAYERS = ("pw-play", "aplay", "paplay")
IDLE_S = 600


def player() -> list[str] | None:
    for name in PLAYERS:
        path = shutil.which(name)
        if path:
            return [path]
    return None


def installed(voice_dir: Path = VOICE_DIR) -> bool:
    return (voice_dir / "venv" / "bin" / "python").exists() and (voice_dir / MODEL).exists()


class Speaker:
    """พูดได้ครั้งละเรื่อง · say() ใหม่ = หยุดเรื่องเก่า · on_state(id, กำลังพูด, ข้อผิดพลาด) เรียกจากเธรดอื่น."""

    def __init__(self, on_state: Callable[[int, bool, str], None] = lambda *a: None,
                 voice_dir: Path = VOICE_DIR, play_cmd: list[str] | None = None,
                 worker_cmd: list[str] | None = None, idle_s: float = IDLE_S):  # fmt: skip
        self._on_state = on_state
        self._voice_dir = voice_dir
        self._play_cmd = play_cmd if play_cmd is not None else player()
        self._worker_cmd = worker_cmd or [str(voice_dir / "venv" / "bin" / "python"), str(WORKER),
                                          str(voice_dir / MODEL)]  # fmt: skip
        self._custom_worker = worker_cmd is not None  # เทสต์ใช้ตัวสังเคราะห์ปลอม
        self._idle_s = idle_s
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._playing: subprocess.Popen | None = None
        self._current = -1  # id ที่กำลังพูด · -1 = เงียบ
        self._next_id = 0
        self._last_used = time.monotonic()
        base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
        self._dir = Path(base) / "aipc-tts"

    @property
    def available(self) -> bool:
        return self._play_cmd is not None and (self._custom_worker or installed(self._voice_dir))

    @property
    def current(self) -> int:
        return self._current

    def say(self, text: str) -> int:
        """เริ่มอ่าน · คืน id ของเรื่องนี้ (-1 = ไม่มีอะไรให้อ่าน)."""
        chunks = sentences(to_speech(text))
        self.stop()
        if not chunks:
            return -1
        with self._lock:
            self._next_id += 1
            jid = self._current = self._next_id
            self._last_used = time.monotonic()
            try:
                self._ensure_worker()
                self._dir.mkdir(mode=0o700, exist_ok=True)
                msg = {"cmd": "say", "id": jid, "chunks": chunks, "dir": str(self._dir)}
                self._proc.stdin.write(json.dumps(msg) + "\n")  # ASCII ล้วน ไม่ขึ้นกับ locale
                self._proc.stdin.flush()
            except (OSError, ValueError) as e:
                self._current = -1
                self._kill_worker()
                self._on_state(jid, False, f"เปิดตัวอ่านออกเสียงไม่ได้: {e}")
                return jid
        self._on_state(jid, True, "")
        return jid

    def stop(self) -> None:
        with self._lock:
            jid, self._current = self._current, -1
            if jid > 0 and self._proc and self._proc.poll() is None:
                try:
                    self._proc.stdin.write(json.dumps({"cmd": "cancel", "id": jid}) + "\n")
                    self._proc.stdin.flush()
                except OSError:
                    pass
            if self._playing and self._playing.poll() is None:
                self._playing.terminate()
        if jid > 0:
            self._on_state(jid, False, "")

    def idle_check(self) -> bool:
        """เรียกเป็นระยะ · ไม่ได้ใช้นานเกิน idle_s → ปิดตัวสังเคราะห์ · คืน True ถ้าปิด."""
        with self._lock:
            if (
                self._proc
                and self._current < 0
                and time.monotonic() - self._last_used > self._idle_s
            ):
                self._kill_worker()
                return True
        return False

    def close(self) -> None:
        self.stop()
        with self._lock:
            self._kill_worker()

    # ---------- ภายใน ----------
    def _ensure_worker(self) -> None:
        if self._proc and self._proc.poll() is None:
            return
        env = {
            **os.environ,
            "OMP_NUM_THREADS": "2",
            "PYTHONIOENCODING": "utf-8",
        }  # เหลือ CPU ให้ AI ในเครื่อง
        pipe = subprocess.PIPE
        quiet = subprocess.DEVNULL
        self._proc = subprocess.Popen(self._worker_cmd, stdin=pipe, stdout=pipe, stderr=quiet,
                                      text=True, encoding="utf-8", env=env)  # fmt: skip
        threading.Thread(target=self._read, args=(self._proc,), daemon=True).start()

    def _kill_worker(self) -> None:
        if self._proc:
            try:
                self._proc.stdin.close()
                self._proc.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                self._proc.kill()
            self._proc = None

    def _read(self, proc: subprocess.Popen) -> None:
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            jid = msg.get("id")
            if jid is None:
                continue
            path = Path(msg["path"]) if msg.get("path") else None
            if jid != self._current:  # ถูกหยุดไปแล้ว
                if path:
                    path.unlink(missing_ok=True)
                continue
            if msg.get("error"):
                with self._lock:
                    self._current = -1
                self._on_state(jid, False, "อ่านออกเสียงไม่สำเร็จ")
                continue
            self._play(jid, path)
            if msg.get("last") and jid == self._current:
                with self._lock:
                    self._current = -1
                    self._last_used = time.monotonic()
                self._on_state(jid, False, "")
        # ตัวสังเคราะห์ตายกลางทาง
        with self._lock:
            mine = self._proc is proc  # ไม่ใช่ = ปิดเองตอนว่าง/ปิดแอป ไม่ใช่ล่ม
            jid = self._current if mine else -1
            if mine:
                self._current, self._proc = -1, None
        if jid > 0:
            self._on_state(jid, False, "ตัวอ่านออกเสียงหยุดทำงาน")

    def _play(self, jid: int, path: Path) -> None:
        try:
            with self._lock:
                if jid != self._current:
                    return
                quiet = subprocess.DEVNULL
                self._playing = subprocess.Popen(
                    [*self._play_cmd, str(path)], stdout=quiet, stderr=quiet
                )
            self._playing.wait()
        except OSError:
            pass
        finally:
            path.unlink(missing_ok=True)
