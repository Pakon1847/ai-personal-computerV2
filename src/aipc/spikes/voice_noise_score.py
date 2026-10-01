"""ให้คะแนนผลถอดเสียงในเสียงรบกวน (docs/benchmarks/2026-10-01-voice-noise) ด้วยตัวแปลคำสั่งของแอป.

    python -m aipc.spikes.voice_noise_score docs/benchmarks/2026-10-01-voice-noise/r1.json

คำสั่งถูก = action/params ตรงเฉลย (นับรวมที่ถามก่อน) · ทำผิดโดยไม่ถาม = action/params ผิดและไม่ถาม (อันตราย) ·
CER = ระยะแก้ไขตัวอักษร ÷ ความยาวต้นฉบับ (ไม่นับช่องว่าง)
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from aipc.skills import command

SENTENCES = (
    Path(__file__).resolve().parents[3] / "docs/benchmarks/2026-10-01-voice-noise/sentences.json"
)


def cer(ref: str, hyp: str) -> float:
    a, b = ref.replace(" ", ""), hyp.replace(" ", "")
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / max(len(a), 1)


def score(data: dict) -> dict:
    truth = {s["text"]: s for s in json.loads(SENTENCES.read_text(encoding="utf-8"))}
    cells: dict = defaultdict(lambda: {"n": 0, "right": 0, "wrong_silent": 0, "cer": 0.0})
    for r in data["rows"]:
        t = truth[r["text"]]
        cmd = command.parse(r["heard"])
        right = (
            cmd is not None and cmd.plan.action == t["action"] and cmd.plan.params == t["params"]
        )
        c = cells[(r["noise"], r["filter"])]
        c["n"] += 1
        c["right"] += right
        c["wrong_silent"] += cmd is not None and not right and not cmd.needs_confirmation
        c["cer"] += cer(r["text"], r["heard"])
    out = {}
    for (noise, flt), c in cells.items():
        out.setdefault(noise, {})[flt] = {
            "right": c["right"], "n": c["n"], "wrong_silent": c["wrong_silent"],
            "cer": round(c["cer"] / c["n"], 3),
        }  # fmt: skip
    return out


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    res = score(json.loads(Path((argv or sys.argv[1:])[0]).read_text(encoding="utf-8")))
    filters = list(next(iter(res.values())))
    print("เสียง".ljust(10) + "".join(f.ljust(22) for f in filters))
    for noise, row in res.items():
        cells = [
            f"{row[f]['right']}/{row[f]['n']} ผิดเงียบ{row[f]['wrong_silent']} CER{row[f]['cer']:.2f}"
            for f in filters
        ]
        print(noise.ljust(10) + "".join(c.ljust(22) for c in cells))
    return 0


if __name__ == "__main__":
    sys.exit(main())
