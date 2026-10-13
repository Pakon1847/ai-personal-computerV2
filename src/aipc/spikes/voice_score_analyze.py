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


def choose(row: dict, stems: list[str], t: float, keep: set[int] | None) -> list[dict]:
    res = row["res"]
    best = None
    for k, c in enumerate(res["cands"]):
        if keep is not None and k not in keep:
            continue
        if c["lp"] is None:
            continue
        m = meaning(c["text"])
        if m and (best is None or c["lp"] > best[0]):
            best = (c["lp"], m)
    if best is None or res["free"] - best[0] > t:
        return []
    return best[1]


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
    free_caught = sum(bool(meaning(r["res"]["text"])) for r in neg)
    print(f"ประโยค {len(rows)} (คำสั่ง {len(cmd)} · ไม่ใช่คำสั่ง {len(neg)})")
    print(f"ถอดอิสระ + กฎ: คำสั่งถูก {free_ok}/{len(cmd)} · ไม่ใช่คำสั่งแต่ถูกจับ {free_caught}/{len(neg)}")
    for k in (None, 12, 8, 5, 3):
        for t in (10, 15, 20, 25, 30):
            ok = caught = 0
            wrong_action = 0
            for r in rows:
                keep = None
                if k is not None:
                    sims = sorted(
                        range(len(stems)), key=lambda i: -similarity(stems[i], r["res"]["text"])
                    )
                    keep = set(sims[:k])
                got = choose(r, stems, t, keep)
                if r["expect"]:
                    ok += got == r["expect"]
                    wrong_action += bool(got) and got != r["expect"]
                else:
                    caught += bool(got)
            label = "ทุกต้นคำ" if k is None else f"K={k}"
            print(
                f"{label:8} T={t:2}: คำสั่งถูก {ok}/{len(cmd)} · ทำผิดคำสั่ง {wrong_action} · "
                f"ไม่ใช่คำสั่งแต่ถูกจับ {caught}/{len(neg)}"
            )


if __name__ == "__main__":
    main()
