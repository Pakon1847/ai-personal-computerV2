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
# หน้าจอภาษาอังกฤษ (การ์ด 0040 · D1 เลือกบน Pi 5: ถอด ~0.8 วิ · RAM ~257 MB · MIT)
EN_MODEL = "ggml-base.en.bin"
# คำที่บอกตัวถอดอังกฤษล่วงหน้า (ชื่อเว็บ/คำสั่งของระบบ) · ลองบน Pi 2026-10-20: ไม่บอก "YouTube" → "you too/U2"
EN_PROMPT = ("Open YouTube, Gmail, Google Maps, Netflix, Spotify, Viu, WeTV, iQIYI, Disney Plus, "
             "Google Docs, Google Drive. Mute, volume up, remind me, what time is it.")  # fmt: skip
MAX_S = 15
# การ์ด 0044 (คีย์ลัด): เงียบ 0.3 วิ = เริ่มถอดล่วงหน้า · คำสั่งครบแล้ว + เงียบ 0.6 วิ = จบเลย (ปกติรอ 1.0 วิ) ·
# ตั้งจากชุดพัฒนา voice_latency_dev (ประโยคเว้นช่วง 0.45 วิ ต้องไม่ถูกตัด)
SPEC_AT_S = 0.3
EARLY_S = 0.6
DECODE_WAIT_S = 20.0
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
        self.voiced = 0  # ช่องที่มีเสียงพูดหลังเริ่มพูด · เปลี่ยน = ผู้ใช้พูดต่อ (การ์ด 0044)

    @property
    def quiet_s(self) -> float:
        """เงียบต่อกันมานานเท่าไรหลังเริ่มพูด (วินาที) · ยังไม่เริ่มพูด = 0."""
        return self._quiet * self.frame_s if self.speaking else 0.0

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
            if level < 0.7 * threshold:
                self._quiet += 1
            else:
                self._quiet = 0
                self.voiced += 1
            if self._quiet >= self.silence_frames:
                return "end"
        return "max" if self.frames >= self.max_frames else None


def _remove(path: Path) -> None:
    """ลบไฟล์เสียง · Windows ปล่อยไฟล์ช้าหลังปิดโปรแกรมอัด (เทสต์) → ลองซ้ำสั้น ๆ."""
    for _ in range(20):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            time.sleep(0.05)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", TAGS.sub(" ", text)).strip()


