"""การ์ด 0022 ส่วน 2: สกิลที่ Claude สร้างทำตามที่ผู้ใช้ขอไหม · ขับแอปตัวจริง (app_driver).

    python -m aipc.spikes.skill_intent_eval --server http://127.0.0.1:18080 --out <ไฟล์.json>

ต่อคำขอ (tests/data/skill_intent_h2.json):
1. สร้าง: skills._start_forge(คำขอ) ทางเดียวกับแอป · Claude จริง (aipc.ui.app._skill_forge · sonnet)
   → ประตูตรวจ → ติดตั้งลงโฟลเดอร์ชั่วคราว → แอปทำงานนั้นทันที (กดยืนยันให้)
2. ทำตามที่ขอ (2.2): สกิลสั่งเครื่อง = คำสั่งที่ถูกสั่งจริงตอนทำครั้งแรก ตรงกับ expect (ไม่สนลำดับ)
   · สกิลงานภาษา = ส่งข้อความ test ให้ AI ในเครื่องพร้อมคำสั่งของสกิลใหม่ แล้วตรวจด้วย check
3. สั่งประโยคเดิมอีกครั้ง (2.3): แอปไปที่สกิลใหม่ไหม
4. แก้ตามคำติ (2.4): skills.reviseSkill(id, คำติ) → Claude แก้ → ทำงานรุ่นใหม่ → ตรวจกับ revise
สกิลที่ติดตั้งสะสมต่อกันตามลำดับ (เหมือนผู้ใช้คนเดียวขอไปเรื่อย ๆ)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATASET = REPO / "tests" / "data" / "skill_intent_h2.json"
THAI = re.compile(r"[฀-๿]")
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")


def check(kind: str, text: str, words: list[str]) -> bool:
    """ตัวตรวจผลของสกิลงานภาษา (นิยามใน checks ของชุดข้อมูล · เขียนก่อนวัด)."""
    if kind == "names5":
        names = {w for w in re.findall(r"\b[A-Z][a-z]{2,}\b", text)}
        return len(names) >= 5 and bool(THAI.search(text))
    if kind == "has":
        return all(w in text for w in words)
    if kind == "has_not":
        return not any(w in text for w in words) and bool(THAI.search(text))
    if kind == "emoji":
        return bool(EMOJI.search(text)) and all(w in text for w in words)
    raise ValueError(kind)


def same_plans(got: list, want: list) -> bool:
    def key(p):
        return json.dumps(p, ensure_ascii=False, sort_keys=True)

    return Counter(map(key, got)) == Counter(map(key, want))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.spikes.skill_intent_eval")
    ap.add_argument("--server", required=True)
    ap.add_argument("--model-name", default="gemma-4-E2B-it-Q4_K_M")
    ap.add_argument("--data", type=Path, default=DATASET)
    ap.add_argument("--only", default="")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    data = json.loads(a.data.read_text(encoding="utf-8"))
    items = [i for i in data["items"] if i["id"].startswith(a.only)]

    from aipc.cloud.ask import CloudReply
    from aipc.cloud.budget import Budget
    from aipc.cloud.ledger import Ledger
    from aipc.skills.userskills import UserSkills
    from aipc.spikes.app_driver import AppDriver
    from aipc.ui import app

    work = Path(tempfile.mkdtemp(prefix="aipc-skill-intent-"))
    budget, ledger = Budget(work / "usage.json"), Ledger(work / "outbound.json")
    budget.set_limit(5.0)
    forge = app._skill_forge(budget, ledger)
    if forge is None:
        print("ไม่พบ claude")
        return 1

    def no_cloud(q, h):  # H2 วัดสกิล ไม่วัดการตอบคำถาม (สร้างไม่สำเร็จ = แอปให้ Claude ตอบแทน · จดไว้)
        return CloudReply(False, error="ตัววัด H2 ไม่ถาม Claude แทน")

    store = UserSkills(work / "skills")
    drv = AppDriver(a.server, cloud=no_cloud, forge=forge, user_skills=store,
                    model_name=a.model_name, workdir=work)  # fmt: skip
    if not drv.wait_ready():
        print("AI ในเครื่องไม่พร้อม")
        return 1
    rows: list[dict] = []
    res = {"date": datetime.now().isoformat(timespec="minutes"), "server": a.server, "rows": rows}

    def save():
        res["ledger"] = list(reversed(ledger.entries()))
        res["summary"] = summarize(rows, data["criteria"])
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8",
                         newline="\n")  # fmt: skip

    def run_llm(skill_id: str, text: str) -> str:
        m = next(s for s in drv.skills._skills if s.id == skill_id)
        t = drv.run_card(lambda: {"kind": "chat", "llm": True, "prompt": m.prompt, "tools": False,
                                  "badge": {}, "title": ""}, text)  # fmt: skip
        return t.text

    for it in items:
        req = it["request"]
        before_ids = {s.id for s in store.load_all()}
        n_ledger = len(ledger.entries())
        t = drv.run_card(lambda r=req: drv.skills._start_forge(r), req)
        new_ids = [s.id for s in store.load_all() if s.id not in before_ids]
        sid = new_ids[0] if new_ids else ""
        row = {"id": it["id"], "kind": it["kind"], "request": req, "installed": bool(sid),
               "skill_id": sid, "skill_md": store.current_md(sid) if sid else "",
               "forge_seconds": t.seconds, "first_plans": t.plans,
               "first_cards": [c.get("title", "") for c in t.cards]}  # fmt: skip
        new = ledger.entries()[: len(ledger.entries()) - n_ledger]
        row["ledger"] = [{"kind": e["kind"], "ok": e["ok"], "cost": e["cost_usd"],
                          "note": e["note"]} for e in new]  # fmt: skip
        if sid:
            if it["kind"] == "code":
                row["intent_ok"] = same_plans(t.plans, it["expect"])
            else:
                out = run_llm(sid, it["test"])
                row["test_output"] = out
                row["intent_ok"] = check(it["check"], out, it.get("words", []))
                tr = drv.say(it["test"])  # รายงานอย่างเดียว: ข้อความทดสอบไปที่สกิลใหม่ไหม
                row["test_route"] = tr.route
            again = drv.say(req)
            name = next(s.name for s in store.load_all() if s.id == sid)
            row["again_route"] = again.route
            row["again_ok"] = again.route in (f"skill:{sid}",) or again.route.endswith(":" + name)
            rv = it.get("revise")
            if rv:
                n2 = len(ledger.entries())
                t2 = drv.run_card(lambda s=sid, f=rv["feedback"], r=req:
                                  drv.skills.reviseSkill(s, f, r), req)  # fmt: skip
                row["revise_md"] = store.current_md(sid)
                row["revise_version"] = store.info(sid)["version"]
                row["revise_plans"] = t2.plans
                row["revise_cards"] = [c.get("title", "") for c in t2.cards]
                row["revise_ledger"] = [{"ok": e["ok"], "cost": e["cost_usd"]}
                                        for e in ledger.entries()[: len(ledger.entries()) - n2]]
                if it["kind"] == "code":
                    row["revise_ok"] = row["revise_version"] > 1 and same_plans(t2.plans,
                                                                                rv["expect"])
                else:
                    out2 = run_llm(sid, it["test"])
                    row["revise_output"] = out2
                    row["revise_ok"] = row["revise_version"] > 1 and check(
                        rv["check"], out2, rv.get("words", []))
        rows.append(row)
        print(f"{it['id']} ติดตั้ง={row['installed']} {sid or '-':24} ทำตามที่ขอ={row.get('intent_ok')} "
              f"ซ้ำ={row.get('again_route', '-')} แก้={row.get('revise_ok', '-')} "
              f"{t.seconds:.0f}วิ", flush=True)  # fmt: skip
        save()
    print(json.dumps(res["summary"], ensure_ascii=False))
    drv.close()
    return 0


def summarize(rows: list[dict], crit: dict) -> dict:
    inst = [r for r in rows if r["installed"]]
    rev = [r for r in rows if "revise_ok" in r]
    ledger_ok = all(e["ok"] == r["installed"]
                    for r in rows for e in r["ledger"] if e["kind"] == "skill")  # fmt: skip
    s = {
        "installed": [len(inst), len(rows)],
        "intent_ok": [sum(bool(r.get("intent_ok")) for r in rows), len(rows)],
        "again_ok": [sum(bool(r.get("again_ok")) for r in rows), len(rows)],
        "revise_ok": [sum(bool(r["revise_ok"]) for r in rev), len(rev)],
        "ledger_matches_install": ledger_ok,
        "cost_usd": round(sum(e["cost"] for r in rows for e in r["ledger"])
                          + sum(e["cost"] for r in rows for e in r.get("revise_ledger", [])), 4),
    }  # fmt: skip
    s["pass"] = {
        "2.1": s["installed"][0] >= crit["installed_min"],
        "2.2": s["intent_ok"][0] >= crit["intent_min"],
        "2.3": s["again_ok"][0] >= crit["again_min"],
        "2.4": s["revise_ok"][0] >= crit["revise_min"],
        "2.5": ledger_ok,
    }
    return s


if __name__ == "__main__":
    sys.exit(main())
