"""การ์ด 0026 (spike · วัดก่อนออกแบบ): เทียบตัวถอดเสียงอีกตัว.

Zipformer ไทย (GigaSpeech2 · sherpa-onnx · int8):

    <venv ที่มี sherpa-onnx>/python -m aipc.spikes.voice_zipformer_eval <โฟลเดอร์โมเดล>
        <โฟลเดอร์เสียง> <ชุด.json ...> [--hotwords] --out ผล.json

ไม่ใช่ dependency ของแอป (venv แยกบน Pi) · ถอดอิสระ + กฎเดิม (aipc.skills.browse)
เหมือนแถว "free+rules" ของ voice_score_eval · --hotwords = เพิ่มน้ำหนักคำสั่ง
(ต้นคำสั่งชุดเดียวกับ voice_score_eval.STEMS) ด้วย modified_beam_search
"""

from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path

from aipc.skills import browse
from aipc.spikes.voice_score_eval import STEMS


def read(path: Path) -> list[float]:
    import array

    with wave.open(str(path)) as w:
        a = array.array("h", w.readframes(w.getnframes()))
    return [x / 32768.0 for x in a]


def main() -> None:
    import sherpa_onnx

    ap = argparse.ArgumentParser()
    ap.add_argument("model_dir")
    ap.add_argument("audio_dir")
    ap.add_argument("sets", nargs="+")
    ap.add_argument("--hotwords", action="store_true")
    ap.add_argument("--hotwords-score", type=float, default=2.0)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    m = Path(a.model_dir)
    kw = {}
    if a.hotwords:
        hw = m / "hotwords.txt"
        hw.write_text("\n".join(STEMS) + "\n", encoding="utf-8")
        kw = dict(
            decoding_method="modified_beam_search",
            hotwords_file=str(hw),
            hotwords_score=a.hotwords_score,
            modeling_unit="bpe",
            bpe_vocab=str(m / "unigram_2000.vocab"),
        )
    t0 = time.monotonic()
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(m / "encoder-epoch-12-avg-5.int8.onnx"),
        decoder=str(m / "decoder-epoch-12-avg-5.onnx"),
        joiner=str(m / "joiner-epoch-12-avg-5.int8.onnx"),
        tokens=str(m / "tokens.txt"),
        num_threads=a.threads,
        **kw,
    )
    print(f"โหลด {time.monotonic() - t0:.1f} วิ", flush=True)
    rows = []
    for set_path in a.sets:
        name = Path(set_path).stem
        items = json.loads(Path(set_path).read_text(encoding="utf-8"))["items"]
        for i, it in enumerate(items):
            samples = read(Path(a.audio_dir) / name / f"{i:02d}-16k.wav")
            t1 = time.monotonic()
            s = rec.create_stream()
            s.accept_waveform(16000, samples)
            rec.decode_stream(s)
            text = s.result.text.strip()
            secs = round(time.monotonic() - t1, 3)
            got = [c.as_dict() for c in browse.parse(text)]
            ok = got == it["expect"]
            rows.append(
                {
                    "set": name,
                    "i": i,
                    "text": it["text"],
                    "heard": text,
                    "expect": it["expect"],
                    "got": got,
                    "ok": ok,
                    "seconds": secs,
                }
            )
            print(
                f"{'✓' if ok else '✗'} {name} {i:02d} {secs:5.2f}s «{text}» ← {it['text']}",
                flush=True,
            )
    cmd = [r for r in rows if r["expect"]]
    neg = [r for r in rows if not r["expect"]]
    secs = sorted(r["seconds"] for r in rows)
    summary = {
        "commands": f"{sum(r['ok'] for r in cmd)}/{len(cmd)}",
        "non_commands_caught": f"{sum(bool(r['got']) for r in neg)}/{len(neg)}",
        "median_s": secs[len(secs) // 2],
        "max_s": secs[-1],
        "hotwords": a.hotwords,
    }
    print(json.dumps(summary, ensure_ascii=False))
    if a.out:
        Path(a.out).write_text(
            json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
