"""ตัวถอดเสียงของคีย์ลัด F9 / Alt+Space (การ์ด 0026): Zipformer ไทย + hotwords คำสั่งเว็บ.

ทำไมไม่ใช้ whisper ทางนี้ (เทียบ 7 แบบบน Pi 5 · docs/benchmarks/2026-10-14-voice-models):
whisper ได้ยินคำสั่งเพี้ยน ("ปิดแท็บ" → «เป๊ก») และช้า (0.8–1.9 วิ) · Zipformer + hotwords ทำถูกมากขึ้น
(ชุดพัฒนา 39 → 50/64) · ไม่เคยทำคำสั่งกับประโยคที่ไม่ใช่คำสั่ง (0/38) · 0.16 วิ · RAM 329 MB
ปุ่มไมค์ในแอป (ประโยคยาว/แชท) ยังใช้ whisper เหมือนเดิม

- เปิดตัวถอดตอนกดคีย์ลัด (warm) ระหว่างผู้ใช้พูด · ไม่ได้ใช้ IDLE_S วินาที → ปิดคืน RAM
- ตัวถอดต่อเน็ตไม่ได้ (กล่องเดียวกับ Piper: tts.sandboxed · onnxruntime ข้างในส่ง telemetry เองได้)
- ไม่ได้ติดตั้ง / ล่ม = available False หรือคืนข้อผิดพลาด → ตัวอัดถอยไปใช้ whisper (ของเดิมไม่พัง)
"""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

from aipc.voice.tts import VOICE_DIR, sandboxed

BASE = VOICE_DIR / "zipformer"  # venv/ + model/ (scripts/pi/install-voice.sh --zipformer)
WORKER = Path(__file__).with_name("zipformer_worker.py")
IDLE_S = 600
LOAD_TIMEOUT_S = 30  # Pi 5 โหลด 3.7 วิ · เผื่อเครื่องร้อน/ดิสก์ช้า
DECODE_TIMEOUT_S = 15
SCORE = 5.0  # น้ำหนัก hotwords ×5 · ตั้งจากชุดพัฒนาเท่านั้น (V1+V2 · hw-dev/)
THREADS = 4  # ค่าที่วัด (0.16 วิ) · ถอดสั้นมาก ไม่แย่ง AI นาน

# hotwords = ประโยคคำสั่งเต็ม + ต้นคำค้นหา (รายการเดียวกับที่วัด · aipc.spikes.voice_cands ใช้ชุดนี้)
SEARCH_STEMS = ["ค้นหา", "หา", "ช่วยค้นหา", "ช่วยหา", "เสิร์ช", "ค้น", "กูเกิล"]
FIXED = [
    "ย้อนกลับ",
    "กลับไปหน้าก่อน",
    "ถอยกลับ",
    "ไปข้างหน้า",
    "เดินหน้า",
    "โหลดใหม่",
    "รีเฟรช",
    "โหลดหน้าใหม่",
    "เลื่อนลง",
    "เลื่อนขึ้น",
    "เลื่อนหน้าลง",
    "เลื่อนหน้าขึ้น",
    "ปิดแท็บ",
    "ปิดหน้านี้",
    "กลับไปแอป",
    "ไปที่แอป",
    "เปิดกูเกิล",
    "เปิดยูทูบ",
    "เปิดวิกิพีเดีย",
    "เปิดจีเมล",
    "เปิดกูเกิลแมพ",
    "รีโหลด",
    "กลับไปหน้าแชท",
    "กลับไปหน้าผู้ช่วย",
    *(f"{v}ลิงก์{n}" for v in ("เข้า", "เปิด", "กด", "คลิก", "กดเข้า") for n in ("แรก", "ที่สอง", "ที่สาม")),
    *(f"เข้าลิงก์ที่{n}" for n in ("หนึ่ง", "สี่", "ห้า")),
    *(f"เข้า{w}{n}" for w in ("เว็บ", "ผลลัพธ์") for n in ("แรก", "ที่สอง", "ที่สาม", "ที่สี่", "ที่ห้า")),
]
HOTWORDS = SEARCH_STEMS + FIXED

