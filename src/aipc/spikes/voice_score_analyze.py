"""การ์ด 0026 (spike): วิเคราะห์ผล voice_score_eval แบบไม่ต้องรันเสียงซ้ำ.

    python -m aipc.spikes.voice_score_analyze ผล.json [--skip-latin]

- ลองค่า T (ระยะห่างคะแนนจากถอดอิสระ) หลายค่า
- จำลองการตัดต้นคำสั่งให้เหลือ K ตัว (เลือกจากความคล้ายของตัวอักษรกับข้อความที่ถอดอิสระ) → ประมาณเวลาที่ลดลง
- --skip-latin: ไม่นับประโยคที่มีตัวอังกฤษ (Piper ทิ้งตัวอังกฤษ = เสียงทดสอบไม่มีคำนั้นเลย)
"""

from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher

from aipc.spikes.voice_score_eval import meaning

TONES = re.compile(r"[ัิ-ฺ็-๎]")  # สระบน/ล่าง วรรณยุกต์ ไม้ไต่คู้ การันต์


def skeleton(s: str) -> str:
    return TONES.sub("", re.sub(r"\s+", "", s))


def similarity(stem: str, heard: str) -> float:
    """ต้นคำสั่งคล้ายตอนต้นของสิ่งที่ได้ยินแค่ไหน (เทียบโครงตัวอักษร ไม่สนวรรณยุกต์/สระบนล่าง)."""
    a, h = skeleton(stem), skeleton(heard)
    best = 0.0
    for n in range(max(1, len(a) - 2), len(a) + 3):
        best = max(best, SequenceMatcher(None, a, h[:n]).ratio())
    # คำสั่งต่อท้าย (…แล้วเข้าลิงก์แรก) ไม่อยู่ตอนต้น → เทียบทั้งประโยคด้วยแบบมีน้ำหนักน้อยกว่า
    best = max(best, 0.8 * SequenceMatcher(None, a, h).find_longest_match().size / max(1, len(a)))
    return best


def choose(row: dict, t: float, m: float, keep: set[int] | None) -> tuple[str, list[dict]]:
    """("do", คำสั่ง) ทำเลย · ("ask", คำสั่ง) ถามกลับ (สองอันดับแรกความหมายต่างกันแต่คะแนนห่างไม่ถึง m) ·
    ("chat", []) ไม่ใช่คำสั่ง (คำสั่งที่ดีที่สุดห่างจากถอดอิสระเกิน t)."""
    res = row["res"]
    by_meaning: dict[str, tuple[float, list[dict]]] = {}
    for k, c in enumerate(res["cands"]):
        if (keep is not None and k not in keep) or c["lp"] is None:
            continue
        mean = meaning(c["text"])
        if not mean:
            continue
        key = json.dumps(mean, ensure_ascii=False, sort_keys=True)
        if key not in by_meaning or c["lp"] > by_meaning[key][0]:
            by_meaning[key] = (c["lp"], mean)
    ranked = sorted(by_meaning.values(), key=lambda x: -x[0])
    if not ranked or res["free"] - ranked[0][0] > t:
        return "chat", []
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < m:
        return "ask", ranked[0][1]
    return "do", ranked[0][1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("result")
    ap.add_argument("--skip-latin", action="store_true")
    a = ap.parse_args()
    d = json.load(open(a.result, encoding="utf-8"))
    stems = d["stems"]
    rows = [r for r in d["rows"] if not (a.skip_latin and re.search(r"[A-Za-z]", r["text"]))]
    cmd = [r for r in rows if r["expect"]]
    neg = [r for r in rows if not r["expect"]]
    free_ok = sum(meaning(r["res"]["text"]) == r["expect"] for r in cmd)
    free_bad = sum(bool(g := meaning(r["res"]["text"])) and g != r["expect"] for r in cmd)
    free_caught = sum(bool(meaning(r["res"]["text"])) for r in neg)
    print(f"ประโยค {len(rows)} (คำสั่ง {len(cmd)} · ไม่ใช่คำสั่ง {len(neg)})")
    print(
        f"ถอดอิสระ + กฎ: ทำถูก {free_ok}/{len(cmd)} · ทำผิดคำสั่ง {free_bad} · "
        f"ไม่ใช่คำสั่งแต่ถูกทำ {free_caught}/{len(neg)}"
    )
    for k in (None, 8, 5, 3):
        for t, m in ((15, 0), (20, 0), (25, 0), (20, 2), (20, 4), (25, 4), (30, 4)):
            ok = ask_ok = ask_bad = bad = caught = neg_ask = 0
            for r in rows:
                keep = None
                if k is not None:
                    text = r["res"]["text"]
                    sims = sorted(range(len(stems)), key=lambda i: -similarity(stems[i], text))
                    keep = set(sims[:k])
                what, got = choose(r, t, m, keep)
                if r["expect"]:
                    ok += what == "do" and got == r["expect"]
                    bad += what == "do" and got != r["expect"]
                    ask_ok += what == "ask" and got == r["expect"]
                    ask_bad += what == "ask" and got != r["expect"]
                else:
                    caught += what == "do"
                    neg_ask += what == "ask"
            label = "ทุกต้นคำ" if k is None else f"K={k}"
            print(
                f"{label:8} T={t:2} M={m}: ทำถูก {ok}/{len(cmd)} · ทำผิด {bad} · "
                f"ถามกลับ {ask_ok}+{ask_bad} (ถูก+ผิด) · ไม่ใช่คำสั่งแต่ถูกทำ {caught}/{len(neg)} "
                f"ถาม {neg_ask}"
            )


if __name__ == "__main__":
    main()
