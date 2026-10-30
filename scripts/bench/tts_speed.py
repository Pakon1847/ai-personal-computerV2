"""วัดเวลาสร้างเสียงของ TTS ทีละประโยค · 2026-10-30 · ไม่ import aipc (รันด้วย venv ของตัว TTS เอง)

    python tts_speed.py --engine wayu --model D:/tools/wayu-model \
        --voices f_young_clear m_young_clear --sentences tests/data/tts_wayu_sentences.json \
        --out ผล.json --keep โฟลเดอร์เสียง
    python tts_speed.py --engine piper --model /opt/aipc-voice/th_TH-tsync2-medium.onnx \
        --voices piper-th ...

ต่อเสียง: โหลด (จับเวลา) → อุ่นเครื่อง 1 ครั้ง → ทุกประโยค N รอบ: เวลาสร้างทั้งประโยค · ความยาวเสียง ·
RTF = เวลาสร้าง ÷ ความยาวเสียง (< 1 = สร้างเร็วกว่าพูด) · เก็บเสียงรอบแรกไว้ที่ --keep ให้คนฟัง (ไม่ใส่ git)
"""

from __future__ import annotations

import argparse
import io
import json
import platform
import statistics
import sys
import time
import wave
from pathlib import Path


def peak_rss_mb() -> float | None:
    try:
        import resource
    except ImportError:  # Windows
        return None
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


def wayu(model: Path, voice: str):
    from wayu_tts import ThaiTTS

    tts = ThaiTTS.from_pretrained(model, device="cpu")

    def say(text: str, keep: Path | None):
        audio = tts(text, voice=voice, seed=0)
        if keep:
            tts.save(keep, audio)
        return len(audio) / tts.sample_rate

    return say


def piper(model: Path, voice: str):
    from piper import PiperVoice

    pv = PiperVoice.load(str(model))

    def say(text: str, keep: Path | None):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            pv.synthesize_wav(text, w)
        buf.seek(0)
        with wave.open(buf, "rb") as r:
            seconds = r.getnframes() / r.getframerate()
        if keep:
            keep.write_bytes(buf.getvalue())
        return seconds

    return say


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=("wayu", "piper"), required=True)
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--voices", nargs="+", required=True)
    ap.add_argument("--sentences", type=Path, required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--keep", type=Path)
    a = ap.parse_args()
    items = json.loads(a.sentences.read_text(encoding="utf-8"))["items"]
    res = {"engine": a.engine, "model": str(a.model), "runs": a.runs,
           "machine": platform.platform(), "python": sys.version.split()[0],
           "voices": {}}  # fmt: skip
    for voice in a.voices:
        t0 = time.monotonic()
        say = (wayu if a.engine == "wayu" else piper)(a.model, voice)
        load_s = time.monotonic() - t0
        # อุ่นเครื่องทั้งไทยและอังกฤษ: ตัวแปลงอังกฤษ (misaki + spaCy) โหลดครั้งแรกที่เจออักษรละติน ~30 วิ
        say("สวัสดีครับ เปิด YouTube", None)
        rows = []
        for it in items:
            times, audio_s = [], 0.0
            for i in range(a.runs):
                keep = None
                if a.keep and i == 0:
                    a.keep.mkdir(parents=True, exist_ok=True)
                    keep = a.keep / f"{a.engine}-{voice}-{it['id']}.wav"
                t = time.monotonic()
                audio_s = say(it["text"], keep)
                times.append(time.monotonic() - t)
            med = statistics.median(times)
            rtf = round(med / audio_s, 3) if audio_s else None
            rows.append({"id": it["id"], "kind": it["kind"], "chars": len(it["text"]),
                         "synth_s": round(med, 3), "synth_all": [round(x, 3) for x in times],
                         "audio_s": round(audio_s, 2), "rtf": rtf})  # fmt: skip
            print(
                f"{voice} {it['id']} {len(it['text']):4d} ตัวอักษร · สร้าง {med:6.2f} วิ · "
                f"เสียง {audio_s:6.2f} วิ · RTF {rtf}",
                flush=True,
            )
        res["voices"][voice] = {
            "load_s": round(load_s, 2),
            "peak_rss_mb": peak_rss_mb(),
            "rows": rows,
        }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
