"""เกณฑ์ข้อ 7 การ์ด 0025: Claude สำรองวางแผนถูกไหม เมื่อ Gemma ทำไม่สำเร็จ · หน้าเว็บที่จับไว้ · claude -p จริง.

    python -m aipc.spikes.agent_cloud_check tests/data/agent_dev.json --ids d07,d08 --out c.json

ส่งข้อความเดียวกับที่แอปส่ง (agent.cloud_prompt + CLOUD_SYSTEM · aipc.cloud.ask.ask_plain ไม่มีเครื่องมือ) ·
ตรวจแผนที่ได้ด้วยตัวเทียบเดียวกับ agent_eval · Claude บน Pi ต้องใช้บัญชีของ Pakon จึงรันบนวินโดวส์
(แบบเดียวกับชุดสอบไฮบริด docs/benchmarks/2026-10-06-exam-hybrid-gemma)
"""

from __future__ import annotations

import argparse
import json
from datetime import date

from aipc.browser import agent
from aipc.cloud import ask
from aipc.spikes.agent_eval import matches


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("set")
    ap.add_argument("--ids", required=True)
    ap.add_argument("--pages", default="tests/data/agent_pages.json")
    ap.add_argument("--problem", default="AI ในเครื่องทำไม่สำเร็จ")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    data = json.load(open(a.set, encoding="utf-8"))
    pages = json.load(open(a.pages, encoding="utf-8"))["pages"]
    today = date.fromisoformat(data.get("today", "2026-10-13"))
    want = a.ids.split(",")
    rows = []
    for item in data["items"]:
        if item["id"] not in want:
            continue
        prompt = agent.cloud_prompt(item["command"], [], a.problem, pages[item["page"]], today)
        r = ask.ask_plain(agent.CLOUD_SYSTEM, prompt)
        steps = None
        for line in reversed([x for x in r.text.splitlines() if x.strip()]):
            steps = agent.parse_steps(line.strip().strip("`"), (*agent.CLOUD_STEPS, "none"))
            if steps:
                break
        ok = bool(steps) and matches(item["expect"], steps)
        rows.append({"id": item["id"], "command": item["command"], "reply": r.text, "ok": ok,
                     "error": r.error, "seconds": r.seconds, "cost_usd": r.cost_usd,
                     "model": r.model, "chars_sent": len(prompt)})  # fmt: skip
        print(f"{'✓' if ok else '✗'} {item['id']} {item['command']} → {r.text!r} "
              f"[{r.seconds}s ${r.cost_usd:.4f}]", flush=True)  # fmt: skip
    print(f"รวม {sum(r['ok'] for r in rows)}/{len(rows)}")
    if a.out:
        json.dump(rows, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
