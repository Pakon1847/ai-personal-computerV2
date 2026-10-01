"""กดค้างเพื่อพูด (การ์ด 0019 ข้อ 9) · อัดด้วย pw-record แล้วถอดด้วย whisper.cpp ในเครื่อง.

- อัดเฉพาะตอนกดค้าง (ยาวสุด MAX_S วิ) · ไฟล์เสียงอยู่ใน $XDG_RUNTIME_DIR (tmpfs ของผู้ใช้) · ถอดเสร็จลบทันที
- Thonburian distill-small f16 + `-ac 512`: Pi 5 ถอดประโยค ~2 วิ ใน ~2 วิ
  (docs/benchmarks/2026-10-01-voice-small)
- ข้อความที่ได้ส่งกลับให้หน้าจอใส่ช่องพิมพ์ **ไม่ส่งเอง** (ทดลองแล้ว: ถอดผิดทำให้ตัวแปลคำสั่งทำผิดโดยไม่ถาม)
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

VOICE_DIR = Path(os.environ.get("AIPC_VOICE_DIR", "/opt/aipc-voice"))
WHISPER = "whisper/bin/whisper-cli"
MODEL = "thonburian-distill-small-f16.bin"
MAX_S = 15
MIN_S = 0.4  # กดแล้วปล่อยทันที = ไม่ถอด
# whisper ใส่ป้ายเช่น [BLANK_AUDIO] (เสียงดนตรี) ตอนไม่มีเสียงพูด
TAGS = re.compile(r"\[[^\]]*\]|\([^)]*\)")


class Endpointer:
    """จับจุดจบเสียงพูดจากความดัง (การ์ด 0019 ข้อ 10) · ป้อน PCM 16-bit mono 16 kHz ทีละก้อน.

    ระดับเสียงพื้นหลังวัดจาก 0.3 วิแรก (ก่อนเริ่มพูด) · เริ่มพูด = ดังเกินเกณฑ์ 3 ช่องติด (90 ms) ·
    จบ = หลังเริ่มพูดแล้วเงียบต่อกัน silence_s วิ · ไม่ใช้โมเดล (CPU น้อย ไม่แย่ง AI)
    feed() คืน None (ฟังต่อ) · "end" · "no_speech" · "max"
    """

    FRAME = 480  # 30 ms

    def __init__(self, silence_s: float = 1.0, no_speech_s: float = 5.0, max_s: float = MAX_S,
                 sr: int = 16000):  # fmt: skip
        self.frame_s = self.FRAME / sr
        self.silence_frames = round(silence_s / self.frame_s)
        self.no_speech_frames = round(no_speech_s / self.frame_s)
        self.max_frames = round(max_s / self.frame_s)
        self._buf = b""
        self._levels: list[float] = []
        self._noise: float | None = None
        self.frames = 0
        self.speaking = False
        self._loud = 0
        self._quiet = 0

    def feed(self, data: bytes) -> str | None:
        import array

        self._buf += data
        n = self.FRAME * 2
        while len(self._buf) >= n:
            frame, self._buf = self._buf[:n], self._buf[n:]
            a = array.array("h")
            a.frombytes(frame)
            level = (sum(x * x for x in a) / len(a)) ** 0.5
            if (r := self._frame(level)) is not None:
                return r
        return None

    def _frame(self, level: float) -> str | None:
        self.frames += 1
        if self._noise is None:
            self._levels.append(level)
            if len(self._levels) < 10:  # 0.3 วิแรก = ระดับเสียงพื้นหลัง
                return None
            self._noise = sorted(self._levels)[len(self._levels) // 2]
            return None
        threshold = max(3.0 * self._noise, 400.0)
        if not self.speaking:
            self._loud = self._loud + 1 if level > threshold else 0
            if self._loud >= 3:
                self.speaking = True
            elif level < threshold:  # ปรับระดับพื้นหลังช้า ๆ ระหว่างยังไม่พูด
                self._noise = 0.95 * self._noise + 0.05 * level
            if not self.speaking and self.frames >= self.no_speech_frames:
                return "no_speech"
        else:
            self._quiet = self._quiet + 1 if level < 0.7 * threshold else 0
            if self._quiet >= self.silence_frames:
                return "end"
        return "max" if self.frames >= self.max_frames else None


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", TAGS.sub(" ", text)).strip()


class Listener:
    """start() เริ่มอัด · stop() หยุดแล้วถอดในเธรดแยก → on_done(ข้อความ, ข้อผิดพลาด, วินาทีที่ถอด)."""

    def __init__(self, on_done: Callable[[str, str, float], None] = lambda *a: None,
                 voice_dir: Path = VOICE_DIR, record_cmd: list[str] | None = None,
                 transcribe_cmd: list[str] | None = None, max_s: float = MAX_S):  # fmt: skip
        self._on_done = on_done
        self._voice_dir = voice_dir
        rec = shutil.which("pw-record")
        auto = [rec, "--rate", "16000", "--channels", "1", "--format", "s16"] if rec else None
        self._record_cmd = record_cmd if record_cmd is not None else auto
        self._transcribe_cmd = transcribe_cmd or [
            str(voice_dir / WHISPER), "-m", str(voice_dir / MODEL), "-l", "th", "-t", "4", "-nt",
            "-ac", "512", "-f"]  # fmt: skip
        self._custom = transcribe_cmd is not None
        self._max_s = max_s
        self._proc: subprocess.Popen | None = None
        self._path: Path | None = None
        self._started = 0.0
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
        self._dir = Path(base) / "aipc-stt"

    @property
    def available(self) -> bool:
        if self._record_cmd is None:
            return False
        return self._custom or (
            (self._voice_dir / WHISPER).exists() and (self._voice_dir / MODEL).exists()
        )

    @property
    def listening(self) -> bool:
        return self._proc is not None

    def start(self) -> str:
        """เริ่มอัด · คืนข้อผิดพลาด ("" = เริ่มได้)."""
        with self._lock:
            if self._proc is not None:
                return ""
            if not self.available:
                return "ยังไม่ได้ติดตั้งตัวถอดเสียง หรือไม่มีไมค์"
            self._dir.mkdir(mode=0o700, exist_ok=True)
            self._path = self._dir / f"rec-{os.getpid()}-{int(time.time() * 1000)}.wav"
            try:
                quiet = subprocess.DEVNULL
                self._proc = subprocess.Popen([*self._record_cmd, str(self._path)], stdout=quiet,
                                              stderr=quiet)  # fmt: skip
            except OSError as e:
                self._proc = None
                return f"เปิดไมค์ไม่ได้: {e}"
            self._started = time.monotonic()
            self._timer = threading.Timer(self._max_s, self.stop)  # กดค้างนานเกิน = หยุดเอง
            self._timer.daemon = True
            self._timer.start()
            return ""

    def stop(self) -> None:
        """หยุดอัด แล้วถอดในเธรดแยก · กดสั้นเกิน = ทิ้ง."""
        with self._lock:
            proc, path, held = self._proc, self._path, time.monotonic() - self._started
            self._proc = None
            if self._timer:
                self._timer.cancel()
        if proc is None or path is None:
            return
        if os.name == "posix":
            proc.send_signal(signal.SIGINT)  # pw-record เขียนหัวไฟล์ WAV ให้ครบก่อนออก
        else:
            proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        if held < MIN_S:
            path.unlink(missing_ok=True)
            self._on_done("", "กดค้างไว้ระหว่างพูด แล้วปล่อยเมื่อพูดจบ", 0.0)
            return
        threading.Thread(target=self._transcribe, args=(path,), daemon=True).start()

    def cancel(self) -> None:
        with self._lock:
            proc, path = self._proc, self._path
            self._proc = None
            if self._timer:
                self._timer.cancel()
        if proc is not None:
            proc.kill()
            proc.wait()
        if path is not None:
            path.unlink(missing_ok=True)

    def _transcribe(self, path: Path) -> None:
        t0 = time.monotonic()
        try:
            r = subprocess.run([*self._transcribe_cmd, str(path)], capture_output=True, text=True,
                               encoding="utf-8", timeout=60)  # fmt: skip
            text, err = clean(r.stdout), ("" if r.returncode == 0 else "ถอดเสียงไม่สำเร็จ")
        except (OSError, subprocess.TimeoutExpired):
            text, err = "", "ถอดเสียงไม่สำเร็จ"
        finally:
            path.unlink(missing_ok=True)  # ไม่เก็บเสียงไว้
        if not text and not err:
            err = "ไม่ได้ยินเสียงพูด ลองพูดใกล้ไมค์อีกครั้ง"
        self._on_done(text, err, round(time.monotonic() - t0, 2))
