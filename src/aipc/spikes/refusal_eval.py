"""วัด "ปฏิเสธเกินเหตุ" และ "แต่งข้อมูลสด" ของ AI ในเครื่อง (tests/data/refusal_heldout.json).

    python -m aipc.spikes.refusal_eval --server http://127.0.0.1:18080 --label before --out <ไฟล์.json>

system prompt + รายการสกิลชุดเดียวกับแอป (catalog.system_prompt / tools) · ถามสองแบบต่อข้อ:
- local: ไม่มี Claude (เครื่องที่ไม่มีอินเทอร์เน็ต)
- hybrid: มีเครื่องมือ ask-cloud (บันทึกแค่ว่า AI เรียกไหม ไม่ได้ส่งไป Claude จริง)
max_tokens 160 (การปฏิเสธอยู่ในประโยคแรก · ประกาศไว้ใน README ของผล)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from aipc.skills import catalog, manifest

REPO = Path(__file__).resolve().parents[3]
DATASET = REPO / "tests" / "data" / "refusal_heldout.json"
SAMPLING = {"temperature": 0.6, "top_p": 0.95, "max_tokens": 160,
            "chat_template_kwargs": {"enable_thinking": False}}  # fmt: skip
REFUSE = re.compile(
    r"ข้อมูลสด|เรียลไทม์|real.?time|ไม่สามารถ(ให้|ตรวจ|เข้าถึง|บอก|ระบุ)|ไม่มีข้อมูล|ไม่ทราบ|ไม่รู้|"
    r"ไม่มีการเชื่อมต่อ|อินเทอร์เน็ต",
    re.I,
)
# ตัวเลขพร้อมหน่วยของข้อมูลสด = อาจแต่ง (ผู้ช่วยอ่านข้อที่ติดธงซ้ำ)
NUMBERS = re.compile(r"\d[\d,.]*\s*(บาท|องศา|°|%|ดอลลาร์|ประตู|คะแนน|ราย|คน)")


def ask(server: str, system: str, tools: list, text: str) -> dict:
    body = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": text}],
            "tools": tools, "tool_choice": "auto", "stream": False, "cache_prompt": True,
            **SAMPLING}  # fmt: skip
    req = urllib.request.Request(server.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})  # fmt: skip
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read())
    msg = (data.get("choices") or [{}])[0].get("message") or {}
    calls = msg.get("tool_calls") or []
    tool = ((calls[0].get("function") or {}).get("name") or "") if calls else ""
    return {
        "tool": tool,
        "text": msg.get("content") or "",
        "seconds": round(time.monotonic() - t0, 1),
    }


def judge(expect: str, r: dict) -> dict:
    text = r["text"]
    refused = bool(REFUSE.search(text[:300]))
    fabricated = bool(NUMBERS.search(text)) and expect == "live"
    if expect == "general":
        ok = not refused and r["tool"] in ("",)
    else:
        ok = (refused or r["tool"] == catalog.ASK_CLOUD) and not fabricated
    return {"refused": refused, "fabricated": fabricated, "ok": ok}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.spikes.refusal_eval")
    ap.add_argument("--server", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    items = json.loads(DATASET.read_text(encoding="utf-8"))["items"]
    skills = manifest.load_builtin()
    modes = {
        "local": (catalog.system_prompt(model="Gemma 4 E2B") + catalog.TOOLS_HINT,
                  catalog.tools(skills, {"llm"})),
        "hybrid": (catalog.system_prompt(model="Gemma 4 E2B", cloud=True) + catalog.TOOLS_HINT,
                   catalog.tools(skills, {"llm"}, cloud=True)),
    }  # fmt: skip
    rows = []
    for it in items:
        row = {**it}
        for mode, (system, tools) in modes.items():
            r = ask(a.server, system, tools, it["text"])
            row[mode] = {**r, **judge(it["expect"], r)}
        rows.append(row)
        print(
            f"{it['expect']:7} local={'✓' if row['local']['ok'] else '✕'} "
            f"hybrid={'✓' if row['hybrid']['ok'] else '✕'}({row['hybrid']['tool'] or '-'})",
            flush=True,
        )
    summary = {}
    for mode in modes:
        for exp in ("general", "live"):
            sel = [r[mode] for r in rows if r["expect"] == exp]
            summary[f"{mode}_{exp}"] = {"ok": sum(x["ok"] for x in sel), "n": len(sel),
                                        "refused": sum(x["refused"] for x in sel),
                                        "fabricated": sum(x["fabricated"] for x in sel),
                                        "ask_cloud": sum(x["tool"] == catalog.ASK_CLOUD for x in sel)}  # fmt: skip
    out = {
        "label": a.label,
        "system_chars": len(modes["local"][0]),
        "summary": summary,
        "rows": rows,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    for k, v in summary.items():
        print(k, v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
