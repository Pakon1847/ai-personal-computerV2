"""วัดตัวจับจุดจบ (aipc.voice.stt.Endpointer) กับไฟล์เสียง · การ์ด 0019 ข้อ 10.

    python -m aipc.spikes.endpoint_eval <โฟลเดอร์ที่มี meta.json> [--out ผล.json]

ใส่เสียงรบกวนแบบเดียวกับการทดลองเสียงรบกวน (brown / babble) แล้วป้อนทีละ 100 ms เหมือนอ่านจากไมค์
"""

from __future__ import annotations

import argparse
import json
import sys
import wave
from pathlib import Path

import numpy as np

from aipc.voice.stt import Endpointer

SR = 16000


def load(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64)


def brown(n: int, rng) -> np.ndarray:
    x = np.cumsum(rng.standard_normal(n))
    x -= np.convolve(x, np.ones(800) / 800, mode="same")
    return x / (np.sqrt(np.mean(x**2)) or 1)


def run(x: np.ndarray) -> tuple[str, float]:
    ep = Endpointer()
    pcm = np.clip(x, -32768, 32767).astype(np.int16).tobytes()
    step = SR // 10 * 2  # 100 ms
    for i in range(0, len(pcm), step):
        if (r := ep.feed(pcm[i : i + step])) is not None:
            return r, ep.frames * ep.frame_s
    return "eof", ep.frames * ep.frame_s


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.spikes.endpoint_eval")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    meta = json.loads((a.folder / "meta.json").read_text(encoding="utf-8"))
    rng = np.random.default_rng(20261001)
    babble_src = [load(a.folder / m["file"]) for m in meta if m["kind"] == "single"]
    rows = []
    for m in meta:
        speech = load(a.folder / m["file"])
        start, end = int(m["speech_start"] * SR), int(m["speech_end"] * SR)
        p = np.mean(speech[start:end] ** 2)
        for cond, snr in (
            ("clean", None),
            ("brown", 20),
            ("babble", 20),
            ("brown", 5),
            ("babble", 5),
        ):
            x = speech.copy()
            if snr is not None:
                if cond == "brown":
                    n = brown(len(x), rng)
                else:  # คนอื่นพูดต่อเนื่องตลอดไฟล์ (ประโยคอื่นต่อกัน)
                    n = np.concatenate(rng.permutation(np.array(babble_src, dtype=object)).tolist())
                    n = np.tile(n, len(x) // len(n) + 1)[: len(x)]
                    n = n / (np.sqrt(np.mean(n**2)) or 1)
                x = x + n * np.sqrt(p / 10 ** (snr / 10))
            result, t = run(x)
            tag = cond if snr is None else f"{cond}{snr}"
            rows.append({"file": m["file"], "kind": m["kind"], "noise": tag, "result": result,
                         "stop_s": round(t, 2),
                         "after_end_s": round(t - m["speech_end"], 2)})  # fmt: skip
    summary = {}
    for tag in dict.fromkeys(r["noise"] for r in rows):
        sel = [r for r in rows if r["noise"] == tag]
        ok = [r for r in sel if r["result"] == "end" and 0 <= r["after_end_s"] <= 1.5]
        cut = [r for r in sel if r["after_end_s"] < 0]
        lat = sorted(
            r["after_end_s"] for r in sel if r["result"] == "end" and r["after_end_s"] >= 0
        )
        summary[tag] = {"n": len(sel), "stop_within_1_5s": len(ok), "cut_early": len(cut),
                        "cut_early_pairs": sum(r["kind"] == "pair" for r in cut),
                        "results": {k: sum(r["result"] == k for r in sel)
                                    for k in ("end", "no_speech", "max", "eof")},
                        "after_end_median": lat[len(lat) // 2] if lat else None}  # fmt: skip
        print(tag, summary[tag])
    if a.out:
        doc = json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1)
        a.out.write_text(doc,
                         encoding="utf-8", newline="\n")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
