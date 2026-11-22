"""วัดด่านตรวจสกิล (การ์ด 0074 ขั้น 0 · S1): สกิลเสียหลุดเข้าได้กี่ตัว · สกิลดีถูกปฏิเสธผิดกี่ตัว.

    python -m aipc.spikes.skill_gate --dataset tests/data/skill_guard_s1.json \
        --out docs/benchmarks/2026-11-05-skill-guard/s1-gate.json

ทางที่วัด = ปุ่มนำเข้าสกิลจากไฟล์ (backend.importSkill): ต้องขึ้นต้นด้วยส่วนหัว --- แล้วผ่าน userskills.gate
โดยมีสกิลในตัวอยู่แล้ว (ผู้ใช้ใหม่) · ทางนี้คือทางที่สกิลจากคนอื่นจะเข้ามา (แชร์สกิล · คำแนะนำข้อ 5)
โค้ดล้วน ไม่มี AI · ผลเหมือนกันทุกเครื่อง · ชุดข้อมูลเขียนและ commit ก่อนรัน (H9)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path

from aipc.skills import manifest, userskills

REPO = Path(__file__).resolve().parents[3]


def check_import(md: str, existing: list[manifest.Manifest]) -> tuple[bool, list[str]]:
    """ตรวจแบบเดียวกับ backend.importSkill · คืน (ติดตั้งได้ไหม, เหตุผลที่ไม่ผ่าน)."""
    if not md.lstrip("﻿ \r\n").startswith("---"):
        return False, ["ไม่มีส่วนหัว --- (ไม่ใช่ไฟล์สกิล)"]
    m, errors = userskills.gate(md, existing)
    return m is not None, errors


def upper95(n: int) -> float:
    """ขอบบน 95% ของอัตราเมื่อเจอ 0 จาก n ครั้ง (1 − 0.05^(1/n) ≈ 3/n)."""
    return 1 - 0.05 ** (1 / n) if n else 1.0


def evaluate(items: list[dict], existing: list[manifest.Manifest]) -> dict:
    rows = []
    for it in items:
        ok, errors = check_import(it["md"], existing)
        rows.append({"id": it["id"], "label": it["label"], "category": it.get("category"),
                     "type": it.get("type"), "accepted": ok, "errors": errors})  # fmt: skip
    bad = [r for r in rows if r["label"] == "bad"]
    good = [r for r in rows if r["label"] == "good"]
    groups: OrderedDict = OrderedDict()
    for r in bad:
        for key in (f"category {r['category']}", f"type {r['type']}"):
            g = groups.setdefault(key, [0, 0])
            g[0] += r["accepted"]
            g[1] += 1
    leaked = sum(r["accepted"] for r in bad)
    return {
        "bad_total": len(bad), "bad_accepted": leaked,
        "bad_accepted_upper95": round(upper95(len(bad)), 3) if not leaked else None,
        "good_total": len(good), "good_accepted": sum(r["accepted"] for r in good),
        "bad_by_group": groups, "rows": rows,
    }  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.spikes.skill_gate")
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    data = json.loads(a.dataset.read_text(encoding="utf-8"))
    res = evaluate(data["items"], manifest.load_builtin())
    from aipc.bench import machine

    commit, dirty = machine.git_commit(REPO)
    res.update(dataset=a.dataset.name, machine={"commit": commit, "dirty": dirty})
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"สกิลเสียติดตั้งได้ {res['bad_accepted']}/{res['bad_total']} · "
          f"สกิลดีติดตั้งได้ {res['good_accepted']}/{res['good_total']}")  # fmt: skip
    for k, (n, total) in res["bad_by_group"].items():
        print(f"  สกิลเสีย {k}: หลุด {n}/{total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