class Listener:
    """start() เริ่มอัด · stop() หยุดแล้วถอดในเธรดแยก → on_done(ข้อความ, ข้อผิดพลาด, วินาทีที่ถอด).

    auto_stop=True (แตะครั้งเดียว · การ์ด 0019 ข้อ 10): อ่านไฟล์ที่กำลังอัดทุก 0.1 วิ ป้อน Endpointer ·
    พูดจบแล้วเงียบ 1 วิ = หยุดและถอดเอง · ไม่ได้ยินเสียงพูด 5 วิ = ทิ้งแล้วบอกผู้ใช้
    fast = ตัวถอดของคีย์ลัด (Zipformer · การ์ด 0026) ใช้เมื่อ start(fast=True) · ไม่มี/ล่ม = ถอยไปใช้ whisper
    """

    def __init__(self, on_done: Callable[[str, str, float], None] = lambda *a: None,
                 voice_dir: Path = VOICE_DIR, record_cmd: list[str] | None = None,
                 transcribe_cmd: list[str] | None = None, max_s: float = MAX_S,
                 auto_stop: bool = True, endpointer=None, fast=None,
                 language: Callable[[], str] = lambda: "th",
                 en_transcribe_cmd: list[str] | None = None,
                 try_english: Callable[[str], bool] | None = None,
                 use_english: Callable[[str], bool] | None = None,
                 complete: Callable[[str], bool] | None = None):  # fmt: skip
        self._on_done = on_done
        # การ์ด 0044: complete(ข้อความไทย) = เป็นคำสั่งครบแล้ว (เว็บ/เครื่อง/ค่าตั้ง) → จบเร็วไม่ต้องรอเงียบ 1 วิ
        self._complete = complete
        self._spec_next: dict | None = None  # ผลถอดล่วงหน้าที่ใช้ได้ ส่งต่อให้ stop() → _transcribe
        # ภาษาของตัวถอด = ภาษาหน้าจอที่ผู้ใช้ตั้ง (การ์ด 0040 · โค้ดเลือก ไม่ให้โมเดลเดาภาษา · H6)
        self._language = language
        self._lang = "th"
        # คีย์ลัดฟังสองภาษา (การ์ด 0040 หัวข้อ 13): หน้าจอไทยแต่ผู้ใช้พูดอังกฤษ → Zipformer ได้คำไทยมั่ว ·
        # try_english(ข้อความไทย) = ไม่ตรงคำสั่งไหน → ถอดเสียงเดิมซ้ำเป็นอังกฤษ ·
        # use_english(ข้อความอังกฤษ) = เป็นคำสั่งที่รู้จักแน่ (ตัวแปลงระยะ C / ใช่-ไม่) จึงใช้ ·
        # ไม่ใช่ = ข้อความไทยเดิม (ไม่เดา)
        self._try_english = try_english
        self._use_english = use_english
        self._fast = fast
        self._use_fast = False
        self._voice_dir = voice_dir
        rec = shutil.which("pw-record")
        auto = [rec, "--rate", "16000", "--channels", "1", "--format", "s16"] if rec else None
        self._record_cmd = record_cmd if record_cmd is not None else auto
        self._transcribe_cmd = transcribe_cmd or [
            str(voice_dir / WHISPER), "-m", str(voice_dir / MODEL), "-l", "th", "-t", "4", "-nt",
            "-ac", "512", "-f"]  # fmt: skip
        self._en_cmd = en_transcribe_cmd or [
            str(voice_dir / WHISPER), "-m", str(voice_dir / EN_MODEL), "-l", "en", "-t", "4", "-nt",
            "-ac", "512", "--prompt", EN_PROMPT, "-f"]  # fmt: skip
        self._custom = transcribe_cmd is not None
        self._custom_en = en_transcribe_cmd is not None
        self._max_s = max_s
        self._auto_stop = auto_stop
        self._make_endpointer = endpointer or (lambda: Endpointer(max_s=max_s))
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
    def english_available(self) -> bool:
        if self._record_cmd is None:
            return False
        return self._custom_en or (
            (self._voice_dir / WHISPER).exists() and (self._voice_dir / EN_MODEL).exists()
        )

    @property
    def listening(self) -> bool:
        return self._proc is not None

    def start(self, fast: bool = False) -> str:
        """เริ่มอัด · คืนข้อผิดพลาด ("" = เริ่มได้) · fast = ถอดด้วยตัวถอดของคีย์ลัด (เปิดรอระหว่างพูด)."""
        with self._lock:
            if self._proc is not None:
                return ""
            if not self.available:
                return "ยังไม่ได้ติดตั้งตัวถอดเสียง หรือไม่มีไมค์"
            self._lang = "en" if self._language() == "en" else "th"
            # คีย์ลัดฟังสองภาษาเสมอ ไม่ขึ้นกับภาษาหน้าจอ (Pakon 2026-10-20 "ใช้ได้ทั้งไทยและอังกฤษรวมกัน"):
            # Zipformer ไทยก่อน · ไม่ตรงคำสั่ง → ลองอังกฤษ (_maybe_english) · ปุ่มไมค์ยังใช้ภาษาหน้าจอ
            self._use_fast = fast and self._fast is not None and self._fast.available
            if self._lang == "en" and not self.english_available and not self._use_fast:
                return "ยังไม่ได้ติดตั้งตัวถอดเสียงภาษาอังกฤษ"
            if self._use_fast:
                self._fast.warm()  # โหลดโมเดล 3.7 วิ ระหว่างผู้ใช้พูด
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
            self._timer = threading.Timer(self._max_s + 1, self.stop)  # กันไมค์ค้าง (ไฟล์ไม่โต)
            self._timer.daemon = True
            self._timer.start()
            if self._auto_stop:
                threading.Thread(
                    target=self._watch, args=(self._proc, self._path), daemon=True
                ).start()
            return ""

    def _watch(self, proc: subprocess.Popen, path: Path) -> None:
        """อ่านเสียงที่อัดเพิ่มทุก 0.1 วิ · Endpointer บอกจบ = หยุดเอง.

        การ์ด 0044 (คีย์ลัด · fast): เงียบ SPEC_AT_S = ถอดเสียงที่ได้ถึงตอนนั้นล่วงหน้า (ระหว่างรอเงียบครบ) ·
        พูดต่อ = ทิ้งผลล่วงหน้า · ผลเป็นคำสั่งครบ + เงียบ EARLY_S = จบเลย · จบตามปกติ = ใช้ผลที่ถอดไว้แล้ว
        """
        ep, offset = self._make_endpointer(), None
        pcm = bytearray()
        spec: dict | None = None
        while self._proc is proc:
            time.sleep(0.1)
            try:
                with path.open("rb") as f:
                    if offset is None:  # หาจุดเริ่มข้อมูลเสียงใน WAV ("data" + ขนาด 4 ไบต์)
                        head = f.read(4096)
                        i = head.find(b"data")
                        if i < 0:
                            continue
                        offset = i + 8
                    f.seek(offset)
                    chunk = f.read()
            except OSError:
                continue
            offset += len(chunk) - len(chunk) % 2
            data = chunk[: len(chunk) - len(chunk) % 2]
            pcm += data
            result = ep.feed(data) if data else None
            if result == "no_speech":
                self.cancel()
                self._on_done("", "ไม่ได้ยินเสียงพูด ลองแตะแล้วพูดใกล้ไมค์อีกครั้ง", 0.0)
                return
            if spec is not None and spec["voiced"] != ep.voiced:
                spec = None  # พูดต่อ = ผลล่วงหน้าไม่ครบประโยค ทิ้ง (เธรดลบไฟล์ของมันเอง)
            if result is not None:
                self._spec_next = spec
                self.stop()
                return
            if not (self._use_fast and ep.speaking):
                continue
            if spec is None and ep.quiet_s >= SPEC_AT_S:
                spec = self._speculate(bytes(pcm), ep.voiced)
            done = spec is not None and spec["done"].is_set() and not spec["err"] and spec["text"]
            if done and ep.quiet_s >= EARLY_S and self._complete and self._complete(spec["text"]):
                self._spec_next = spec
                self.stop()
                return

    def _speculate(self, pcm: bytes, voiced: int) -> dict:
        """ถอดเสียงที่ได้ถึงตอนนี้ในเธรดแยก (รวมลองอังกฤษถ้าต้อง) · ไฟล์ชั่วคราวลบทันทีหลังถอด."""
        import wave

        spec = {"voiced": voiced, "done": threading.Event(), "text": "", "err": ""}
        snap = self._dir / f"spec-{os.getpid()}-{int(time.time() * 1000)}.wav"
        try:
            with wave.open(str(snap), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(16000)
                w.writeframes(pcm)
        except OSError as e:
            spec["err"] = str(e)
            spec["done"].set()
            return spec

        def run() -> None:
            try:
                # ถอดล่วงหน้าเฉพาะภาษาไทย · ลองอังกฤษทำบนไฟล์เต็มตอนจบ (_transcribe) เหมือนเดิม:
                # ไฟล์ล่วงหน้าเงียบท้ายสั้น whisper อ่านคำสั่งอังกฤษหลุด (ชุดพัฒนา: 3/6 → 2/6)
                text, err = self._fast.transcribe(snap)
                spec["text"] = text if not err else ""
                spec["err"] = err
            finally:
                _remove(snap)
                spec["done"].set()

        threading.Thread(target=run, daemon=True).start()
        return spec

    def stop(self) -> None:
        """หยุดอัด แล้วถอดในเธรดแยก · กดสั้นเกิน = ทิ้ง."""
        with self._lock:
            proc, path, held = self._proc, self._path, time.monotonic() - self._started
            spec, self._spec_next = self._spec_next, None
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
            _remove(path)
            self._on_done("", "กดค้างไว้ระหว่างพูด แล้วปล่อยเมื่อพูดจบ", 0.0)
            return
        threading.Thread(target=self._transcribe, args=(path, spec), daemon=True).start()

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
            _remove(path)

    def _maybe_english(self, path: Path, thai: str) -> str:
        """ข้อความที่จะใช้: ภาษาไทยเดิม หรือภาษาอังกฤษเมื่อไทยไม่ตรงคำสั่งแต่อังกฤษตรง (คีย์ลัด · หน้าจอไทย)."""
        if not (self._try_english and self._use_english and self.english_available):
            return thai
        try:
            if not self._try_english(thai):
                return thai
            r = subprocess.run([*self._en_cmd, str(path)], capture_output=True, text=True,
                               encoding="utf-8", timeout=30)  # fmt: skip
            en = clean(r.stdout) if r.returncode == 0 else ""
            return en if en and self._use_english(en) else thai
        except (OSError, subprocess.TimeoutExpired, ValueError):
            return thai  # ถอดอังกฤษไม่ได้ = ใช้ไทยตามเดิม (ไม่ทำให้คีย์ลัดเสีย)

    def _transcribe(self, path: Path, spec: dict | None = None) -> None:
        t0 = time.monotonic()
        # การ์ด 0044: ถอดล่วงหน้าไว้แล้ว (ไม่มีเสียงพูดเพิ่มหลังจากนั้น) = ใช้ผลนั้น ไม่ต้องถอดซ้ำ
        if (
            self._use_fast
            and spec is not None
            and spec["done"].wait(DECODE_WAIT_S)
            and not spec["err"]
        ):
            text = self._maybe_english(path, spec["text"])  # ไทยไม่ตรงอะไร = ลองอังกฤษบนไฟล์เต็ม
            _remove(path)
            err = "" if text else "ไม่ได้ยินเสียงพูด ลองพูดใกล้ไมค์อีกครั้ง"
            self._on_done(text, err, round(time.monotonic() - t0, 2))
            return
        if self._use_fast:
            text, err = self._fast.transcribe(path)
            if not err:  # ล่ม/ค้าง = ถอยไปใช้ whisper ข้างล่าง (ไม่ทิ้งสิ่งที่ผู้ใช้พูด · H2)
                text = self._maybe_english(path, text)
                _remove(path)
                if not text:
                    err = "ไม่ได้ยินเสียงพูด ลองพูดใกล้ไมค์อีกครั้ง"
                self._on_done(text, err, round(time.monotonic() - t0, 2))
                return
        try:
            cmd = self._en_cmd if self._lang == "en" else self._transcribe_cmd
            r = subprocess.run([*cmd, str(path)], capture_output=True, text=True,
                               encoding="utf-8", timeout=60)  # fmt: skip
            text, err = clean(r.stdout), ("" if r.returncode == 0 else "ถอดเสียงไม่สำเร็จ")
        except (OSError, subprocess.TimeoutExpired):
            text, err = "", "ถอดเสียงไม่สำเร็จ"
        finally:
            _remove(path)  # ไม่เก็บเสียงไว้
        if not text and not err:
            err = "ไม่ได้ยินเสียงพูด ลองพูดใกล้ไมค์อีกครั้ง"
        self._on_done(text, err, round(time.monotonic() - t0, 2))
