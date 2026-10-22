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

from aipc.skills import when
from aipc.skills.actions import PAGES, SITES, Plan, app_table
from aipc.skills.thainum import find_number

# คำสุภาพ ตัดเฉพาะหัว/ท้ายประโยค (ตัดซ้ำจนไม่เหลือ เช่น "หน่อย" + "ครับ")
# "อยาก": สำรวจบน Pi 5 2026-10-12 "อยากดูไฟล์ของฉัน" ไม่เข้ากฎ → AI ตอบว่าเปิดให้ไม่ได้
POLITE_START = ("ช่วย", "กรุณา", "ขอ", "อยาก")
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
    # การ์ด 0031 · "ปฏิทิน" เฉย ๆ = หน้าปฏิทินของเครื่อง (การ์ด 0038) · ต้องมีคำว่ากูเกิลถึงเป็นเว็บ
    "docs": (
        "googledocs",
        "googledoc",
        "กูเกิลด็อก",
        "กูเกิลด็อกส์",
        "กูเกิ้ลด็อก",
        "กูเกิลด็อค",
        "กูเกิลเอกสาร",
        "เอกสารกูเกิล",
        "เอกสารกูเกิ้ล",
    ),
    "news": ("ข่าว", "เว็บข่าว", "ไทยพีบีเอส", "thaipbs", "ข่าวไทยพีบีเอส"),
    # การ์ด 0031 รอบ 2 (Pakon เลือก 2026-10-19)
    "netflix": ("netflix", "เน็ตฟลิกซ์", "เน็ตฟลิก", "เน็ตฟิก", "เน็ตฟลิกส์", "เนตฟลิกซ์", "เน็ตฟลิค"),
    "viu": ("viu", "วิว", "วีไอยู"),
    "iqiyi": ("iqiyi", "ไอฉีอี้", "อ้ายฉีอี้", "ไอคิวยี่", "ไอคิวอี้", "ไอฉีอี่"),
    "wetv": ("wetv", "วีทีวี"),
    "disney": (
        "disneyplus",
        "disney+",
        "disney",
        "disneyhotstar",
        "ดิสนีย์พลัส",
        "ดิสนีย์",
        "ดิสนีย์พลัสฮอตสตาร์",
        "hotstar",
        "ฮอตสตาร์",
    ),
    "spotify": ("spotify", "สปอติฟาย", "สปอตติฟาย", "สปอทิฟาย", "สปอติฟาย์"),
    "calendar": ("googlecalendar", "ปฏิทินกูเกิล", "กูเกิลปฏิทิน", "ปฏิทินกูเกิ้ล", "ปฏิทินgoogle"),
    "drive": ("googledrive", "กูเกิลไดรฟ์", "กูเกิ้ลไดรฟ์", "กูเกิลไดร์ฟ", "กูเกิ้ลไดร์ฟ", "ไดรฟ์", "ไดร์ฟ"),
}
# ตั้งใจไม่มีในระบบ (Pakon ตัดสิน 2026-10-19: เอา Facebook/Instagram ออก · LINE ไม่มีบน Linux) ·
# ตรงคำเรียก = บอกตรง ๆ ว่าไม่มี ไม่เดาเป็นเป้าหมายอื่น (เดิม "เปิดไลน์" ใกล้ "ไฟล์" → ถามว่าเปิดหน้าไฟล์ไหม)
UNSUPPORTED = {
    "Facebook": ("facebook", "เฟซบุ๊ก", "เฟสบุ๊ก", "เฟสบุ๊ค", "เฟซบุ๊ค", "เฟซบุค", "เฟสบุค", "เฟซ", "เฟส"),
    "Instagram": ("instagram", "อินสตาแกรม", "อินสตา", "ไอจี", "ig"),
    "LINE": ("line", "ไลน์"),
}
# คำเรียกสั้น/เป็นคำทั่วไป ต้องตรงทั้งคำ: "ดูข่าวน้ำท่วม" (หัวข้อหาย) · "เปิดรีวิวหนัง" มีคำว่า "วิว" ไม่ใช่ Viu
EXACT_ONLY = ("news", "viu", "iqiyi", "wetv")
# "ไดรฟ์" ในเครื่องนี้ยังหมายถึงไดรฟ์ USB (หน้าสำรองข้อมูล) · มีคำพวกนี้ = ไม่ใช่ Google Drive (การ์ด 0031)
LOCAL_DRIVE_WORDS = ("usb", "ยูเอสบี", "แฟลช", "ฮาร์ด", "สำรอง")
APP_ALIASES = {
    # "เบาเซอร์" = ที่ Pakon พิมพ์จริงบน Pi 5 (2026-10-14 · เดิมต้องกด "ใช่" ก่อนเปิด)
    # "เบราเซอร์" = สะกดที่พบบ่อย
    "browser": (
        "เบราว์เซอร์",
        "บราวเซอร์",
        "เบาเซอร์",
        "เบราเซอร์",
        "เว็บเบราว์เซอร์",
        "chromium",
        "โครเมียม",
        "อินเทอร์เน็ต",
    ),
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
    # การ์ด 0038 · "เปิดปฏิทินกูเกิล" (เว็บ · การ์ด 0031) ยาวกว่า จึงชนะตามกฎคำเรียกที่ยาวที่สุด
    "calendar": ("ปฏิทิน", "หน้าปฏิทิน", "calendar"),
}