_REPEAT = re.compile(r"^(.{4,}?)(?:\s*\1)+$")  # ทั้งประโยคคือข้อความเดิมซ้ำ (เช่น ค้นหาX ค้นหาX)


def tidy(text: str) -> str:
    """แก้ลักษณะเฉพาะของ Zipformer ก่อนส่งให้ตัวแปลคำสั่ง (พบบนเสียงสังเคราะห์ V4 2026-10-14).

    - เขียนสระอำเป็นนิคหิต + สระอา ("น้ํา") → "น้ำ" (ตาเห็นเหมือนกัน แต่ตัวแปล/เว็บค้นหาเห็นต่างกัน)
    - ถอดทั้งประโยคซ้ำสองรอบ → เหลือรอบเดียว (ซ้ำแค่บางคำไม่แตะ · ต้องยาว ≥ 4 ตัวอักษร กันคำซ้ำสั้น ๆ)
    """
    text = re.sub(r"\s+", " ", text.replace("ํา", "ำ")).strip()
    m = _REPEAT.match(text)
    return m.group(1).strip() if m else text


def installed(base: Path = BASE) -> bool:
    return (base / "venv" / "bin" / "python").exists() and (base / "model" / "tokens.txt").exists()


class Transcriber:
    """ถอดไฟล์ WAV ทีละไฟล์ (เรียกจากเธรดของตัวอัด) · transcribe() คืน (ข้อความ, ข้อผิดพลาด)."""

    def __init__(self, base: Path = BASE, worker_cmd: list[str] | None = None,
                 idle_s: float = IDLE_S, load_timeout_s: float = LOAD_TIMEOUT_S,
                 extra_hotwords: Callable[[], list[str]] | None = None):  # fmt: skip
        self._base = base
        # การ์ด 0028 ทาง ข: ประโยคของสกิลผู้ใช้ต่อท้าย hotwords (SkillsController.voicePhrases)
        # None = รายการเดิมของ 0026
        self.extra_hotwords = extra_hotwords
        self._hot_used: list[str] | None = None  # รายการที่ตัวถอดที่เปิดอยู่ใช้
        self._custom = worker_cmd is not None  # เทสต์ใช้ตัวถอดปลอม
        self._worker_cmd = worker_cmd
        self._idle_s = idle_s
        self._load_timeout_s = load_timeout_s
        self._lock = threading.Lock()  # ถอดทีละไฟล์ · กันเปิดตัวถอดซ้อน
        self._proc: subprocess.Popen | None = None
        self._replies: queue.Queue = queue.Queue()
        self._ready = threading.Event()
        self._next_id = 0
        self._last_used = time.monotonic()
        base_dir = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
        self._dir = Path(base_dir) / "aipc-stt"

    @property
    def available(self) -> bool:
        return self._custom or installed(self._base)

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def hotwords(self) -> list[str]:
        """รายการเดิมของ 0026 (ไม่เปลี่ยน) + ประโยคไทยของสกิลผู้ใช้ (ไม่ซ้ำ · บรรทัดเดียว)."""
        words = list(HOTWORDS)
        for p in self.extra_hotwords() if self.extra_hotwords else []:
            p = re.sub(r"\s+", " ", str(p)).strip()
            if re.search("[฀-๿]", p) and p not in words:  # Zipformer ไทยไม่รู้จักคำอังกฤษ
                words.append(p)
        return words

    def warm(self) -> None:
        """เริ่มโหลดโมเดลเบื้องหลัง (กดคีย์ลัด = ผู้ใช้กำลังจะพูด ~2–3 วิ ซ่อนเวลาโหลดได้)."""
        if self.available and (not self.running or self.hotwords() != self._hot_used):
            threading.Thread(target=self._warm, daemon=True).start()

    def _warm(self) -> None:
        with self._lock:
            try:
                self._ensure()
            except OSError:
                pass

    def transcribe(self, path: Path, timeout_s: float = DECODE_TIMEOUT_S) -> tuple[str, str]:
        with self._lock:
            self._last_used = time.monotonic()
            try:
                self._ensure()
                if not self._ready.wait(self._load_timeout_s) or not self.running:
                    self._kill()
                    return "", "เปิดตัวถอดเสียงไม่ได้"
                self._next_id += 1
                jid = self._next_id
                self._proc.stdin.write(json.dumps({"id": jid, "wav": str(path)}) + "\n")
                self._proc.stdin.flush()
                deadline = time.monotonic() + timeout_s
                while (left := deadline - time.monotonic()) > 0:
                    try:
                        msg = self._replies.get(timeout=left)
                    except queue.Empty:
                        break
                    if msg is None:  # ตัวถอดตาย
                        self._kill()
                        return "", "ตัวถอดเสียงหยุดทำงาน"
                    if msg.get("id") != jid:  # คำตอบเก่าที่หมดเวลาไปแล้ว
                        continue
                    if "error" in msg:
                        return "", "ถอดเสียงไม่สำเร็จ"
                    return tidy(str(msg.get("text", ""))), ""
                self._kill()  # ค้าง = ปิดทิ้ง ครั้งหน้าเปิดใหม่
                return "", "ถอดเสียงนานเกินไป"
            except (OSError, ValueError):
                self._kill()
                return "", "เปิดตัวถอดเสียงไม่ได้"
            finally:
                self._last_used = time.monotonic()

    def idle_check(self) -> bool:
        """เรียกเป็นระยะ · ไม่ได้ใช้นานเกิน idle_s → ปิดคืน RAM (~329 MB) · คืน True ถ้าปิด."""
        if not self._lock.acquire(blocking=False):  # กำลังถอดอยู่
            return False
        try:
            if self._proc is not None and time.monotonic() - self._last_used > self._idle_s:
                self._kill()
                return True
            return False
        finally:
            self._lock.release()

    def close(self) -> None:
        with self._lock:
            self._kill()

    # ---------- ภายใน (เรียกขณะถือ _lock) ----------
    def _ensure(self) -> None:
        words = self.hotwords()
        if self.running and words == self._hot_used:
            return
        self._kill()  # สกิลเปลี่ยน = เริ่มใหม่พร้อมรายการใหม่ (โหลด ~3.7 วิ · เฉพาะครั้งแรกหลังเปลี่ยน)
        self._hot_used = words
        if self._custom:
            cmd = list(self._worker_cmd)
        else:
            self._dir.mkdir(mode=0o700, exist_ok=True)
            hot = self._dir / "hotwords.txt"
            hot.write_text("\n".join(words) + "\n", encoding="utf-8")
            py = self._base / "venv" / "bin" / "python"
            model = self._base / "model"
            cmd = [str(py), str(WORKER), str(model), str(hot), str(SCORE), str(THREADS)]
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        if not self._custom:
            cmd = sandboxed(cmd, env)
        self._ready = threading.Event()  # ของโปรเซสนี้ (ตัวเก่าที่ตายช้าไม่มาปน)
        self._replies = queue.Queue()
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                      env=env)  # fmt: skip
        args = (self._proc, self._replies, self._ready)
        threading.Thread(target=self._read, args=args, daemon=True).start()

    @staticmethod
    def _read(proc: subprocess.Popen, replies: queue.Queue, ready: threading.Event) -> None:
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("ready"):
                ready.set()
            elif "id" in msg:
                replies.put(msg)
        proc.stdout.close()
        replies.put(None)
        ready.set()  # ตายก่อนพร้อม = ไม่ต้องรอจนหมดเวลา

    def _kill(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            proc.stdin.close()
            proc.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            proc.kill()
            proc.wait()
