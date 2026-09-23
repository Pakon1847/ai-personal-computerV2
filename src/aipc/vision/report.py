"""สรุป log การทดสอบใบหน้ากับคนจริงตามเกณฑ์ BRIEF (docs/evaluation/face-protocol.md).

    python -m aipc.vision.report <face-scans.log> [--out ผล.json]

ใช้เฉพาะบรรทัดที่มี subject (รหัสผู้ที่สแกนจริง ใส่ด้วย camera scan --who) · แต่ละการสแกนเป็นหนึ่งใน:
- ถูกคน     account == subject
- ผิดคน     account เป็นคนอื่น            → นับ "จับคู่ผิดคน" (เกณฑ์: 0 จาก N)
- ปฏิเสธ    ไม่ได้ account                → นับใน FRR (เกณฑ์ ≤ 5%) · ถ้าเหตุผลคือ spoof นับใน BPCER ด้วย
เวลา = total_ms ของการสแกน (median ≤ 1.5 วิ, p95 ≤ 3 วิ ตาม BRIEF)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np


def summarize(entries: list[dict]) -> dict:
    rows = [e for e in entries if e.get("subject")]
    per: dict[str, Counter] = {}
    times = []
    for e in rows:
        c = per.setdefault(e["subject"], Counter())
        c["attempts"] += 1
        if e.get("account") == e["subject"]:
            c["correct"] += 1
        elif e.get("account"):
            c["wrong_person"] += 1
        else:
            c["rejected"] += 1
            c[f"reason:{e.get('reason')}"] += 1
            if e.get("reason") == "spoof":
                c["spoof_rejected"] += 1
        times.append(float(e.get("total_ms", 0.0)))
    n = len(rows)
    rejected = sum(c["rejected"] for c in per.values())
    wrong = sum(c["wrong_person"] for c in per.values())
    spoof = sum(c["spoof_rejected"] for c in per.values())
    return {
        "attempts": n,
        "subjects": len(per),
        "frr": round(rejected / n, 4) if n else None,
        "wrong_person": wrong,
        "bpcer": round(spoof / n, 4) if n else None,
        "time_ms": {"median": round(float(np.median(times)), 1) if times else None,
                    "p95": round(float(np.percentile(times, 95)), 1) if times else None},
        "per_subject": {s: dict(sorted(c.items())) for s, c in sorted(per.items())},
        "criteria": {"frr_max": 0.05, "wrong_person": 0, "bpcer_max": 0.05,
                     "time_median_ms_max": 1500, "time_p95_ms_max": 3000},
    }  # fmt: skip


def verdicts(s: dict) -> dict:
    """ผ่าน/ไม่ผ่านต่อเกณฑ์ · ยังไม่ถึงจำนวนขั้นต่ำ (≥ 5 คน × ≥ 50 ครั้ง) = บอกว่าข้อมูลไม่พอ."""
    enough = s["subjects"] >= 5 and all(c["attempts"] >= 50 for c in s["per_subject"].values())
    cr = s["criteria"]
    t = s["time_ms"]
    return {
        "enough_data": enough,
        "frr": s["frr"] is not None and s["frr"] <= cr["frr_max"],
        "wrong_person": s["wrong_person"] == cr["wrong_person"],
        "bpcer": s["bpcer"] is not None and s["bpcer"] <= cr["bpcer_max"],
        "time": t["median"] is not None and t["median"] <= cr["time_median_ms_max"]
        and t["p95"] <= cr["time_p95_ms_max"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.vision.report")
    ap.add_argument("log", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    entries = [json.loads(line) for line in a.log.read_text(encoding="utf-8").splitlines() if line]
    s = summarize(entries)
    s["verdicts"] = verdicts(s)
    text = json.dumps(s, ensure_ascii=False, indent=2)
    if a.out:
        a.out.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
