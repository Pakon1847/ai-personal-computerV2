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
    # search · open · back · forward · reload · scroll · close · app · site · url (การ์ด 0031) ·
    # media (การ์ด 0035 · direction = pause | play | next) · site_search (การ์ด 0036 · site + query)
    kind: str
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
_ORD = r"(?:อัน|ลำดับ)?\s*(?:ที่\s*)?(แรก|หนึ่ง|สอง|สาม|สี่|ห้า|หก|เจ็ด|แปด|เก้า|สิบ|\d{1,2})"
_OPEN = rf"(?:กด\s*)?(?:เข้า|เปิด|กด|คลิก|ไป|ดู)\s*(?:ไป\s*)?(?:ใน\s*|ดู\s*)?(?:ที่\s*)?{_LINK}\s*{_ORD}"
_OPEN_RE = re.compile(rf"{_OPEN}")
_COMPOUND = re.compile(rf"^(.+?)\s*(?:แล้ว\s*)?({_OPEN})$")
# "A แล้ว B" ทั่วไป (ปิดแท็บแล้วกลับไปหน้าผู้ช่วย · ค้นหา X แล้วเลื่อนลง · ชุด H2 = ชุดพัฒนารอบ 3)
_THEN = re.compile(r"(.+?)\s*แล้ว\s*(.+)")

