"""คำขอหาไฟล์ของผู้ใช้ในเครื่อง ("หาไฟล์ใบเสร็จซ่อมแอร์" · "สัญญาเช่าอยู่ไหน") → ค้นด้วย aipc.files_search.

กฎแน่นอนก่อนถึง AI (AI ในเครื่องเปิดไฟล์ไม่ได้อยู่แล้ว) · ต้องมีทั้ง "สิ่งที่เป็นไฟล์/ที่จดไว้" และ "การถามหา"
ผล: docs/benchmarks/2026-10-01-file-intent
"""

from __future__ import annotations

import re

# สิ่งที่ผู้ใช้เก็บเป็นไฟล์ ("ไฟ" เฉย ๆ ไม่นับ: ต้องเป็น "ไฟล์")
THING = (r"(ไฟล์|เอกสาร|โน้ต|บันทึก(?!นัด|ไว้ว่า)|ที่(เคย)?จด|สลิป|สัญญา(?!ณ)|"
         r"ใบ(เสร็จ|แจ้งหนี้|กำกับ|รับรอง|สั่งซื้อ|เสนอราคา)|"
         r"เรซูเม่|สแกน|pdf|พรีเซนต์|ตาราง\S*ที่)")  # fmt: skip
FIND_VERB = re.compile(rf"(หา|ค้น(หา)?)\s*{THING}", re.I)
WHERE = re.compile(
    rf"{THING}.*?(อยู่\s*(ไหน|ที่ไหน|ตรงไหน|โฟลเดอร์ไหน)|ไฟล์ไหน|เก็บไว้\s*(ที่)?\s*ไหน|ชื่ออะไร)", re.I
)
HAVE = re.compile(rf"(มี|ขอ(ดู)?){THING}.*?(ไหน(บ้าง)?ที่|ในเครื่อง|ที่(เคย)?(จด|เขียน|ทำ|เก็บ))", re.I)
NOTED = re.compile(r"(เคย)?(จด|บันทึก|เขียน)\S*.*?ไว้.*?(ช่วย)?หา", re.I)
# ถามความรู้/สั่งงานอื่นเกี่ยวกับไฟล์ ไม่ใช่หาไฟล์ของตัวเอง
NOT_FIND = re.compile(
    r"แปลงไฟล์|บีบอัด|(คือ|ต่างกัน|ปลอดภัย)|ยังไง|อย่างไร|ต้องมีอะไร|ควรมีอะไร|"
    r"^(ช่วย)?\s*(สร้าง|ลบ|เปิด|ร่าง|เขียน|สรุป|แปล)",
)


def file_intent(text: str) -> bool:
    t = text.strip()
    if not t or NOT_FIND.search(t):
        return False
    return bool(FIND_VERB.search(t) or WHERE.search(t) or HAVE.search(t) or NOTED.search(t))


# ---------- ดูไฟล์ตามช่วงเวลา ("ไฟล์ที่แก้เมื่อวาน" · "เอกสารล่าสุด") ----------
# ผล: docs/benchmarks/2026-10-01-file-intent (หัวข้อค้นไฟล์ตามเวลา)
TIME_THING = r"(ไฟล์|เอกสาร|โน้ต|สไลด์|ที่(เคย)?จด)"
TIMES = [
    ("yesterday", r"เมื่อวาน(?!ซืน)"),
    ("today", r"วันนี้"),
    ("last_week", r"(สัปดาห์|อาทิตย์)\s*(ที่แล้ว|ก่อน)"),
    ("this_week", r"(สัปดาห์|อาทิตย์)\s*นี้"),
    ("last_month", r"เดือน\s*(ที่แล้ว|ก่อน)"),
    ("this_month", r"เดือน\s*นี้"),
    ("latest", r"ล่าสุด|เพิ่ง\s*(แก้|สร้าง|ทำ|เขียน|เปิด|จด)"),
]
FILE_VERB = r"(แก้|สร้าง|ทำ|เขียน|จด|เปิด|เซฟ|บันทึก)"
TIME_NOT = re.compile(
    r"แปลงไฟล์|ยังไง|อย่างไร|ต้อง(ใช้|เตรียม|ส่ง)|ส่งไฟล์|ตั้ง(เตือน|ปลุก)|"
    r"^(ช่วย)?\s*(สร้าง|ลบ|ร่าง|เขียน|สรุป|แปล|แก้ไข|จด)"
)


