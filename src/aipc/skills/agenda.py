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


def _range(t: str, today: date) -> Query | None:
    """ช่วงวันจากคำในประโยค (สัปดาห์นี้/หน้า · วันนี้/พรุ่งนี้/มะรืน) · ไม่มี = None."""
    for w in WEEK_WORDS:
        if w in t:
            nxt = "หน้า" in w
            start = today + timedelta(days=7 - today.weekday()) if nxt else today
            end = start + timedelta(days=6 - start.weekday())
            return Query(start, (end - start).days + 1, w)
    for w in sorted(DAYS, key=len, reverse=True):
        if w in t:
            return Query(today + timedelta(days=DAYS[w]), 1, w)
    return None


_PAST = re.compile(r"(?:วัน(?:จันทร์|อังคาร|พุธ|พฤหัสบดี|พฤหัส|ศุกร์|เสาร์|อาทิตย์)|อาทิตย์|สัปดาห์|เดือน)(?:ที่)?แล้ว")


def parse(text: str, today: date) -> Query | None:
    t = re.sub(r"\s+", "", text)
    topic = any(k in t for k in TOPIC) or (t.startswith(WHEN_FIRST) and "มีอะไร" in t)
    if not any(a in t for a in ASK) or not topic:
        return None
    if t.startswith(("เตือน", "จด", "บันทึก", "ตั้ง", "สร้าง")):  # สั่งจดนัด ไม่ใช่ถาม
        return None
    if "วันหยุด" in t and not any(k in t for k in ("นัด", "ต้องทำ", "ตาราง")):
        return None  # "สัปดาห์หน้ามีวันหยุดไหม" = คำถามวันหยุด (การ์ด 0033) ไม่ใช่ตารางนัด
    if _PAST.search(t):  # ถามย้อนหลัง: ตอบนัดที่จะถึงไม่ได้ (เดิม "วันจันทร์ที่แล้ว" ได้จันทร์หน้า · ตรวจทั้งระบบ 3.6)
        return None
    if q := _detail_range(t, today):  # วันในสัปดาห์ · วันที่ · เดือน (การ์ด 0037)
        return q
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


# ---------- วันหยุดไทย (การ์ด 0033) ----------
# "วันหยุดถัดไปคือวันอะไร" · "วันหยุดราชการครั้งหน้าวันไหน"
_NEXT_HOLIDAY = re.compile(
    r"(?:ขอ)?(?:ดู|บอก)?วันหยุด(?:ราชการ|นักขัตฤกษ์)?(?:ครั้ง)?(?:ถัดไป|ต่อไป|หน้า|ที่จะถึง|ที่ใกล้ที่สุด)"
    r"(?:คือ|เป็น|ตรงกับ)?(?:วัน)?(?:อะไร|ไหน|เมื่อไหร่|เมื่อไร)?(?:ครับ|ค่ะ|คะ|หน่อย|นะ|บ้าง)*[?？]*"
)
# "อีกกี่วันจะถึงวันหยุด" (วันหยุดราชการถัดไป ไม่ระบุชื่อ)
_UNTIL_ANY_HOLIDAY = re.compile(
    r"(?:อีก|เหลือ)กี่วัน(?:จะ)?(?:ถึง)?วันหยุด(?:ราชการ|นักขัตฤกษ์)?(?:ครั้ง)?(?:ถัดไป|หน้า)?"
    r"(?:ครับ|ค่ะ|คะ|นะ|อะ)*[?？]*"
)
_POLITE_END = ("ครับ", "ค่ะ", "คะ", "นะ", "อะ", "จ้ะ", "จ้า", "แล้ว", "?", "？")


def asks_next_holiday(text: str) -> bool:
    t = re.sub(r"\s+", "", text)
    return bool(_NEXT_HOLIDAY.fullmatch(t) or _UNTIL_ANY_HOLIDAY.fullmatch(t))


def holiday_range(text: str, today: date) -> Query | None:
    """ "สัปดาห์หน้ามีวันหยุดไหม" · "พรุ่งนี้หยุดไหม" → ช่วงวัน · ไม่ใช่คำถามนี้ = None."""
    t = re.sub(r"\s+", "", text)
    if not any(a in t for a in ASK):
        return None
    if "วันหยุด" not in t and not re.search(r"(?:หยุด|เป็นวันหยุด)(?:ไหม|มั้ย|หรือเปล่า)", t):
        return None
    if any(k in t for k in ("นัด", "ต้องทำ", "ไปเที่ยว", "ทำอะไรดี", "ไปไหน")):
        return None  # "วันหยุดไปเที่ยวไหนดี" ไม่ใช่ถามวันที่
    return _range(t, today)


def until_target(text: str) -> str | None:
    """ชื่อวันในคำถาม "อีกกี่วันจะถึง X" / "X อีกกี่วัน" (ใช้หาในปฏิทินวันหยุด) · ไม่ใช่คำถามนี้ = None."""
    t = re.sub(r"\s+", "", text)
    m = _UNTIL.search(t)
    if m is None:
        return None
    rest = t[m.end() :] or t[: m.start()]
    rest = rest.removeprefix("ถึง").removeprefix("จะถึง")
    changed = True
    while changed:
        changed = False
        for w in _POLITE_END:
            if rest.endswith(w) and len(rest) > len(w):
                rest, changed = rest[: -len(w)], True
    return rest or None