_POLITE = re.compile(
    r"(?:\s*(?:ให้หน่อย|หน่อย|ด้วย|เลย|ครับผม|ครับ|ค่ะ|คะ|นะ|ฮะ|จ้ะ|จ้า|ให้|อีกที|อีกครั้ง|ได้ไหม|ได้มั้ย|ได้ป่ะ|ที|สิ|อีกนิด|แทน))+$"
)
# คำขอนำหน้า (ขอ… · ช่วย… · รบกวน… · ลอง… · กดปุ่ม… · กดย้อนกลับ) · ชุด H2 = ชุดพัฒนารอบ 3
_ASK = re.compile(r"^(?:(?:ขอ|ช่วย|รบกวน|ลอง)\s*|กด\s*(?:ปุ่ม\s*)?(?=ย้อน|ถอย|ไป|รี|โหลด|ปิด|กลับ))+")
# คำขอกลางประโยค ("หน้านี้ค้าง ช่วยโหลดใหม่ให้หน่อย") → ลองแปลส่วนหลังคำขอ (เฉพาะคำสั่งที่ไม่ใช่ค้นหา)
_ASK_MID = re.compile(r"(?:ช่วย|ขอ|รบกวน)")
_BACK = re.compile(
    r"(?:ย้อน|ถอย)\s*กลับ(?:\s*(?:ไป)?\s*หน้า\s*(?:ก่อน(?:หน้า)?|ที่แล้ว|เดิม|เมื่อกี้)|\s*ไป)?"
    r"|กลับ\s*(?:ไป)?\s*หน้า\s*(?:ก่อน(?:หน้า)?|ที่แล้ว|เดิม|เมื่อกี้)|back"
)
_FORWARD = re.compile(r"ไป\s*(?:หน้า\s*)?ข้างหน้า|ไป\s*(?:ที่\s*)?หน้า\s*(?:ถัด|ต่อ)\s*ไป|เดินหน้า|forward")
_RELOAD = re.compile(
    r"โหลด\s*(?:หน้า\s*(?:นี้|เว็บ)?\s*)?ใหม่|รี\s*(?:เฟรช|เฟรซ|โหลด)(?:\s*หน้า\s*(?:นี้|เว็บ)?)?|refresh|reload"
)
_SCROLL = re.compile(
    r"(?:เลื่อน|สกรอ(?:ลล์|ล)?)\s*(?:หน้า\s*(?:จอ|เว็บ)?\s*)?(?:กลับ\s*)?(ลง|ขึ้น)\s*(?:ไป|มา)?\s*(?:ดู\s*)?"
    r"(?:ข้าง\s*(?:ล่าง|บน))?\s*(?:ดู\s*ต่อ|อีก)?"
)
# คุมเพลง/วิดีโอ (การ์ด 0035) · ต้องมีคำว่าเพลง/วิดีโอ/คลิป ("หยุด" เดี่ยว ๆ ไม่ใช่คำสั่ง) ·
# "ปิดเสียง/เปิดเสียง/เพิ่มเสียง" ยังเป็นเสียงของเครื่อง (การ์ด 0008) · มีเวลาต่อท้าย ("…ตอนสามทุ่ม") = ไม่ตรงทั้งประโยค
_MEDIA = r"(?:เพลง|ว[ิี]ด[ิี]โอ|คลิป)"
_PAUSE = re.compile(
    rf"(?:หยุด|พัก|ปิด)\s*(?:เล่น\s*)?{_MEDIA}(?:\s*(?:นี้|ก่อน|ชั่วคราว|แป๊บ|แปบ))*|หยุด\s*ชั่วคราว"
)
_PLAY = re.compile(rf"(?:เล่น\s*(?:{_MEDIA}\s*)?|เปิด\s*{_MEDIA}\s*)ต่อ(?:\s*เลย)?")
_NEXT = re.compile(rf"(?:(?:ไป|เปิด|เล่น)\s*)?{_MEDIA}\s*(?:ถัด|ต่อ)\s*ไป|ข้าม\s*{_MEDIA}(?:\s*นี้)?")
_CLOSE = re.compile(r"ปิด\s*(?:แท็บ|แทบ|tab|หน้า\s*(?:นี้|เว็บ)|เว็บ)\s*(?:นี้|ที่\s*เปิด\s*อยู่)?\s*(?:ไป)?")
_APP = re.compile(
    r"(?:กลับ|ไป|สลับ)\s*(?:ไป)?\s*(?:ที่|หา)?\s*(?:แอป|แอพ|หน้า(?:ต่าง)?\s*(?:ผู้ช่วย|แชท|หลัก|แอป|แอพ)|ผู้ช่วย)"
)
SITE_NAMES = {
    "maps": r"กูเกิ้?ล\s*แม[พป]|แผนที่\s*กูเกิ้?ล|google\s*maps",
    "google": r"กูเกิ้?ล|google",
    "youtube": r"ยูทู[บป]|youtube",
    "wikipedia": r"วิกิพีเดีย|wikipedia",
    "gmail": r"จีเมล|gmail",
    # การ์ด 0031 · ปฏิทินต้องมีคำว่ากูเกิล ("เปิดปฏิทิน" เฉย ๆ = หน้าปฏิทินของเครื่อง ทางคำสั่งเครื่อง)
    "facebook": r"เฟ[ซส]\s*บุ[๊]?[กค]|facebook",
    "instagram": r"อินสตา(?:แกรม)?|ไอจี|instagram",
    "calendar": r"ปฏิทิน\s*กูเกิ้?ล|กูเกิ้?ล\s*ปฏิทิน|google\s*calendar",
    "drive": r"กูเกิ้?ล\s*ไดร์?[ฟบ]์?|ไดร์?[ฟบ]์?|google\s*drive",
}
# ค้นในบริการ (การ์ด 0036) · ชื่อบริการต้องตามหลัง "ใน" หรือ "เปิด" ·
# ไม่มีชื่อบริการ = ทางเดิม (ค้น Google / หาไฟล์) · ไดรฟ์ต้องมีคำว่ากูเกิล ("ไดรฟ์" เดี่ยว ๆ อาจหมายถึง USB) ·
# Google เองใช้ทางค้นเว็บเดิม
SEARCH_SITE_NAMES = {
    "youtube": SITE_NAMES["youtube"],
    "maps": SITE_NAMES["maps"] + r"|แผนที่",
    "wikipedia": SITE_NAMES["wikipedia"] + r"|วิกิ",
    "facebook": SITE_NAMES["facebook"],
    "drive": r"กูเกิ้?ล\s*ไดร์?[ฟบ]์?|google\s*drive",
    "gmail": r"จีเมล์?|อีเมล์?|gmail",
}
_SVC = "(?:" + "|".join(f"(?P<{k}>{v})" for k, v in SEARCH_SITE_NAMES.items()) + ")"
# "หา" ที่เป็นต้นคำอื่นไม่นับ (เหมือน _FIND ข้างล่าง: หาย หาก หาด …)
# พูดชื่อบริการชัดแล้ว จึงไม่ต้องกัน "หาร" (หารเลข) เหมือนค้นเว็บทั่วไป → "หารูป…" นับเป็นกริยา (พบในชุดวัดรอบ 1 · S20)
_VERB = r"(?:ค้น\s*หา|ค้น|หา(?![กดยม]|ว(?!ิ))|เสิร์[ชด]|เซิร์ช)"
_SAID = r"(?P<said>คำว่า|ว่า)?"
# "ค้นในยูทูบว่า X" · "ค้นหา X ในยูทูบ" · "เปิดยูทูบ(แล้ว)หา X" · คำค้น = กลุ่มชื่อ q
_IN_FIRST = re.compile(rf"(?:ช่วย\s*)?{_VERB}\s*(?:ดู\s*)?ใน\s*{_SVC}\s*{_SAID}\s*(?P<q>.*)")
_IN_LAST = re.compile(rf"(?:ช่วย\s*)?{_VERB}\s*{_SAID}\s*(?P<q>.+?)\s*ใน\s*{_SVC}")
_OPEN_THEN = re.compile(rf"เปิด\s*{_SVC}\s*(?:แล้ว\s*)?{_VERB}\s*{_SAID}\s*(?P<q>.+)")
MAX_QUERY = 200
# เล่าว่าหาไม่เจอ = เล่าปัญหา ไม่ใช่สั่งค้น ("เปิดยูทูบแล้วหาปุ่มตั้งค่าไม่เจอ" · พบในชุดวัดรอบ 1 · N10) ·
# ไม่ใช้ _LOST ทั้งก้อน: "อยู่ไหน" เป็นคำค้นแผนที่ได้ ("ค้นในแผนที่ว่าโรงพยาบาลอยู่ไหน")
_NOT_FOUND = re.compile(r"ไม่เจอ|ไม่พบ")
# ไม่มี "ว่า" และคำค้นขึ้นต้นด้วยคำเชื่อม = เล่าเรื่องต่อ ไม่ใช่คำค้น
# ("ค้นในเฟซบุ๊กแล้วมันค้างทุกที" · พบในชุดวัดรอบ 2 · Q06) · มี "ว่า" = ค้นได้ ("ค้นในยูทูบว่าแล้วไง")
_STORY = re.compile(r"(?:แล้ว|แต่|ทีไร)")


