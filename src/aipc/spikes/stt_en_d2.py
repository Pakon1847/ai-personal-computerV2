"""การ์ด 0040 เกณฑ์ D2 บน Pi 5: Pakon อ่านคำสั่งภาษาอังกฤษ 40 ประโยค.

ถอดด้วยตัวถอดของแอป (whisper base.en) แล้วเทียบช่องข้อมูลกับตอนพิมพ์ประโยคเดียวกัน ·

ประโยค (ประกาศก่อนอัด · ไม่เลือกหลังเห็นผล): ชุด C1 รอบ 2 (tests/data/english_cmd/set2.json) ·
คำสั่ง C02 C04 … C50 (เลขคู่ 25 ข้อ) + C01 C11 C21 C31 C41 = 30 · ไม่ใช่คำสั่ง N01–N10 = 10

    # อัด (ที่จอ Pi · ไมค์จริง · ข้อละ 6 วิ · กด Enter แล้วอ่านประโยคที่ขึ้น) · ไฟล์เสียงอยู่นอก git
    python -m aipc.spikes.stt_en_d2 record --dir ~/voice-bench/en-d2
    # ให้คะแนน (รันครั้งเดียวหลังอัดครบ)
    python -m aipc.spikes.stt_en_d2 score --dir ~/voice-bench/en-d2 --out ผล.json

ผ่านเมื่อ: คำสั่งได้ช่องข้อมูลตรงกับตอนพิมพ์ ≥ 80% (≥ 24/30) · ไม่ใช่คำสั่งถูกแปลงเป็นคำสั่ง 0/10
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from aipc.spikes.english_cmd_eval import slots
from aipc.spikes.stt_en_spike import same, transcribe

SET = Path("tests/data/english_cmd/set2.json")
MODEL = Path("/opt/aipc-voice/ggml-base.en.bin")
COMMANDS = [f"C{i:02d}" for i in range(2, 51, 2)] + ["C01", "C11", "C21", "C31", "C41"]
NEGATIVES = [f"N{i:02d}" for i in range(1, 11)]
SECONDS = 6


def items() -> list[dict]:
    by_id = {it["id"]: it for it in json.loads(SET.read_text(encoding="utf-8"))["items"]}
    return [by_id[i] for i in COMMANDS + NEGATIVES]


def record(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    todo = [it for it in items() if not (d / f"{it['id']}.wav").exists()]
    print(f"เหลือ {len(todo)} ประโยค · ข้อละ {SECONDS} วิ · Ctrl+C หยุดได้ (อัดต่อได้ทีหลัง)")
    for n, it in enumerate(todo, 1):
        input(f"\n[{n}/{len(todo)}] กด Enter แล้วอ่าน:\n    {it['text']}\n")
        out = d / f"{it['id']}.wav"
        cmd = ["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16", str(out)]
        try:
            subprocess.run(cmd, timeout=SECONDS)
        except subprocess.TimeoutExpired:
            pass  # หยุดเมื่อครบเวลา (pw-record เขียนไฟล์ระหว่างอัด)
        print("  ✓ อัดแล้ว")


def score(d: Path, out: Path) -> int:
    rows = []
    for it in items():
        wav = d / f"{it['id']}.wav"
        if not wav.exists():
            print(f"ขาดไฟล์ {wav} · อัดให้ครบก่อน")
            return 2
        heard, secs, hwm = transcribe(MODEL, wav)
        ref, got = slots(it["text"]), slots(heard)
        command = it["kind"] != "none"
        ok = same(ref, got) if command else got["kind"] == "none"
        rows.append({"id": it["id"], "text": it["text"], "heard": heard,
                     "secs": round(secs, 2), "hwm_mb": round(hwm, 1), "command": command,
                     "ok": ok, "got": got})  # fmt: skip
        print(f"{'✓' if ok else '✗'} {it['id']} {it['text'][:50]:50} | {heard}")
    cmds = [r for r in rows if r["command"]]
    negs = [r for r in rows if not r["command"]]
    ok_c = sum(r["ok"] for r in cmds)
    conv = sum(not r["ok"] for r in negs)
    passed = ok_c >= 24 and conv == 0
    summary = {"commands_ok": f"{ok_c}/{len(cmds)}", "negatives_converted": f"{conv}/{len(negs)}",
               "passed": passed}  # fmt: skip
    print(json.dumps(summary, ensure_ascii=False))
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
                   encoding="utf-8")  # fmt: skip
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["record", "score"])
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if a.mode == "record":
        record(a.dir)
        return 0
    return score(a.dir, a.out or Path("results-d2.json"))


if __name__ == "__main__":
    sys.exit(main())
