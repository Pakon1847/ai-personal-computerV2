"""การ์ด 0026 หัวข้อ 8: วัดเกณฑ์ผ่านบนชุด H (120 ข้อ) ด้วยเสียงสังเคราะห์ Piper บน Pi 5.

ไม่มีเสียงคน (Pakon เลือก 2026-10-14) → Piper พูดประโยคชุด H · ข้อ say = prompt ·
ข้อ task = ประโยคที่ล็อกไว้ก่อนรัน
(tests/data/voice_h_synth.json) · คำตอบที่ถูกอ่านจาก tests/data/voice_real_prompts.json เท่านั้น

ทางใหม่ (แอปจริง): aipc.voice.zipformer.Transcriber (กล่องตัดเน็ต · hotwords · tidy) → browse.parse
ทางเดิม (เกณฑ์ข้อ 4): whisper.cpp ค่าเดียวกับ aipc.voice.stt.Listener → stt.clean → browse.parse

    python -m aipc.spikes.voice_h_eval <โฟลเดอร์งาน> --zip-base <ฐาน zipformer> [--out ผล.json]

<ฐาน zipformer> = โฟลเดอร์ที่มี venv/ และ model/ แบบเดียวกับ /opt/aipc-voice/zipformer
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from pathlib import Path

from aipc.skills import browse
from aipc.spikes.voice_models_analyze import matches, only_query_differs
from aipc.voice import stt, tts
from aipc.voice.zipformer import HOTWORDS, Transcriber

ROOT = Path(__file__).resolve().parents[3]
PROMPTS = ROOT / "tests/data/voice_real_prompts.json"
SAID = ROOT / "tests/data/voice_h_synth.json"

SYNTH = r"""
import sys, wave, json
from piper import PiperVoice
v = PiperVoice.load(sys.argv[1])
for i, text in enumerate(json.load(open(sys.argv[2], encoding="utf-8"))):
    with wave.open(f"{sys.argv[3]}/{i:03d}.wav", "wb") as w:
        v.synthesize_wav(text, w)