def _site_search(t: str) -> BrowseCommand | None:
    if _NOT_FOUND.search(t):
        return None
    for pat in (_IN_FIRST, _IN_LAST, _OPEN_THEN):
        if m := pat.fullmatch(t):
            if not m.group("said") and _STORY.match(m.group("q")):
                return None
            site = next(k for k in SEARCH_SITE_NAMES if m.group(k))
            query = m.group("q").strip(" \"'“”")[:MAX_QUERY].strip()
            if not query:  # "ค้นในยูทูบ" เฉย ๆ = เปิดหน้าบริการ
                return BrowseCommand("site", site=site)
            return BrowseCommand("site_search", query=query, site=site)
    return None


_SITE = re.compile(
    r"(?:เปิด|เข้า|ไป\s*(?:ที่)?)\s*(?:เว็บ\s*)?("
    + "|".join(f"(?P<{k}>{v})" for k, v in SITE_NAMES.items())
    + r")"
)
_SEARCH = re.compile(
    r"(?:ช่วย\s*)?(?:ค้น\s*หา|ค้น|เสิร์[ชด]|เซิร์ช|search|(?:กูเกิ้?ล|google)\s*(?:หา|ดู)?(?=\s*(?:ว่า|คำว่า)|(?<=หา)|(?<=ดู)))\s*"
    r"(?:ดู\s*(?:หน่อย\s*)?)?(?:ใน\s*(?:กูเกิ้?ล|google|เน็ต|อินเทอร์เน็ต|เว็บ)\s*)?(?:ว่า|คำว่า)?\s*(.+)"
)
# กริยาค้นหาอยู่ท้ายประโยค ("ราคาน้ำมัน ช่วยหาให้หน่อย" · "… ลองกูเกิลดู" · "… ช่วยหาในเน็ต") · การ์ด 0026 รอบ 2–3
_WHERE = r"(?:\s*ใน\s*(?:เน็ต|อินเทอร์เน็ต|เว็บ|กูเกิ้?ล))?"
_SEARCH_END = re.compile(
    r"(.+?)\s*(?:ลอง\s*)?(?:ช่วย\s*(?:ค้น\s*หา|ค้น|หา|เสิร์ช)|ค้น\s*หา|ค้น|เสิร์ช|กูเกิ้?ล(?=\s*ดู))(?:\s*ดู)?"
    + _WHERE
    + r"(?:\s*ให้)?"
)
# "X หาให้หน่อย" ("หา" เดี่ยวท้ายประโยค) นับเฉพาะเมื่อพูดเป็นคำขอ (มี ให้/หน่อย/ที ตามหลัง) · กัน "ของที่ต้องหา"
_SEARCH_END_ASKED = re.compile(r"(.+?)\s*หา" + _WHERE)
_ASKED_FIND = re.compile(r"หา" + _WHERE + r"\s*(?:ให้|หน่อย|ที)")
# "หา" ที่เป็นต้นคำอื่น (หาก หาด หาย หาว หาม หาร=หารเลข · หาร้าน หาวิธี หาราคา ไม่นับ ·
# "หาราคา…" เคยไม่ถูกจับ: พบในชุด H เสียงสังเคราะห์ การ์ด 0026 · ผลชุด H ไม่ได้รันซ้ำหลังแก้)
_FIND = re.compile(r"(?:ช่วย\s*)?หา(?![กดยม]|ว(?!ิ)|ร(?![้า]))\s*(.+)")
# "หา" ที่ไม่ใช่ค้นเว็บ: ของหาย ("หาแว่นไม่เจอ วางไว้ไหน") · หาเพื่อนคุย (ชุด H2 = ชุดพัฒนารอบ 3)
_LOST = re.compile(r"ไม่เจอ|ไม่พบ|วางไว้|ไว้ไหน|อยู่ไหน|เพื่อนคุย|คนคุย|เหงา")
# "หา/ค้นหา X" ที่เป็นงานในเครื่อง (สกิลค้นไฟล์) หรือโจทย์เลข ไม่ใช่ค้นเว็บ
_NOT_WEB = re.compile(r"(?:ไฟล์|เอกสาร|โฟลเดอร์|รูป(?:ในเครื่อง)?|ค่า|ผลรวม|ผลบวก|ผลคูณ|ผลต่าง|คำตอบ)")


