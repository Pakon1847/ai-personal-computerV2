"""วัดเกณฑ์ข้อ 2 ของการ์ด 0014: ถามตารางนัดที่มีทั้งนัด Google และนัดในเครื่อง ต้องได้ช่วงวันและรายการถูก 20/20.

ชุดวัด tests/data/gcal_eval/ (calendar.ics + set.json) เขียนโดยผู้ช่วยอีกตัวที่ไม่เห็นโค้ด
และ commit ก่อนรันครั้งแรก (H9) ·
ห้ามแก้ชุดวัดให้ผ่าน · รันผ่านทางเดียวกับที่ผู้ใช้พิมพ์ (SkillsController.handle)
ด้วยตัวดึงปลอมที่คืนไฟล์ .ics ของชุดวัด ·
แต่ละข้อใช้เวลา "ตอนนี้" ของข้อนั้น (ดึงปฏิทินตอนนั้น = ช่วงสำเนา −1/+60 วันของข้อนั้น)

    python -m aipc.spikes.gcal_eval [--set tests/data/gcal_eval/set.json] [--out ผล.json]

ต้องรันบนเครื่องที่ตั้งเขตเวลาเป็น Asia/Bangkok (นัดในเครื่องใช้เขตเวลาของเครื่อง) · ไม่ใช่ = หยุดและบอก (H5)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BKK = timezone(timedelta(hours=7))
LINK = "https://calendar.google.com/calendar/ical/eval%40example.com/private-0000eval/basic.ics"
MONTH_NAMES = "ม.ค. ก.พ. มี.ค. เม.ย. พ.ค. มิ.ย. ก.ค. ส.ค. ก.ย. ต.ค. พ.ย. ธ.ค.".split()
MONTHS = {m: i + 1 for i, m in enumerate(MONTH_NAMES)}
# บรรทัดนัดในการ์ด เช่น "✓ ศ. 16 ต.ค. 2569 · 09:00 น. · โทรหาหมอ · Google"
# หรือ "จ. 19 ต.ค. 2569 · ทั้งวัน · ไปเชียงใหม่ · Google" (นัดในเครื่องไม่มีป้าย Google)
LINE = re.compile(
    r"^(?:✓ )?\S+ (\d{1,2}) (\S+) (\d{4}) · (ทั้งวัน|\d{2}:\d{2} น\.) · "
    r"(.+?)(?: · ซ้ำ.*?)?( · Google)?$"
)
NOT_ITEM = ("ปฏิทิน Google:", "จดนัดได้เลย", "นัดจากปฏิทิน Google")


def parse_lines(lines: list[str]) -> tuple[list[tuple], list[str]]:
    """(รายการนัดที่อ่านได้, บรรทัดที่อ่านไม่ออก) · ตัดบรรทัดบอกที่มา/คำแนะนำออก."""
    items, odd = [], []
    for line in lines:
        if line.startswith(NOT_ITEM):
            continue
        m = LINE.match(line)
        if m is None:
            odd.append(line)
            continue
        d = date(int(m[3]) - 543, MONTHS[m[2]], int(m[1]))
        t = "all-day" if m[4] == "ทั้งวัน" else m[4][:5]
        items.append((d.isoformat(), t, m[5], "google" if m[6] else "local"))
    return items, odd


def run_item(item: dict, ics: bytes, local: list[dict]) -> dict:
    from aipc.skills import gcal, reminders
    from aipc.ui.backend import SkillsController

    now = datetime.fromisoformat(item["now"]).replace(tzinfo=BKK)
    with tempfile.TemporaryDirectory(prefix="aipc-gcal-eval-") as tmp:
        root = Path(tmp)
        cal = gcal.GoogleCalendar(
            root / "link.json",
            root / "events.json",
            fetcher=lambda _link: ics,
            clock=lambda: now,
            tz=BKK,
        )
        sync = cal.connect(LINK)
        store = reminders.ReminderStore(root / "reminders.json")
        created = datetime(2026, 10, 1, tzinfo=BKK)
        for r in local:
            when = datetime.fromisoformat(r["when"]).replace(tzinfo=BKK)
            rem = reminders.Reminder(r["what"], when, created=created, repeat=r.get("repeat", ""))
            store.add(rem, created)
        # สร้างตัวคุมหลังมีนัดแล้ว = เหมือนเข้าสู่ระบบตอน "now" (นัดซ้ำที่ผ่านไปเลื่อนไปครั้งถัดไปเอง)
        s = SkillsController(
            reminders_path=root / "reminders.json", clock=lambda: now, run_timer=False, gcal=cal
        )
        card = s.handle(item["q"])
    got, odd = parse_lines(card.get("lines", []))
    want = [(e["date"], e["time"], e["what"], e["source"]) for e in item["expect"]]
    missing = list((Counter(want) - Counter(got)).elements())
    extra = list((Counter(got) - Counter(want)).elements())
    ok = sync.ok and not missing and not extra and not odd
    return {"id": item["id"], "now": item["now"], "q": item["q"], "ok": ok, "sync_ok": sync.ok,
            "title": card.get("title", ""), "lines": card.get("lines", []), "missing": missing,
            "extra": extra, "unparsed": odd}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--set", default="tests/data/gcal_eval/set.json")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    offset = datetime(2026, 12, 1, 12).astimezone().utcoffset()
    if offset != timedelta(hours=7):
        print(f"เขตเวลาของเครื่องไม่ใช่ UTC+7 ({offset}) · ตั้งเป็น Asia/Bangkok ก่อนวัด", file=sys.stderr)
        return 2
    path = Path(a.set)
    data = json.loads(path.read_text(encoding="utf-8"))
    ics = (path.parent / "calendar.ics").read_bytes()
    rows = [run_item(it, ics, data.get("local_reminders", [])) for it in data["items"]]
    passed = sum(r["ok"] for r in rows)
    for r in rows:
        mark = "✓" if r["ok"] else "✗"
        print(f"{mark} {r['id']} {r['now']} {r['q']}")
        for label in ("missing", "extra", "unparsed"):
            if r[label]:
                print(f"    {label}: {r[label]}")
    print(f"ผ่าน {passed}/{len(rows)}")
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"passed": passed, "total": len(rows), "rows": rows},
                                  ensure_ascii=False, indent=1), encoding="utf-8")  # fmt: skip
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