# ประโยคที่มีคำเหล่านี้คือ "ให้ทำทีหลัง" ไม่ใช่คำสั่งตอนนี้ → ส่งต่อให้สกิลนัดหมาย/โน้ต
# (ชุดสำรองการ์ด 0008: "เตือนปิดเสียงตอนประชุมบ่ายสาม" เคยปิดเสียงทันที)
# ตรวจทั้งประโยค ไม่ใช่แค่คำขึ้นต้น: "อีก 10 นาทีเตือนให้ลดเสียง" เคยลดเสียงทันที (พบ 2026-09-28)
LATER_WORDS = ("เตือน", "นัด", "จด", "บันทึก", "อย่าลืม")
# ตั้งงานประจำ/สร้างสกิล = ไม่ใช่คำสั่งตอนนี้ → ส่งต่อให้ AI (สกิลอัตโนมัติ การ์ด 0017)
# ชุดประเมินรอบ 1: "ช่วยทำคำสั่งประจำ ... เปิดยูทูบกับปรับเสียง 80" เคยเปิดยูทูบทันทีแทนการสร้างสกิล (4/16 ข้อ)
# คำที่ใช้มาจากชุดพัฒนา tests/data/create_skill_dev.json · "สกิล" เดี่ยว ๆ ไม่นับ ("เปิดหน้าสกิล" เป็นคำสั่ง)
DEFINE_WORDS = ("สร้างสกิล", "อยากได้สกิล", "ขอสกิล", "ทำสกิล", "สกิลใหม่", "โหมด", "คำสั่งประจำ",
                "ทุกครั้ง", "ต่อไปถ้า", "จากนี้", "พอพูดว่า", "ถ้าพูดว่า", "ถ้าพิมพ์ว่า", "ถ้าบอกว่า",
                "ทางลัด")  # fmt: skip
# ปฏิเสธ: "อย่าปิดเสียงนะ" เคยปิดเสียง (พบ 2026-09-28) · ไม่ใช้ "ไม่" เดี่ยว ๆ ("ไม่ได้ยิน เพิ่มเสียงหน่อย" เป็นคำสั่ง)
NEGATIONS = ("อย่า", "ไม่ต้อง", "ห้าม")
# มีคำว่า "เสียง" แต่ไม่ใช่เสียงลำโพง · ตัวเลขที่ตามด้วยหน่วยเวลาไม่ใช่ระดับเสียง ("อัดเสียง 10 นาที" เคยได้ 10%)
NOT_VOLUME = ("อัดเสียง", "ข้อความเสียง", "ไฟล์เสียง", "ส่งเสียง")
DURATION = re.compile(r"นาที|ชั่วโมง|ชม\.|วินาที")
# ล็อกหน้าจอทันที (การ์ด 0051) · ต้องเป็นคำสั่งทั้งประโยค (หลังตัดคำสุภาพ) ไม่ใช่แค่มีคำว่าล็อก
# ("ทำไมหน้าจอล็อกเอง" = คำถาม ไม่ใช่คำสั่ง) · สะกด ล็อก/ล็อค ทั้งสองแบบเพราะตัวถอดเสียงให้ได้ทั้งคู่
LOCK_PHRASES = tuple(
    f"{v}{w}{o}"
    for v in ("ล็อก", "ล็อค")
    for w in ("หน้าจอ", "จอ", "เครื่อง", "คอม")
    for o in ("", "ที", "เลย", "ไว้")
) + ("lockscreen", "lockthescreen")
# ปิด/รีสตาร์ตเครื่อง (การ์ด 0052) · ทั้งประโยคเท่านั้น และถามยืนยันเสมอ (ความเสี่ยงสูง)
# "ปิดเครื่องดูดฝุ่น" "ปิดเครื่องปรับอากาศ" = ไม่ใช่คำสั่ง
_ENDS = ("", "เลย", "ที", "ได้เลย")
_OFF = ("ปิดเครื่อง", "ปิดคอม", "ปิดคอมพิวเตอร์", "ชัตดาวน์", "ชัทดาวน์", "shutdown",
        "shutdownthecomputer", "poweroff", "turnoffthecomputer")  # fmt: skip
