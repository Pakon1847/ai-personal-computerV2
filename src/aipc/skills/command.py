"""สกิล 4: แปลคำสั่งเครื่องภาษาไทยแบบกำหนดแน่นอน (BRIEF 5.6 ข้อ 2) — ไม่ผ่าน LLM.

ทำไมไม่ใช้ LLM: คำสั่งเครื่องต้องตอบเร็วและต้องไม่เดา · LLM บน Pi ใช้เวลาหลายวินาทีกว่าจะตอบ
และอาจตีความผิด ตัวแปลแบบกฎจึงเร็วกว่า ทดสอบได้ครบทุกกรณี และอธิบายกรรมการได้บรรทัดต่อบรรทัด

ขั้นตอน:
1. ทำความสะอาดข้อความ: ตัดคำสุภาพที่ **หัวหรือท้ายประโยค** เท่านั้น ("ช่วย…" "…หน่อยครับ") และช่องว่าง
   ไม่ตัดกลางคำ — เคยตัด "ช่วย" ออกจาก "ผู้ช่วย" จนหน้าผู้ช่วยเปิดด้วยเสียงไม่ได้เลย (ผล baseline การ์ด 0008)
2. หาชนิดคำสั่งจากคำกริยา/คำสำคัญ: เสียง → หน้าในระบบ → เว็บ/แอป
3. หาเป้าหมายจากรายชื่อที่รู้จัก (รวมคำเรียกแบบไทย เช่น "ยูทูบ")
   **คำเรียกที่ยาวที่สุดชนะ** ("ตัวจัดการไฟล์" ชนะ "ไฟล์") · ยาวเท่ากันแต่คนละเป้า = ไม่มั่นใจ ถามก่อน
   ตรงเป๊ะ = มั่นใจ · ใกล้เคียง (สะกดผิด/ถอดเสียงเพี้ยน) = ถามก่อนว่า "หมายถึง … ใช่ไหม"
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from aipc.skills.actions import APPS, PAGES, SITES, Plan
from aipc.skills.thainum import find_number

# คำสุภาพ ตัดเฉพาะหัว/ท้ายประโยค (ตัดซ้ำจนไม่เหลือ เช่น "หน่อย" + "ครับ")
POLITE_START = ("ช่วย", "กรุณา", "ขอ")
POLITE_END = ("ให้หน่อย", "หน่อย", "ครับ", "ค่ะ", "คะ", "นะ", "จ้า", "ด้วย", "เลย")
# ยาวก่อนสั้น: "ไปที่" ต้องตรวจก่อน "ไป" · "ดู"/"เช็ค" ใช้กับหน้าในระบบและเว็บ ("ขอดูไฟล์ของฉัน")
OPEN_VERBS = ("กลับไปที่", "กลับไป", "ไปที่", "เปิด", "เข้า", "ไป", "ดู", "เช็ค", "เช็ก", "open")

# คำเรียกของแต่ละเป้าหมาย · ใส่คำที่ระบบถอดเสียงมักให้ออกมาด้วย (BRIEF 5.6 ควรมี: ชื่ออังกฤษต้องมีคำไทย)
SITE_ALIASES = {
    "youtube": ("youtube", "ยูทูบ", "ยูทูป", "ยูทิวบ์"),
    "gmail": ("gmail", "จีเมล", "จีเมล์", "อีเมล", "เมล"),
    "google": ("google", "กูเกิล", "กูเกิ้ล"),
    "wikipedia": ("wikipedia", "วิกิพีเดีย", "วิกิ"),
    "maps": ("googlemaps", "maps", "แผนที่", "กูเกิลแมพ"),
}
APP_ALIASES = {
    "browser": ("เบราว์เซอร์", "บราวเซอร์", "เว็บเบราว์เซอร์", "chromium", "โครเมียม", "อินเทอร์เน็ต"),
    "terminal": ("เทอร์มินัล", "เทอมินัล", "terminal"),
    "filemanager": ("ตัวจัดการไฟล์", "จัดการไฟล์", "โฟลเดอร์", "filemanager"),
}
PAGE_ALIASES = {
    "settings": ("ตั้งค่า", "การตั้งค่า", "settings", "เซ็ตติ้ง"),
    "files": ("ไฟล์ของฉัน", "ไฟล์", "files"),
    "health": ("สุขภาพเครื่อง", "สถานะเครื่อง", "health"),
    "skills": ("สกิล", "skill", "skills"),
    "privacy": ("ความเป็นส่วนตัว", "privacy"),
    "workspace": ("ผู้ช่วย", "แชท", "หน้าหลัก"),
}

SURE = 1.0
FUZZY_CUTOFF = 0.72  # ต่ำกว่านี้ถือว่าไม่ใช่คำสั่ง · สูงกว่านี้แต่ไม่ตรงเป๊ะ = ถามก่อน


@dataclass(frozen=True)
class Command:
    plan: Plan
    confidence: float
    heard: str

    @property
    def needs_confirmation(self) -> bool:
        """ถามก่อนเมื่อไม่มั่นใจ หรือ Action เสี่ยงสูง (BRIEF 5.6 ตารางระดับความเสี่ยง)."""
        return self.confidence < 0.9 or self.plan.spec.risk == "high"


def normalize(text: str) -> str:
    t = re.sub(r"\s+", "", text.strip().lower())
    changed = True
    while changed:
        changed = False
        for w in POLITE_START:
            if t.startswith(w) and len(t) > len(w):
                t, changed = t[len(w) :], True
        for w in POLITE_END:
            if t.endswith(w) and len(t) > len(w):
                t, changed = t[: -len(w)], True
    return t


AMBIGUOUS = 0.8  # คำเรียกยาวเท่ากันแต่ชี้คนละเป้า → ต่ำกว่า 0.9 = ถามก่อน


def _match(targets: list[str], groups: list[tuple[str, dict]]) -> tuple[str, str, float] | None:
    """หาเป้าหมายจากทุกกลุ่มพร้อมกัน · คืน (กลุ่ม, id, ความมั่นใจ) หรือ None.

    ตรงแบบมีคำเรียกอยู่ในข้อความ: เลือกคำเรียกที่ยาวที่สุด · ไม่มีเลย: ลองแบบใกล้เคียง (สะกดผิด)
    """
    hits = [
        (len(name), group, key)
        for group, aliases in groups
        for key, names in aliases.items()
        for name in names
        if any(name in t for t in targets)
    ]
    if hits:
        longest = max(n for n, _, _ in hits)
        best = {(g, k) for n, g, k in hits if n == longest}
        group, key = next((g, k) for _, g, k in hits if (g, k) in best)
        return group, key, SURE if len(best) == 1 else AMBIGUOUS
    flat = {
        n: (group, key)
        for group, aliases in groups
        for key, names in aliases.items()
        for n in names
    }
    close = difflib.get_close_matches(targets[-1], flat, n=1, cutoff=FUZZY_CUTOFF)
    if close:
        ratio = difflib.SequenceMatcher(None, targets[-1], close[0]).ratio()
        return (*flat[close[0]], ratio)
    return None


def _volume(t: str, heard: str) -> Command | None:
    # ต้องตรวจ "เปิดเสียง" ก่อน เพราะคำว่า "เปิดเสียง" มี "ปิดเสียง" ซ้อนอยู่ข้างใน (เ-ปิดเสียง)
    if "เปิดเสียง" in t or "unmute" in t:
        if find_number(t) is None:
            return Command(Plan("unmute", {}, "เปิดเสียงแล้ว"), SURE, heard)
    elif "ปิดเสียง" in t or "mute" in t:
        return Command(Plan("mute", {}, "ปิดเสียงแล้ว"), SURE, heard)
    if "เสียง" not in t and "volume" not in t:
        return None
    n = find_number(t)
    if n is not None:
        if not 0 <= n <= 100:
            return None
        return Command(Plan("set_volume", {"percent": n}, f"ปรับเสียงเป็น {n}%"), SURE, heard)
    # ต้องมีคำบอกทิศทางชัด ๆ · "ดัง"/"เบา" เดี่ยว ๆ ไม่นับ ("เสียงข้างบ้านดังมาก" ไม่ใช่คำสั่ง)
    # "…ไป" แบบไทย = มากเกิน: "เสียงดังไป" = ให้ลด · ตรวจก่อน "ดังขึ้น"
    if any(w in t for w in ("ดังไป", "เบาลง", "ลดเสียง", "เบาเสียง", "เบากว่านี้")):
        return Command(Plan("change_volume", {"step": -10}, "ลดเสียงลง 10%"), SURE, heard)
    if any(w in t for w in ("เบาไป", "ดังขึ้น", "เพิ่มเสียง", "เร่งเสียง", "ดังกว่านี้")):
        return Command(Plan("change_volume", {"step": 10}, "เพิ่มเสียงขึ้น 10%"), SURE, heard)
    return None


def parse(text: str) -> Command | None:
    """แปลงประโยคเป็นคำสั่ง · None = ไม่ใช่คำสั่งเครื่อง (ส่งต่อให้สกิลอื่น)."""
    heard = text.strip()
    t = normalize(text)
    if not t:
        return None

    vol = _volume(t, heard)
    if vol:
        return vol

    verb = next((v for v in OPEN_VERBS if t.startswith(v)), None)
    if verb is None:
        return None
    raw = t[len(verb) :]
    target = raw.removeprefix("หน้า").removeprefix("เว็บ").removeprefix("แอป").removeprefix("โปรแกรม")
    if not target:
        return None

    # ลองทั้งแบบมีคำนำ ("หน้าหลัก") และแบบตัดคำนำแล้ว ("ตั้งค่า")
    hit = _match(
        [raw, target], [("page", PAGE_ALIASES), ("site", SITE_ALIASES), ("app", APP_ALIASES)]
    )
    if not hit:
        return None
    group, key, conf = hit
    if group == "page":
        plan = Plan("open_page", {"page": key}, f"เปิดหน้า{PAGES[key]}")
    elif group == "site":
        plan = Plan("open_url", {"site": key}, f"เปิด {SITES[key][0]}")
    else:
        plan = Plan("open_app", {"app": key}, f"เปิด{APPS[key][0]}")
    return Command(plan, conf, heard)
