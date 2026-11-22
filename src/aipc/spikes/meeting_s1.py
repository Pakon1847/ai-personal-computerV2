"""การ์ด 0082 S1: ถอดเสียงไทยยาว ๆ ได้แม่นและเร็วพอไหม (วัดก่อนสร้าง · ตัดสินไปต่อหรือหยุด).

รันบน Pi 5 ด้วยเสียงจริงที่อัดผ่านไมค์ของเครื่อง · ห้าม commit เสียงของคน (กฎเหล็กข้อ 4):
    python -m aipc.spikes.meeting_s1 run --audio เสียง.wav --ref เฉลย.txt --label A-1m --out ผล.json

เสียงต้องเป็น 16 kHz · 16 bit · mono (อัดด้วย pw-record --rate 16000 --channels 1 --format s16)
ตัดเสียงเป็นท่อน ≤ 30 วิ ที่ช่วงเงียบ แล้วถอดทีละท่อนด้วย whisper-cli และโมเดลตัวเดียวกับแอป
CER = จำนวนตัวอักษรที่ผิดเมื่อเทียบเฉลย ÷ จำนวนตัวอักษรในเฉลย · เทียบเฉพาะตัวอักษรไทย
"""

from __future__ import annotations

import argparse
import array
import json
import re
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

from aipc.voice import stt

RATE = 16000
MAX_CHUNK_S = 30
FRAME_S = 0.02
SILENCE_S = 0.3
THAI = re.compile(r"[ก-ฺเ-๎]")


def only_thai(text: str) -> str:
    """เหลือเฉพาะตัวอักษรไทย: ไม่นับช่องว่าง เครื่องหมาย ตัวเลข และภาษาอื่น."""
    return "".join(THAI.findall(text))


def edit_distance(a: str, b: str) -> int:
    """ระยะแก้ไขแบบเก็บแถวเดียว (ความจำตามความยาวเฉลย)."""
    if len(a) < len(b):
        a, b = b, a
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        prev, row[0] = row[0], i
        for j, cb in enumerate(b, start=1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (ca != cb))
    return row[-1]


def cer(reference: str, heard: str) -> float:
    ref, got = only_thai(reference), only_thai(heard)
    if not ref:
        raise ValueError("เฉลยไม่มีตัวอักษรไทย")
    return edit_distance(ref, got) / len(ref)


def frame_levels(samples: array.array) -> list[float]:
    size = int(RATE * FRAME_S)
    out = []
    for i in range(0, len(samples) - size + 1, size):
        frame = samples[i : i + size]
        out.append(sum(abs(x) for x in frame) / size)
    return out


def split_points(levels: list[float]) -> list[tuple[int, int]]:
    """ท่อน (เริ่ม, จบ) หน่วยเฟรม · ตัดที่ช่วงเงียบ · ยาวไม่เกิน MAX_CHUNK_S · ตัดช่วงเงียบล้วนทิ้ง."""
    if not levels:
        return []
    ordered = sorted(levels)
    # ระดับเสียงรบกวนของไฟล์นี้ · ไม่เกินครึ่งของเสียงพูด (พูดต่อเนื่องจนแทบไม่มีช่วงเงียบก็ยังแยกได้)
    quiet = max(50, min(ordered[len(levels) // 10] * 3 + 50, ordered[len(levels) // 2] / 2))
    max_frames = int(MAX_CHUNK_S / FRAME_S)
    need = int(SILENCE_S / FRAME_S)
    out, start, silent, voiced = [], 0, 0, False
    for i, level in enumerate(levels):
        if level < quiet:
            silent += 1
        else:
            silent, voiced = 0, True
        length = i - start + 1
        if (silent >= need and voiced) or length >= max_frames:
            if voiced:
                out.append((start, i + 1))
            start, silent, voiced = i + 1, 0, False
        elif silent >= need and not voiced:
            start, silent = i + 1, 0
    if voiced:
        out.append((start, len(levels)))
    return out


def read_wav(path: Path) -> array.array:
    with wave.open(str(path), "rb") as w:
        if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (RATE, 1, 2):
            raise ValueError("ต้องเป็น 16 kHz · 16 bit · mono")
        data = array.array("h")
        data.frombytes(w.readframes(w.getnframes()))
    return data


def write_wav(path: Path, samples: array.array) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(samples.tobytes())


def transcribe(path: Path, threads: int) -> str:
    """ค่าเดียวกับเสียงกดค้างของแอป (โมเดล Thonburian distill-small · -ac 512)."""
    cmd = [str(stt.VOICE_DIR / stt.WHISPER), "-m", str(stt.VOICE_DIR / stt.MODEL), "-l", "th",
           "-t", str(threads), "-nt", "-ac", "512", "-f", str(path)]  # fmt: skip
    done = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=600)
    if done.returncode != 0:
        raise RuntimeError(done.stderr[-300:])
    return stt.clean(done.stdout)


def rss_mb() -> float:
    try:
        text = Path("/proc/self/status").read_text()
    except OSError:
        return 0.0
    return int(re.search(r"VmHWM:\s+(\d+)", text).group(1)) / 1024


def cmd_run(a) -> int:
    samples = read_wav(Path(a.audio))
    reference = Path(a.ref).read_text(encoding="utf-8")
    audio_s = len(samples) / RATE
    size = int(RATE * FRAME_S)
    spans = split_points(frame_levels(samples))
    parts, seconds = [], []
    with tempfile.TemporaryDirectory(prefix="aipc-s1-") as tmp:
        for n, (start, end) in enumerate(spans, start=1):
            path = Path(tmp) / f"{n}.wav"
            write_wav(path, samples[start * size : end * size])
            t0 = time.monotonic()
            parts.append(transcribe(path, a.threads))
            seconds.append(round(time.monotonic() - t0, 2))
            print(f"{n}/{len(spans)} · {seconds[-1]} วิ", flush=True)
    heard = "\n".join(parts)
    result = {
        "label": a.label, "audio_s": round(audio_s, 1), "chunks": len(spans),
        "decode_s": round(sum(seconds), 1), "ratio": round(sum(seconds) / audio_s, 3),
        "cer": round(cer(reference, heard), 4), "ref_chars": len(only_thai(reference)),
        "heard_chars": len(only_thai(heard)), "threads": a.threads, "seconds": seconds,
    }  # fmt: skip
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.save_text:  # บทถอดอาจมีข้อมูลของคนอื่น เก็บเมื่อสั่งเท่านั้น และห้าม commit
        Path(a.save_text).write_text(heard, encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "seconds"}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m aipc.spikes.meeting_s1")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--audio", required=True)
    r.add_argument("--ref", required=True)
    r.add_argument("--label", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--threads", type=int, default=4)  # เท่าแอป (stt.py)
    r.add_argument("--save-text", default="")
    r.set_defaults(fn=cmd_run)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
