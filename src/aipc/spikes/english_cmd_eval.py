"""วัดเกณฑ์ C1 ของการ์ด 0039: คำสั่งภาษาอังกฤษ → ช่องข้อมูลที่ระบบเข้าใจ.

ชุดวัด tests/data/english_cmd/set.json เขียนโดยผู้ช่วยตัวใหม่ที่ไม่เห็นโค้ดและไม่ใช้เครื่องมือ ·
commit ก่อนรันครั้งแรก (H9) · ทุกข้อใช้ "ตอนนี้" = NOW · แปลงด้วย english.to_thai
แล้วอ่านช่องข้อมูลจากตัวแปลไทยเดิมตามลำดับเดียวกับ SkillsController._handle

ผ่านเมื่อ: คำสั่งถูกทุกช่อง ≥ 90% · ข้อที่ไม่ใช่คำสั่ง (kind = none) ถูกแปลงเป็นคำสั่ง 0 ข้อ

เฉลยต่อข้อ (ช่องตามชนิด):
    open    target  = site:<youtube|gmail|google|wikipedia|maps|facebook|instagram|calendar|drive>
                      | app:<browser|terminal|filemanager>
                      | page:<workspace|calendar|files|skills|privacy|health|settings>
    volume  volume  = mute | unmute | up | down | set:<0–100>
    remind  what (คำของผู้ใช้) · date YYYY-MM-DD | null · time HH:MM | null ·
            repeat "" | daily | weekdays | weekends | weekly:<0–6 จันทร์ = 0>
    cancel  what (คำที่ใช้หานัด) | all
    agenda  start YYYY-MM-DD · days
    files   range = today | yesterday | this_week
    time · next · none  ไม่มีช่องเพิ่ม

เทียบคำของผู้ใช้ (what): ตัวพิมพ์เล็ก · ตัดเครื่องหมายวรรคตอน · ตัด the/my/a/an นำหน้า · cancel เทียบแบบไม่มีช่องว่าง
(ตัวลบนัดจริงหานัดแบบไม่สนช่องว่าง)

    python -m aipc.spikes.english_cmd_eval [--set tests/data/english_cmd/set.json] [--out ผล.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

NOW = datetime(2026, 10, 21, 10, 0)  # วันพุธ
SET = Path("tests/data/english_cmd/set.json")
VOLUME = {"mute": "mute", "unmute": "unmute"}


def slots(text: str, now: datetime = NOW) -> dict:
    """ช่องข้อมูลที่ระบบเข้าใจจากประโยคอังกฤษ · ไม่แปลง = {"kind": "none"}."""
    from aipc.skills import agenda, command, english, when
    from aipc.skills.fileintent import file_time

    th = english.to_thai(text)
    if th is None:
        return {"kind": "none"}
    out: dict = {"thai": th}
    if q := agenda.parse(th, now.date()):
        return out | {"kind": "agenda", "start": q.start.isoformat(), "days": q.days}
    if agenda.asks_time(th):
        return out | {"kind": "time"}
    if (key := agenda.cancel_target(th)) is not None:
        return out | {"kind": "cancel", "what": key or "all"}
    if agenda.asks_next(th):
        return out | {"kind": "next"}
    if label := file_time(th):
        return out | {"kind": "files", "range": label}
    if c := command.parse(th):
        p = c.plan
        if p.action == "open_url":
            return out | {"kind": "open", "target": "site:" + p.params["site"]}
        if p.action == "open_app":
            return out | {"kind": "open", "target": "app:" + p.params["app"]}
        if p.action == "open_page":
            return out | {"kind": "open", "target": "page:" + p.params["page"]}
        if p.action in VOLUME:
            return out | {"kind": "volume", "volume": VOLUME[p.action]}
        if p.action == "change_volume":
            return out | {"kind": "volume", "volume": "up" if p.params["step"] > 0 else "down"}
        if p.action == "set_volume":
            return out | {"kind": "volume", "volume": f"set:{p.params['percent']}"}
        return out | {"kind": "other", "action": p.action}
    if th.startswith("เตือน"):
        r = when.parse(th, now)
        return out | {
            "kind": "remind",
            "what": r.what,
            "date": r.at.date().isoformat() if r.at else None,
            "time": r.at.strftime("%H:%M") if r.at else None,
            "repeat": r.repeat,
        }
    return out | {"kind": "other"}


def norm(s: str | None) -> str:
    t = re.sub(r"[^\w\s]", " ", (s or "").lower())
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"^(?:(?:the|my|a|an) )+", "", t)


FIELDS = {
    "open": ("target",),
    "volume": ("volume",),
    "remind": ("what", "date", "time", "repeat"),
    "cancel": ("what",),
    "agenda": ("start", "days"),
    "files": ("range",),
}


def compare(gold: dict, got: dict) -> list[str]:
    """ช่องที่ไม่ตรง · [] = ถูกทุกช่อง."""
    if gold["kind"] != got["kind"]:
        return ["kind"]
    wrong = []
    for f in FIELDS.get(gold["kind"], ()):
        g, s = gold.get(f), got.get(f)
        if f == "what" and gold["kind"] == "cancel":
            g, s = norm(g).replace(" ", ""), norm(s).replace(" ", "")
        elif f == "what":
            g, s = norm(g), norm(s)
        elif f == "repeat":
            g, s = g or "", s or ""
        if g != s:
            wrong.append(f)
    return wrong


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=Path, default=SET)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    items = json.loads(a.set.read_text(encoding="utf-8"))["items"]
    rows = []
    for it in items:
        got = slots(it["text"])
        gold = {k: v for k, v in it.items() if k not in ("id", "text", "note")}
        wrong = compare(gold, got)
        rows.append({"id": it["id"], "text": it["text"], "gold": gold, "got": got,
                     "ok": not wrong, "wrong": wrong})  # fmt: skip
        mark = "✓" if not wrong else "✗ " + ",".join(wrong)
        print(f"{mark:14} {it['id']:5} {it['text'][:60]:60} → {got.get('thai', '-')}")
    cmds = [r for r in rows if r["gold"]["kind"] != "none"]
    negs = [r for r in rows if r["gold"]["kind"] == "none"]
    ok = sum(r["ok"] for r in cmds)
    converted = sum(r["got"]["kind"] != "none" for r in negs)
    pct = 100 * ok / len(cmds) if cmds else 0.0
    passed = len(cmds) >= 40 and len(negs) >= 20 and pct >= 90 and converted == 0
    print(f"คำสั่งถูกทุกช่อง {ok}/{len(cmds)} = {pct:.1f}% (เกณฑ์ ≥ 90%) · "
          f"ไม่ใช่คำสั่งแต่ถูกแปลง {converted}/{len(negs)} (เกณฑ์ 0)")  # fmt: skip
    print("ผ่าน" if passed else "ไม่ผ่าน")
    if a.out:
        summary = {"now": NOW.isoformat(), "commands": len(cmds), "commands_ok": ok,
                   "percent": round(pct, 1), "negatives": len(negs),
                   "negatives_converted": converted, "passed": passed}  # fmt: skip
        data = {"summary": summary, "rows": rows}
        a.out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
