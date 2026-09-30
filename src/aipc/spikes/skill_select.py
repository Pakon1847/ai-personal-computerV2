"""วัดการเลือกสกิล: กฎอย่างเดียว เทียบกับ กฎ + AI ในเครื่อง (ADR-007 เกณฑ์ข้อ 6).

อาจารย์ขอให้ local AI เรียกใช้สกิลเอง ·

    python -m aipc.spikes.skill_select --label typhoon25-4b-q4km --server http://127.0.0.1:8080 \
        --out docs/benchmarks/$(date +%F)-skill-select-pi5/typhoon25-4b-q4km.json

--mode rules-first (ค่าเริ่มต้น = แอปตอนนี้): ตัวคัดสกิลแบบกฎก่อน (router.route) ·
ถ้ากฎไม่ตรงสกิลใด → ส่งให้ llama-server พร้อมรายการสกิล
(aipc.skills.catalog · system prompt ชุดเดียวกับ ChatController) แล้วดูว่า AI เรียกเครื่องมือไหน
--mode ai-first (แบบที่ลองเทียบ): ตัวแปลคำสั่งเครื่องก่อน (ชื่อแอป/เว็บต้องแน่นอน) · ที่เหลือให้ AI เลือกทุกข้อ ·
กฎให้คะแนนคำสำคัญใช้เฉพาะตอนไม่มี AI (ผลวัดกฎก่อน 2026-09-29: ประโยคหลอก 6 ข้อกฎตัดสินผิดหมดก่อนถึง AI)
ชุดประโยค tests/data/skill_selection.json เขียนและ commit ก่อนวัด (H9) · ห้ามแก้หลังเริ่มวัด
ก่อนวัดถาม /props ว่า chat template รับรายการเครื่องมือไหม · ไม่รับ = หยุด (llama-server ทิ้งรายการเงียบ ๆ ·
รอบแรก 2026-09-29 ของ Typhoon เป็นแบบนี้ ผลจึงใช้ไม่ได้)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from collections import OrderedDict
from pathlib import Path

from aipc.skills import catalog, manifest, router

REPO = Path(__file__).resolve().parents[3]
DATASET = REPO / "tests" / "data" / "skill_selection.json"
SAMPLING = {"temperature": 0.6, "top_p": 0.95, "max_tokens": 48,
            "chat_template_kwargs": {"enable_thinking": False}}  # fmt: skip
# system prompt ชุดเดียวกับแชทของแอป (ไม่มีไฮบริด) · ก่อน 2026-09-30 บ่ายใช้ catalog.SYSTEM สั้น ๆ
SYSTEM_PROMPT = catalog.system_prompt() + catalog.TOOLS_HINT  # เลือกเครื่องมือ = ไม่ต้องตอบยาว
MODES = ("rules-first", "ai-first")


def server_info(server: str, timeout: float = 30) -> dict:
    """chat template ที่ llama-server ใช้จริง · supports_tools False = AI ไม่เห็นรายการสกิลเลย."""
    with urllib.request.urlopen(server.rstrip("/") + "/props", timeout=timeout) as resp:
        props = json.loads(resp.read())
    tpl = props.get("chat_template") or ""
    caps = props.get("chat_template_caps") or {}
    return {
        "supports_tools": bool(caps.get("supports_tools")),
        "template_chars": len(tpl),
        "template_sha256": hashlib.sha256(tpl.encode()).hexdigest(),
        "model": props.get("model_path", ""),
    }


def ask_ai(server: str, text: str, tools: list[dict], timeout: float = 300) -> dict:
    """ถาม llama-server 1 ข้อพร้อมรายการสกิล · คืนชื่อเครื่องมือที่ AI เรียก ("" = ตอบเอง) + เวลา."""
    body = {"messages": [{"role": "system", "content": SYSTEM_PROMPT},
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


def by_rules(text: str, skills, avail: set[str], ai, mode: str) -> str:
    """สกิลที่กฎเลือก · "" = ให้ AI ตัดสิน (ตามแบบที่วัด)."""
    if mode == "ai-first" and ai is not None:
        r = router.route_ai_first(text, skills)  # ตัวเดียวกับ SkillsController.handle
    else:
        r = router.route(text, skills, avail)
    return r.skill.id if r.skill is not None else ""


def evaluate(items: list[dict], skills, ai=None, mode: str = "rules-first") -> dict:
    """ai(text) → ชื่อเครื่องมือ · None = วัดกฎอย่างเดียว."""
    if mode not in MODES:
        raise ValueError(f"mode ต้องเป็น {MODES}")
    avail = {"llm"}
    tools = catalog.tools(skills, avail)
    known = {t["function"]["name"] for t in tools}
    rows = []
    for it in items:
        row = {**it, "by": "rule"}
        got = by_rules(it["text"], skills, avail, ai, mode) or "none"
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
        # ข้อแรกที่ถาม AI = prompt ยังไม่อยู่ใน cache (รายการสกิล ~1,000 token) · ข้อต่อไปอ่านเฉพาะส่วนที่ต่าง
        "ai_seconds_first": ai_rows[0]["seconds"] if ai_rows else None,
        "ai_seconds_max": secs[-1] if secs else None,
        "mode": mode, "rows": rows,
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
    ap.add_argument("--mode", choices=MODES, default="rules-first")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    skills = manifest.load_builtin()
    ai = None
    info = {}
    if a.server:
        info = server_info(a.server)
        if not info["supports_tools"]:
            n = info["template_chars"]
            print(f"หยุด: chat template ของ server ไม่รับรายการเครื่องมือ ({n} ตัวอักษร)"
                  " · ใส่ --chat-template-file ของโมเดลต้นฉบับ (scripts/pi/chat-templates)",
                  file=sys.stderr)  # fmt: skip
            return 2

        def ai(text, tools):
            return ask_ai(a.server, text, tools)

    res = evaluate(data["items"], skills, ai, a.mode)
    res.update(
        label=a.label, method="rules + AI" if ai else "rules only", skills=[s.id for s in skills],
        server=info,
    )  # fmt: skip
    from aipc.bench import machine

    commit, dirty = machine.git_commit(REPO)
    res["machine"] = {"board": machine.board_model(), "ram_mb": machine.ram_total_mb(),
                      "temp_c": machine.cpu_temp_c(), "throttled": machine.throttled_raw(),
                      "commit": commit, "dirty": dirty}  # fmt: skip
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8",
                     newline="\n")  # fmt: skip
    print(f"{a.label} ({res['method']} · {a.mode}): {verdict(res, data['criteria'])}")
    for k, (c, n) in res["by_kind"].items():
        print(f"  {k}: {c}/{n}")
    if ai:
        print(f"  ถาม AI {res['ai_asked']} ข้อ · median {res['ai_seconds_median']} วิ/ข้อ"
              f" · ข้อแรก {res['ai_seconds_first']} วิ · ช้าสุด {res['ai_seconds_max']} วิ")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
