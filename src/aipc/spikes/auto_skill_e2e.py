"""ปลายทางจริงของสกิลอัตโนมัติ (การ์ด 0017 ข้อ 10.4): Claude จริงสร้าง → ประตู → ติดตั้ง → สั่งซ้ำ AI ในเครื่องเรียกเอง.

    python -m aipc.spikes.auto_skill_e2e --server http://127.0.0.1:18080 \
        --out docs/benchmarks/2026-09-30-auto-skill/e2e.json

คำขอ = ข้อ "create" ของชุดประเมิน tests/data/create_skill_calls.json เลือกทุกข้อที่ 3 (c01 c04 c07 c10 c13 · กำหนดก่อนวัด)
ติดตั้งลงโฟลเดอร์ชั่วคราว (ไม่แตะสกิลของผู้ใช้จริง) · สกิลที่ติดตั้งแล้วสะสมต่อกัน (เหมือนผู้ใช้ใช้งานต่อเนื่อง)
สั่งซ้ำ = ข้อความเดิม ผ่านทางเดียวกับแอป (route_ai_first → AI ในเครื่องพร้อมรายการเครื่องมือที่มีสกิลใหม่)
เกณฑ์: ติดตั้งได้ ≥ 4/5 · เวลาจากส่งถึงติดตั้ง มัธยฐาน ≤ 60 วิ · สั่งซ้ำเรียกสกิลใหม่ ≥ 4/5
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

from aipc.skills import catalog, forge, manifest, router, userskills
from aipc.spikes import create_skill_calls, skill_select

PICK = ("c01", "c04", "c07", "c10", "c13")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--server", required=True)
    ap.add_argument("--model-name", default="gemma-4-E2B-it-Q4_K_M")
    ap.add_argument("--claude", default=shutil.which("claude") or "claude")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    items = {i["id"]: i for i in json.loads(create_skill_calls.DATASET.read_text(encoding="utf-8"))["items"]}
    version = forge.run_process([a.claude, "--version"], "", ".", 30)[1].strip()
    builtin = manifest.load_builtin()
    rows = []
    with tempfile.TemporaryDirectory(prefix="aipc-e2e-") as d:
        store = userskills.UserSkills(Path(d))
        for iid in PICK:
            text = items[iid]["text"]
            skills = builtin + store.load()
            t0 = time.monotonic()
            p = forge.forge(text, skills=skills, claude=a.claude, model="sonnet", claude_version=version,
                            check=lambda md, s=skills: userskills.gate(md, s)[1])  # fmt: skip
            row = {"id": iid, "text": text, "attempts": p.attempts, "cost_usd": round(p.cost_usd, 4),
                   "errors": p.errors, "skill_id": p.skill_id, "skill_md": p.skill_md}  # fmt: skip
            try:
                m = store.install(p.skill_md, skills, request=text, model=p.model, cost_usd=p.cost_usd)
                row["installed"] = True
            except manifest.InvalidSkill as e:
                m, row["installed"], row["errors"] = None, False, [*row["errors"], *e.errors]
            row["seconds"] = round(time.monotonic() - t0, 1)
            if m is not None:  # สั่งซ้ำ: ทางเดียวกับแอป
                skills = builtin + store.load()
                r = router.route_ai_first(text, skills)
                if r.kind == "skill":
                    row.update(again_by="rule", again=r.skill.id)
                elif r.kind == "create":
                    row.update(again_by="rule", again=catalog.CREATE_SKILL)
                else:
                    system = catalog.system_prompt(date.today(), cloud=True, model=a.model_name, forge=True)
                    skill_select.SYSTEM_PROMPT = system + catalog.TOOLS_HINT
                    tools = catalog.tools([], set(), cloud=True) + catalog.tools(skills, {"llm"}, forge=True)
                    res = skill_select.ask_ai(a.server, text, tools)
                    row.update(again_by="ai", again=res["tool"] or "none", again_text=res.get("text", "")[:200])
                row["again_ok"] = row["again"] == m.id
            rows.append(row)
            print(f"{iid} ติดตั้ง={row['installed']} {row['seconds']} วิ {row['attempts']} รอบ "
                  f"${row['cost_usd']} · {row.get('skill_id')} · สั่งซ้ำ → {row.get('again')} "
                  f"({row.get('again_by')})" + (f" · {row['errors'][:1]}" if not row["installed"] else ""))  # fmt: skip
    ok = [r for r in rows if r["installed"]]
    secs = [r["seconds"] for r in rows]
    summary = {
        "installed": [len(ok), len(rows)], "seconds_median": statistics.median(secs),
        "again_ok": [sum(r.get("again_ok", False) for r in ok), len(rows)],
        "cost_usd": round(sum(r["cost_usd"] for r in rows), 3), "claude": version,
    }  # fmt: skip
    passed = summary["installed"][0] >= 4 and summary["seconds_median"] <= 60 and summary["again_ok"][0] >= 4
    print(f"ติดตั้ง {summary['installed'][0]}/5 (≥ 4) · มัธยฐาน {summary['seconds_median']} วิ (≤ 60) · "
          f"สั่งซ้ำเรียกสกิลใหม่ {summary['again_ok'][0]}/5 (≥ 4) · ${summary['cost_usd']} → "
          f"{'ผ่าน' if passed else 'ไม่ผ่าน'}")  # fmt: skip
    if a.out:
        a.out.write_text(json.dumps({"summary": summary, "passed": passed, "date": date.today().isoformat(),
                                     "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
