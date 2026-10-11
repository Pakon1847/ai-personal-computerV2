"""การ์ด 0022 ส่วน 1: AI ในเครื่องส่งต่อ Claude ถูกจังหวะไหม · ขับแอปตัวจริง (app_driver) ทีละกรณี.

    python -m aipc.spikes.hybrid_eval --data tests/data/hybrid_h1.json \
        --server http://127.0.0.1:18080 --out <ไฟล์.json> [--stub-cloud]

--stub-cloud = Claude ปลอม (ตอบ "[stub]" ไม่เสียเงิน) ใช้กับชุดพัฒนา D1 ตอนปรับกฎ ·
ไม่ใส่ = Claude จริงผ่าน aipc.ui.app._cloud_client (งบ/บันทึกส่งออกอยู่ในโฟลเดอร์ชั่วคราวของการวัด)

รายงานคู่: กฎยอมแพ้เดิม (ก่อนการ์ด 0022) vs กฎปัจจุบัน บนคำตอบชุดเดียวกันของ AI ในเครื่อง
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from aipc.cloud import ask

# กฎยอมแพ้ก่อนการ์ด 0022 (คัดลอกไว้เทียบ · ห้ามแก้)
OLD_MAX, OLD_WORDS = 160, ("ไม่รู้", "ไม่ทราบ", "ไม่มีข้อมูล", "ไม่สามารถให้ข้อมูล", "ไม่สามารถตอบ",
                           "ไม่สามารถบอก", "ข้อมูลสด")  # fmt: skip
OLD_NOT = ("ผิดกฎหมาย", "อันตราย")


def old_gave_up(text: str) -> bool:
    t = " ".join(text.split())
    if not t or len(t) > OLD_MAX or any(w in t for w in OLD_NOT):
        return False
    return any(w in t for w in OLD_WORDS)


def stub_cloud(question, history):
    return ask.CloudReply(True, "[stub] คำตอบจาก Claude ปลอม", seconds=0.0)


def _route_ok(r: dict, names: dict) -> bool:
    """สกิลที่คาดไว้ (id) ตรงกับทางที่แอปไป: skill:<id> (AI เลือก) หรือ rule:<ชนิด>:<ชื่อสกิล> (กฎ)."""
    return bool(r.get("skill")) and (r["route"] == f"skill:{r['skill']}"
                                     or r["route"].endswith(":" + names.get(r["skill"], "?")))


def summarize(rows: list[dict], crit: dict) -> dict:
    from aipc.skills import manifest

    names = {m.id: m.name for m in manifest.load_builtin()}

    def n(sel):
        return sum(1 for r in rows if sel(r))

    def sent(r):
        return r["route"] == "cloud" or bool(r["forwarded"])

    def old(r):  # กฎเดิมบนคำตอบเดียวกัน (AI เลือก ask-cloud เอง หรือกฎยอมแพ้เดิมจับได้)
        return r["local_tool"] == "ask-cloud" or (not r["local_tool"] and r["old_rule"])

    g = {k: [r for r in rows if r["group"] == k] for k in "LKS"}
    s = {
        "L": [sum(map(sent, g["L"])), len(g["L"])],
        "L_multi": [n(lambda r: r["group"] == "L" and r["multi"] and sent(r)),
                    sum(r["multi"] for r in g["L"])],
        "K_wrong": [sum(map(sent, g["K"])), len(g["K"])],
        "S_cloud": [sum(map(sent, g["S"])), len(g["S"])],
        "S_route_ok": [sum(_route_ok(r, names) for r in g["S"]), len(g["S"])],
        "cloud_ok": [n(lambda r: r["route"] == "cloud" and r.get("cloud_ok")), n(sent)],
        "old_rule_L": sum(map(old, g["L"])),
        "old_rule_K": sum(map(old, g["K"])),
    }  # fmt: skip
    secs = [r["cloud_seconds"] for r in rows if r.get("cloud_seconds")]
    s["cloud_seconds_median"] = statistics.median(secs) if secs else None
    s["cloud_cost"] = round(sum(r.get("cloud_cost") or 0 for r in rows), 4)
    if crit:
        s["pass"] = {
            "1.1": s["L"][0] >= crit["L_min"] and s["L_multi"][0] >= crit["L_multi_min"],
            "1.2": s["K_wrong"][0] <= crit["K_wrong_max"],
            "1.3": s["S_cloud"][0] <= crit["S_cloud_max"],
            "1.4": not s["cloud_ok"][1]
            or s["cloud_ok"][0] / s["cloud_ok"][1] >= crit["cloud_ok_min"],
            "1.5": all(r.get("ledger_match", True) for r in rows),
        }  # fmt: skip
    return s


def _save(path: Path, res: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.spikes.hybrid_eval")
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--server", required=True)
    ap.add_argument("--model-name", default="gemma-4-E2B-it-Q4_K_M")  # เท่ากับแอปบน Pi
    ap.add_argument("--stub-cloud", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    data = json.loads(a.data.read_text(encoding="utf-8"))
    items = [i for i in data["items"] if i["id"].startswith(a.only)]
    from aipc.spikes.app_driver import AppDriver

    work = Path(tempfile.mkdtemp(prefix="aipc-hybrid-eval-"))
    ledger = None
    if a.stub_cloud:
        cloud = stub_cloud
    else:
        from aipc.cloud.budget import Budget
        from aipc.cloud.ledger import Ledger
        from aipc.ui import app

        budget, ledger = Budget(work / "usage.json"), Ledger(work / "outbound.json")
        budget.set_limit(5.0)
        real = app._cloud_client(budget, ledger)
        if real is None:
            print("ไม่พบ claude")
            return 1

        def cloud(question, history):  # ตัวจริงของแอป + จดเวลาที่ Claude ใช้
            r = real(question, history)
            last["seconds"] = r.seconds
            return r

    last: dict = {}

    def forge_stub(request, **kw):  # H1 ไม่สร้างสกิลจริง · ถูกเรียก = จดว่า AI ขอสร้างสกิล
        from aipc.skills import forge

        return forge.Proposal(False, request, errors=["ตัววัด H1 ไม่สร้างสกิล"])

    from aipc.skills.userskills import UserSkills

    drv = AppDriver(a.server, cloud=cloud, forge=forge_stub,
                    user_skills=UserSkills(work / "skills"), model_name=a.model_name,
                    workdir=work)  # fmt: skip
    if not drv.wait_ready():
        print("AI ในเครื่องไม่พร้อม")
        return 1
    rows = []
    res = {"data": str(a.data), "server": a.server, "stub_cloud": a.stub_cloud,
           "date": datetime.now().isoformat(timespec="minutes"), "rows": rows}  # fmt: skip
    for it in items:
        hist = data.get("histories", {}).get(it.get("history", ""), [])
        before = len(ledger.entries()) if ledger else 0
        last.clear()
        t = drv.say(it["q"], hist)
        stripped = drv.chat._FAKE_LABEL.sub("", t.local_text)
        row = {"id": it["id"], "group": it["group"], "multi": bool(hist), "q": it["q"],
               "skill": it.get("skill", ""), "route": t.route, "forwarded": t.forwarded,
               "local_tool": t.local_tool, "local_text": t.local_text, "raw": t.raw,
               "local_chars": len(stripped),
               "old_rule": old_gave_up(stripped), "new_rule": ask.local_gave_up(stripped),
               "text": t.text, "note": t.note, "seconds": t.seconds}  # fmt: skip
        if t.route == "cloud" or t.forwarded:
            row["cloud_ok"] = t.route == "cloud" and bool(t.text)
            row["cloud_seconds"] = last.get("seconds")
            if ledger:
                new = ledger.entries()[: len(ledger.entries()) - before]
                if new:
                    e = new[0]
                    match = e["sent"] == ask.build_input(it["q"], hist)
                    row.update(cloud_cost=e["cost_usd"], ledger_ok=e["ok"], ledger_match=match)
                else:
                    row["ledger_match"] = False
        if t.route == "infra" or t.note == drv.chat.NOTE["crashed"]:
            # การเชื่อมต่อไป llama-server หลุด (tunnel) ไม่ใช่ผลของระบบ → ทั้งรอบใช้ไม่ได้ ต้องรันใหม่ทั้งชุด
            res["void"] = f"{it['id']}: {t.note}"
            _save(a.out, res)
            print("รอบนี้ใช้ไม่ได้:", res["void"])
            drv.close()
            return 2
        rows.append(row)
        print(f"{row['id']} {row['group']}{'m' if row['multi'] else ' '} → {row['route']:24} "
              f"tool={row['local_tool'] or '-':10} เดิม={int(row['old_rule'])} "
              f"ใหม่={int(row['new_rule'])} {row['local_chars']:4}ตัว {row['seconds']:6.1f}วิ · "
              f"{stripped[:70]!r}", flush=True)  # fmt: skip
        res["summary"] = summarize(rows, data.get("criteria", {}))
        _save(a.out, res)
    if ledger:
        res["ledger"] = list(reversed(ledger.entries()))
        _save(a.out, res)
    print(json.dumps(res["summary"], ensure_ascii=False))
    drv.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
