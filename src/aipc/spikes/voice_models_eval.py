"""การ์ด 0026 (spike): เทียบโมเดลถอดเสียงหลายตัวบนเสียงชุดเดียวกัน · วิธีให้คะแนนตัวเลือก (FIX) · บน Pi.

    python -m aipc.spikes.voice_models_eval <โมเดล ggml> <โฟลเดอร์เสียง> <ชุด.json ...> --out ผล.json

ต่อเสียงหนึ่งประโยค (ตัวช่วย tools/whisper-score · เข้ารหัสเสียงครั้งเดียว):
1. GO → ถอดอิสระ (greedy · หน้าต่างเสียงพอดีความยาว) + คะแนนของข้อความนั้น
2. สร้างตัวเลือกจากข้อความที่ได้ยิน (aipc.spikes.voice_cands.candidates)
3. AGAIN → ให้คะแนนตัวเลือกทุกตัวบนเสียงเดิม
เก็บค่าดิบทั้งหมด · การตั้งเกณฑ์และสรุปผลอยู่ที่ voice_models_analyze (ไม่ต้องรันเสียงซ้ำ)
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from aipc.spikes.voice_cands import candidates
from aipc.spikes.voice_score_eval import Helper


def peak_rss_mb(pid: int) -> float | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        return None
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("audio_dir")
    ap.add_argument("sets", nargs="+")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--keep", type=int, default=8)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    h = Helper(Path(a.model), a.threads)
    rows = []
    for set_path in a.sets:
        name = Path(set_path).stem
        items = json.loads(Path(set_path).read_text(encoding="utf-8"))["items"]
        for i, it in enumerate(items):
            wav = Path(a.audio_dir) / name / f"{i:02d}-16k.wav"
            t0 = time.monotonic()
            free = h.ask(wav, [])
            heard = free.get("text", "")
            cands = candidates(heard, a.keep) if "error" not in free else []
            h.p.stdin.write("".join(f"FIX {c}\n" for c in cands) + "AGAIN\n")
            h.p.stdin.flush()
            again = json.loads(h.p.stdout.readline())
            wall_ms = round((time.monotonic() - t0) * 1000)
            scored = [[c, r["lp"]] for c, r in zip(cands, again.get("cands", []), strict=True)]
            rows.append(
                {
                    "set": name,
                    "i": i,
                    "text": it["text"],
                    "expect": it["expect"],
                    "secs": free.get("secs"),
                    "heard": heard,
                    "free_lp": free.get("free"),
                    "full_ms": free.get("full_ms"),
                    "score_ms": again.get("score_ms"),
                    "wall_ms": wall_ms,
                    "cands": scored,
                }
            )
            print(
                f"{name} {i:02d} {wall_ms:5d}ms ({len(cands)} ตัวเลือก) «{heard}» ← {it['text']}",
                flush=True,
            )
    out = {"model": Path(a.model).name, "peak_rss_mb": peak_rss_mb(h.p.pid), "rows": rows}
    h.p.stdin.close()
    h.p.wait()
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
