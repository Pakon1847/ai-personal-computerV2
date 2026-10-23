"""การ์ด 0044: เวลาจาก "พูดจบ" ถึง "ได้ข้อความ" ของคีย์ลัด (ทางเดียวกับแอปทุกขั้น) · บน Pi 5.

    python -m aipc.spikes.voice_e2e_latency tests/data/voice_latency_dev.json --out ผล.json

ทุกประโยค: Piper พูด (เสียงสังเคราะห์) → แปลง 16 kHz → ตัวส่งเสียงปลอมเขียน WAV ทีละ 0.1 วิตามเวลาจริง
(เสียงพื้นหลังเบา 0.4 วิ · คำพูด (หลายท่อนเว้น pause_s) · เงียบ 3 วิ) แทน pw-record → aipc.voice.stt.Listener
ตัวจริงของแอป (Endpointer · Zipformer · ทางลองอังกฤษ · callbacks ของ backend) → วัดเวลาที่ on_done ถูกเรียก
ลบด้วยเวลาที่คำพูดจบในสายเสียง · เสียงสังเคราะห์ไม่ใช่เสียงคน (ดูเวลา + การตัดกลางประโยค ไม่ใช่ความแม่นของคน)

การ์ด 0056: --babble 15 = มีคนพูด (ประโยคอื่นของชุด) เบากว่าเรา 15 dB ตลอดสาย และต่อหลังพูดจบ 16 วิ ·
--lead 0 = พูดทันทีไม่มีช่วงเงียบนำ (ประโยคแรกยังมี 0.4 วิ ให้ Listener จำระดับเสียงรอบข้าง แล้วส่งต่อประโยคถัดไป)
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path

from aipc.voice import stt, tts, zipformer

SYNTH = r"""
import sys, wave, json
from piper import PiperVoice
v = PiperVoice.load(sys.argv[1])
for i, text in enumerate(json.load(open(sys.argv[2], encoding="utf-8"))):
    with wave.open(f"{sys.argv[3]}/{i:03d}.wav", "wb") as w:
        v.synthesize_wav(text, w)
"""
# ตัวส่งเสียงปลอม: argv = ไฟล์ปลายทาง, ไฟล์ PCM ต้นทาง, ไฟล์บันทึกเวลาเริ่ม · เขียนหัว WAV แล้วเขียนทีละ 0.1 วิ
STREAMER = r"""
import signal, struct, sys, time
dst, src, stamp = sys.argv[1], sys.argv[2], sys.argv[3]
pcm = open(src, "rb").read()
f = open(dst, "wb")
fmt = struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16)
f.write(b"RIFF" + struct.pack("<I", 0) + b"WAVEfmt " + fmt + b"data" + struct.pack("<I", 0))
f.flush()
def finish(*_):  # เหมือน pw-record: หยุด (SIGINT) = เขียนขนาดในหัว WAV ให้ครบแล้วออก
    n = f.tell() - 44
    f.seek(4); f.write(struct.pack("<I", 36 + n)); f.seek(40); f.write(struct.pack("<I", n))
    f.close(); sys.exit(0)