def file_time(text: str) -> str | None:
    """ช่วงเวลาของคำขอดูไฟล์ (today yesterday … latest) · ไม่ใช่คำขอดูไฟล์ตามเวลา = None."""
    t = text.strip()
    if not t or TIME_NOT.search(t) or not re.search(TIME_THING, t, re.I):
        return None
    for label, pat in TIMES:
        m = re.search(pat, t)
        if not m:
            continue
        # คำกริยาเกี่ยวกับไฟล์อยู่ใกล้คำบอกเวลา (ก่อนหรือหลัง ไม่เกิน ~20 ตัวอักษร)
        near = t[max(0, m.start() - 20) : m.end() + 20]
        if re.search(FILE_VERB, near):
            return label
    return None


def time_range(label: str, now):
    """(เริ่ม, จบ) ของช่วงเวลา · latest = (None, None) (เรียงใหม่สุดเฉย ๆ)."""
    from datetime import datetime, timedelta

    day = datetime(now.year, now.month, now.day)
    week = day - timedelta(days=day.weekday())
    month = day.replace(day=1)
    prev_month = (month - timedelta(days=1)).replace(day=1)
    return {
        "today": (day, day + timedelta(days=1)),
        "yesterday": (day - timedelta(days=1), day),
        "this_week": (week, week + timedelta(days=7)),
        "last_week": (week - timedelta(days=7), week),
        "this_month": (month, (month + timedelta(days=32)).replace(day=1)),
        "last_month": (prev_month, month),
    }.get(label, (None, None))


LABELS = {"today": "วันนี้", "yesterday": "เมื่อวาน", "this_week": "สัปดาห์นี้",
          "last_week": "สัปดาห์ที่แล้ว", "this_month": "เดือนนี้", "last_month": "เดือนที่แล้ว",
          "latest": "ล่าสุด"}  # fmt: skip
# "อยาก": พบ 2026-10-12 "อยากดูไฟล์ที่ทำสัปดาห์นี้ทั้งหมด" ได้หัวข้อ "อยาก" → ไม่พบไฟล์
_WORDS = """อยาก ขอ ดู หา ค้น ช่วย แสดง ให้ หน่อย ที ทั้งหมด อะไร บ้าง ไหน อยู่ ตรง ไป ที่ ฉัน ผม เรา ของ ใน
เมื่อ ไว้ ไฟล์ เอกสาร โน้ต รายการ list มี ครับ ค่ะ คะ นะ เคย แก้ไข แก้ สร้าง ทำ เขียน จด เปิด เซฟ บันทึก
เพิ่ง คือ ล่าสุด วันนี้ เมื่อวาน สัปดาห์ อาทิตย์ เดือน ที่แล้ว ก่อน นี้""".split()
# คำยาวก่อน ("เมื่อวาน" ก่อน "เมื่อ" · "แก้ไข" ก่อน "แก้")
# ตัดเลขและเครื่องหมาย ASCII เท่านั้น (สระ/วรรณยุกต์ไทยไม่ใช่ \w จึงห้ามตัดด้วย \W)
FILLER = re.compile("|".join(sorted(_WORDS, key=len, reverse=True)), re.I)


def topic(text: str) -> str:
    """คำที่เหลือหลังตัดคำขอ/เวลา ("หาไฟล์รายงานที่แก้เมื่อวาน" → "รายงาน") · ว่าง = ดูตามเวลาอย่างเดียว."""
    rest = FILLER.sub(" ", text)
    rest = re.sub(r"[0-9!-/:-@\[-`{-~]", " ", rest)
    rest = re.sub(r"\s+", " ", rest).strip()
    return rest if len(rest.replace(" ", "")) >= 3 else ""
