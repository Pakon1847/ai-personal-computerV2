"""เสียงสำหรับวัดตัวจับจุดจบ (การ์ด 0019 ข้อ 10) · รันบน Pi ด้วย venv ของ ~/voice-bench.

    ~/voice-bench/venv/bin/python make-endpoint-audio.py sentences.json outdir/

เขียน single-NN.wav (ประโยคเดียว) และ pair-NN.wav (สองประโยค เว้นกลาง 0.5 วิ) · 16 kHz mono ·
meta.json บอกจุดเริ่ม/จบเสียงพูด
ทุกไฟล์มีเงียบนำ 0.5 วิ และเงียบท้าย 3 วิ (ให้ตัวจับจุดจบมีที่หยุด)
"""

import json
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np
from piper import PiperVoice

SR = 16000
D = os.path.expanduser("~/voice-bench")


def main() -> int:
    sents = [s["text"] for s in json.load(open(sys.argv[1], encoding="utf-8"))][::2]
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    voice = PiperVoice.load(f"{D}/th_TH-tsync2-medium.onnx")
    tmp = tempfile.mkdtemp()

    def synth(text: str) -> np.ndarray:
        raw, w16 = f"{tmp}/a.wav", f"{tmp}/b.wav"
        with wave.open(raw, "wb") as w:
            voice.synthesize_wav(text, w)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-ar", str(SR), "-ac", "1", w16],
            check=True,
        )
        with wave.open(w16) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        # ตัดเงียบหัวท้ายที่ Piper ใส่มา ให้รู้จุดจบเสียงพูดแม่น
        idx = np.nonzero(np.abs(x) > 500)[0]
        return x[idx[0] : idx[-1] + 1] if len(idx) else x

    meta = []
    lead, tail, gap = (
        np.zeros(SR // 2, np.int16),
        np.zeros(3 * SR, np.int16),
        np.zeros(SR // 2, np.int16),
    )
    for i, text in enumerate(sents):
        a = synth(text)
        b = synth(sents[(i + 1) % len(sents)])
        for kind, body in (("single", a), ("pair", np.concatenate([a, gap, b]))):
            x = np.concatenate([lead, body, tail])
            name = f"{kind}-{i:02d}.wav"
            with wave.open(os.path.join(out, name), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SR)
                w.writeframes(x.tobytes())
            meta.append({"file": name, "kind": kind, "speech_start": len(lead) / SR,
                         "speech_end": (len(lead) + len(body)) / SR})  # fmt: skip
    json.dump(
        meta,
        open(os.path.join(out, "meta.json"), "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )
    print(len(meta), "files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
