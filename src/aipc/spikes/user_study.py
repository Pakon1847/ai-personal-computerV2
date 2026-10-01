"""คิดผลทดสอบกับผู้ใช้จริง (docs/eval/user-study) · งานสำเร็จ · เวลา · คะแนน SUS (Brooke 1996).

    python -m aipc.spikes.user_study results.csv

คอลัมน์: participant, group, T1..T8 (ok | help | fail), T1_s..T8_s (วินาที), SUS1..SUS10 (1–5)
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from statistics import mean, median

TASKS = [f"T{i}" for i in range(1, 9)]
OUTCOMES = ("ok", "help", "fail")


def sus(answers: list[int]) -> float:
    """ข้อคี่ = คะแนน − 1 · ข้อคู่ = 5 − คะแนน · รวม × 2.5."""
    if len(answers) != 10 or any(a not in (1, 2, 3, 4, 5) for a in answers):
        raise ValueError("SUS ต้องมี 10 ข้อ คะแนน 1–5")
    return sum((a - 1) if i % 2 == 0 else (5 - a) for i, a in enumerate(answers)) * 2.5


def summarize(rows: list[dict]) -> dict:
    out: dict = {"n": len(rows), "groups": {}}
    for group in sorted({r["group"] for r in rows}) + ["all"]:
        sel = rows if group == "all" else [r for r in rows if r["group"] == group]
        outcomes = [r[t] for r in sel for t in TASKS]
        if any(o not in OUTCOMES for o in outcomes):
            raise ValueError(f"ผลงานต้องเป็น {OUTCOMES}")
        scores = [sus([int(r[f"SUS{i}"]) for i in range(1, 11)]) for r in sel]
        out["groups"][group] = {
            "people": len(sel),
            "task_ok_pct": round(100 * outcomes.count("ok") / len(outcomes), 1),
            "task_help_pct": round(100 * outcomes.count("help") / len(outcomes), 1),
            "sus_mean": round(mean(scores), 1),
            "per_task_ok": {t: sum(r[t] == "ok" for r in sel) for t in TASKS},
            "per_task_median_s": {t: median(float(r[f"{t}_s"]) for r in sel) for t in TASKS},
        }
    return out


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    path = Path((argv or sys.argv[1:])[0])
    with path.open(encoding="utf-8") as f:
        res = summarize(list(csv.DictReader(f)))
    for g, s in res["groups"].items():
        print(f"{g}: {s['people']} คน · งานสำเร็จเอง {s['task_ok_pct']}%"
              f" · มีคนช่วย {s['task_help_pct']}%"
              f" · SUS เฉลี่ย {s['sus_mean']}")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