_REBOOT = ("รีสตาร์ต", "รีสตาร์ท", "รีสตาร์ทเครื่อง", "รีสตาร์ตเครื่อง", "รีบูต", "รีบูท", "รีบูตเครื่อง",
           "เริ่มเครื่องใหม่", "restart", "reboot", "restartthecomputer")  # fmt: skip
POWER_PHRASES = {
    "power_off": tuple(v + o for v in _OFF for o in _ENDS),
    "reboot": tuple(v + o for v in _REBOOT for o in _ENDS),
}
# ดูอุปกรณ์ที่ต่ออยู่ (การ์ด 0051) · ต้องมีคำว่าต่อ/เสียบ ("อุปกรณ์อะไรดี" = ถามความเห็น ไม่ใช่คำสั่ง)
DEVICES = re.compile(
    r"^(มี|ดู|เช็[คก]|ตรวจ|เปิด(หน้า)?|แสดง)?อุปกรณ์(อะไร)?(ที่)?(ต่อ|เสียบ)(อยู่)?(บ้าง)?(อะไรบ้าง)?(ไหม|มั้ย)?$"
    r"|^(list|show)(the)?devices$|^whatdevicesare(connected|pluggedin)$"
)
# ดึงปฏิทิน Google ใหม่ทันที (การ์ด 0051) · ทั้งประโยคเหมือนคำสั่งล็อก
GCAL_SYNC_PHRASES = tuple(
    f"{v}{c}{o}"
    for v in ("อัปเดต", "อัพเดต", "อัพเดท", "อัปเดท", "ซิงค์", "ซิงก์", "รีเฟรช", "ดึง")
    for c in ("ปฏิทิน", "ปฎิทิน", "ปฏิทินกูเกิล", "ปฏิทินgoogle")
    for o in ("", "ใหม่", "ที")
) + ("updatecalendar", "updatethecalendar", "synccalendar", "syncthecalendar", "refreshcalendar")
# แชท 2 แบบ (การ์ด 0053) · ทั้งประโยค ("แชทงานคืออะไร" = คำถาม ไม่ใช่คำสั่ง)
CHAT_MODE = re.compile(r"^(สลับ|เปลี่ยน|กลับ|เปิด|ใช้|ไป)(ไป|เป็น|มา)?(ที่)?(หน้า)?แชท(งาน|ทั่วไป)$")
CHAT_MODE_EN = re.compile(r"^(switch|go|change)(back)?to(the)?(work|general)chat$")
# เลือกโมเดลของแชทงาน · ต้องมีคำกริยา ใช้/เปลี่ยน ("ช่วยเขียนกลอนไฮกุ" ≠ เลือกโมเดล)
MODEL_NAMES = {
    "haiku": ("haiku", "ไฮกุ", "ไฮคุ"),
    "sonnet": ("sonnet", "ซอนเน็ต", "ซอนเนต", "ซอนเน็ท"),
    "opus": ("opus", "โอปัส", "โอปุส"),
}
MODEL_CMD = re.compile(
    r"^(ใช้|เปลี่ยน|สลับ|use|switchto)(โมเดล|model)?(เป็น|ไป)?(โมเดล|model)?(?P<name>[a-zก-๙]+)$"
)

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