signal.signal(signal.SIGINT, finish)
signal.signal(signal.SIGTERM, finish)
open(stamp, "w").write(repr(time.time()))
step = 3200
t0 = time.time()
for k in range(0, len(pcm), step):
    f.write(pcm[k:k + step]); f.flush()
    time.sleep(max(0.0, t0 + (k // step + 1) * 0.1 - time.time()))
time.sleep(30)
"""
NOISE_S, TAIL_S = 0.4, 3.0
THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def noise(seconds: float) -> bytes:
    import random
    import struct

    rnd = random.Random(7)
    return b"".join(struct.pack("<h", rnd.randint(-30, 30)) for _ in range(int(16000 * seconds)))


def mix(stream: bytes, others: bytes, speech: bytes, db: float) -> bytes:
    """ซ้อนเสียงคนอื่นพูด (others วนซ้ำ) ให้เบากว่าเสียงพูดของเรา db dB ตลอดสาย (การ์ด 0056)."""
    import array

    s, o, v = array.array("h"), array.array("h"), array.array("h")
    s.frombytes(stream)
    o.frombytes(others)
    v.frombytes(speech)

    def rms(a):
        return (sum(x * x for x in a) / max(1, len(a))) ** 0.5

    gain = rms(v) / (rms(o) or 1) * 10 ** (-db / 20)
    out = array.array("h", (max(-32768, min(32767, int(x + gain * o[i % len(o)])))
                            for i, x in enumerate(s)))  # fmt: skip
    return out.tobytes()


def pcm16k(path: Path, work: Path) -> bytes:
    out = work / (path.stem + "-16k.wav")
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", str(path), "-ar", "16000", "-ac", "1"]
    subprocess.run([*cmd, "-sample_fmt", "s16", str(out)], check=True)
    with wave.open(str(out)) as w:
        return trim(w.readframes(w.getnframes()))


def trim(pcm: bytes, level: int = 300) -> bytes:
    """ตัดความเงียบหัว-ท้ายที่ Piper ใส่มา (ไม่งั้นช่วงเว้นระหว่างท่อนยาวกว่า pause_s ที่ตั้งไว้)."""
    import array

    a = array.array("h")
    a.frombytes(pcm)
    loud = [i for i, x in enumerate(a) if abs(x) > level]
    if not loud:
        return pcm
    pad = 800  # เผื่อ 50 ms ไม่ให้หางเสียงขาด
    lo, hi = max(0, loud[0] - pad), min(len(a), loud[-1] + pad)
    return a[lo:hi].tobytes()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--babble", type=float)
    ap.add_argument("--lead", type=float, default=NOISE_S)
    a = ap.parse_args(argv)
    from aipc.ui import backend

    data = json.loads(a.dataset.read_text(encoding="utf-8"))
    items, pause = data["items"], float(data.get("pause_s", 0.45))
    work = Path(tempfile.mkdtemp(prefix="lat-"))
    py = stt.VOICE_DIR / "venv" / "bin" / "python"
    audio = []
    for voice, model in (("th", tts.MODEL), ("en", tts.EN_MODEL)):  # สังเคราะห์แยกตามภาษา
        parts = [p for it in items if it.get("voice", "th") == voice for p in it["parts"]]
        if not parts:
            continue
        d = work / voice
        d.mkdir()
        (d / "texts.json").write_text(json.dumps(parts, ensure_ascii=False), encoding="utf-8")
        subprocess.run([str(py), "-c", SYNTH, str(stt.VOICE_DIR / model), str(d / "texts.json"),
                        str(d)], check=True)  # fmt: skip
        pcm = iter(
            [pcm16k(d / f"{i:03d}.wav", d) for i in range(len(parts))]
        )  # สร้างเลย (ตัวแปร d เปลี่ยนในรอบถัดไป)
        audio.append((voice, pcm))
    by_voice = dict(audio)
    (work / "streamer.py").write_text(STREAMER, encoding="utf-8")

    fast = zipformer.Transcriber(extra_hotwords=None)
    fast.warm()
    fast.transcribe(Path("/nonexistent.wav"))  # รอโหลดเสร็จ (ไฟล์ไม่มี = error แต่โมเดลพร้อมแล้ว)
    rows = []
    speeches = []
    for it in items:
        chunks = [next(by_voice[it.get("voice", "th")]) for _ in it["parts"]]
        speeches.append((b"\x00\x00" * int(16000 * pause)).join(chunks))
    floor = None
    for k, (it, speech) in enumerate(zip(items, speeches, strict=True)):
        lead = NOISE_S if k == 0 else a.lead
        stream = noise(lead) + speech + noise(TAIL_S if a.babble is None else 16.0)
        if a.babble is not None:
            others = b"".join(speeches[k + 1 :] + speeches[:k])
            stream = mix(stream, others, speech, a.babble)
        src = work / "stream.pcm"
        src.write_bytes(stream)
        stamp = work / "stamp.txt"
        stamp.unlink(missing_ok=True)
        done = threading.Event()
        got: dict = {}

        def on_done(text, err, secs, got=got, done=done):
            got.update(text=text, err=err, at=time.time())
            done.set()

        lis = stt.Listener(on_done, record_cmd=[sys.executable, str(work / "streamer.py")],
                           fast=fast, try_english=backend._thai_missed,
                           use_english=backend._english_command,
                           **getattr(backend, "listener_extras", dict)())  # fmt: skip
        # ตัวส่งเสียงต้องได้ไฟล์ต้นทาง + ไฟล์เวลา (Listener ต่อท้ายด้วยไฟล์ปลายทาง → สลับลำดับในสคริปต์)
        lis._record_cmd = [sys.executable, "-c",
                           "import sys,runpy; sys.argv=[sys.argv[0], sys.argv[1], "
                           f"{str(src)!r}, {str(stamp)!r}]; "
                           f"runpy.run_path({str(work / 'streamer.py')!r}, "
                           "run_name='__main__')"]  # fmt: skip
        lis._noise_floor = floor  # Listener ตัวเดียวในแอปจำค่านี้ข้ามครั้ง (ตัววัดสร้างใหม่ทุกประโยค)
        err = lis.start(fast=True)
        if err:
            print("เริ่มไม่ได้:", err)
            return 1
        done.wait(25)
        lis.cancel()
        floor = getattr(lis, "_noise_floor", None)
        t_start = float(stamp.read_text()) if stamp.exists() else float("nan")
        end_of_speech = t_start + lead + len(speech) / 32000
        latency = round(got.get("at", float("nan")) - end_of_speech, 3)
        text = got.get("text", "")
        norm = text.replace(" ", "").lower().translate(THAI_DIGITS)
        must = it.get("must", "").lower().replace(" ", "")
        cut = bool(must) and must not in norm
        rows.append({"said": " / ".join(it["parts"]), "kind": it["kind"], "heard": text,
                     "err": got.get("err", "timeout"), "latency_s": latency,
                     "cut": cut})  # fmt: skip
        print(f"{latency:5.2f}s {'✂ ' if cut else ''}{rows[-1]['said']} → «{text}»", flush=True)
    fast.close()

    def med(kind):
        xs = [
            r["latency_s"] for r in rows if r["kind"] == kind and r["latency_s"] == r["latency_s"]
        ]
        return round(statistics.median(xs), 3) if xs else None

    summary = {"command_median_s": med("command"), "question_median_s": med("question"),
               "english_median_s": med("english"),
               "english_ok": sum(not r["cut"] for r in rows if r["kind"] == "english"),
               "english_n": sum(r["kind"] == "english" for r in rows),
               "cut": sum(r["cut"] for r in rows if r["kind"] != "english"),
               "with_pause": sum(len(it["parts"]) > 1 for it in items),
               "n": len(rows)}  # fmt: skip
    a.out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
                     encoding="utf-8")  # fmt: skip
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
