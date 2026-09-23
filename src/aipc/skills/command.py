"""สกิล 4: แปลคำสั่งเครื่องภาษาไทยแบบกำหนดแน่นอน (BRIEF 5.6 ข้อ 2) — ไม่ผ่าน LLM.

ทำไมไม่ใช้ LLM: คำสั่งเครื่องต้องตอบเร็วและต้องไม่เดา · LLM บน Pi ใช้เวลาหลายวินาทีกว่าจะตอบ
และอาจตีความผิด ตัวแปลแบบกฎจึงเร็วกว่า ทดสอบได้ครบทุกกรณี และอธิบายกรรมการได้บรรทัดต่อบรรทัด

ขั้นตอน:
1. ทำความสะอาดข้อความ: ตัดคำลงท้ายสุภาพ ("ครับ" "หน่อย") และช่องว่าง
2. หาชนิดคำสั่งจากคำกริยา/คำสำคัญ: เสียง → หน้าในระบบ → เว็บ/แอป
3. หาเป้าหมายจากรายชื่อที่รู้จัก (รวมคำเรียกแบบไทย เช่น "ยูทูบ")
   ตรงเป๊ะ = มั่นใจ · ใกล้เคียง (สะกดผิด/ถอดเสียงเพี้ยน) = ถามก่อนว่า "หมายถึง … ใช่ไหม"
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from aipc.skills.actions import APPS, PAGES, SITES, Plan
from aipc.skills.thainum import find_number

POLITE = ("ให้หน่อย", "หน่อยนะ", "หน่อย", "ครับ", "ค่ะ", "คะ", "นะ", "จ้า", "ด้วย", "กรุณา", "ช่วย", "ขอ")
OPEN_VERBS = ("เปิด", "เข้า", "ไปที่", "ไป", "open")

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
    "filemanager": ("ตัวจัดการไฟล์", "โฟลเดอร์", "filemanager"),
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
    t = text.strip().lower()
    for word in POLITE:
        t = t.replace(word, "")
    return re.sub(r"\s+", "", t)


def _match(target: str, aliases: dict[str, tuple[str, ...]]) -> tuple[str, float] | None:
    """หาเป้าหมายที่ตรงที่สุด · คืน (id, ความมั่นใจ) หรือ None."""
    for key, names in aliases.items():
        if any(n in target for n in names):
            return key, SURE
    flat = {n: key for key, names in aliases.items() for n in names}
    close = difflib.get_close_matches(target, flat, n=1, cutoff=FUZZY_CUTOFF)
    if close:
        return flat[close[0]], difflib.SequenceMatcher(None, target, close[0]).ratio()
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
    if any(w in t for w in ("เบาลง", "ลดเสียง", "เบา")):
        return Command(Plan("change_volume", {"step": -10}, "ลดเสียงลง 10%"), SURE, heard)
    if any(w in t for w in ("ดังขึ้น", "เพิ่มเสียง", "เร่งเสียง", "ดัง")):
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
    target = t[len(verb) :]
    target = (
        target.removeprefix("หน้า").removeprefix("เว็บ").removeprefix("แอป").removeprefix("โปรแกรม")
    )
    if not target:
        return None

    for aliases, make in (
        (PAGE_ALIASES, lambda k: Plan("open_page", {"page": k}, f"เปิดหน้า{PAGES[k]}")),
        (SITE_ALIASES, lambda k: Plan("open_url", {"site": k}, f"เปิด {SITES[k][0]}")),
        (APP_ALIASES, lambda k: Plan("open_app", {"app": k}, f"เปิด{APPS[k][0]}")),
    ):
        hit = _match(target, aliases)
        if hit:
            key, conf = hit
            return Command(make(key), conf, heard)
    return None
