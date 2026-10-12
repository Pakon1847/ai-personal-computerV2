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


# ถามเวลาตอนนี้ (สำรวจบน Pi 5 2026-10-12: "ตอนนี้กี่โมง" AI ในเครื่องตอบว่าไม่รู้
# → ส่งต่อ Claude ทั้งที่นาฬิกาอยู่ในเครื่อง)
# system prompt มีแค่วันที่ (ไม่ใส่เวลา เพื่อให้แคชใช้ได้ทั้งวัน) → ตอบจากนาฬิกาเครื่องด้วยโค้ด
# ต้องเป็นประโยคถามเวลาทั้งประโยค · "นัดพรุ่งนี้กี่โมง" "ร้านเปิดกี่โมง" "ญี่ปุ่นตอนนี้กี่โมง" ไม่เข้าข่าย
_TIME_TH = re.compile(
    r"(ตอนนี้|เดี๋ยวนี้|ขณะนี้)?(เวลา)?(กี่โมง|กี่ทุ่ม|กี่นาฬิกา|เท่าไหร่|เท่าไร)(แล้ว)?"
    r"(ครับ|คับ|คะ|ค่ะ|จ้ะ|จ้า|นะ|อะ|เหรอ)*[?？]*"
)
_TIME_EN = re.compile(r"(what('s|is)?(the)?timeisit(now)?|what('s|is)thetime(now)?|timenow)[?]*")


def asks_time(text: str) -> bool:
    t = re.sub(r"\s+", "", text).lower()
    m = _TIME_TH.fullmatch(t)
    # "เท่าไหร่" เฉย ๆ ไม่ใช่ถามเวลา
    if m and m.group(3) in ("เท่าไหร่", "เท่าไร") and not m.group(2):
        return False
    return bool(m) or bool(_TIME_EN.fullmatch(t))


# ยกเลิก/ลบนัดด้วยการพิมพ์ (สำรวจบน Pi 5 2026-10-12: แอปไม่มีทางลบนัดเลย ทั้งที่การ์ดนัดซ้ำบอกว่า "ลบได้"
# · "ลบนัดทั้งหมด" ถูกส่งต่อ Claude) · ต้องขึ้นต้นด้วย ยกเลิก/ลบ + นัด/เตือน · คืนคำที่ใช้หานัด ("" = ทุกนัด)
_CANCEL = re.compile(
    r"(?:ช่วย|ขอ)?(?:ยกเลิก|ลบ)(?:การ)?(?:นัดหมาย|นัด|การเตือน|เตือน)(?:ที่ชื่อ|เรื่อง|ชื่อ)?(.*)"
)
_CANCEL_END = ("ให้หน่อย", "หน่อย", "ครับ", "ค่ะ", "คะ", "นะ", "ด้วย", "เลย", "ให้")
ALL_WORDS = ("ทั้งหมด", "หมดเลย", "ทุกนัด", "ทุกอัน", "หมด")


def cancel_target(text: str) -> str | None:
    """None = ไม่ใช่คำขอลบนัด · "" = ลบทุกนัด · อื่น ๆ = คำที่ใช้หานัดที่จะลบ."""
    m = _CANCEL.fullmatch(re.sub(r"\s+", "", text))
    if m is None:
        return None
    rest = m.group(1)
    while rest.endswith(_CANCEL_END):
        rest = rest[: -len(next(e for e in _CANCEL_END if rest.endswith(e)))]
    return "" if rest in ALL_WORDS else rest


# "นัดล่าสุด/ถัดไปของฉันคืออะไร" (สำรวจบน Pi 5 2026-10-12: ไม่มีคำบอกวัน → AI ตอบไม่รู้ → ส่งต่อ Claude
# ซึ่งไม่เห็นนัดของผู้ใช้) → นัดที่ยังไม่ถึงเวลา · ทั้งประโยคต้องเป็นคำถามนี้
# ("นัดต่อไปของแมนซิตี้เจอใคร" = นัดฟุตบอล ในชุดทดสอบไฮบริด ต้องไม่เข้า)
_NEXT = re.compile(
    r"(?:ขอ)?(?:ดู|บอก|แสดง)?นัด(?:หมาย)?(?:ล่าสุด|ถัดไป|ต่อไป|หน้า|ที่เหลือ|ทั้งหมด|ที่มี)"
    r"(?:ของ(?:ฉัน|ผม|เรา|หนู|ดิฉัน))?(?:คือ|มี|เป็น)?"
    r"(?:อะไร|อะไรบ้าง|กี่โมง|เมื่อไหร่|เมื่อไร|วันไหน|ไหน)?(?:ครับ|ค่ะ|คะ|หน่อย|นะ|บ้าง)*[?？]*"
)


def asks_next(text: str) -> bool:
    return bool(_NEXT.fullmatch(re.sub(r"\s+", "", text)))


# "เลื่อนนัดประชุมไปบ่ายสาม" เคยถูกจดเป็นนัดใหม่ชื่อ "เลื่อนนัดประชุมไป" · ยังเลื่อนเองไม่ได้ → บอกวิธี
_MOVE = re.compile(r"(?:ช่วย|ขอ)?เลื่อน(?:การ)?(?:นัดหมาย|นัด|การเตือน|เตือน)(.*)")


def move_target(text: str) -> str | None:
    """None = ไม่ใช่คำขอเลื่อนนัด · คืนข้อความที่เหลือ (ใช้หานัด)."""
    m = _MOVE.fullmatch(re.sub(r"\s+", "", text))
    return None if m is None else m.group(1)


# "อีกกี่วันจะถึงปีใหม่" (สำรวจบน Pi 5 2026-10-12: AI ในเครื่องตอบ 109 วัน ที่ถูกคือ 81 · ชุดสอบข้อ C06)
# → นับด้วยโค้ดจากวันที่ของเครื่อง · รู้เฉพาะวันที่ตายตัว (ลอยกระทง/วันพระ ฯลฯ ตามจันทรคติ = ไม่ตอบเอง)
_UNTIL = re.compile(r"(?:อีก|เหลือ)กี่วัน|กี่วันจะถึง|กี่วันถึง")
HOLIDAYS = {
    "ปีใหม่": (1, 1), "สงกรานต์": (4, 13), "คริสต์มาส": (12, 25), "คริสมาส": (12, 25),
    "วาเลนไทน์": (2, 14), "วันแม่": (8, 12), "วันพ่อ": (12, 5), "วันเด็ก": None,
}  # fmt: skip


def days_until(text: str, today: date) -> tuple[str, date] | None:
    """(ชื่อวัน, วันที่) ของคำถาม "อีกกี่วันจะถึง …" · None = ไม่ใช่คำถามนี้ หรือไม่รู้วันที่แน่นอน."""
    from aipc.skills.when import MONTHS

    t = re.sub(r"\s+", "", text)
    if not _UNTIL.search(t):
        return None
    for name, md in HOLIDAYS.items():
        if name in t:
            if md is None:
                return None
            d = date(today.year, *md)
            return (name, d if d > today else date(today.year + 1, *md))
    months = "|".join(sorted((re.escape(m) for m in MONTHS), key=len, reverse=True))
    if m := re.search(rf"(?:วันที่)?(\d{{1,2}})\.?({months})\.?", t):
        try:
            d = date(today.year, MONTHS[m[2]], int(m[1]))
        except ValueError:
            return None
        if d <= today:
            d = date(today.year + 1, d.month, d.day)
        return (f"วันที่ {d.day}/{d.month}", d)
    return None
