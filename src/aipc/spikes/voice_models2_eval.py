"""การ์ด 0026 รอบ 2: เทียบตัวถอดเสียงไทยหลายตัว.

Pakon 2026-10-14 บ่าย: "หา model ที่เหมาะกับ Pi · เทสใน notebook ก่อน"

ขั้น 1 สร้างเสียง (Piper เสียงเดียวกับบน Pi · ไฟล์เสียงอยู่นอก git):

    <python ที่มี piper> -m aipc.spikes.voice_models2_eval synth <เสียง> <Piper .onnx> v1 v2 d h2

ขั้น 2 ถอด + ตัดสิน (python ที่มี sherpa-onnx · PYTHONPATH=src):

    python -m aipc.spikes.voice_models2_eval run <เสียง> <โมเดล> --sets v1 v2 d
        --models zip-hw5 ty-free --out ผล.json

ชุด: v1 v2 = tests/data/browse_v1/v2 (ชุดพัฒนาเดิม) ·
d = ชุด D (พัฒนา · ประโยค task ใน voice_d_synth.json) ·
h2 = ชุดทดสอบใหม่ voice_h2_synth.json (เขียนโดยผู้ช่วยอีกตัวที่ไม่เห็นตัวแปลและผลเดิม · ล็อกก่อนรัน) ·
ข้อความที่ถอดได้ผ่าน zipformer.tidy + browse.parse แบบเดียวกับแอป · ตัดสินด้วย voice_h_eval.judge
เวลาที่วัดบนโน้ตบุ๊ก = ใช้คัดกรองเท่านั้น (ตัวเลขความเร็วต้องมาจาก Pi 5 · H9)
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tests/data"


def load_set(name: str) -> list[dict]:
    """[{id, text, expect}] ตามลำดับ."""
    if name in ("v1", "v2"):
        items = json.loads((DATA / f"browse_{name}.json").read_text(encoding="utf-8"))["items"]
        return [
            {"id": f"{name}-{i:02d}", "text": it["text"], "expect": it["expect"]}
            for i, it in enumerate(items)
        ]
    if name == "d":
        said = json.loads((DATA / "voice_d_synth.json").read_text(encoding="utf-8"))["said"]
        prompts = json.loads((DATA / "voice_real_prompts.json").read_text(encoding="utf-8"))[
            "items"
        ]
        return [
            {
                "id": it["id"],
                "text": it["prompt"] if it["mode"] == "say" else said[it["id"]],
                "expect": it["expect"],
            }
            for it in prompts
            if it["set"] == "D"
        ]
    if name == "h2":
        items = json.loads((DATA / "voice_h2_synth.json").read_text(encoding="utf-8"))["items"]
        return [{"id": it["id"], "text": it["text"], "expect": it["expect"]} for it in items]
    raise ValueError(name)


# ---------- ขั้น 1: สร้างเสียง ----------
def synth(audio: Path, voice: str, sets: list[str]) -> None:
    import wave

    from piper import PiperVoice

    v = PiperVoice.load(voice)
    for name in sets:
        out = audio / name
        out.mkdir(parents=True, exist_ok=True)
        for it in load_set(name):
            raw, wav = out / f"{it['id']}.raw.wav", out / f"{it['id']}.wav"
            if wav.exists():
                continue
            with wave.open(str(raw), "wb") as w:
                v.synthesize_wav(it["text"], w)
            # 16 kHz mono ด้วย ffmpeg (วิธีเดียวกับชุดบน Pi)
            subprocess.run(
                [
                    "ffmpeg",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(raw),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(wav),
                ],
                check=True,
            )
            raw.unlink()
        print(f"{name}: {len(load_set(name))} ไฟล์", flush=True)


# ---------- ขั้น 2: ถอด ----------
def read(path: Path) -> list[float]:
    import array
    import wave

    with wave.open(str(path)) as w:
        a = array.array("h", w.readframes(w.getnframes()))
    return [x / 32768.0 for x in a]


def recognizer(spec: str, models: Path, threads: int):
    """spec: zip-free · zip-hw<น้ำหนัก> · ty-free · ty-hw<น้ำหนัก>.

    ty = Typhoon ASR Realtime แบบ NeMo transducer."""
    import sherpa_onnx

    from aipc.voice.zipformer import HOTWORDS

    fam, mode = spec.split("-", 1)
    kw: dict = {}
    if mode.startswith("hw"):
        hw = models / f"hotwords-{fam}.txt"
        hw.write_text("\n".join(HOTWORDS) + "\n", encoding="utf-8")
        vocab = models / (
            "zipformer-th/unigram_2000.vocab" if fam == "zip" else "typhoon-int8/bpe.vocab"
        )
        kw = dict(
            decoding_method="modified_beam_search",
            hotwords_file=str(hw),
            hotwords_score=float(mode[2:]),
            modeling_unit="bpe",
            bpe_vocab=str(vocab),
        )
    if fam == "zip":
        m = models / "zipformer-th"
        return sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(m / "encoder-epoch-12-avg-5.int8.onnx"),
            decoder=str(m / "decoder-epoch-12-avg-5.onnx"),
            joiner=str(m / "joiner-epoch-12-avg-5.int8.onnx"),
            tokens=str(m / "tokens.txt"),
            num_threads=threads,
            **kw,
        )
    if fam == "ty":
        m = models / "typhoon-int8"
        return sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(m / "encoder.int8.onnx"),
            decoder=str(m / "decoder.int8.onnx"),
            joiner=str(m / "joiner.int8.onnx"),
            tokens=str(m / "tokens.txt"),
            num_threads=threads,
            model_type="nemo_transducer",
            **kw,
        )
    raise ValueError(spec)


def run(audio: Path, models: Path, sets: list[str], specs: list[str], threads: int) -> dict:
    from aipc.skills import browse
    from aipc.spikes.voice_h_eval import judge
    from aipc.voice.zipformer import tidy

    res = {}
    for spec in specs:
        rec = recognizer(spec, models, threads)
        rows = []
        for name in sets:
            for it in load_set(name):
                t0 = time.perf_counter()
                s = rec.create_stream()
                s.accept_waveform(16000, read(audio / name / f"{it['id']}.wav"))
                rec.decode_stream(s)
                heard = tidy(s.result.text)
                secs = round(time.perf_counter() - t0, 3)
                got = [c.as_dict() for c in browse.parse(heard)]
                rows.append(
                    {
                        **it,
                        "set": name,
                        "heard": heard,
                        "got": got,
                        "seconds": secs,
                        "verdict": judge(got, it["expect"]),
                    }
                )
        res[spec] = {"summary": summary(rows), "rows": rows}
        print(line(spec, res[spec]["summary"]), flush=True)
    return res


def summary(rows: list[dict]) -> dict:
    out = {}
    for name in sorted({r["set"] for r in rows}) + ["all"]:
        rs = [r for r in rows if name in ("all", r["set"])]
        v = [r["verdict"] for r in rs]
        n_cmd = sum(bool(r["expect"]) for r in rs)
        out[name] = {
            "ok": v.count("ok"),
            "n_cmd": n_cmd,
            "wrong": v.count("wrong"),
            "miss": v.count("miss"),
            "neg_do": v.count("neg_do"),
            "n_neg": len(rs) - n_cmd,
            "median_s": round(statistics.median(r["seconds"] for r in rs), 3),
        }
    return out


def line(spec: str, s: dict) -> str:
    parts = [
        f"{k} ถูก {v['ok']}/{v['n_cmd']} ผิด {v['wrong']} ไม่ทำ {v['miss']} "
        f"ไม่ใช่คำสั่งแต่ทำ {v['neg_do']}/{v['n_neg']}"
        for k, v in s.items()
    ]
    return " · ".join(parts) + f"  [{spec}]"


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("synth")
    a1.add_argument("audio")
    a1.add_argument("voice")
    a1.add_argument("sets", nargs="+")
    a2 = sub.add_parser("run")
    a2.add_argument("audio")
    a2.add_argument("models")
    a2.add_argument("--sets", nargs="+", required=True)
    a2.add_argument("--models", dest="specs", nargs="+", required=True)
    a2.add_argument("--threads", type=int, default=4)
    a2.add_argument("--out", default="")
    a = ap.parse_args()
    if a.cmd == "synth":
        synth(Path(a.audio), a.voice, a.sets)
        return
    res = run(Path(a.audio), Path(a.models), a.sets, a.specs, a.threads)
    if a.out:
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
