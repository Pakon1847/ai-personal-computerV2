"""วัดว่าเวลาของคีย์ลัดเสียงหมดไปกับขั้นไหน (Pakon 2026-10-20: "ถอดเสียงช้ามาก") · บน Pi 5.

    python -m aipc.spikes.voice_latency <โฟลเดอร์เสียง 16k> <ชุด.json> [--n 30] --out ผล.json

ขั้นที่วัด (ตัวเดียวกับแอป):
1. Zipformer โหลดครั้งแรก (cold) และถอดแต่ละไฟล์ (warm)
2. ทางลองอังกฤษ (_maybe_english): ข้อความไทยไม่ตรงคำสั่ง → whisper base.en ถอดซ้ำ
   (โปรเซสใหม่ทุกครั้ง) · นับว่าเกิดกี่ครั้ง
3. ช่วงรอเงียบของ Endpointer = ค่าคงที่ในโค้ด (silence_s) · ไม่ต้องวัด
เสียงสังเคราะห์ (Piper) ไม่ใช่เสียงคน · ใช้ดูเวลาเท่านั้น ไม่ใช่ความแม่น
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

from aipc.voice import stt, zipformer


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", type=Path)
    ap.add_argument("dataset", type=Path)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    from aipc.ui import backend  # _thai_missed / _english_command = ทางเดียวกับแอป

    rows = json.loads(a.dataset.read_text(encoding="utf-8"))["rows"][: a.n]
    tr = zipformer.Transcriber()
    t0 = time.monotonic()
    tr.warm()
    first = a.audio / f"{int(rows[0]['id'][1:]) - 1:03d}-16k.wav"
    text, err = tr.transcribe(first)
    cold = time.monotonic() - t0
    en_cmd = stt.Listener()._en_cmd
    out = []
    for r in rows:
        wav = a.audio / f"{int(r['id'][1:]) - 1:03d}-16k.wav"
        t = time.monotonic()
        heard, err = tr.transcribe(wav)
        zip_s = time.monotonic() - t
        en_s, en_used = None, False
        if backend._thai_missed(heard):
            t = time.monotonic()
            res = subprocess.run(
                [*en_cmd, str(wav)], capture_output=True, text=True, encoding="utf-8"
            )
            en_s = time.monotonic() - t
            en = stt.clean(res.stdout)
            en_used = bool(en) and backend._english_command(en)
        out.append({"id": r["id"], "said": r["text"], "heard": heard, "zip_s": round(zip_s, 3),
                    "english_tried": en_s is not None,
                    "english_s": None if en_s is None else round(en_s, 3),
                    "english_used": en_used})  # fmt: skip
    tr.close()
    zs = [x["zip_s"] for x in out]
    es = [x["english_s"] for x in out if x["english_s"] is not None]
    summary = {
        "n": len(out), "cold_load_s": round(cold, 2),
        "zip_median_s": round(statistics.median(zs), 3), "english_tried": len(es),
        "english_median_s": round(statistics.median(es), 3) if es else None,
        "english_used": sum(x["english_used"] for x in out),
        "endpointer_silence_s": stt.Endpointer().silence_frames * stt.Endpointer.FRAME / 16000,
    }  # fmt: skip
    a.out.write_text(json.dumps({"summary": summary, "rows": out}, ensure_ascii=False, indent=1),
                     encoding="utf-8")  # fmt: skip
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
