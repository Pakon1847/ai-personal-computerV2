"""วัดเกณฑ์ข้อ 2 ของการ์ด 0037: ถามนัดละเอียดขึ้น 30 ข้อ.

ตอบได้ 20 ข้อ ต้องถูก 20/20 · ข้อหลอก 10 ข้อ ต้องไม่ถูกตอบเป็นคำถามนัด 10/10 ·

ชุดวัด tests/data/agenda_eval/set.json เขียนโดยผู้ช่วยอีกตัวที่ไม่เห็นโค้ด และ commit ก่อนรันครั้งแรก (H9) ·
ใช้ปฏิทินและนัดในเครื่องชุดเดียวกับการ์ด 0014 (tests/data/gcal_eval) · ถามผ่าน SkillsController.handle

    python -m aipc.spikes.agenda_eval [--set tests/data/agenda_eval/set.json] [--out ผล.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from aipc.spikes.gcal_eval import BKK, LINK, parse_lines


def run_item(item: dict, ics: bytes, local: list[dict]) -> dict:
    from aipc.skills import gcal, reminders
    from aipc.ui.backend import SkillsController

    now = datetime.fromisoformat(item["now"]).replace(tzinfo=BKK)
    with tempfile.TemporaryDirectory(prefix="aipc-agenda-eval-") as tmp:
        root = Path(tmp)
        cal = gcal.GoogleCalendar(
            root / "link.json", root / "events.json", fetcher=lambda _link: ics,
            clock=lambda: now, tz=BKK,
        )  # fmt: skip
        sync = cal.connect(LINK)
        store = reminders.ReminderStore(root / "reminders.json")
        created = datetime(2026, 10, 1, tzinfo=BKK)
        for r in local:
            when = datetime.fromisoformat(r["when"]).replace(tzinfo=BKK)
            rem = reminders.Reminder(r["what"], when, created=created, repeat=r.get("repeat", ""))
            store.add(rem, created)
        s = SkillsController(
            reminders_path=root / "reminders.json", clock=lambda: now, run_timer=False, gcal=cal
        )
        card = s.handle(item["q"])
    kind = item["type"]
    agenda = card.get("route") == "agenda"
    row = {
        "id": item["id"],
        "now": item["now"],
        "q": item["q"],
        "type": kind,
        "title": card.get("title", ""),
        "lines": card.get("lines", []),
        "route": card.get("route", ""),
    }
    if kind == "negative":
        row["ok"] = not agenda
        return row
    if kind == "invalid":
        row["ok"] = agenda and row["title"].startswith("ไม่มีวันที่")
        return row
    got, odd = parse_lines(card.get("lines", []))
    want = [(e["date"], e["time"], e["what"], e["source"]) for e in item["expect"]]
    row["missing"] = list((Counter(want) - Counter(got)).elements())
    row["extra"] = list((Counter(got) - Counter(want)).elements())
    row["unparsed"] = odd
    row["ok"] = sync.ok and agenda and not row["missing"] and not row["extra"] and not odd
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--set", default="tests/data/agenda_eval/set.json")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    if datetime(2026, 12, 1, 12).astimezone().utcoffset() != timedelta(hours=7):
        print("เขตเวลาของเครื่องไม่ใช่ UTC+7 · ตั้งเป็น Asia/Bangkok ก่อนวัด", file=sys.stderr)
        return 2
    path = Path(a.set)
    data = json.loads(path.read_text(encoding="utf-8"))
    ics = (path.parent / data["calendar"]).read_bytes()
    local = json.loads((path.parent / data["local_reminders_from"]).read_text(encoding="utf-8"))
    rows = [run_item(it, ics, local.get("local_reminders", [])) for it in data["items"]]
    answerable = [r for r in rows if r["type"] != "negative"]
    negative = [r for r in rows if r["type"] == "negative"]
    for r in rows:
        print(f"{'✓' if r['ok'] else '✗'} {r['id']} [{r['type']}] {r['now']} {r['q']}")
        if not r["ok"]:
            print(f"    title: {r['title']} · route: {r['route']}")
            for label in ("missing", "extra", "unparsed"):
                if r.get(label):
                    print(f"    {label}: {r[label]}")
    a_ok, n_ok = sum(r["ok"] for r in answerable), sum(r["ok"] for r in negative)
    print(f"ตอบได้ถูก {a_ok}/{len(answerable)} · ข้อหลอกไม่เข้า {n_ok}/{len(negative)}")
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        summary = {
            "answerable": [a_ok, len(answerable)],
            "negative": [n_ok, len(negative)],
            "rows": rows,
        }
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if a_ok == len(answerable) and n_ok == len(negative) else 1


if __name__ == "__main__":
    raise SystemExit(main())
