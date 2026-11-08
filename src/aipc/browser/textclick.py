"""กดปุ่มตามคำที่เห็นบนหน้าเว็บ (การ์ด 0069) · โค้ดเทียบคำกับป้ายของปุ่มที่มองเห็นจริง ไม่ใช่ AI เดา (H6).

ที่มา: สกิลประจำเว็บที่ Claude สร้างเดาตัวเลือก CSS โดยไม่เห็นหน้าเว็บ (H3 ไม่ส่งหน้าให้ Claude) →
เดาถูกบ้างผิดบ้าง (Pakon ที่จอ 2026-10-28: Viu/Youku "เข้าสู่ระบบ") · เบราว์เซอร์รู้อยู่แล้วว่าปุ่มไหนเขียนว่าอะไร →
อ่านป้ายจากหน้าจริง (control.BUTTONS_JS) แล้วเทียบด้วยโค้ดนี้

ผลการเลือก: ตรง 1 ความหมาย = กด (ปุ่มซ้ำชื่อเดียวกัน = ตัวบนสุด) · ใกล้หลายปุ่ม = บอกชื่อให้เลือก ไม่กด ·
ปุ่มที่แตะเงิน/บัญชี (คำเสี่ยงชุดเดียวกับสกิลประจำเว็บ) = บอกให้กดเองที่จอ ไม่กด (H1 H2) · ไม่เจอ = ไม่กดอะไร
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# คำที่มีความหมายเดียวกัน (ป้ายบนเว็บมักเป็นภาษาอังกฤษ ผู้ใช้พูดไทย) · คู่ที่พบบ่อยเท่านั้น ไม่ใช่พจนานุกรม
SAME = (
    ("เข้าสู่ระบบ", "ล็อกอิน", "ล็อคอิน", "ลงชื่อเข้าใช้", "login", "log in", "sign in", "signin"),
    ("ค้นหา", "search"),
    ("หน้าแรก", "หน้าหลัก", "home"),
    ("ถัดไป", "ต่อไป", "หน้าถัดไป", "next"),
    ("ก่อนหน้า", "หน้าก่อน", "previous", "prev"),
    ("ดูทั้งหมด", "ทั้งหมด", "see all", "view all", "show all"),
    ("ดูเพิ่มเติม", "เพิ่มเติม", "อ่านต่อ", "ดูเพิ่ม", "more", "show more", "read more", "see more"),
    ("เมนู", "menu"),
    ("ปิด", "close"),
    ("ตกลง", "ok", "okay"),
    ("ยอมรับ", "ยอมรับทั้งหมด", "accept", "accept all", "agree", "i agree"),
    ("ภาษาไทย", "ไทย", "thai"),
    ("ภาษาอังกฤษ", "อังกฤษ", "english"),
    ("ตั้งค่า", "settings", "setting"),
    ("ช่วยเหลือ", "help"),
    ("ดาวน์โหลด", "download"),
)
# คำพูดนำหน้า/ลงท้ายที่ไม่ใช่ชื่อปุ่ม · "เข้า" ไม่ตัดเมื่อเป็น "เข้าสู่ระบบ"
_LEAD = re.compile(
    r"^(?:(?:ช่วย|ขอ|ลอง|รบกวน)\s*)*(?:(?:กด|คลิ๊?ก|จิ้ม|เลือก|แตะ|เข้า(?!\s*สู่)|ไปที่)\s*)+"
    r"(?:(?:ที่\s*)?(?:ปุ่ม|ลิ้?ง[กค]์?|เมนู|แท็บ|คำว่า)\s*)*"
)
_TAIL = re.compile(r"(?:\s*(?:ให้หน่อย|หน่อย|ให้ที|ที|ครับ|ค่ะ|คะ|นะ|เลย|ด้วย|ซิ|สิ))+$")
_QUESTION = re.compile(r"ไหม|มั้ย|อะไร|ทำไม|ยังไง|อย่างไร|ไหน|เมื่อไ|กี่|หรือเปล่า|\?")
_PUNCT = re.compile(r"[\s​.,:;!?()\[\]{}\"'“”‘’·•|/\\>+*_–—-]+")
MAX_WORDS = 30  # ยาวกว่านี้ = ประโยคคุย/เล่าเรื่อง ไม่ใช่ชื่อปุ่ม
MAX_PARTIAL_LABEL = 40  # ป้ายยาว (หัวข้อข่าว ชื่อคลิป) ที่บังเอิญมีคำสั้น ๆ ไม่นับว่าเป็นปุ่มนั้น
MAX_CHOICES = 4
# ไม่สนวรรณยุกต์ ไม้ไต่คู้ การันต์ และ ค = ก: คนสะกดไม่ตรงกัน
# (บุ๊กมาร์ค/บุ๊กมาร์ก ในหน้า Viu จริง 2026-10-28 · ล็อคอิน/ล็อกอิน · กูเกิ้ล/กูเกิล)
_MARKS = re.compile("[\u0e47-\u0e4c]")
# ไม่มีปุ่ม "เข้าสู่ระบบ" ในหน้า → ทางเข้าบัญชีของเว็บ (Viu = "โปรไฟล์" · Youku = รูปคนมุมขวาบนไม่มีชื่อ
# ที่ BUTTONS_JS ตั้งป้ายให้ว่า "ไอคอนบัญชี") · กดแล้วหน้าเข้าสู่ระบบขึ้น (ลองบน Pi 5 2026-10-28)
ACCOUNT = ("ไอคอนบัญชี", "โปรไฟล์", "profile", "บัญชี", "บัญชีของฉัน", "account", "my account", "ฉัน", "me")


def norm(text: str) -> str:
    return _MARKS.sub("", _PUNCT.sub("", (text or "").lower())).replace("ค", "ก")


def spoken_target(text: str) -> tuple[str, bool]:
    """(ชื่อปุ่มที่พูด, พูดคำว่า กด/คลิก ไหม) · ไม่ใช่ชื่อปุ่ม = ("", False)."""
    t = (text or "").strip()
    if not t or _QUESTION.search(t):
        return "", False
    m = _LEAD.match(t)
    said_press = bool(m and m.group(0).strip())
    words = _TAIL.sub("", t[m.end() :] if m else t).strip()
    if not words or len(words) > MAX_WORDS:
        return "", False
    return words, said_press


def variants(words: str) -> set[str]:
    """คำที่พูด + คำที่ความหมายเดียวกัน (normalize แล้ว)."""
    n = norm(words)
    for group in SAME:
        g = {norm(w) for w in group}
        if n in g:
            return g
    return {n} if n else set()


def risky(label: str) -> bool:
    from aipc.skills.sitecmd import RISKY

    low = label.lower()
    return any(w in low for w in RISKY)


@dataclass
class Pick:
    item: dict | None = None  # ปุ่มที่จะกด {"i", "label", "kind"}
    instead: bool = False  # ไม่มีปุ่มเข้าสู่ระบบ → กดทางเข้าบัญชีแทน (บอกผู้ใช้)
    choices: list[str] = field(default_factory=list)  # ใกล้หลายปุ่ม = ชื่อให้ผู้ใช้เลือก
    risky: bool = False


def choose(words: str, items: list[dict]) -> Pick:
    """เลือกปุ่มจากรายการ (เรียงบนลงล่างแล้ว) · words มีหลายแบบได้ คั่นด้วย "|" (สกิลประจำเว็บ)."""
    want: set[str] = set()
    for w in (words or "").split("|"):
        want |= variants(w)
    if not want:
        return Pick()
    exact = [it for it in items if norm(it.get("label", "")) in want]
    hits = exact or [
        it
        for it in items
        if len(lab := norm(it.get("label", ""))) <= MAX_PARTIAL_LABEL
        and any(len(v) >= 3 and v in lab for v in want)
    ]
    if not hits:
        if want & variants("เข้าสู่ระบบ"):
            entry = {norm(x) for x in ACCOUNT}
            if acc := [it for it in items if norm(it.get("label", "")) in entry]:
                return Pick(item=acc[0], instead=True)
        return Pick()
    labels = list(dict.fromkeys(it["label"] for it in hits))
    # ตรงเป๊ะ = ความหมายเดียวกันทั้งหมด (ป้ายซ้ำหัว/ท้ายหน้า หรือคำพ้อง) → ตัวบนสุด · ใกล้หลายแบบ = ถาม
    if not exact and len({norm(x) for x in labels}) > 1:
        return Pick(choices=labels[:MAX_CHOICES])
    it = hits[0]
    return Pick(item=it, risky=risky(it["label"]) or any(risky(w) for w in words.split("|")))


def refuse_text(words: str, pick: Pick) -> str:
    """คำบอกเมื่อไม่กด (H5) · "" = กดได้."""
    if pick.risky and pick.item:
        return f"ปุ่ม “{pick.item['label']}” เกี่ยวกับเงินหรือบัญชี · กดเองที่จอ · ไม่ได้กดอะไร"
    if pick.choices:
        names = " · ".join(f"“{c}”" for c in pick.choices)
        return f"เจอหลายปุ่ม: {names} · พูดชื่อปุ่มให้ตรง · ไม่ได้กดอะไร"
    if pick.item is None:
        first = words.split("|")[0]
        return f"ไม่เห็นปุ่ม “{first}” บนจอ · เลื่อนหน้าให้เห็นปุ่มก่อน หรือกดเองที่จอ · ไม่ได้กดอะไร"
    return ""
