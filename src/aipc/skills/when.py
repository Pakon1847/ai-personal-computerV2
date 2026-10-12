"""แปลงคำบอกเวลาภาษาไทยเป็นวันเวลา — ด้วยโค้ด ไม่ใช้ LLM (การ์ดออกแบบ 0001, หลักการ H6).

ทำไมต้องเป็นโค้ด: "วันศุกร์หน้า" ต้องกลายเป็นวันที่ที่ถูกแน่นอน โมเดลเล็กคำนวณวันที่ผิดได้
ส่วนโค้ดทำตามกฎที่เขียนไว้ทุกครั้งเหมือนเดิม และเทสต์ได้ครบ

ผลลัพธ์บอกเสมอว่า "ตีความเองตรงไหน" (assumptions) เพื่อให้หน้าจอแสดงให้ผู้ใช้ยืนยัน (H5)
และบอกว่า "มั่นใจไหม" (confident) · ไม่มั่นใจ = ห้ามบันทึกจนกว่าผู้ใช้จะระบุเอง

รูปแบบที่รองรับ (ประกาศไว้ในการ์ด 0001 หัวข้อ 6):
  วัน:   วันนี้ คืนนี้ พรุ่งนี้ มะรืน · วัน<จันทร์–อาทิตย์>(นี้|หน้า) · อีก N วัน/ชั่วโมง/นาที
         วันที่ N · N <เดือน> [ปี] · N/M
  เวลา:  14:00 14.30 · เที่ยง · บ่ายโมง–บ่ายห้า · N โมงเช้า/เย็น · N โมง · N ทุ่ม · ตี N · "ครึ่ง"
         ตอนเช้า/บ่าย/เย็น/ค่ำ
กฎ "นี้/หน้า": นี้ = วันนั้นที่ใกล้ที่สุดที่ยังไม่ผ่าน · หน้า = วันนั้นของสัปดาห์ถัดไป (สัปดาห์เริ่มวันจันทร์)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from aipc.skills.thainum import words_to_int

WEEKDAYS = {"จันทร์": 0, "อังคาร": 1, "พุธ": 2, "พฤหัสบดี": 3, "พฤหัส": 3, "ศุกร์": 4,
            "เสาร์": 5, "อาทิตย์": 6}  # fmt: skip
MONTHS = {
    "มกราคม": 1, "มกรา": 1, "ม.ค": 1, "กุมภาพันธ์": 2, "กุมภา": 2, "ก.พ": 2,
    "มีนาคม": 3, "มีนา": 3, "มี.ค": 3, "เมษายน": 4, "เมษา": 4, "เม.ย": 4,
    "พฤษภาคม": 5, "พฤษภา": 5, "พ.ค": 5, "มิถุนายน": 6, "มิถุนา": 6, "มิ.ย": 6,
    "กรกฎาคม": 7, "กรกฎา": 7, "ก.ค": 7, "สิงหาคม": 8, "สิงหา": 8, "ส.ค": 8,
    "กันยายน": 9, "กันยา": 9, "ก.ย": 9, "ตุลาคม": 10, "ตุลา": 10, "ต.ค": 10,
    "พฤศจิกายน": 11, "พฤศจิกา": 11, "พ.ย": 11, "ธันวาคม": 12, "ธันวา": 12, "ธ.ค": 12,
}  # fmt: skip
DEFAULT_TIME = time(9, 0)
PART_OF_DAY = {"เช้า": time(9, 0), "บ่าย": time(13, 0), "เย็น": time(18, 0),
               "ค่ำ": time(20, 0), "กลางคืน": time(20, 0)}  # fmt: skip

# คำที่บอกว่าเป็นรูปแบบที่ยังไม่รองรับ → ต้องไม่ตีความเอง (การ์ด 0001: ไม่บันทึกผิดเงียบ ๆ)
UNSUPPORTED = {
    "สิ้นเดือน": "“สิ้นเดือน” ยังไม่รองรับ ระบุวันที่แทน",
    "ต้นเดือน": "“ต้นเดือน” ยังไม่รองรับ ระบุวันที่แทน",
    "กลางเดือน": "“กลางเดือน” ยังไม่รองรับ ระบุวันที่แทน",
    "เดือนหน้า": "“เดือนหน้า” ยังไม่รองรับ ระบุวันที่แทน",
    "สัปดาห์หน้า": "“สัปดาห์หน้า” กว้างเกินไป ระบุวันแทน เช่น วันจันทร์หน้า",
}

NUM = r"(\d{1,2}|สิบเอ็ด|สิบสอง|สิบ|หนึ่ง|สอง|สาม|สี่|ห้า|หก|เจ็ด|แปด|เก้า)"
# ระยะเวลาสัมพัทธ์: "อีก 30 นาที" "อีกสองชั่วโมงครึ่ง" "อีก 1 ชั่วโมง 30 นาที" "อีก 3 วัน"
# เคยรับแค่ "อีก N หน่วย" ส่วน "ครึ่ง" และ "M นาที" ที่ตามมาไปปนในชื่อนัด (พบ 2026-09-28)
RELATIVE = (r"อีก\s*(ครึ่ง|" + NUM + r")\s*(ชั่วโมง|ชม\.?|นาที|วัน)(\s*ครึ่ง)?"
            r"(?:\s*(?:กับ|และ)?\s*" + NUM + r"\s*นาที)?")  # fmt: skip
TRIGGERS = ("ช่วยเตือน", "ตั้งเตือน", "เตือนให้", "เตือนฉัน", "เตือน", "อย่าลืม", "นัดหมาย", "ปลุก")
POLITE = ("ด้วยนะ", "ด้วย", "หน่อย", "ครับ", "ค่ะ", "คะ", "นะ", "จ้า")


@dataclass
class WhenResult:
    at: datetime | None
    what: str
    assumptions: list[str] = field(default_factory=list)
    confident: bool = True
    problem: str = ""
    repeat: str = ""  # นัดซ้ำ: daily | weekdays | weekends | weekly:<0–6> · "" = ครั้งเดียว


# ---------- นัดซ้ำ (Pakon เลือก 2026-10-02 · docs/benchmarks/2026-10-02-repeat) ----------
# เดิมคำว่า "ทุก" = ปฏิเสธทั้งประโยค ทำให้ "เตือนให้บอกทุกคน…" จดไม่ได้ด้วย → จับเฉพาะรูปนัดซ้ำจริง
_WD = "จันทร์|อังคาร|พุธ|พฤหัสบดี|พฤหัส|ศุกร์|เสาร์|อาทิตย์"
_PART = "คืน|เช้า|เย็น|ค่ำ"
REPEAT_UNSUPPORTED = re.compile(
    r"ทุก\s*(เดือน|ปี|\d+|สอง|สาม|สี่|ห้า|หก)\s*(ชั่วโมง|ชม|นาที|วัน|เดือน|สัปดาห์)?|ทุก\s*ชั่วโมง|วันเว้นวัน"
)
REPEAT_NAMES = {"daily": "ทุกวัน", "weekdays": "ทุกวันจันทร์–ศุกร์", "weekends": "ทุกเสาร์–อาทิตย์"}
_DAYNAMES = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]


def repeat_name(rule: str) -> str:
    if rule.startswith("weekly:"):
        return "ทุกวัน" + _DAYNAMES[int(rule.split(":")[1])]
    return REPEAT_NAMES.get(rule, "")


def repeat_rule(text: str) -> tuple[str, str, list[str], bool]:
    """(กฎซ้ำ, ข้อความที่ตัดคำบอกการซ้ำออกแล้ว, หมายเหตุ, มั่นใจไหม) · ไม่ใช่นัดซ้ำ = ("", text, [], True)."""
    # "ไม่ต้องทุกวัน" = ปฏิเสธการซ้ำ · "ทุก ๆ วัน" = ทุกวัน (พบในชุดอิสระรอบ 1)
    if re.search(r"ไม่\s*(ต้อง)?\s*(เตือน)?\s*(ซ้ำ|ทุก)", text):
        return "", text, [], True
    t = re.sub(r"ทุก\s*ๆ\s*", "ทุก", text)
    notes: list[str] = []
    sure = True
    if re.search(r"จันทร์\s*(ถึง|[-–])\s*(วัน)?\s*ศุกร์|วันธรรมดา|วันทำงาน", t):
        rule = "weekdays"
    elif re.search(r"เสาร์\s*([-–]|กับ|และ)?\s*(วัน)?\s*อาทิตย์|สุดสัปดาห์", t) and re.search(
        r"ทุก|วันหยุด|ซ้ำ", t
    ):
        rule = "weekends"
    elif m := re.search(rf"ทุก\s*(?:{_PART}\s*)?(วัน)?\s*({_WD})", t):  # "ทุกคืนวันจันทร์" (ชุดอิสระรอบ 2)
        rule = f"weekly:{WEEKDAYS[m[2]]}"
        if m[2] == "อาทิตย์" and not m[1]:  # "ทุกอาทิตย์" อาจแปลว่าทุกสัปดาห์
            notes.append("“ทุกอาทิตย์” ถือว่าเป็นทุกวันอาทิตย์ · ถ้าหมายถึงทุกสัปดาห์ ระบุวันให้ชัด")
            sure = False
    elif re.search(r"ทุก\s*(วัน|คืน|เช้า|เย็น|ค่ำ)|วันละ\s*(ครั้ง|หน)|ซ้ำทุกวัน", t):
        rule = "daily"
    else:
        return "", text, [], True
    # ตัดคำบอกการซ้ำออก (คงคำ เช้า/เย็น/คืน ไว้ให้ตัวอ่านเวลา)
    t = re.sub(rf"ทุก\s*({_PART})\s*(?=(วัน)?\s*({_WD}))", r" \1 ทุก", t)  # คงคำ คืน/เช้า ไว้
    for pat in (rf"ทุก\s*(วัน)?\s*({_WD})(?!\s*[-–]|\s*ถึง)", r"(เตือน)?ซ้ำ", r"วันละ\s*(ครั้ง|หน)",
                r"ทุก\s*สุดสัปดาห์|สุดสัปดาห์",
                r"(เฉพาะ)?\s*(วันหยุด)?\s*(ทุก\s*)?(วัน)?\s*เสาร์\s*([-–]|กับ|และ)?\s*(วัน)?\s*อาทิตย์",
                r"(ทุก\s*)?(วัน)?\s*จันทร์\s*(ถึง|[-–])\s*(วัน)?\s*ศุกร์", r"(ทุก\s*)?วัน(ธรรมดา|ทำงาน)",
                r"ทุก\s*(สัปดาห์|วัน)", r"ทุก(?=\s*(คืน|เช้า|เย็น|ค่ำ))"):  # fmt: skip
        t = re.sub(pat, " ", t)
    t = re.sub(r"(?<![ก-๙])คืน(?![ก-๙]*นี้)", " ค่ำ ", t)  # "ทุกคืน 4 ทุ่ม" → เหลือ "ค่ำ"
    # "ทุกเช้าหกโมง" → "หกโมงเช้า" ให้ตัวอ่านเวลารู้ว่าเป็นเช้า (เดิมได้ 18:00 · พบในชุดอิสระรอบ 1)
    t = re.sub(r"(เช้า|เย็น)\s*" + NUM + r"\s*โมง", r"\2โมง\1", t)
    return rule, t, notes, sure


def matches(rule: str, d: date) -> bool:
    wd = d.weekday()
    if rule == "daily":
        return True
    if rule == "weekdays":
        return wd < 5
    if rule == "weekends":
        return wd >= 5
    if rule.startswith("weekly:"):
        return wd == int(rule.split(":")[1])
    return False


def next_on(rule: str, tm: time, after: datetime) -> datetime:
    """ครั้งถัดไปหลัง after ที่ตรงกฎ (เวลา tm)."""
    d = after.date()
    for _ in range(8):
        cand = datetime.combine(d, tm)
        if after.tzinfo is not None:
            cand = cand.replace(tzinfo=after.tzinfo)
        if matches(rule, d) and cand > after:
            return cand
        d += timedelta(days=1)
    raise ValueError(rule)


def _n(token: str) -> int | None:
    return int(token) if token.isdigit() else words_to_int(token)


class _Text:
    """ข้อความที่ค่อย ๆ ถูกตัดส่วนที่เป็นวันเวลาออก เหลือไว้เป็น "เรื่องที่ต้องทำ"."""

    def __init__(self, text: str):
        self.s = text

    def take(self, pattern: str) -> re.Match | None:
        m = re.search(pattern, self.s)
        if m:
            self.s = self.s[: m.start()] + " " + self.s[m.end() :]
        return m


def _time(t: _Text, notes: list[str]) -> tuple[time | None, bool]:
    """คืน (เวลา, เป็นการบอกเวลาแบบชัดเจนไหม)."""
    half = r"\s*(ครึ่ง)?"

    def mk(h, m, halfmark=None):
        if h is None or not (0 <= h <= 23) or not (0 <= m <= 59):
            return None
        return time(h, 30 if halfmark and m == 0 else m)

    # ตัวเลขที่ตามด้วยหน่วยเงิน/ขนาดไม่ใช่เวลา: "1.50 บาท" เคยกลายเป็น 01:50 (พบ 2026-09-28)
    m = t.take(r"(\d{1,2})\s*[:.]\s*(\d{2})(?!\d)(?!\s*(?:บาท|฿|%|เปอร์เซ็นต์|กิโล|กก|ลิตร|เมตร|ซม|มม))"
               r"\s*(น\.)?")  # fmt: skip
    if m:
        return mk(int(m[1]), int(m[2])), True
    if t.take(r"เที่ยงคืน"):
        notes.append("“เที่ยงคืน” ใช้เวลา 00:00 น. ตอนเริ่มวันที่แสดง")
        return time(0, 0), True
    m = t.take(r"เที่ยง(วัน)?" + half)
    if m:
        return mk(12, 0, m[2]), True
    m = t.take(r"บ่าย\s*(?:(โมง)|" + NUM + r"\s*(?:โมง)?)" + half)
    if m:
        h = 1 if m[1] else _n(m[2])
        return (mk(12 + h, 0, m[3]) if h and 1 <= h <= 5 else None), True
    # "ครึ่ง" มาก่อนหรือหลัง เช้า/เย็น ก็ได้: "หกโมงครึ่งเย็น" "หกโมงเย็นครึ่ง" (พบในชุดนัดซ้ำ 2026-10-02)
    m = t.take(NUM + r"\s*โมง\s*(ครึ่ง)?\s*เย็น" + half)
    if m:
        h = _n(m[1])
        return (mk(12 + h if h and h < 12 else h, 0, m[2] or m[3])), True
    m = t.take(NUM + r"\s*ทุ่ม" + half)
    if m:
        h = _n(m[1])
        return (mk(18 + h, 0, m[2]) if h and 1 <= h <= 5 else None), True
    m = t.take(
        r"(?<!\d)ทุ่ม(?!เท)(?:\s*(?:หนึ่ง|นึง))?" + half
    )  # "ทุ่มครึ่ง" ไม่มีตัวเลข = 19:30 (ชุดอิสระรอบ 2)
    if m:
        return mk(19, 0, m[1]), True
    m = t.take(r"ตี\s*" + NUM + half)
    if m:  # ตีหนึ่ง–ตีหก (ตีหก = 06:00 ใช้กันทั่วไป · เดิมรับถึงตีห้า)
        h = _n(m[1])
        return (mk(h, 0, m[2]) if h and 1 <= h <= 6 else None), True
    m = t.take(NUM + r"\s*โมง\s*(ครึ่ง)?\s*(เช้า)?" + half)
    if m:
        h = _n(m[1])
        halfmark = m[2] or m[4]
        if h is None or h > 12:
            return None, True
        if m[3]:  # โมงเช้า: แบบดั้งเดิม หนึ่งโมงเช้า–ห้าโมงเช้า = 7–11 น.
            return mk(h + 6 if h <= 5 else h, 0, halfmark), True
        if h <= 6:  # "สามโมง" ไม่มีเช้า/เย็น — คนส่วนใหญ่หมายถึงบ่าย
            notes.append(f"“{m[1]}โมง” ตีความเป็น {12 + h}:00 น.")
            return mk(12 + h, 0, halfmark), True
        return mk(h, 0, halfmark), True
    m = t.take(r"(?:ตอน)?(เช้า|บ่าย|เย็น|ค่ำ|กลางคืน)")
    if m:
        pt = PART_OF_DAY[m[1]]
        notes.append(f"“{m[1]}” ใช้เวลา {pt:%H:%M} น.")
        return pt, False
    return None, False


def _next_year(d: date) -> date | None:
    """วันเดียวกันของปีหน้า · None = ปีหน้าไม่มีวันนี้ (29 ก.พ.)."""
    try:
        return d.replace(year=d.year + 1)
    except ValueError:
        return None


def _date(t: _Text, now: datetime, notes: list[str]) -> tuple[date | None, str, bool]:
    """คืน (วันที่, ปัญหา, มาจากชื่อวันในสัปดาห์ไหม) · ปัญหา ≠ "" แปลว่าวันที่ที่ระบุใช้ไม่ได้."""
    today = now.date()
    if t.take(r"วันนี้|คืนนี้"):
        return today, "", False
    if t.take(r"พรุ่งนี้"):
        d = today + timedelta(days=1)
        if now.hour < 4:  # ยังไม่นอนแต่เลยเที่ยงคืนแล้ว — คนมักหมายถึง "วันนี้" ตามปฏิทิน · บอกให้ชัด
            notes.append(f"ตอนนี้เลยเที่ยงคืนแล้ว “พรุ่งนี้” จึงเป็นวันที่ {d.day}/{d.month}")
        return d, "", False
    if t.take(r"มะรืน(นี้)?"):
        return today + timedelta(days=2), "", False
    m = t.take(
        r"(วันที่)?\s*(\d{1,2})\s*("
        + "|".join(sorted(MONTHS, key=len, reverse=True))
        + r")\.?\s*(\d{4})?"
    )
    if m:
        day, month = int(m[2]), MONTHS[m[3]]
        year = int(m[4]) if m[4] else today.year
        if year > 2400:
            year -= 543  # พ.ศ. → ค.ศ.
        try:
            d = date(year, month, day)
        except ValueError:
            return None, f"ไม่มีวันที่ {day} {m[3]}", False
        if d < today and not m[4]:
            d = _next_year(d)
            if d is None:  # 29 ก.พ. ที่ปีถัดไปไม่มี · เคยโยน ValueError ถึงหน้าจอ (พบ 2026-09-28)
                return None, f"ปีหน้าไม่มีวันที่ {day} {m[3]} ระบุปีให้ชัด", False
            notes.append("วันที่นี้ผ่านไปแล้วปีนี้ จึงใช้ปีหน้า")
        return d, "", False
    m = t.take(r"(\d{1,2})\s*/\s*(\d{1,2})(?:\s*/\s*(\d{2,4}))?")
    if m:
        day, month = int(m[1]), int(m[2])
        if m[3] and len(m[3]) == 2:
            # ปีย่อ 2 หลักของคนไทยคือ พ.ศ. (69 = 2569) · เคยตีเป็น ค.ศ. 2069 (พบ 2026-09-28)
            year = 2500 + int(m[3]) - 543
            notes.append(f"ปี {m[3]} ตีความเป็น พ.ศ. 25{m[3]}")
        else:
            year = int(m[3]) if m[3] else today.year
            year = year - 543 if year > 2400 else year
        try:
            d = date(year, month, day)
        except ValueError:
            return None, f"ไม่มีวันที่ {m[0].strip()}", False
        if d < today and not m[3]:
            d = _next_year(d)
            if d is None:
                return None, f"ปีหน้าไม่มีวันที่ {m[0].strip()} ระบุปีให้ชัด", False
            notes.append("วันที่นี้ผ่านไปแล้วปีนี้ จึงใช้ปีหน้า")
        return d, "", False
    m = t.take(r"วันที่\s*(\d{1,2})")
    if m:
        day = int(m[1])
        y, mo = today.year, today.month
        for _ in range(2):
            try:
                d = date(y, mo, day)
            except ValueError:
                d = None
            if d and d >= today:
                if mo != today.month:
                    notes.append(f"วันที่ {day} ของเดือนนี้ผ่านไปแล้ว จึงใช้เดือนหน้า")
                return d, "", False
            mo, y = (1, y + 1) if mo == 12 else (mo + 1, y)
        return None, f"ไม่มีวันที่ {day} ในเดือนนี้และเดือนหน้า", False
    m = t.take(r"วัน(" + "|".join(sorted(WEEKDAYS, key=len, reverse=True)) + r")\s*(นี้|หน้า)?")
    if m:
        wd = WEEKDAYS[m[1]]
        if m[2] == "หน้า":
            next_monday = today + timedelta(days=7 - today.weekday())
            return next_monday + timedelta(days=wd), "", True
        return today + timedelta(days=(wd - today.weekday()) % 7), "", True
    return None, "", False


def parse(text: str, now: datetime) -> WhenResult:
    if REPEAT_UNSUPPORTED.search(text):
        why = "รองรับนัดซ้ำแค่ ทุกวัน · ทุกวัน<จันทร์–อาทิตย์> · วันธรรมดา · เสาร์อาทิตย์"
        return WhenResult(None, text.strip(), confident=False, problem=why)
    rule, rest, rnotes, sure = repeat_rule(text)
    if rule:
        w = _parse_once(rest, now)
        if w.at is None and w.problem == "ไม่พบวันหรือเวลาในประโยค":
            w = _parse_once(rest + " 09:00", now)  # "ทุกวันจันทร์ ประชุมทีม" ไม่บอกเวลา
            w.assumptions.append(f"ไม่ได้บอกเวลา ใช้ {DEFAULT_TIME:%H:%M} น.")
            sure = False  # นัดซ้ำที่เดาเวลา = ถามยืนยันก่อนบันทึก (การ์ด 0001: ไม่บันทึกผิดเงียบ ๆ)
        if w.at is None:
            return WhenResult(None, w.what, confident=False, problem=w.problem, repeat=rule)
        at = next_on(rule, w.at.time(), now)
        notes = [n for n in w.assumptions if "พรุ่งนี้" not in n and "ผ่านไปแล้ว" not in n] + rnotes
        return WhenResult(at, w.what, notes, confident=w.confident and sure, repeat=rule)
    return _parse_once(text, now)


def _parse_once(text: str, now: datetime) -> WhenResult:
    notes: list[str] = []
    for word, why in UNSUPPORTED.items():
        if word in text:
            return WhenResult(None, text.strip(), confident=False, problem=why)
    # "อาทิตย์หน้า" ที่ไม่มีคำว่า "วัน" นำหน้า อาจหมายถึงสัปดาห์หน้า หรือวันอาทิตย์หน้า — ถามก่อน
    if re.search(r"(?<!วัน)อาทิตย์หน้า", text):
        why = "“อาทิตย์หน้า” อาจหมายถึงสัปดาห์หน้า หรือวันอาทิตย์หน้า — ระบุวันให้ชัด"
        return WhenResult(None, text.strip(), confident=False, problem=why)

    t = _Text(text)
    # ระยะเวลาสัมพัทธ์ "อีก N ..." ตรวจก่อน เพราะกำหนดทั้งวันและเวลาในตัว
    m = t.take(RELATIVE)
    at: datetime | None = None
    from_weekday = False
    if m:
        unit = m[3]
        amount = 0.5 if m[1] == "ครึ่ง" else _n(m[2])
        if unit == "วัน":
            d, tm = now.date() + timedelta(days=int(amount)), None
        else:
            if unit.startswith("ช"):
                extra = 30 if m[4] else 0  # "…ชั่วโมงครึ่ง"
                if m[5]:  # "…ชั่วโมง M นาที"
                    extra += _n(m[5]) or 0
                minutes = amount * 60 + extra
            else:
                minutes = amount + (0.5 if m[4] else 0)
            at = (now + timedelta(minutes=minutes)).replace(second=0, microsecond=0)
    if at is None:
        tm, explicit = _time(t, notes)
        if m is None:
            d, problem, from_weekday = _date(t, now, notes)
            if problem:
                return WhenResult(None, text.strip(), confident=False, problem=problem)
        if re.search(r"\d+\s*นาฬิกา", t.s) or (explicit and tm is None):
            return WhenResult(None, text.strip(), confident=False, problem="เวลาที่ระบุไม่ถูกต้อง")
        if d is None and tm is None:
            return WhenResult(None, _what(t.s), confident=False, problem="ไม่พบวันหรือเวลาในประโยค")
        if tm is None:
            tm = DEFAULT_TIME
            notes.append(f"ไม่ได้บอกเวลา ใช้ {DEFAULT_TIME:%H:%M} น.")
        if d is None:
            d = now.date()
            if datetime.combine(d, tm) <= now:
                d += timedelta(days=1)
                notes.append("เวลานี้ของวันนี้ผ่านไปแล้ว จึงเป็นพรุ่งนี้")
        at = datetime.combine(d, tm)
        if at <= now:
            if from_weekday:  # "วันพุธนี้ 08:00" ตอนวันพุธ 10:00 → พุธถัดไป (นี้ = ที่ใกล้ที่สุดที่ยังไม่ผ่าน)
                at += timedelta(days=7)
                notes.append("เวลานี้ของวันนี้ผ่านไปแล้ว จึงเป็นสัปดาห์ถัดไป")
            else:
                return WhenResult(None, _what(t.s), confident=False, problem="วันเวลาที่ระบุผ่านไปแล้ว")
    return WhenResult(at, _what(t.s), notes)


# ใช้แค่ดูว่ามีคำบอกวันไหม ไม่ได้คำนวณวันจริง · ไกลในอดีตจะได้ไม่มีอะไร "ผ่านไปแล้ว"
_REFERENCE = datetime(2000, 1, 3)


def mentions_time(text: str, *, part_of_day: bool = True) -> bool:
    """ประโยคนี้มีคำบอกวันหรือเวลาไหม (ไม่สนว่าถูกต้องหรือผ่านไปแล้ว).

    ใช้แยก "ทำตอนนี้" กับ "ให้ทำทีหลัง" · พบ 2026-09-28: "อีก 10 นาทีเตือนให้ลดเสียง" เคยลดเสียงทันที
    part_of_day=False = ไม่นับ "เช้า/บ่าย/เย็น" ลอย ๆ (เช่น "น้ำเย็น" ไม่ใช่เวลา) ใช้ตอนตัดสินว่าเป็นนัดหมายไหม
    """
    t = _Text(text)
    if t.take(RELATIVE):
        return True
    notes: list[str] = []
    tm, explicit = _time(t, notes)
    if explicit or (tm is not None and part_of_day):
        return True
    d, problem, _ = _date(t, _REFERENCE, notes)
    return d is not None or bool(problem)


def _what(rest: str) -> str:
    s = rest
    for w in TRIGGERS:
        s = s.replace(w, " ")
    s = re.sub(r"\b(เวลา|ตอน)\b", " ", s)
    for w in POLITE:
        s = s.replace(w, " ")
    s = re.sub(r"\s+", " ", s).strip(" ,.")
    s = re.sub(r"^(วัน|เวลา|ตอน)\s*", "", s).strip()
    # ช่วงของวันที่เหลือเป็นคำเดี่ยวหน้า/ท้ายชื่อนัด (สำรวจบน Pi 5 2026-10-12:
    # "พรุ่งนี้เช้า 9 โมงมีประชุม" → "เช้า มีประชุม") · ติดกับคำอื่นไม่ตัด ("กินข้าวเย็น")
    day = r"(เช้า|สาย|บ่าย|เย็น|ค่ำ|ดึก|คืน)(นี้)?"
    s = re.sub(rf"^{day}\s+|\s+{day}$", "", s).strip()
    s = re.sub(r"(ตอน|เวลา)$", "", s).strip()  # "เตือนกินข้าวเย็นตอน 6 โมงเย็น" → "กินข้าวเย็นตอน"
    return s or "เตือนความจำ"