def holiday_key(name: str) -> str:
    """ชื่อสำหรับเทียบ: ตัดช่องว่าง/คำว่า "วัน" นำหน้า · ทนสะกดของ Google ("วันขื้นปีใหม่")."""
    k = re.sub(r"\s+", "", name).replace("ขื้น", "ขึ้น")
    return k.removeprefix("วัน")


# ชื่อวันหยุด/วันสำคัญของไทยในปฏิทินวันหยุดของ Google (ไม่มีคำว่า "วัน" นำหน้า) · ใช้ตัดสินว่า "อีกกี่วันถึง X"
# เป็นคำถามวันหยุดไหม เมื่อปฏิทินยังไม่มีวัน X · ตรวจทั้งระบบ 2026-10-18 ข้อ 3.5: เดิมทุก X ไปปฏิทินวันหยุด →
# "อีกกี่วันจะถึงนัดโทรหาหมอ" ตอบ "ยังไม่มีข้อมูล" · "อีกกี่วันจะถึงวันพระ" ตอบวันคล้ายวันพระบรมราชสมภพ
HOLIDAY_NAMES = ("ขึ้นปีใหม่", "ปีใหม่", "เด็ก", "ครู", "ตรุษจีน", "วาเลนไทน์", "มาฆบูชา", "จักรี", "สงกรานต์",
                 "แรงงาน", "ฉัตรมงคล", "พืชมงคล", "วิสาขบูชา", "อาสาฬหบูชา", "เข้าพรรษา", "ออกพรรษา",
                 "เฉลิมพระชนมพรรษา", "แม่", "พ่อ", "ปิยมหาราช", "นวมินทรมหาราช", "มหิดล",
                 "คล้ายวันพระบรมราชสมภพ", "คล้ายวันสวรรคต", "ลอยกระทง", "ฮาโลวีน", "รัฐธรรมนูญ",
                 "คริสต์มาส", "สิ้นปี")  # fmt: skip


def holiday_match(key: str, name: str) -> bool:
    """ชื่อที่ถาม (key) ตรงกับชื่อวันในปฏิทินไหม: ชื่อในปฏิทินขึ้นต้นด้วยคำที่ถาม ("แม่" → "แม่แห่งชาติ") ·
    อยู่กลางชื่อนับเฉพาะคำยาว ≥ 6 ตัว (เดิมนับทุกความยาว: "พระ" ไปตรงกับ "…พระบรมราชสมภพ")."""
    k = holiday_key(name)
    return k.startswith(key) or (len(key) >= 6 and key in k)


def is_holiday_name(target: str) -> bool:
    k = holiday_key(target)
    return any(k.startswith(n) for n in HOLIDAY_NAMES)


# ---------- ถามนัดละเอียดขึ้น (การ์ด 0037) ----------
# "วันศุกร์นี้" · "วันจันทร์หน้า" · ต้องมีคำว่า "วัน" นำหน้า: "อาทิตย์นี้" เดี่ยว ๆ = สัปดาห์นี้ (กฎเดิม)
_WEEKDAY = re.compile(r"วัน(จันทร์|อังคาร|พุธ|พฤหัสบดี|พฤหัส|ศุกร์|เสาร์|อาทิตย์)(นี้|หน้า)?")


def _month_end(d: date) -> date:
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return nxt - timedelta(days=1)


def _invalid(label: str, today: date) -> Query:
    """วันที่ไม่มีจริง (31 พ.ย.) · days = 0 → ตัวตอบบอกว่าไม่มีวันนี้ ไม่เดาวันใกล้เคียง."""
    return Query(today, 0, label)


def _on_or_after(today: date, mon: int, day: int, label: str) -> Query:
    """วันที่ day/mon ครั้งถัดไป (ผ่านแล้วปีนี้ = ปีหน้า) · ไม่มีจริง (31 พ.ย.) = บอกว่าไม่มี."""
    try:
        d = date(today.year, mon, day)
        if d < today:
            d = date(today.year + 1, mon, day)
    except ValueError:
        return _invalid(label, today)
    return Query(d, 1, label)