# ตัวถอดเสียงได้ยินผิดแบบที่เจอบ่อย (ชุดพัฒนา browse_heard_dev · เสียง Piper ของ V1+V2 · 2026-10-13 ·
# เพิ่มจากชุดพัฒนา V1 V2 D กับ Zipformer/Typhoon 2026-10-14 · ไม่ได้ใช้ H/H2) ·
# แก้เฉพาะคำสั่ง/ชื่อเว็บ ไม่แก้คำค้น · ทางที่ไม่แน่ใจให้ไปทางปลอดภัย (ไฟ → ไฟล์ = สกิลค้นไฟล์ ไม่ส่งชื่อไฟล์ไปเว็บ)
_HEARD = [
    (r"^(ช่วย)?คน(?=หา(?!ย)|ใน(?:กูเกิ|เน็ต|อินเทอร์|เว็บ))", r"\1ค้น"),
    (r"^(ช่วย)?เสิร์[จฟ]", r"\1เสิร์ช"),
    (r"กู้?เกิ้?น|กู้เกิ้?ล", "กูเกิล"),
    (r"^(?:ยอน|ยาน)(?=\s*กลับ)", "ย้อน"),
    (r"^ตลับ", "กลับ"),
    (r"(^|แล้ว)(?:ข้าว|เท่า)(?=(?:ลิ|หลิ|เว|อัน|ผล))", r"\1เข้า"),
    (r"(เข้า|เปิด|คลิก|กด)หลิ", r"\1ลิ"),
    (r"^(?:คลึก|ขลิก|คลิ๊ก|คลีก)ก?(?=ลิ|อัน|เว)", "คลิก"),
    (r"^กฎ(?=ลิ|อัน|เว|ผล)", "กด"),
    (r"(?<=เข้า|เปิด|คลิก)(?:เวทย์|เวฟ|เว็ป|เวป)", "เว็บ"),
    (r"(?<=ลิง)แร[่ดต]$", "แรก"),
    (r"ผลลั?[บาพ]+(?=ที่|แรก)", "ผลลัพธ์"),
    (r"^ต?รีเฟ(?:ลด|รด|รน|ส|ด)", "รีเฟรช"),
    (r"^(?:ตีโหลด|รีโลด)", "รีโหลด"),
    (r"^เตือนหน้า$", "เดินหน้า"),
    (r"(?<=ไป)นะ(?=ก่อน|ที่แล้ว)", "หน้า"),
    (r"^โลด(?=ใหม่|หน้า)", "โหลด"),
    (r"^ไป(?:หน้า)?[ขค]้าง(?:หน้า|มา)?$", "ไปข้างหน้า"),
    (r"^เลื่อ[ดต]", "เลื่อน"),
    (r"^เลื่อนน่า", "เลื่อนหน้า"),
    (r"^เลื่อน(?:หน้า|น่า)?คืน", "เลื่อนขึ้น"),
    (r"(?<=ลง)อี$", "อีก"),
    (r"หน้า(?:หนี|มี)(?=$|ใหม่)", "หน้านี้"),
    (r"(?<=แ)(?:อ๊ก|อ๊ป|อ็ป|อ๊บ|อด|อฟ|อค|อ๊ค)$", "อป"),
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


def _single(t: str, asked: bool = False) -> BrowseCommand | None:
    one = _single_exact(t, asked)
    if one is None and (bare := _ASK.sub("", t)) != t and bare:
        one = _single_exact(bare, asked)  # "ขอกลับไปหน้าที่แล้ว" · "ลองหาข่าว…" · "กดปุ่มไปข้างหน้า"
    return one


def _single_exact(t: str, asked: bool) -> BrowseCommand | None:
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
    for direction, pat in (("pause", _PAUSE), ("play", _PLAY), ("next", _NEXT)):
        if pat.fullmatch(t):
            return BrowseCommand("media", direction=direction)
    if _CLOSE.fullmatch(t):
        return BrowseCommand("close")
    if _APP.fullmatch(t):
        return BrowseCommand("app")
    if m := _SITE.fullmatch(t):
        return BrowseCommand("site", site=next(k for k in SITE_NAMES if m.group(k)))
    if found := _site_search(t):  # ก่อนค้นเว็บทั่วไปและก่อนตัดเรื่องไฟล์: พูดชื่อบริการชัดเจนแล้ว
        return found
    m = _SEARCH.fullmatch(t) or _FIND.fullmatch(t)
    end = None
    if not m:
        end = _SEARCH_END.fullmatch(t) or (_SEARCH_END_ASKED.fullmatch(t) if asked else None)
    # หาไฟล์/โน้ตในเครื่อง = สกิลค้นไฟล์ ไม่ใช่ค้นเว็บ · หาของหาย/หาเพื่อนคุย ไม่ใช่ค้นเว็บ
    if (m or end) and not (fileintent.file_intent(t) or fileintent.file_time(t) or _LOST.search(t)):
        query = _POLITE.sub("", (m or end).group(1)).strip()
        # กริยาอยู่ท้าย: คำว่าไฟล์/เอกสารอยู่ตรงไหนของคำค้นก็ได้ ("…สรุปไว้ในไฟล์ไหน ช่วยหาให้หน่อย")
        bad = _NOT_WEB.search(query) if end else _NOT_WEB.match(query)
        if query and not bad:
            return BrowseCommand("search", query=query)
    return None


def parse(text: str) -> list[BrowseCommand]:
    raw = re.sub(r"(?<=[ก-๙])\s+(?=[ก-๙])", "", text.strip().lower())
    asked = bool(_ASKED_FIND.search(raw))
    t = _clean(text)
    if not t:
        return []
    # ค้นหาแล้วเข้าลิงก์ในประโยคเดียว (ดูก่อน: ไม่งั้นคำค้นกินท่อน "เข้าลิงก์แรก" ไปด้วย)
    if m := _COMPOUND.fullmatch(t):
        first, second = _single(_clean(m.group(1))), _single(m.group(2))
        if first and first.kind == "search" and second:
            return [first, second]
    # "A แล้ว B" ทั่วไป · B ต้องไม่ใช่ค้นหา (คำค้นมีคำว่า "แล้ว" ได้)
    if m := _THEN.fullmatch(t):
        first, second = _single(_clean(m.group(1))), _single(_clean(m.group(2)))
        if first and second and second.kind != "search":
            return [first, second]
    if one := _single(t, asked):
        return [one]
    # คำขอกลางประโยค: "หน้านี้ค้าง ช่วยโหลดใหม่ให้หน่อย" → แปลส่วนหลังคำขอ (ไม่ใช่ค้นหา)
    for m in _ASK_MID.finditer(t):
        if m.start() > 0 and (one := _single(t[m.start() :])) and one.kind != "search":
            return [one]
    return []
