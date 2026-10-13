"""วัดผู้ช่วยเว็บที่ AI คิดเอง (การ์ด 0025 หัวข้อ 8) บนหน้าเว็บที่จับไว้ · llama-server จริง (Pi ผ่าน SSH tunnel).

    python -m aipc.spikes.agent_eval tests/data/agent_dev.json --out x.json  (--url ค่าเริ่มต้น :18080)

ทุกข้อ: ขั้น A (แผน) → ขั้น B (ดูหน้า) ถ้าแผนมี look ตั้งแต่ขั้นแรก · look หลังขั้นที่เปลี่ยนหน้า = ไม่มีหน้าให้ดูต่อ
(นับเป็น "look") · เทียบกับ expect (ข้อใดข้อหนึ่ง) · --preread = อ่านหน้าไว้ก่อนแล้วจึงถาม (วัดเวลาเกณฑ์ข้อ 4)
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from datetime import date

from aipc.browser import agent
from aipc.chat.client import Target

CHANGES_PAGE = {"search", "find", "open", "result", "back", "forward", "reload", "close", "app"}


def norm(t: str) -> str:
    return re.sub(r"\s+", "", t.lower().replace("ํา", "ำ"))


def _words_ok(spec: str, text: str) -> bool:
    """'~ก|ข~ค' = (ก หรือ ข) และ ค อยู่ในข้อความ (ไม่สนวรรค/ตัวพิมพ์) · '=ก' = ต้องเท่ากับ ก ทุกตัวอักษร
    (ตัวเทียบของ 0024 · เกณฑ์ข้อ 2)."""
    got = norm(text)
    if spec.startswith("="):
        return got == norm(spec[1:])
    return all(any(norm(alt) in got for alt in group.split("|")) for group in spec.split("~")[1:])


def step_ok(spec: str, st: agent.Step) -> bool:
    act, _, arg = spec.partition(" ")
    if act != st.action:
        return False
    if act in ("result", "click"):
        return st.n in {int(x) for x in arg.split("|")}
    if act == "type":
        n, _, words = arg.partition(" ")
        return st.n == int(n) and _words_ok(words, st.text)
    if act == "look" or not arg:
        return True
    return _words_ok(arg, st.text)


def matches(expect: list[list[str]], steps: list[agent.Step]) -> bool:
    return any(
        len(alt) == len(steps) and all(step_ok(s, st) for s, st in zip(alt, steps, strict=True))
        for alt in expect
    )


def run_item(llm: agent.Llm, item: dict, obs: dict, today: date, preread: bool) -> dict:
    head = {"title": obs.get("title", ""), "url": obs.get("url", "")} if obs else {}
    row = {"id": item["id"], "cat": item["cat"], "page": item["page"], "command": item["command"]}
    t0 = time.monotonic()
    plan, tm = llm.ask(agent.plan_messages(item["command"], head), agent.PLAN_GRAMMAR, 60)
    row["plan"] = {"reply": plan, "s": round(time.monotonic() - t0, 2),
                   "prompt_n": tm.get("prompt_n"),
                   "predicted_n": tm.get("predicted_n")}  # fmt: skip
    steps = agent.parse_steps(plan, (*agent.PLAN_STEPS, "chat")) or []
    final: list[agent.Step] = []
    moved = False
    for st in steps:
        if st.action == "look" and not moved and obs:
            if preread:
                t1 = time.monotonic()
                pt = llm.preread(agent.preread_messages(obs))
                row["preread"] = {"s": round(time.monotonic() - t1, 2),
                                  "prompt_n": pt.get("prompt_n")}  # fmt: skip
            t1 = time.monotonic()
            reply, tm = llm.ask(
                agent.look_messages(st.text, obs, today), agent.look_grammar(obs), 120
            )
            row["look"] = {"task": st.text, "reply": reply, "s": round(time.monotonic() - t1, 2),
                           "prompt_n": tm.get("prompt_n"),
                           "predicted_n": tm.get("predicted_n")}  # fmt: skip
            got = agent.parse_steps(reply, (*agent.LOOK_STEPS, "none")) or [agent.Step("none")]
            final += got
            moved = moved or any(s.action in CHANGES_PAGE for s in got)
            continue
        final.append(st)
        moved = moved or st.action in CHANGES_PAGE
    row["final"] = [str(s) for s in final]
    row["ok"] = matches(item["expect"], final)
    row["s"] = round(time.monotonic() - t0, 2)
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("set")
    ap.add_argument("--pages", default="tests/data/agent_pages.json")
    ap.add_argument("--url", default="http://127.0.0.1:18080")
    ap.add_argument("--out", default="")
    ap.add_argument("--only", default="", help="เฉพาะ id ที่ขึ้นต้นด้วย (คั่นด้วย ,)")
    ap.add_argument("--preread", action="store_true")
    a = ap.parse_args()
    data = json.load(open(a.set, encoding="utf-8"))
    pages = json.load(open(a.pages, encoding="utf-8"))["pages"]
    today = date.fromisoformat(data.get("today", "2026-10-13"))
    llm = agent.Llm(Target(url=a.url), timeout=600)
    rows = []
    only = [x for x in a.only.split(",") if x]
    for item in data["items"]:
        if only and not any(item["id"].startswith(o) for o in only):
            continue
        r = run_item(llm, item, pages[item["page"]], today, a.preread)
        rows.append(r)
        mark = "✓" if r["ok"] else "✗"
        print(f"{mark} {r['id']:5} {r['cat']:5} {r['page']:15} {r['command'][:34]:34} → "
              f"{' ; '.join(r['final'])[:70]}  [{r['s']}s]", flush=True)  # fmt: skip
    total = Counter(r["cat"] for r in rows)
    ok = Counter(r["cat"] for r in rows if r["ok"])
    summary = {c: f"{ok[c]}/{total[c]} = {100 * ok[c] / total[c]:.1f}%" for c in sorted(total)}
    plan_s = sorted(r["plan"]["s"] for r in rows)
    summary["plan_median_s"] = plan_s[len(plan_s) // 2] if plan_s else None
    looks = sorted(r["look"]["s"] for r in rows if "look" in r)
    summary["look_median_s"] = looks[len(looks) // 2] if looks else None
    print(json.dumps(summary, ensure_ascii=False))
    if a.out:
        json.dump({"set": a.set, "summary": summary, "rows": rows},
                  open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)  # fmt: skip


if __name__ == "__main__":
    main()
