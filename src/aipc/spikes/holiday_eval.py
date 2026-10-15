"""วัดเกณฑ์ข้อ 2 ของการ์ด 0033: คำถามวันหยุดไทย 15 ข้อ ต้องถูก 15/15.

ชุดวัด tests/data/holiday_eval/ (holidays.ics + set.json) เขียนโดยผู้ช่วยอีกตัวที่ไม่เห็นโค้ด
และ commit ก่อนรันครั้งแรก (H9) · ห้ามแก้ชุดวัดให้ผ่าน · ถามผ่านทางเดียวกับที่ผู้ใช้พิมพ์ (SkillsController.handle) ·
ตัวดึงปลอมคืนไฟล์ .ics ของชุดวัด · แต่ละข้อใช้ "ตอนนี้" ของข้อนั้น

    python -m aipc.spikes.holiday_eval [--set tests/data/holiday_eval/set.json] [--out ผล.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BKK = timezone(timedelta(hours=7))
MONTH_NAMES = "ม.ค. ก.พ. มี.ค. เม.ย. พ.ค. มิ.ย. ก.ค. ส.ค. ก.ย. ต.ค. พ.ย. ธ.ค.".split()
MONTHS = {m: i + 1 for i, m in enumerate(MONTH_NAMES)}
DATE = re.compile(r"^\S+ (\d{1,2}) (\S+) (\d{4})")


def _date(line: str) -> str:
    m = DATE.match(line)
    return "" if m is None else date(int(m[3]) - 543, MONTHS[m[2]], int(m[1])).isoformat()


def read_card(kind: str, card: dict) -> dict | list:
    """อ่านการ์ดคำตอบเป็นรูปเดียวกับเฉลย."""
    title, lines = card.get("title", ""), card.get("lines", [])
    if kind == "range":
        return [{"date": _date(x), "name": x.split(" · ", 1)[1]} for x in lines if " · " in x]
    if title.startswith("ยังไม่มีข้อมูล"):
        return {"no_data": True}
    first = lines[0] if lines else ""
    if kind == "next":
        name = re.sub(r"^(วันหยุดถัดไป|วันนี้เป็นวันหยุด): ", "", title)
        m = re.search(r"อีก (\d+) วัน", first)
        return {"name": name, "date": _date(first), "days": int(m[1]) if m else 0}
    m = re.match(r"^อีก (\d+) วันถึง(.+)$", title)
    name, days = (m[2], int(m[1])) if m else (title.removeprefix("วันนี้คือ"), 0)
    kind_text = "holiday" if "วันหยุดราชการ" in first else "observance"
    return {"name": name, "date": _date(first), "days": days, "kind": kind_text}


def run_item(item: dict, ics: bytes) -> dict:
    from aipc.skills import gcal
    from aipc.ui.backend import SkillsController

    now = datetime.fromisoformat(item["now"]).replace(tzinfo=BKK)
    with tempfile.TemporaryDirectory(prefix="aipc-holiday-eval-") as tmp:
        root = Path(tmp)
        hol = gcal.GoogleCalendar(
            root / "link.json",
            root / "hol.json",
            fetcher=lambda _link: ics,
            clock=lambda: now,
            tz=BKK,
            source="holidays",
            future=gcal.HOLIDAY_FUTURE,
            stale_after=gcal.HOLIDAY_STALE,
            sent=gcal.HOLIDAY_SENT,
            classify=True,
        )
        sync = hol.connect(gcal.HOLIDAYS_TH)
        s = SkillsController(
            reminders_path=root / "r.json", clock=lambda: now, run_timer=False, holidays=hol
        )
        card = s.handle(item["q"])
    got = read_card(item["type"], card)
    want = item["expect"]
    if item["type"] == "range":
        ok = sorted(got, key=json.dumps) == sorted(want, key=json.dumps)
    else:
        ok = got == want
    return {"id": item["id"], "now": item["now"], "q": item["q"], "ok": ok and sync.ok,
            "title": card.get("title", ""), "lines": card.get("lines", []), "got": got,
            "want": want}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--set", default="tests/data/holiday_eval/set.json")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    if datetime(2026, 12, 1, 12).astimezone().utcoffset() != timedelta(hours=7):
        print("เขตเวลาของเครื่องไม่ใช่ UTC+7 · ตั้งเป็น Asia/Bangkok ก่อนวัด", file=sys.stderr)
        return 2
    path = Path(a.set)
    data = json.loads(path.read_text(encoding="utf-8"))
    ics = (path.parent / "holidays.ics").read_bytes()
    rows = [run_item(it, ics) for it in data["items"]]
    passed = sum(r["ok"] for r in rows)
    for r in rows:
        print(f"{'✓' if r['ok'] else '✗'} {r['id']} {r['now']} {r['q']}")
        if not r["ok"]:
            print(f"    ได้: {r['got']}\n    เฉลย: {r['want']}")
    print(f"ผ่าน {passed}/{len(rows)}")
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"passed": passed, "total": len(rows), "rows": rows},
                                  ensure_ascii=False, indent=1), encoding="utf-8")  # fmt: skip
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
