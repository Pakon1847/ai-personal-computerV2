"""สั่งสกิลที่ Claude สร้างด้วยสำนวนอื่น (การ์ด 0017 ต่อจากข้อ 10.4) · ทางเดียวกับแอป.

    python -m aipc.spikes.auto_skill_paraphrase --server http://127.0.0.1:18080 \
        --out docs/benchmarks/2026-09-30-auto-skill/paraphrase.json

สกิล = ไฟล์ที่ติดตั้งในปลายทางจริงรอบ 2 (e2e-r2.json) · ประโยค = tests/data/auto_skill_paraphrase.json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

from aipc.skills import catalog, manifest, router, userskills
from aipc.spikes import skill_select

REPO = Path(__file__).resolve().parents[3]
E2E = REPO / "docs/benchmarks/2026-09-30-auto-skill/e2e-r2.json"
DATASET = REPO / "tests/data/auto_skill_paraphrase.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--server", required=True)
    ap.add_argument("--model-name", default="gemma-4-E2B-it-Q4_K_M")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    builtin = manifest.load_builtin()
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as d:
        store = userskills.UserSkills(Path(d))
        for r in json.loads(E2E.read_text(encoding="utf-8"))["rows"]:
            store.install(r["skill_md"], builtin + store.load(), request=r["text"])
        skills = builtin + store.load()
    system = catalog.system_prompt(date.today(), cloud=True, model=a.model_name, forge=True)
    skill_select.SYSTEM_PROMPT = system + catalog.TOOLS_HINT
    tools = catalog.tools([], set(), cloud=True) + catalog.tools(skills, {"llm"}, forge=True)
    rows = []
    for it in data["items"]:
        r = router.route_ai_first(it["text"], skills)
        row = dict(it)
        if r.kind == "create":
            row.update(by="rule", got=catalog.CREATE_SKILL)
        elif r.skill is not None:
            row.update(by="rule", got=r.skill.id)
        else:
            res = skill_select.ask_ai(a.server, it["text"], tools)
            row.update(by="ai", got=res["tool"] or "none", reply=res.get("text", "")[:200])
        row["ok"] = row["got"] == it["expect"]
        rows.append(row)
        print(f"{'✓' if row['ok'] else '✗'} {it['id']} {row['by']:4} {row['got']:24} {it['text']}")
    hit = sum(r["ok"] for r in rows)
    by_ai = [r for r in rows if r["by"] == "ai"]
    line = (f"สำนวนอื่น: เรียกสกิลที่ Claude สร้างถูก {hit}/{len(rows)} = {hit / len(rows):.0%} "
            f"(เกณฑ์ ≥ {data['criteria']['hit_min']:.0%}) · กฎตัดสิน {len(rows) - len(by_ai)} · AI ตัดสิน {len(by_ai)} "
            f"(ถูก {sum(r['ok'] for r in by_ai)}) · ขอสร้างซ้ำ {sum(r['got'] == catalog.CREATE_SKILL for r in rows)}")  # fmt: skip
    print(line)
    if a.out:
        a.out.write_text(json.dumps({"summary": line, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
