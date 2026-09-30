"""วัดว่า AI ในเครื่องเรียก create-skill ถูกจังหวะไหม (การ์ด 0017 ข้อ 10.3).

    python -m aipc.spikes.create_skill_calls --label gemma4-e2b --server http://127.0.0.1:18080 \
        --out docs/benchmarks/2026-09-30-auto-skill/calls-gemma4-e2b.json

ทางเดียวกับแอป: router.route_ai_first ก่อน (คำสั่งตรง/กฎ) → ไม่ตรง = ถาม llama-server ด้วย
system prompt และ
รายการเครื่องมือชุดเดียวกับ ChatController (ask-cloud + create-skill + สกิลในตัว)
· ชุด tests/data/create_skill_calls.json
เขียนและ commit ก่อนวัด (H9) · ห้ามปรับ prompt ด้วยชุดนี้
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from aipc.skills import catalog, manifest, router
from aipc.spikes import skill_select

REPO = Path(__file__).resolve().parents[3]
DATASET = REPO / "tests" / "data" / "create_skill_calls.json"


def app_prompt_and_tools(model: str, today: date | None = None) -> tuple[str, list[dict]]:
    """system prompt + เครื่องมือ แบบที่แอปส่งเมื่อมี Claude (ไฮบริด + สกิลอัตโนมัติ)."""
    skills = manifest.load_builtin()
    tools = catalog.tools([], set(), cloud=True) + catalog.tools(skills, {"llm"}, forge=True)
    system = catalog.system_prompt(today or date.today(), cloud=True, model=model, forge=True)
    return system + catalog.TOOLS_HINT, tools


def evaluate(items: list[dict], ai, skills=None) -> dict:
    skills = skills if skills is not None else manifest.load_builtin()
    rows = []
    for it in items:
        r = router.route_ai_first(it["text"], skills)
        row = {**it}
        if r.kind == "create":  # กฎตั้งโหมด/งานประจำ (router.define_intent) ตัดสินก่อนถึง AI
            row.update(by="rule", got=catalog.CREATE_SKILL)
        elif r.skill is not None:  # กฎ/คำสั่งตรงตัดสินก่อนถึง AI (แอปจริงก็เป็นแบบนี้)
            row.update(by="rule", got=r.skill.id)
        else:
            res = ai(it["text"])
            row.update(
                by="ai",
                got=res["tool"] or "none",
                seconds=res["seconds"],
                timings=res["timings"],
                reply=res.get("text", "")[:300],
            )
        row["called"] = row["got"] == catalog.CREATE_SKILL
        rows.append(row)
    create = [r for r in rows if r["expect"] == "create"]
    no = [r for r in rows if r["expect"] == "no"]
    return {
        "create_hit": [sum(r["called"] for r in create), len(create)],
        "no_false": [sum(r["called"] for r in no), len(no)],
        "by_style": {
            s: [
                sum(r["called"] for r in rows if r["style"] == s),
                sum(1 for r in rows if r["style"] == s),
            ]
            for s in dict.fromkeys(r["style"] for r in rows)
        },
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--label", required=True)
    ap.add_argument("--server", required=True)
    ap.add_argument("--model-name", default="gemma-4-E2B-it-Q4_K_M")
    ap.add_argument("--out", type=Path)
    ap.add_argument(
        "--dataset", type=Path, default=DATASET, help="ชุดพัฒนา: tests/data/create_skill_dev.json"
    )
    ap.add_argument(
        "--show", action="store_true", help="พิมพ์คำตอบของ AI ข้อที่ไม่เรียกเครื่องมือ (ใช้กับชุดพัฒนา)"
    )
    a = ap.parse_args(argv)
    info = skill_select.server_info(a.server)
    if not info["supports_tools"]:
        print("หยุด: chat template ไม่รับรายการเครื่องมือ", file=sys.stderr)
        return 2
    data = json.loads(a.dataset.read_text(encoding="utf-8"))
    data.setdefault("criteria", json.loads(DATASET.read_text(encoding="utf-8"))["criteria"])
    system, tools = app_prompt_and_tools(a.model_name)
    skill_select.SYSTEM_PROMPT = system  # ask_ai ใช้ค่านี้

    def ai(text):
        return skill_select.ask_ai(a.server, text, tools)

    res = evaluate(data["items"], ai)
    c = data["criteria"]
    hit, n_c = res["create_hit"]
    fal, n_n = res["no_false"]
    ok = hit / n_c >= c["create_hit_min"] and fal / n_n <= c["no_false_max"]
    line = (
        f"{a.label}: ควรสร้าง เรียก {hit}/{n_c} = {hit / n_c:.0%} "
        f"(เกณฑ์ ≥ {c['create_hit_min']:.0%}) · "
        f"ไม่ควร เรียกผิด {fal}/{n_n} = {fal / n_n:.0%} (เกณฑ์ ≤ {c['no_false_max']:.0%}) → "
        f"{'ผ่าน' if ok else 'ไม่ผ่าน'}"
    )
    print(line)
    for s, (k, n) in res["by_style"].items():
        print(f"  {s}: เรียก create-skill {k}/{n}")
    for r in res["rows"]:
        mark = "✓" if r["called"] == (r["expect"] == "create") else "✗"
        print(f"  {mark} {r['id']} {r['by']:4} {r['got']:16} {r['text'][:50]}")
        if a.show and r.get("reply"):
            print("      AI: " + " ".join(r["reply"].split())[:160])
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        out = {
            "label": a.label,
            "server": info,
            "summary": line,
            "system_chars": len(system),
            "date": date.today().isoformat(),
            **res,
        }
        a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