def _detail_range(t: str, today: date) -> Query | None:
    from aipc.skills.when import MONTHS, WEEKDAYS
    from aipc.ui.thaidate import MONTHS_SHORT

    # วันที่ชัดเจนมาก่อนวันในสัปดาห์ (ตรวจทั้งระบบ 2026-10-18 ข้อ 3.6): "วันศุกร์ที่ 20 พฤศจิกายน" = 20 พ.ย.
    # (เดิมได้ศุกร์นี้) · "วันพุธที่ 28" = วันที่ 28 · "วันที่ 25/12" = 25 ธ.ค. · "วันที่ 20 เดือนหน้า" = 20 ของเดือนหน้า
    months = "|".join(sorted((re.escape(k) for k in MONTHS), key=len, reverse=True))
    if m := re.search(r"(\d{1,2})/(\d{1,2})(?![/\d])", t):
        return _on_or_after(today, int(m[2]), int(m[1]), f"วันที่ {int(m[1])}/{int(m[2])}")
    if m := re.search(rf"(?:ที่)?(\d{{1,2}})({months})\.?", t):
        day, mon = int(m[1]), MONTHS[m[2]]
        return _on_or_after(today, mon, day, f"วันที่ {day} {MONTHS_SHORT[mon - 1]}")
    if m := re.search(r"ที่(\d{1,2})", t):
        day = int(m[1])
        y, mon = today.year, today.month
        if "เดือนหน้า" in t or day < today.day:
            y, mon = (y + 1, 1) if mon == 12 else (y, mon + 1)
        label = f"วันที่ {day}" + (f" {MONTHS_SHORT[mon - 1]}" if "เดือนหน้า" in t else "")
        try:
            return Query(date(y, mon, day), 1, label)
        except ValueError:
            return _invalid(f"{label} {MONTHS_SHORT[mon - 1]}", today)
    if m := _WEEKDAY.search(t):
        wd = WEEKDAYS[m[1]]
        # วันนั้นของสัปดาห์หน้า · "อาทิตย์หน้าวันอังคาร" ก็นับ (เดิมได้อังคารนี้)
        if m[2] == "หน้า" or re.search(r"(?:อาทิตย์|สัปดาห์)หน้า", t[: m.start()]):
            d = today + timedelta(days=7 - today.weekday() + wd)
        else:  # ครั้งถัดไป นับวันนี้ด้วย
            d = today + timedelta(days=(wd - today.weekday()) % 7)
        return Query(d, 1, f"วัน{m[1]}{m[2] or ''}")
    if "เดือนนี้" in t:
        return Query(today, (_month_end(today) - today).days + 1, "เดือนนี้")
    if "เดือนหน้า" in t:
        first = _month_end(today) + timedelta(days=1)
        return Query(first, (_month_end(first) - first).days + 1, "เดือนหน้า")
    return None


# ค้นนัดตามชื่อ: "นัดหมอวันไหน" · "มีนัดกับหมอไหม" · "ประชุมทีมครั้งหน้าเมื่อไหร่"
_WHEN_ASK = r"(?:วันไหน|เมื่อไหร่|เมื่อไร|กี่โมง|วันที่เท่าไหร่)"
_END = r"(?:ครับ|ค่ะ|คะ|นะ|จ๊ะ|จ้ะ)*[?？]*"
_TITLE_ASK = re.compile(rf"(?:ขอ)?(?:มี)?นัด(.+?)(?:ครั้ง(?:หน้า|ถัดไป))?{_WHEN_ASK}{_END}")
_TITLE_HAVE = re.compile(rf"มีนัด(.+?)(?:ไหม|มั้ย|หรือเปล่า){_END}")
_TITLE_NEXT = re.compile(rf"(.+?)ครั้ง(?:หน้า|ถัดไป){_WHEN_ASK}{_END}")
_NOT_NAMES = ("ถัดไป", "ต่อไป", "ล่าสุด", "ทั้งหมด", "ที่เหลือ", "ของฉัน", "ของผม", "อะไร", "ไหน")
_SPORT = ("ชิง", "รอบ", "แข่ง")
_SPORT_WORDS = ("ฟุตบอล", "บอลโลก", "แมตช์", "ลีก", "คัพ", "ทีมชาติ", "พรีเมียร์", "แข่งขัน")


def title_query(text: str) -> tuple[str, bool] | None:
    """(คำที่ใช้ค้นชื่อนัด, ต้องตอบแม้ไม่เจอไหม) · ไม่ใช่คำถามนี้ = None.

    มีคำว่า "นัด" = คำถามเรื่องนัดแน่ ๆ (ไม่เจอก็ตอบว่าไม่เจอ) · "<ชื่อ>ครั้งหน้าเมื่อไหร่" ไม่มีคำว่านัด
    อาจถามเรื่องอื่น ("ทีมชาติไทยแข่งครั้งหน้าเมื่อไหร่") → ตอบเฉพาะเมื่อเจอนัดชื่อนี้
    """
    t = re.sub(r"\s+", "", text)
    for rx, strict in ((_TITLE_ASK, True), (_TITLE_HAVE, True), (_TITLE_NEXT, False)):
        if m := rx.fullmatch(t):
            name = m[1]
            for pre in ("กับ", "เรื่อง", "ที่"):
                name = name.removeprefix(pre)
            if len(name) < 2 or any(w in name for w in _NOT_NAMES):
                return None
            # "นัด" = แมตช์กีฬาได้ ("นัดชิงฟุตบอลโลกวันไหน" · ตรวจทั้งระบบ 3.8) → ตอบเฉพาะเมื่อเจอนัดชื่อนี้
            if name.startswith(_SPORT) or any(w in name for w in _SPORT_WORDS):
                strict = False
            return name, strict
    return None
