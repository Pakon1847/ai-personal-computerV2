"""ตัดเสียงทุ้มก่อนถอดเสียง ช่วยกันเสียงรอบข้างไหม (docs/benchmarks/2026-10-01-voice-noise) · รันบน Pi ด้วย venv ของ ~/voice-bench.

    ~/voice-bench/venv/bin/python scripts/pi/measure-voice-noise.py sentences.json /tmp/noise.json

sentences.json = [{"text": ...}, ...] · เขียนผลการถอดทุกแบบลงไฟล์ · การให้คะแนน (ตัวแปลคำสั่ง) ทำบนเครื่องที่มีแอป
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import wave

import numpy as np
from piper import PiperVoice

D = os.path.expanduser("~/voice-bench")
MODEL = f"{D}/thonburian-distill-small-f16.bin"
SR = 16000
SNR_DB = 5.0
FILTERS = {"none": None, "hp100": "highpass=f=100", "hp200": "highpass=f=200", "hp300": "highpass=f=300",
           "afftdn": "afftdn"}  # fmt: skip


def noise(kind: str, n: int, rng) -> np.ndarray:
    if kind == "brown":  # พลังงานลดลงตามความถี่ 1/f² · ทุ้มเหมือนพัดลม/แอร์/รถ
        x = np.cumsum(rng.standard_normal(n))
        x -= np.convolve(x, np.ones(800) / 800, mode="same")  # ตัดการลอย (DC) ออก
    elif kind == "pink":  # 1/f · กว้างทุกความถี่
        f = np.fft.rfftfreq(n, 1 / SR)
        spec = rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))
        spec[1:] /= np.sqrt(f[1:])
        spec[0] = 0
        x = np.fft.irfft(spec, n)
    elif kind == "hum":  # ไฟหึ่ง 50 Hz + ฮาร์มอนิก
        t = np.arange(n) / SR
        x = sum(a * np.sin(2 * np.pi * 50 * k * t) for k, a in ((1, 1.0), (2, 0.5), (3, 0.3), (4, 0.15)))
    else:
        raise ValueError(kind)
    return x / (np.sqrt(np.mean(x**2)) or 1)


def read16(path: str) -> np.ndarray:
    with wave.open(path) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64)


def write16(path: str, x: np.ndarray) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.clip(x, -32768, 32767).astype(np.int16).tobytes())


def transcribe(path: str) -> tuple[str, float]:
    t0 = time.monotonic()
    r = subprocess.run([f"{D}/whisper.cpp/build/bin/whisper-cli", "-m", MODEL, "-l", "th", "-t", "4", "-nt",
                        "-ac", "512", "-f", path], capture_output=True, text=True)  # fmt: skip
    return r.stdout.strip(), round(time.monotonic() - t0, 2)


def main() -> int:
    sents = json.load(open(sys.argv[1], encoding="utf-8"))[::2]  # 22 ประโยค (Pi ร้อนจนช้า · ดูหมายเหตุใน README)
    voice = PiperVoice.load(f"{D}/th_TH-tsync2-medium.onnx")
    rng = np.random.default_rng(20261001)
    rows = []
    tmp = tempfile.mkdtemp(prefix="vn-")
    for i, s in enumerate(sents):
        raw = f"{tmp}/{i}-22k.wav"
        with wave.open(raw, "wb") as w:
            voice.synthesize_wav(s["text"], w)
        clean = f"{tmp}/{i}.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-ar", str(SR), "-ac", "1", clean], check=True)
        speech = read16(clean)
        # เว้นเงียบหัวท้าย 0.3 วิ (มีแต่เสียงรบกวน เหมือนกดปุ่มก่อนพูด)
        pad = np.zeros(int(0.3 * SR))
        speech = np.concatenate([pad, speech, pad])
        p_speech = np.mean(speech[speech != 0] ** 2)
        for cond in ("clean", "brown", "hum", "pink"):
            x = speech.copy()
            if cond != "clean":
                x = x + noise(cond, len(x), rng) * np.sqrt(p_speech / 10 ** (SNR_DB / 10))
            mixed = f"{tmp}/{i}-{cond}.wav"
            write16(mixed, x)
            for name, flt in FILTERS.items():
                path = mixed
                if flt:
                    path = f"{tmp}/{i}-{cond}-{name}.wav"
                    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mixed, "-af", flt, path], check=True)
                heard, secs = transcribe(path)
                rows.append({"i": i, "text": s["text"], "noise": cond, "filter": name, "heard": heard, "seconds": secs})
        print(f"{i + 1}/{len(sents)} {s['text']}", flush=True)
    json.dump({"snr_db": SNR_DB, "model": os.path.basename(MODEL), "rows": rows},
              open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