"""


def h_items() -> list[dict]:
    """ชุด H ตามลำดับ id · text = สิ่งที่ Piper พูด."""
    said = json.loads(SAID.read_text(encoding="utf-8"))["said"]
    out = []
    for it in json.loads(PROMPTS.read_text(encoding="utf-8"))["items"]:
        if it["set"] != "H":
            continue
        text = it["prompt"] if it["mode"] == "say" else said[it["id"]]
        out.append({"id": it["id"], "mode": it["mode"], "text": text, "expect": it["expect"]})
    return out


def judge(got: list[dict], expect: list[dict]) -> str:
    """ok = ตรงทุกค่า · wrong = ทำคำสั่งผิดชนิด/ผิดค่า (รวมคำค้นไม่มีคำหลัก) · miss = ไม่ทำ (ไปแชท) ·
    neg_do = ไม่ใช่คำสั่งแต่ทำ · neg_ok = ไม่ใช่คำสั่งและไม่ทำ."""
    if not expect:
        return "neg_do" if got else "neg_ok"
    if not got:
        return "miss"
    return "ok" if matches(got, expect) else "wrong"


def summarize(rows: list[dict], key: str) -> dict:
    cmd = [r for r in rows if r["expect"]]
    neg = [r for r in rows if not r["expect"]]
    v = [r[key]["verdict"] for r in rows]
    secs = sorted(r[key]["seconds"] for r in rows)
    ok = v.count("ok")
    return {
        "n": len(rows),
        "n_cmd": len(cmd),
        "n_neg": len(neg),
        "ok": ok,
        "ok_pct": round(100 * ok / len(cmd), 1),
        "wrong": v.count("wrong"),
        "wrong_query_only": sum(
            r[key]["verdict"] == "wrong" and only_query_differs(r[key]["got"], r["expect"])
            for r in rows
        ),
        "miss": v.count("miss"),
        "neg_do": v.count("neg_do"),
        "median_s": round(statistics.median(secs), 3),
        "p90_s": secs[min(len(secs) - 1, int(0.9 * len(secs)))],
        "max_s": secs[-1],
    }


def criteria(z: dict, w: dict) -> dict:
    """การ์ด 0026 หัวข้อ 8 ข้อ 1–4 (ข้อ 5 ตรวจแยก)."""
    return {
        "1_wrong_le_2_and_neg_le_1": z["wrong"] <= 2 and z["neg_do"] <= 1,
        "2_first_time_ge_90pct": z["ok_pct"] >= 90.0,
        "3_median_le_1.5_p90_le_2.5": z["median_s"] <= 1.5 and z["p90_s"] <= 2.5,
        "4_not_worse_than_whisper": (
            z["wrong"] + z["neg_do"] <= w["wrong"] + w["neg_do"] and z["ok"] >= w["ok"]
        ),
    }


def temp() -> str:
    try:
        return subprocess.run(
            ["vcgencmd", "measure_temp"], capture_output=True, text=True
        ).stdout.strip()
    except OSError:
        return "?"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--zip-base", required=True)
    ap.add_argument("--out", default="")
    # การ์ด 0028 ข4: hotwords ของสกิลต่อท้าย (ไฟล์ JSON รายการประโยค) · วัดเฉพาะ Zipformer (ข้าม whisper)
    ap.add_argument("--extra-hotwords", default="")
    ap.add_argument("--zip-only", action="store_true")
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    items = h_items()
    assert len(items) == 120, len(items)

    # 1) Piper พูด → 16 kHz mono (ทำครั้งเดียว · ใช้ไฟล์เดิมทั้งสองทาง)
    if not (work / f"{len(items) - 1:03d}-16k.wav").exists():
        (work / "texts.json").write_text(
            json.dumps([it["text"] for it in items], ensure_ascii=False), encoding="utf-8"
        )
        py = tts.VOICE_DIR / "venv" / "bin" / "python"
        subprocess.run(
            [
                str(py),
                "-c",
                SYNTH,
                str(tts.VOICE_DIR / tts.MODEL),
                str(work / "texts.json"),
                str(work),
            ],
            check=True,
        )
        for i in range(len(items)):
            subprocess.run(
                [
                    "ffmpeg",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(work / f"{i:03d}.wav"),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(work / f"{i:03d}-16k.wav"),
                ],
                check=True,
            )
    print(f"เสียงพร้อม 120 ไฟล์ · {temp()}", flush=True)

    # 2) ทางใหม่: ตัวถอดของแอปจริง (อุ่นก่อน = เหมือนกดคีย์ลัดแล้วพูด)
    extra = (
        json.loads(Path(a.extra_hotwords).read_text(encoding="utf-8")) if a.extra_hotwords else []
    )
    z = Transcriber(base=Path(a.zip_base), extra_hotwords=lambda: extra)
    print(
        f"hotwords {len(z.hotwords())} (เพิ่มจากสกิล {len(z.hotwords()) - len(HOTWORDS)})", flush=True
    )
    assert z.available, "ไม่มี venv/ หรือ model/ ใต้ --zip-base"
    t0 = time.monotonic()
    z.transcribe(work / "000-16k.wav")
    print(f"zipformer โหลด+ถอดแรก {time.monotonic() - t0:.1f} วิ · {temp()}", flush=True)
    rows = []
    for i, it in enumerate(items):
        wav = work / f"{i:03d}-16k.wav"
        t1 = time.monotonic()
        heard, err = z.transcribe(wav)
        secs = round(time.monotonic() - t1, 3)
        got = [c.as_dict() for c in browse.parse(heard)]
        rows.append(
            {
                **it,
                "zip": {
                    "heard": heard,
                    "err": err,
                    "got": got,
                    "seconds": secs,
                    "verdict": judge(got, it["expect"]),
                },
            }
        )
        print(
            f"Z {it['id']} {rows[-1]['zip']['verdict']:6} {secs:5.2f}s «{heard}» ← {it['text']}",
            flush=True,
        )
    z.close()
    print(f"zipformer จบ · {temp()}", flush=True)

    if a.zip_only:  # การ์ด 0028 ข4: เทียบแค่ Zipformer ก่อน/หลังเพิ่ม hotwords
        zs = summarize(rows, "zip")
        print(json.dumps({"zipformer": zs}, ensure_ascii=False, indent=1))
        if a.out:
            Path(a.out).write_text(
                json.dumps(
                    {"zipformer": zs, "extra_hotwords": extra, "rows": rows},
                    ensure_ascii=False,
                    indent=1,
                ),
                encoding="utf-8",
            )
        return

    # 3) ทางเดิม: whisper ค่าเดียวกับแอป (เปิดใหม่ทุกประโยคเหมือนแอป)
    whisper = [
        str(stt.VOICE_DIR / stt.WHISPER),
        "-m",
        str(stt.VOICE_DIR / stt.MODEL),
        "-l",
        "th",
        "-t",
        "4",
        "-nt",
        "-ac",
        "512",
        "-f",
    ]
    for i, r in enumerate(rows):
        t1 = time.monotonic()
        p = subprocess.run(
            [*whisper, str(work / f"{i:03d}-16k.wav")],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        secs = round(time.monotonic() - t1, 3)
        heard = stt.clean(p.stdout)
        got = [c.as_dict() for c in browse.parse(heard)]
        r["whisper"] = {
            "heard": heard,
            "got": got,
            "seconds": secs,
            "verdict": judge(got, r["expect"]),
        }
        print(f"W {r['id']} {r['whisper']['verdict']:6} {secs:5.2f}s «{heard}»", flush=True)
    print(f"whisper จบ · {temp()}", flush=True)

    zs, ws = summarize(rows, "zip"), summarize(rows, "whisper")
    res = {"zipformer": zs, "whisper": ws, "criteria": criteria(zs, ws), "rows": rows}
    print(
        json.dumps(
            {k: res[k] for k in ("zipformer", "whisper", "criteria")}, ensure_ascii=False, indent=1
        )
    )
    if a.out:
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
