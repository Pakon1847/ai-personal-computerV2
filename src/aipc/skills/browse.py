"""แปลคำพูดเป็นคำสั่งเว็บ (การ์ด 0024) · กฎล้วน ไม่ใช้ LLM · ใช้เฉพาะทางคีย์ลัดสั่งด้วยเสียง.

คืนรายการคำสั่งตามลำดับ (เช่น "ค้นหาราคาทองแล้วเข้าลิงก์แรก" = ค้นหา + เปิดลิงก์ 1) ·
[] = ไม่ใช่คำสั่งเว็บ → แอปส่งประโยคนี้ไปทางเดิม (สกิล / AI ในเครื่อง / Claude)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from aipc.skills import fileintent


@dataclass(frozen=True)
class BrowseCommand:
    kind: str  # search · open · back · forward · reload · scroll · close · app · site
    query: str = ""
    n: int = 0
    direction: str = ""
    site: str = ""

    def as_dict(self) -> dict:
        extra = {"query": self.query, "n": self.n, "direction": self.direction, "site": self.site}
        return {"kind": self.kind, **{k: v for k, v in extra.items() if v}}


NUMBERS = {"แรก": 1, "หนึ่ง": 1, "สอง": 2, "สาม": 3, "สี่": 4, "ห้า": 5,
           "หก": 6, "เจ็ด": 7, "แปด": 8, "เก้า": 9, "สิบ": 10}  # fmt: skip
_LINK = r"(?:ลิ้?ง(?:[กค]์)?|link|เว็บ|ผล(?:ลัพธ์|การค้นหา)?|อัน)"
_ORD = r"(?:อัน)?\s*(?:ที่\s*)?(แรก|หนึ่ง|สอง|สาม|สี่|ห้า|หก|เจ็ด|แปด|เก้า|สิบ|\d{1,2})"
_OPEN = rf"(?:กด\s*)?(?:เข้า|เปิด|กด|คลิก|ไป)\s*(?:ที่\s*)?{_LINK}\s*{_ORD}"
_OPEN_RE = re.compile(rf"{_OPEN}")
_COMPOUND = re.compile(rf"^(.+?)\s*(?:แล้ว\s*)?({_OPEN})$")

_POLITE = re.compile(r"(?:\s*(?:ให้หน่อย|หน่อย|ด้วย|เลย|ครับผม|ครับ|ค่ะ|คะ|นะ|ฮะ|จ้ะ|จ้า|ให้|อีกที|อีกครั้ง))+$")
_BACK = re.compile(
    r"(?:ย้อน|ถอย)\s*กลับ(?:\s*(?:ไป)?\s*หน้า\s*(?:ก่อน(?:หน้า)?|ที่แล้ว|เดิม)|\s*ไป)?"
    r"|กลับ\s*(?:ไป)?\s*หน้า\s*(?:ก่อน(?:หน้า)?|ที่แล้ว|เดิม)|back"
)
_FORWARD = re.compile(r"ไป\s*(?:หน้า\s*)?ข้างหน้า|เดินหน้า|forward")
_RELOAD = re.compile(
    r"โหลด\s*(?:หน้า\s*(?:นี้|เว็บ)?\s*)?ใหม่|รี\s*(?:เฟรช|เฟรซ|โหลด)(?:\s*หน้า\s*(?:นี้|เว็บ)?)?|refresh|reload"
)
_SCROLL = re.compile(r"เลื่อน\s*(?:หน้า\s*(?:จอ|เว็บ)?\s*)?(?:กลับ\s*)?(ลง|ขึ้น)\s*(?:ไป|มา)?\s*(?:อีก)?")
_CLOSE = re.compile(r"ปิด\s*(?:แท็บ|แทบ|tab|หน้า\s*(?:นี้|เว็บ)|เว็บ)\s*(?:นี้)?")
_APP = re.compile(r"(?:กลับ|ไป)\s*(?:ไป)?\s*(?:ที่|หา)?\s*(?:แอป|แอพ|หน้า\s*(?:ผู้ช่วย|แชท|หลัก)|ผู้ช่วย)")
SITE_NAMES = {
    "google": r"กูเกิ้?ล|google",
    "youtube": r"ยูทู[บป]|youtube",
    "wikipedia": r"วิกิพีเดีย|wikipedia",
    "gmail": r"จีเมล|gmail",
    "maps": r"กูเกิ้?ลแม[พป]|google\s*maps",
}
_SITE = re.compile(
    r"เปิด\s*(?:เว็บ\s*)?(" + "|".join(f"(?P<{k}>{v})" for k, v in SITE_NAMES.items()) + r")"
)
_SEARCH = re.compile(
    r"(?:ช่วย\s*)?(?:ค้น\s*หา|ค้น|เสิร์[ชด]|เซิร์ช|search|(?:กูเกิ้?ล|google)\s*(?:หา|ดู)?(?=\s*(?:ว่า|คำว่า)|(?<=หา)|(?<=ดู)))\s*"
    r"(?:ใน\s*(?:กูเกิ้?ล|google|เน็ต|อินเทอร์เน็ต|เว็บ)\s*)?(?:ว่า|คำว่า)?\s*(.+)"
)
# "หา" ที่เป็นต้นคำอื่น (หาก หาด หาย หาว หาม หาร=หารเลข · หาร้าน หาวิธี หาราคา ไม่นับ ·
# "หาราคา…" เคยไม่ถูกจับ: พบในชุด H เสียงสังเคราะห์ การ์ด 0026 · ผลชุด H ไม่ได้รันซ้ำหลังแก้)
_FIND = re.compile(r"(?:ช่วย\s*)?หา(?![กดยม]|ว(?!ิ)|ร(?![้า]))\s*(.+)")
# "หา/ค้นหา X" ที่เป็นงานในเครื่อง (สกิลค้นไฟล์) หรือโจทย์เลข ไม่ใช่ค้นเว็บ
_NOT_WEB = re.compile(r"(?:ไฟล์|เอกสาร|โฟลเดอร์|รูป(?:ในเครื่อง)?|ค่า|ผลรวม|ผลบวก|ผลคูณ|ผลต่าง|คำตอบ)")


# whisper ถอดเสียงพูดผิดแบบที่เจอบ่อย (ชุดพัฒนา browse_heard_dev · เสียง Piper ของ V1+V2 · 2026-10-13) ·
# แก้เฉพาะคำสั่ง/ชื่อเว็บ ไม่แก้คำค้น · ทางที่ไม่แน่ใจให้ไปทางปลอดภัย (ไฟ → ไฟล์ = สกิลค้นไฟล์ ไม่ส่งชื่อไฟล์ไปเว็บ)
_HEARD = [
    (r"^(ช่วย)?คน(?=หา(?!ย)|ใน(?:กูเกิ|เน็ต|อินเทอร์|เว็บ))", r"\1ค้น"),
    (r"^(ช่วย)?เสิร์[จฟ]", r"\1เสิร์ช"),
    (r"กูเกิ้?น", "กูเกิล"),
    (r"^ยอน", "ย้อน"),
    (r"^ตลับ", "กลับ"),
    (r"(^|แล้ว)(?:ข้าว|เท่า)(?=(?:ลิ|หลิ|เว|อัน|ผล))", r"\1เข้า"),
    (r"(เข้า|เปิด|คลิก|กด)หลิ", r"\1ลิ"),
    (r"^(?:คลึก|ขลิก|คลิ๊ก)ก?(?=ลิ|อัน|เว)", "คลิก"),
    (r"(?<=เข้า|เปิด|คลิก)(?:เวทย์|เวฟ|เว็ป|เวป)", "เว็บ"),
    (r"(?<=ลิง)แร่$", "แรก"),
    (r"ผลลับ", "ผลลัพธ์"),
    (r"^รีเฟ(?:ลด|รด|ส|ด)", "รีเฟรช"),
    (r"^ตีโหลด", "รีโหลด"),
    (r"^โลด(?=ใหม่|หน้า)", "โหลด"),
    (r"^ไป(?:หน้า)?[ขค]้าง(?:หน้า|มา)?$", "ไปข้างหน้า"),
    (r"^เลื่อ[ดต]", "เลื่อน"),
    (r"^เลื่อนน่า", "เลื่อนหน้า"),
    (r"^เลื่อน(?:หน้า|น่า)?คืน", "เลื่อนขึ้น"),
    (r"(?<=ลง)อี$", "อีก"),
    (r"หน้า(?:หนี|มี)(?=$|ใหม่)", "หน้านี้"),
    (r"(?<=แ)(?:อ๊ก|อ๊ป|อ็ป|อ๊บ|อด)$", "อป"),
    (r"(?<=หน้า)แฉด$", "แชท"),
    (r"ยูทู[ลก]$", "ยูทูบ"),
    (r"วิกฤติพีเดีย", "วิกิพีเดีย"),
    (r"^((?:ช่วย)?(?:ค้นหา|ค้น|หา))ไฟ(?!ล์|ฉาย|แช็|ไหม้|ดับ|ฟ้า|แนนซ์)", r"\1ไฟล์"),
]
_HEARD_RE = [(re.compile(a), b) for a, b in _HEARD]


def _clean(text: str) -> str:
    t = re.sub(r"\s+", " ", text.strip().strip(".!?,。 ")).lower()
    t = re.sub(r"(?<=[ก-๙])\s+(?=[ก-๙])", "", t)  # whisper เว้นวรรคระหว่างคำไทย ("เลื่อน ลง")
    t = _POLITE.sub("", t).strip()
    for pat, new in _HEARD_RE:
        t = pat.sub(new, t)
    return t


def _ordinal(word: str) -> int:
    return int(word) if word.isdigit() else NUMBERS[word]


def _single(t: str) -> BrowseCommand | None:
    if m := _OPEN_RE.fullmatch(t):
        return BrowseCommand("open", n=_ordinal(m.group(1)))
    if _BACK.fullmatch(t):
        return BrowseCommand("back")
    if _FORWARD.fullmatch(t):
        return BrowseCommand("forward")
    if _RELOAD.fullmatch(t):
        return BrowseCommand("reload")
    if m := _SCROLL.fullmatch(t):
        return BrowseCommand("scroll", direction="down" if m.group(1) == "ลง" else "up")
    if _CLOSE.fullmatch(t):
        return BrowseCommand("close")
    if _APP.fullmatch(t):
        return BrowseCommand("app")
    if m := _SITE.fullmatch(t):
        return BrowseCommand("site", site=next(k for k in SITE_NAMES if m.group(k)))
    m = _SEARCH.fullmatch(t) or _FIND.fullmatch(t)
    # หาไฟล์/โน้ตในเครื่อง = สกิลค้นไฟล์ ไม่ใช่ค้นเว็บ
    if m and not (fileintent.file_intent(t) or fileintent.file_time(t)):
        query = _POLITE.sub("", m.group(1)).strip()
        if query and not _NOT_WEB.match(query):
            return BrowseCommand("search", query=query)
    return None


def parse(text: str) -> list[BrowseCommand]:
    t = _clean(text)
    if not t:
        return []
    # ค้นหาแล้วเข้าลิงก์ในประโยคเดียว (ดูก่อน: ไม่งั้นคำค้นกินท่อน "เข้าลิงก์แรก" ไปด้วย)
    if m := _COMPOUND.fullmatch(t):
        first, second = _single(_clean(m.group(1))), _single(m.group(2))
        if first and first.kind == "search" and second:
            return [first, second]
    one = _single(t)
    return [one] if one else []