def _two_targets(t: str, tables: list[dict]) -> bool:
    """มีเว็บ/แอปมากกว่าหนึ่งอย่างคั่นด้วยคำเชื่อม ("เปิดวิกิกับกูเกิล") · คำเรียกที่ซ้อนในคำที่ยาวกว่าไม่นับ.

    ต้องมีคำเชื่อม: "เปิดแผนที่กูเกิล" (ไม่มีคำเชื่อม) ยังเป็นคำสั่งเดี่ยวที่ถามยืนยันก่อนตามเดิม (การ์ด 0008)
    """
    if not any(c in t for c in ("กับ", "และ", "แล้ว", ",", "+", "&")):
        return False
    names = {(key, n) for table in tables for key, ns in table.items() for n in ns if n in t}
    keys = {k for k, n in names if not any(n != m and n in m for _, m in names)}
    return len(keys) > 1


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
    if any(w in t for w in NOT_VOLUME) or DURATION.search(t):
        return None
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


VOLUME_CUES = (
    "ปิดเสียง",
    "เปิดเสียง",
    "เพิ่มเสียง",
    "ลดเสียง",
    "เร่งเสียง",
    "เบาเสียง",
    "ปรับเสียง",
    "ดังขึ้น",
    "เบาลง",
)


def _several_actions(t: str) -> bool:
    """มีทั้งคำสั่งเสียงและ "เปิด…" อย่างอื่นในประโยคเดียว (เช่น "เปิดยูทูบแล้วเพิ่มเสียง").

    ชุดอิสระชุดที่ 2 (การ์ด 0017): "…เปิด YouTube แล้วเพิ่มเสียง" เคยเพิ่มเสียงอย่างเดียว ทิ้งส่วนที่เหลือเงียบ ๆ
    """
    if not any(c in t for c in VOLUME_CUES):
        return False
    rest = t.replace("เปิดเสียง", "")
    return "เปิด" in rest or "open" in rest


def _discovered_aliases() -> dict[str, tuple[str, ...]]:
    from aipc.skills import apps

    return {f"desk:{a.desktop}": a.aliases for a in apps.REGISTRY.apps().values()}


def _known_app(target: str, heard: str):
    """คำเรียกตรงรายการแอปที่รู้จัก → Command เปิดตัวที่ติดตั้งแล้ว หรือ Entry ที่ยังไม่มี · ไม่ตรง = None."""
    from aipc.skills import app_catalog

    entry = app_catalog.find(target, app_catalog.load())
    if entry is None:
        return None
    table = app_table()
    for key, aliases in _discovered_aliases().items():
        if key in table and set(aliases) & set(entry.aliases):
            return Command(Plan("open_app", {"app": key}, f"เปิด{table[key][0]}"), SURE, heard)
    return entry


def unsupported(text: str) -> str | None:
    """ "เปิดเฟซบุ๊ก" · "เปิดไลน์ให้หน่อย" → ชื่อบริการที่ระบบตั้งใจไม่มี · อื่น ๆ = None."""
    t = normalize(text)
    verb = next((v for v in OPEN_VERBS if t.startswith(v)), None)
    if verb is None:
        return None
    target = t[len(verb) :].removeprefix("แอป").removeprefix("เว็บ").removeprefix("โปรแกรม")
    return next((name for name, words in UNSUPPORTED.items() if target in words), None)


