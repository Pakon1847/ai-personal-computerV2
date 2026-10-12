"""วัดว่า AI ในเครื่อง "ทำให้เลย" หรือ "ถามกลับ" (การ์ด 0023).

    python -m aipc.spikes.askback_eval --data tests/data/askback_h4.json \
        --server http://127.0.0.1:18080 [--rule "<ประโยคที่เพิ่ม>"] --out <ไฟล์.json>

ขับแอปตัวจริง (aipc.spikes.app_driver) · Claude ปลอม (จดว่าถูกส่ง ไม่เสียเงิน) ·
--rule = ต่อท้าย catalog.RULES ในโปรเซสนี้เท่านั้น (ไม่แก้ไฟล์) · ไม่ใส่ = prompt ที่ใช้อยู่

ตัดสินอัตโนมัติ (ประกาศในการ์ด 0023 หัวข้อ 8 ก่อนรัน):
- O ผ่าน = มีงานที่ขอจริง: บรรทัดที่ไม่ใช่คำถาม ≥ min_lines หรือ ตัวอักษรในบรรทัดที่ไม่ใช่คำถาม ≥ min_chars
- N ผ่าน = ถามหาสิ่งที่ขาด (มี ? หรือ กรุณา/รบกวน/โปรด + พูดถึงข้อความ/ไฟล์/โค้ด…) และไม่ยาวเกิน 400 ตัวอักษร
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

ASK_WORDS = ("กรุณา", "รบกวน", "โปรด", "ช่วยส่ง", "ช่วยวาง", "ช่วยระบุ", "ช่วยบอก")
MISSING = ("ข้อความ", "ประโยค", "โค้ด", "ไฟล์", "อีเมล", "บทความ", "ย่อหน้า", "วาง", "ส่ง", "แนบ")


def work_lines(text: str) -> list[str]:
    """บรรทัดที่เป็นเนื้องาน (ไม่ใช่คำถามกลับ)."""
    out = []
    for line in text.splitlines():
        s = line.strip().strip("*#-• ").strip()
        if s and not s.rstrip(" )").endswith(("?", "？")):
            out.append(s)
    return out


def judge(item: dict, text: str) -> bool:
    if item["group"] == "O":
        c = item["check"]
        lines = work_lines(text)
        if "min_lines" in c:
            return len(lines) >= c["min_lines"]
        return sum(len(s) for s in lines) >= c["min_chars"]
    asks = "?" in text or "？" in text or any(w in text for w in ASK_WORDS)
    return asks and any(w in text for w in MISSING) and len(text) <= 400


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--server", default="http://127.0.0.1:18080")
    p.add_argument("--rule", default="")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)

    from aipc.cloud.ask import CloudReply
    from aipc.skills import catalog
    from aipc.spikes.app_driver import AppDriver

    if a.rule:
        catalog.RULES = catalog.RULES + " · " + a.rule
    data = json.loads(Path(a.data).read_text(encoding="utf-8"))
    asked: list[str] = []

    def cloud(q, h):
        asked.append(q)
        return CloudReply(True, text="[Claude ปลอม]", cost_usd=0.0)

    d = AppDriver(a.server, cloud=cloud, workdir=Path(tempfile.mkdtemp(prefix="askback-")))
    if not d.wait_ready(300):
        print("AI ในเครื่องไม่พร้อม", file=sys.stderr)
        return 2
    rows = []
    for it in data["items"]:
        n = len(asked)
        t = d.say(it["q"], timeout=300)
        if t.route in ("infra", "error"):
            print(f"{it['id']} หยุด: {t.route} {t.note}", file=sys.stderr)
            return 2
        text = t.text or ""
        row = {"id": it["id"], "group": it["group"], "q": it["q"], "route": t.route, "text": text,
               "cloud": asked[n:], "seconds": t.seconds, "pass": judge(it, text)}  # fmt: skip
        rows.append(row)
        first = re.sub(r"\s+", " ", text)[:70]
        mark = "✓" if row["pass"] else "✗"
        head = f"{it['id']} {it['group']} {mark} {t.route:<24}"
        print(f"{head} {t.seconds:5.1f}วิ · {first}", flush=True)
    d.close()
    summary = {g: [sum(r["pass"] for r in rows if r["group"] == g),
                   sum(1 for r in rows if r["group"] == g)] for g in ("O", "N")}  # fmt: skip
    summary["cloud"] = sum(1 for r in rows if r["cloud"])
    out = {"data": a.data, "rule": a.rule, "summary": summary, "rows": rows}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
