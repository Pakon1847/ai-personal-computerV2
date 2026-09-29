"""วัดการเลือกสกิล: กฎอย่างเดียว เทียบกับ กฎ + AI ในเครื่อง (ADR-007 เกณฑ์ข้อ 6).

อาจารย์ขอให้ local AI เรียกใช้สกิลเอง ·

    python -m aipc.spikes.skill_select --label typhoon25-4b-q4km --server http://127.0.0.1:8080 \
        --out docs/benchmarks/$(date +%F)-skill-select-pi5/typhoon25-4b-q4km.json

ทำเหมือนแอปจริงทุกขั้น: ตัวคัดสกิลแบบกฎก่อน (router.route) · ถ้ากฎไม่ตรงสกิลใด → ส่งให้ llama-server พร้อมรายการสกิล
(aipc.skills.catalog · system prompt ชุดเดียวกับ ChatController) แล้วดูว่า AI เรียกเครื่องมือไหน
ชุดประโยค tests/data/skill_selection.json เขียนและ commit ก่อนวัด (H9) · ห้ามแก้หลังเริ่มวัด
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from collections import OrderedDict
from pathlib import Path

from aipc.skills import catalog, manifest, router

REPO = Path(__file__).resolve().parents[3]
DATASET = REPO / "tests" / "data" / "skill_selection.json"
SAMPLING = {"temperature": 0.6, "top_p": 0.95, "max_tokens": 48}  # เลือกเครื่องมือ = ไม่ต้องตอบยาว


def ask_ai(server: str, text: str, tools: list[dict], timeout: float = 300) -> dict:
    """ถาม llama-server 1 ข้อพร้อมรายการสกิล · คืนชื่อเครื่องมือที่ AI เรียก ("" = ตอบเอง) + เวลา."""
    body = {"messages": [{"role": "system", "content": catalog.SYSTEM + catalog.TOOLS_HINT},
                         {"role": "user", "content": text}],
            "tools": tools, "tool_choice": "auto", "stream": False, "cache_prompt": True,
            **SAMPLING}  # fmt: skip
    req = urllib.request.Request(server.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})  # fmt: skip
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    msg = (data.get("choices") or [{}])[0].get("message") or {}
    calls = msg.get("tool_calls") or []
    name = ((calls[0].get("function") or {}).get("name") or "") if calls else ""
    return {
        "tool": name,
        "seconds": round(time.monotonic() - t0, 2),
        "timings": data.get("timings", {}),
    }


def evaluate(items: list[dict], skills, ai=None) -> dict:
    """ai(text) → ชื่อเครื่องมือ · None = วัดกฎอย่างเดียว."""
    avail = {"llm"}
    tools = catalog.tools(skills, avail)
    known = {t["function"]["name"] for t in tools}
    rows = []
    for it in items:
        r = router.route(it["text"], skills, avail)
        row = {**it, "by": "rule"}
        got = r.skill.id if r.skill is not None else "none"
        if got == "none" and ai is not None:
            res = ai(it["text"], tools)
            row.update(
                by="ai", seconds=res["seconds"], timings=res["timings"], raw_tool=res["tool"]
            )
            # ชื่อที่ไม่มีในรายการ = แอปจริงตอบแบบคุยทั่วไป (SkillsController.handleAs)
            got = res["tool"] if res["tool"] in known else "none"
        row.update(got=got, ok=got == it["expect"])
        rows.append(row)
    none = [r for r in rows if r["expect"] == "none"]
    by_kind: OrderedDict = OrderedDict()
    for r in rows:
        k = by_kind.setdefault(r["kind"], [0, 0])
        k[0] += r["ok"]
        k[1] += 1
    ai_rows = [r for r in rows if r["by"] == "ai"]
    secs = sorted(r["seconds"] for r in ai_rows)
    return {
        "correct": sum(r["ok"] for r in rows), "total": len(rows),
        "false_calls": sum(r["got"] != "none" for r in none), "none_total": len(none),
        "by_kind": by_kind, "ai_asked": len(ai_rows),
        "ai_seconds_median": secs[len(secs) // 2] if secs else None,
        "rows": rows,
    }  # fmt: skip


def verdict(res: dict, criteria: dict) -> str:
    c = res["correct"] / res["total"]
    f = res["false_calls"] / max(res["none_total"], 1)
    ok = c >= criteria["correct_min"] and f <= criteria["false_call_max"]
    result = "ผ่าน" if ok else "ไม่ผ่าน"
    wrong = f"{res['false_calls']}/{res['none_total']} = {f:.0%}"
    return (f"ถูก {res['correct']}/{res['total']} = {c:.0%} · เรียกสกิลทั้งที่ไม่ควร {wrong}"
            f" → {result}เกณฑ์ ADR-007 ข้อ 6")  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.spikes.skill_select")
    ap.add_argument("--label", required=True)
    ap.add_argument("--server", default="", help="ว่าง = วัดกฎอย่างเดียว")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    skills = manifest.load_builtin()
    ai = None
    if a.server:

        def ai(text, tools):
            return ask_ai(a.server, text, tools)

    res = evaluate(data["items"], skills, ai)
    res.update(
        label=a.label, method="rules + AI" if ai else "rules only", skills=[s.id for s in skills]
    )
    from aipc.bench import machine

    commit, dirty = machine.git_commit(REPO)
    res["machine"] = {"board": machine.board_model(), "ram_mb": machine.ram_total_mb(),
                      "temp_c": machine.cpu_temp_c(), "throttled": machine.throttled_raw(),
                      "commit": commit, "dirty": dirty}  # fmt: skip
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8",
                     newline="\n")  # fmt: skip
    print(f"{a.label} ({res['method']}): {verdict(res, data['criteria'])}")
    for k, (c, n) in res["by_kind"].items():
        print(f"  {k}: {c}/{n}")
    if ai:
        print(f"  ถาม AI {res['ai_asked']} ข้อ · median {res['ai_seconds_median']} วิ/ข้อ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