def parse(text: str) -> Command | None:
    """แปลงประโยคเป็นคำสั่ง · None = ไม่ใช่คำสั่งเครื่อง (ส่งต่อให้สกิลอื่น)."""
    heard = text.strip()
    t = normalize(text)
    if (
        not t
        or any(w in t for w in LATER_WORDS + NEGATIONS + DEFINE_WORDS)
        or when.mentions_time(heard)
    ):
        return None  # ให้ทำทีหลัง / สั่งไม่ให้ทำ → ไม่ใช่คำสั่งตอนนี้ (ส่งต่อให้สกิลนัดหมายหรือแชท)

    if unsupported(heard):
        return None  # ไม่ให้คำเรียกที่ใกล้เคียงชนะ ("ไลน์" ≈ "ไฟล์") · หน้าจอบอกว่าไม่มี

    if _several_actions(t):
        return None  # สั่งหลายอย่างในประโยคเดียว = ไม่ใช่คำสั่งเดี่ยว → AI (สร้างสกิล/ตอบ) · เดิมทำแค่บางส่วน

    vol = _volume(t, heard)
    if vol:
        return vol

    for action, phrases in POWER_PHRASES.items():
        if t in phrases:
            say = "ปิดเครื่อง" if action == "power_off" else "รีสตาร์ตเครื่อง"
            return Command(Plan(action, {}, say), SURE, heard)
    if t in LOCK_PHRASES:
        return Command(Plan("lock_screen", {}, "ล็อกหน้าจอแล้ว · ปลดด้วยรหัสผ่าน"), SURE, heard)
    if t in GCAL_SYNC_PHRASES:
        return Command(Plan("gcal_sync", {}, "ดึงปฏิทิน Google ใหม่"), SURE, heard)
    if DEVICES.match(t):
        return Command(Plan("show_devices", {}, "อุปกรณ์ที่ต่ออยู่"), SURE, heard)
    if (m := CHAT_MODE.match(t)) or (m := CHAT_MODE_EN.match(t)):
        mode = "work" if m.group(m.lastindex) in ("งาน", "work") else "general"
        say = "สลับไปแชทงาน" if mode == "work" else "กลับแชททั่วไป"
        return Command(Plan("chat_mode", {"mode": mode}, say), SURE, heard)
    if m := MODEL_CMD.match(t):
        model = next((k for k, names in MODEL_NAMES.items() if m["name"] in names), None)
        if model:
            plan = Plan("cloud_model", {"model": model}, f"แชทงานใช้โมเดล {model}")
            return Command(plan, SURE, heard)

    verb = next((v for v in OPEN_VERBS if t.startswith(v)), None)
    if verb is None:
        return None
    raw = t[len(verb) :]
    target = raw.removeprefix("หน้า").removeprefix("เว็บ").removeprefix("แอป").removeprefix("โปรแกรม")
    if not target:
        return None

    # การ์ด 0054: แอปที่รู้จัก (app_catalog) · ตรงทั้งคำเท่านั้น และตรวจก่อนตัวเดาคำใกล้เคียง
    # ติดตั้งแล้ว = เปิดตัวที่ติดตั้ง (ได้คำเรียกไทยของรายการด้วย) · ยังไม่มี = ให้หน้าจอถามติดตั้ง/เปิดเว็บ
    known = _known_app(raw, heard) or _known_app(target, heard)
    if known is not None:
        if isinstance(known, Command):
            return known
        plan = Plan("missing_app", {"app": known.key}, f"ไม่มี {known.name} ในเครื่อง")
        return Command(plan, SURE, heard)

    # ลองทั้งแบบมีคำนำ ("หน้าหลัก") และแบบตัดคำนำแล้ว ("ตั้งค่า")
    # แอปที่ติดตั้งจริง (ไฟล์ .desktop) เป็นกลุ่มสุดท้าย · คำเรียกไทยของตารางคงที่มาก่อนเสมอ
    table = app_table()
    found = {k: a for k, a in _discovered_aliases().items() if k in table}
    if _two_targets(raw, [SITE_ALIASES, {**found, **APP_ALIASES}]):
        return None  # "เปิดวิกิกับกูเกิล" = สองอย่าง ไม่ใช่คำสั่งเดี่ยว → AI (เดิมเปิดแค่อย่างเดียว · การ์ด 0017)
    hit = _match(
        [raw, target],
        [("page", PAGE_ALIASES), ("site", SITE_ALIASES), ("app", {**found, **APP_ALIASES})],
    )
    if not hit:
        return None
    group, key, conf = hit
    if key == "drive" and any(w in raw for w in LOCAL_DRIVE_WORDS):
        return None  # "เปิดแฟลชไดรฟ์" · "เปิดไดรฟ์ USB" = ไดรฟ์ในเครื่อง ไม่ใช่เว็บ
    if key in EXACT_ONLY and target not in SITE_ALIASES[key]:
        return None  # "ดูข่าวน้ำท่วม" = อยากรู้เรื่องนั้น ไม่ใช่เปิดหน้าแรกเว็บข่าว (หัวข้อหาย) → ทางเดิม
    if group == "page":
        plan = Plan("open_page", {"page": key}, f"เปิดหน้า{PAGES[key]}")
    elif group == "site":
        plan = Plan("open_url", {"site": key}, f"เปิด {SITES[key][0]}")
    else:
        plan = Plan("open_app", {"app": key}, f"เปิด{table[key][0]}")
    return Command(plan, conf, heard)
