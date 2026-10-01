"""รอบ 2: เสียงคนพูดแทรก (ห้องสอบ) · rnnoise · VAD (docs/benchmarks/2026-10-01-voice-noise) · รันบน Pi ด้วย venv ของ ~/voice-bench.

    ~/voice-bench/venv/bin/python scripts/pi/measure-voice-noise2.py sentences.json /tmp/noise2.json
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import wave

import numpy as np

spec = importlib.util.spec_from_file_location("r1", os.path.join(os.path.dirname(__file__), "measure-voice-noise.py"))
r1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r1)

D = r1.D
RNN = f"{D}/rnnoise-sh.rnnn"
VAD = f"{D}/ggml-silero-v6.2.0.bin"
CONDS = (("clean", None), ("babble", 5.0), ("room", 5.0), ("babble", 20.0), ("room", 20.0))
METHODS = {"none": (None, False), "hp100": ("highpass=f=100", False), "rnnoise": (f"arnndn=m={RNN}", False),
           "vad": (None, True), "hp100+rnnoise+vad": (f"highpass=f=100,arnndn=m={RNN}", True)}  # fmt: skip


def transcribe(path: str, vad: bool) -> tuple[str, float]:
    args = [f"{D}/whisper.cpp/build/bin/whisper-cli", "-m", r1.MODEL, "-l", "th", "-t", "4", "-nt", "-ac", "512"]
    if vad:
        args += ["--vad", "-vm", VAD]
    t0 = time.monotonic()
    r = subprocess.run([*args, "-f", path], capture_output=True, text=True)
    return r.stdout.strip(), round(time.monotonic() - t0, 2)


def main() -> int:
    from piper import PiperVoice

    sents = json.load(open(sys.argv[1], encoding="utf-8"))[::2]  # 22 ประโยค (ทุกข้อที่สอง)
    voice = PiperVoice.load(f"{D}/th_TH-tsync2-medium.onnx")
    rng = np.random.default_rng(20261002)
    tmp = tempfile.mkdtemp(prefix="vn2-")

    def synth(text: str, name: str) -> np.ndarray:
        raw = f"{tmp}/{name}-22k.wav"
        with wave.open(raw, "wb") as w:
            voice.synthesize_wav(text, w)
        out = f"{tmp}/{name}.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-ar", str(r1.SR), "-ac", "1", out], check=True)
        return r1.read16(out)

    rows = []
    for i, s in enumerate(sents):
        pad = np.zeros(int(0.3 * r1.SR))
        speech = np.concatenate([pad, synth(s["text"], f"s{i}"), pad])
        p_speech = np.mean(speech[speech != 0] ** 2)
        # เสียงคนอื่น: ประโยคอื่น 2 ประโยคซ้อนกัน วนให้ยาวเท่าเสียงหลัก
        others = [sents[(i + k) % len(sents)]["text"] for k in (5, 11)]
        babble = np.zeros(len(speech))
        for k, t in enumerate(others):
            b = synth(t, f"b{i}-{k}")
            b = np.tile(b, len(speech) // len(b) + 1)[k * 2000 : k * 2000 + len(speech)]
            babble += b / (np.sqrt(np.mean(b**2)) or 1)
        babble /= np.sqrt(np.mean(babble**2)) or 1
        for cond, snr in CONDS:
            x = speech.copy()
            if cond != "clean":
                n = babble if cond == "babble" else (babble + r1.noise("brown", len(x), rng)) / np.sqrt(2)
                x = x + n * np.sqrt(p_speech / 10 ** (snr / 10))
            tag = cond if snr is None else f"{cond}{int(snr)}"
            mixed = f"{tmp}/{i}-{tag}.wav"
            r1.write16(mixed, x)
            for name, (flt, vad) in METHODS.items():
                path = mixed
                if flt:
                    path = f"{tmp}/{i}-{tag}-{name}.wav"
                    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mixed, "-af", flt, path], check=True)
                heard, secs = transcribe(path, vad)
                rows.append({"i": i, "text": s["text"], "noise": tag, "filter": name, "heard": heard,
                             "seconds": secs})  # fmt: skip
        print(f"{i + 1}/{len(sents)} {s['text']}", flush=True)
    json.dump({"model": os.path.basename(r1.MODEL), "rows": rows}, open(sys.argv[2], "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
