"""ถามตารางนัด "วันนี้ต้องทำอะไร" (ข้อเสนอ 2026-09-29 หัวข้อ 1 ข้อ 2 · ฟีเจอร์ข้อ 5 ที่ Pakon อนุมัติ 2026-10-01).

ตอบจากไฟล์นัดของผู้ใช้ด้วยโค้ด ไม่ให้ AI เดา · พบ 2026-10-01: "วันนี้มีนัดอะไร" เคยถูกตีเป็นคำขอจดนัดใหม่ชื่อ "มีนัดอะไร"
ต้องเป็นคำถาม (มีคำถามอย่าง อะไร/ไหม/บ้าง/กี่) และพูดถึงนัด/งาน/ตาราง หรือ "ต้องทำอะไร" · ประโยคสั่งจดนัดไม่เข้าข่าย
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

DAYS = {"วันนี้": 0, "พรุ่งนี้": 1, "มะรืน": 2, "มะรืนนี้": 2}
WEEK_WORDS = ("สัปดาห์นี้", "อาทิตย์นี้", "สัปดาห์หน้า", "อาทิตย์หน้า")
ASK = ("อะไร", "ไหม", "มั้ย", "บ้าง", "กี่", "หรือเปล่า", "?")
TOPIC = ("นัด", "ต้องทำ", "ตาราง", "งานอะไร", "ภารกิจ", "กิจกรรม", "เตือนอะไร")
# "มีอะไร" เฉย ๆ นับเฉพาะเมื่อขึ้นต้นด้วยวัน ("พรุ่งนี้มีอะไรบ้าง") · "ข่าวเด่นวันนี้มีอะไรบ้าง" (ชุดสอบจบ B05) ไม่ใช่ถามนัด
WHEN_FIRST = tuple(DAYS) + WEEK_WORDS


@dataclass(frozen=True)
class Query:
    start: date
    days: int  # จำนวนวันที่ครอบคลุม
    label: str


def parse(text: str, today: date) -> Query | None:
    t = re.sub(r"\s+", "", text)
    topic = any(k in t for k in TOPIC) or (t.startswith(WHEN_FIRST) and "มีอะไร" in t)
    if not any(a in t for a in ASK) or not topic:
        return None
    if t.startswith(("เตือน", "จด", "บันทึก", "ตั้ง", "สร้าง")):  # สั่งจดนัด ไม่ใช่ถาม
        return None
    for w in WEEK_WORDS:
        if w in t:
            nxt = "หน้า" in w
            start = today + timedelta(days=7 - today.weekday()) if nxt else today
            end = start + timedelta(days=6 - start.weekday())
            return Query(start, (end - start).days + 1, w)
    for w in sorted(DAYS, key=len, reverse=True):
        if w in t:
            return Query(today + timedelta(days=DAYS[w]), 1, w)
    if "ต้องทำอะไร" in t or "มีนัดอะไร" in t or "นัดของฉัน" in t:
        return Query(today, 1, "วันนี้")
    return None


def items_for(store, q: Query) -> list:
    """นัดในช่วงวันของคำถาม (รวมที่เตือนไปแล้ว · เรียงตามเวลา)."""
    from dataclasses import replace

    from aipc.skills.when import matches

    out = []
    for r in store.items:
        if getattr(r, "repeat", ""):  # นัดซ้ำ: ทุกวันในช่วงที่ตรงกฎ (ตั้งแต่ตอนที่จด) · วันที่ผ่านแล้วขึ้น ✓
            when = r.when.astimezone()
            since = r.created.astimezone()
            for i in range(q.days):
                at = datetime.combine(q.start + timedelta(days=i), when.timetz())
                if at >= since and matches(r.repeat, at.date()):
                    out.append(replace(r, when=at))
            continue
        d = r.when.astimezone().date() if isinstance(r.when, datetime) else r.when
        if q.start <= d < q.start + timedelta(days=q.days):
            out.append(r)
    return sorted(out, key=lambda r: r.when)
