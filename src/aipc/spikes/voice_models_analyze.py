"""การ์ด 0026 (spike): สรุปผลเทียบโมเดล (ไม่ต้องรันเสียงซ้ำ) ตามกติกาในการ์ด 0026 หัวข้อ 7.

    python -m aipc.spikes.voice_models_analyze ผล1.json ผล2.json ...
        [--dev browse_v1,browse_v2] [--skip-latin]

- ผลจาก voice_models_eval (whisper): (ก) ถอดอิสระ + กฎ · (ข) ให้คะแนนตัวเลือก
  โดยตั้ง ts tc m จากชุด --dev เท่านั้น
- ผลจาก voice_zipformer_eval: (ก) อย่างเดียว
- นับ: ทำถูกครั้งแรก · ทำคำสั่งผิด · ไม่ใช่คำสั่งแต่ถูกทำ · ถามกลับ · เวลาตัดสินใจ (median/p90) · RAM
- --skip-latin: ไม่นับประโยคที่มีตัวอังกฤษ (Piper ทิ้งคำอังกฤษ = เสียงทดสอบไม่มีคำนั้น)
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
from pathlib import Path

from aipc.spikes.voice_cands import decide, meaning

TS = [2, 3, 4, 5, 6, 7, 8, 10, 12, 15]
TC = [4, 6, 8, 10, 12, 14, 16, 20, 25]
M = [0, 1, 2, 3, 4]


def count(rows: list[dict], pick) -> dict:
    """pick(row) → (what, commands) · what = do / ask / chat."""
    c = dict.fromkeys(
        ("ok", "wrong", "qdiff", "ask", "miss", "neg_do", "neg_ask", "n_cmd", "n_neg"), 0
    )
    for r in rows:
        what, got = pick(r)
        if r["expect"]:
            c["n_cmd"] += 1
            if what == "do":
                c["ok" if got == r["expect"] else "wrong"] += 1
                # ชนิดคำสั่งถูกหมดแต่คำค้นเพี้ยน (ยังนับเป็นผิด · แสดงแยกเพราะเว็บค้นหาแก้คำผิดได้)
                c["qdiff"] += got != r["expect"] and only_query_differs(got, r["expect"])
            else:
                c["ask" if what == "ask" else "miss"] += 1
        else:
            c["n_neg"] += 1
            c["neg_do"] += what == "do"
            c["neg_ask"] += what == "ask"
    return c


def only_query_differs(got: list[dict], expect: list[dict]) -> bool:
    """ต่างกันแค่คำค้น (ลิงก์ที่ N ผิด = ผิดจริง ไม่ใช่คำค้นเพี้ยน)."""
    strip = [
        {k: v for k, v in x.items() if not (x["kind"] == "search" and k == "query")} for x in got
    ]
    want = [
        {k: v for k, v in x.items() if not (x["kind"] == "search" and k == "query")} for x in expect
    ]
    return strip == want


def free_pick(r: dict) -> tuple[str, list[dict]]:
    got = meaning(r["heard"])
    return ("do", got) if got else ("chat", [])


def score_pick(ts: float, tc: float, m: float):
    def pick(r: dict) -> tuple[str, list[dict]]:
        if r.get("free_lp") is None:
            return "chat", []
        d = decide(r["heard"], r["free_lp"], [tuple(x) for x in r["cands"]], ts, tc, m)
        return d.what, d.commands

    return pick


def badness(c: dict) -> tuple:
    # กติกาการ์ดหัวข้อ 7: ทำผิดน้อยสุด → ทำถูกมากสุด → ถามกลับน้อยสุด
    return (c["wrong"] + c["neg_do"], -c["ok"], c["ask"] + c["neg_ask"])


def pct(xs: list[float], q: float) -> float | None:
    xs = sorted(x for x in xs if x is not None)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None


def line(name: str, c: dict) -> str:
    return (
        f"{name:28} ถูก {c['ok']:3}/{c['n_cmd']} · ผิด {c['wrong']} (คำค้นเพี้ยน {c['qdiff']}) · "
        f"ถาม {c['ask']} · "
        f"ไม่ทำ {c['miss']} · ไม่ใช่คำสั่งแต่ทำ {c['neg_do']}/{c['n_neg']} (ถาม {c['neg_ask']})"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--dev", default="browse_v1,browse_v2")
    ap.add_argument("--skip-latin", action="store_true")
    a = ap.parse_args()
    dev_sets = set(a.dev.split(","))
    for path in a.results:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        rows = [r for r in d["rows"] if not (a.skip_latin and re.search(r"[A-Za-z]", r["text"]))]
        dev = [r for r in rows if r["set"] in dev_sets]
        rest = [r for r in rows if r["set"] not in dev_sets]
        model = d.get("model") or Path(path).stem
        print(f"\n## {model} · RAM สูงสุด {d.get('peak_rss_mb', 'ไม่ได้วัด')} MB")
        if "cands" not in rows[0]:  # zipformer: ถอดอิสระอย่างเดียว · เวลา = ถอดทั้งประโยค
            secs = [r["seconds"] * 1000 for r in rows]
            print(f"เวลาตัดสินใจ median {pct(secs, 0.5):.0f} ms · p90 {pct(secs, 0.9):.0f} ms")
            print(line("ถอดอิสระ+กฎ (dev)", count(dev, free_pick)))
            print(line("ถอดอิสระ+กฎ (ทดสอบ)", count(rest, free_pick)))
            continue
        full = [r["full_ms"] for r in rows]
        total = [(r["full_ms"] or 0) + (r["score_ms"] or 0) for r in rows]
        print(
            f"ถอดอิสระ median {pct(full, 0.5)} ms · ถอด+ให้คะแนน median {pct(total, 0.5)} ms "
            f"p90 {pct(total, 0.9)} ms · ตัวเลือก median {pct([len(r['cands']) for r in rows], 0.5)}"
        )
        best = min(itertools.product(TS, TC, M), key=lambda p: badness(count(dev, score_pick(*p))))
        print(line("ถอดอิสระ+กฎ (dev)", count(dev, free_pick)))
        tag = f"ให้คะแนน ts{best[0]} tc{best[1]} m{best[2]}"
        print(line(f"{tag} (dev)", count(dev, score_pick(*best))))
        print(line("ถอดอิสระ+กฎ (ทดสอบ)", count(rest, free_pick)))
        print(line("ให้คะแนน ค่าเดียวกัน (ทดสอบ)", count(rest, score_pick(*best))))


if __name__ == "__main__":
    main()
