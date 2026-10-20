"""สกิลประจำเว็บ (การ์ด 0046): หัวข้อ "## คำสั่ง" ในไฟล์สกิล .md · คำพูด → กดคีย์ลัด / คลิกปุ่ม ในหน้าเว็บนั้น.

    ---
    id: youtube-voice
    name: สั่ง YouTube ด้วยเสียง
    description: …
    site: youtube                 ← ชื่อในรายการ SITES (ที่เปิดในเบราว์เซอร์ของผู้ช่วย) หรือ https://…
    permissions: page_actions
    ---
    ## คำสั่ง
    - ถอยหลังสิบวิ | ย้อนสิบวิ → กดคีย์ j
    - กดไลก์ → คลิก like-button-view-model button
    - ยกเลิกสมัครสมาชิก → คลิก … · ยืนยันก่อน

กติกา (โค้ดตรวจ · ไฟล์เป็นข้อมูลจาก Claude ไม่ใช่คำสั่ง · H8 · ADR-011):
- ทำได้แค่ "กดคีย์" (คีย์ลัดในรายการ ไม่พิมพ์ข้อความ) กับ "คลิก" (ตัวเลือก CSS เขียนตายตัว) ·
  ทำงานเฉพาะเมื่อหน้าที่เปิดอยู่เป็นเว็บของสกิล
- คำสั่งที่มีคำเสี่ยง (ลบ ซื้อ จ่าย ส่ง โพสต์ สมัคร ยกเลิก ออกจากระบบ …) ต้องมี "ยืนยันก่อน" ·
  ตัวเลือกห้ามแตะช่องรหัสผ่าน/ชำระเงิน
- เว็บที่เปิดในหน้าต่างบัญชีแยก (Gmail Drive Docs ปฏิทิน Google · การ์ด 0031) ใช้ไม่ได้ เพราะระบบไม่ได้คุมหน้าต่างนั้น
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import urlsplit

SECTION = "คำสั่ง"
PERMISSION = "page_actions"
MAX_COMMANDS = 40
MAX_PHRASE = 40
MAX_SELECTOR = 200
# คำสั่งที่ย้อนไม่ได้ / แตะบัญชีหรือเงิน → ต้องยืนยันก่อนเสมอ (ตัวตรวจบังคับ)
RISKY = ("ลบ", "ยกเลิก", "ซื้อ", "จ่าย", "ชำระ", "ส่ง", "โพสต์", "สมัคร", "ออกจากระบบ", "บล็อก",
         "รายงาน", "แชร์", "ล็อกเอาต์", "delete", "remove", "unsubscribe", "subscribe", "buy", "pay",
         "send", "post", "log out", "sign out", "report", "block", "share")  # fmt: skip
_SPECIAL = ("ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space", "Enter", "Escape", "Tab",
            "PageUp", "PageDown", "Home", "End")  # fmt: skip
KEY_RE = re.compile(
    r"(?:(?:Shift|Ctrl|Alt)\+)*(?:[A-Za-z0-9]|" + "|".join(_SPECIAL) + r"|[,./;'\[\]=<>?-])"
)
# คีย์ของตัวเบราว์เซอร์ (ปิดแท็บ/หน้าต่าง เปิดหน้าต่างใหม่ พิมพ์ ที่อยู่) ไม่ใช่คีย์ลัดของเว็บ → ห้าม
BROWSER_KEYS = set(
    "ctrl+w ctrl+shift+w ctrl+q ctrl+shift+q ctrl+t ctrl+shift+t ctrl+n ctrl+shift+n ctrl+l ctrl+p "
    "ctrl+s ctrl+o ctrl+h ctrl+j ctrl+u ctrl+shift+i ctrl+shift+j ctrl+shift+delete alt+f4".split()
)
_BAD_SELECTOR = re.compile(r"javascript:|[{};`]|passw|checkout|payment|credit|cvv|billing", re.I)
_LINE = re.compile(r"\s*-\s+(.+?)\s*(?:→|->)\s*(กดคีย์|คลิก)\s+(.+?)\s*")
_CONFIRM = re.compile(r"(.*?)\s*·\s*ยืนยันก่อน")


@dataclass(frozen=True)
class SiteCommand:
    phrases: tuple[str, ...]
    kind: str  # key | click
    arg: str  # คีย์ เช่น "Shift+N" หรือตัวเลือก CSS
    confirm: bool = False


def parse_section(rows: list[tuple[int, str]]) -> tuple[list[SiteCommand], list[str]]:
    """บรรทัดในหัวข้อ "## คำสั่ง" → (คำสั่ง, ปัญหา)."""
    out: list[SiteCommand] = []
    errors: list[str] = []
    for n, line in rows:
        if not line.strip():
            continue
        m = _LINE.fullmatch(line)
        if not m:
            errors.append(
                f"บรรทัด {n}: คำสั่งต้องเป็นรูป “- คำพูด | คำพูด → กดคีย์ <คีย์>” หรือ “→ คลิก <ตัวเลือก>”"
            )
            continue
        phrases = tuple(p.strip() for p in m.group(1).split("|") if p.strip())
        arg, confirm = m.group(3), False
        if c := _CONFIRM.fullmatch(arg):
            arg, confirm = c.group(1).strip(), True
        kind = "key" if m.group(2) == "กดคีย์" else "click"
        if not phrases or any(len(p) > MAX_PHRASE for p in phrases):
            errors.append(f"บรรทัด {n}: คำพูดต้องมีและยาวไม่เกิน {MAX_PHRASE} ตัวอักษร")
        if kind == "key" and arg.lower() in BROWSER_KEYS:
            errors.append(f"บรรทัด {n}: คีย์ “{arg}” เป็นคีย์ของตัวเบราว์เซอร์ ไม่ใช่คีย์ลัดของเว็บ")
        elif kind == "key" and not KEY_RE.fullmatch(arg):
            errors.append(
                f"บรรทัด {n}: คีย์ “{arg}” ไม่อยู่ในรายการ "
                "(ตัวอักษร ตัวเลข ลูกศร Space Enter Escape Tab + Shift/Ctrl/Alt)"
            )
        if kind == "click" and (len(arg) > MAX_SELECTOR or _BAD_SELECTOR.search(arg) or not arg):
            errors.append(
                f"บรรทัด {n}: ตัวเลือก “{arg[:60]}” ใช้ไม่ได้ (ยาวเกิน/มีอักขระต้องห้าม/แตะรหัสผ่านหรือชำระเงิน)"
            )
        if not confirm and any(w in p.lower() for p in phrases for w in RISKY):
            errors.append(
                f"บรรทัด {n}: คำสั่ง “{phrases[0]}” ย้อนไม่ได้หรือแตะบัญชี ต้องลงท้ายด้วย “· ยืนยันก่อน”"
            )
        out.append(SiteCommand(phrases, kind, arg, confirm))
    if not out and not errors:
        errors.append("หัวข้อ “## คำสั่ง” ว่าง")
    if len(out) > MAX_COMMANDS:
        errors.append(f"คำสั่งมากเกิน {MAX_COMMANDS} ข้อ")
    return out, errors


def site_host(site: str) -> str:
    """โดเมนของเว็บในสกิล · "" = ใช้ไม่ได้."""
    from aipc.skills.actions import SITES

    if site.startswith("https://"):
        return (urlsplit(site).hostname or "").removeprefix("www.")
    return (urlsplit(SITES[site][1]).hostname or "").removeprefix("www.") if site in SITES else ""


def check_site(site: str) -> list[str]:
    from aipc.skills.actions import SITES, SYSTEM_BROWSER_SITES

    if site in SYSTEM_BROWSER_SITES:
        return [f"เว็บ {site} เปิดในหน้าต่างบัญชีแยกที่ระบบไม่ได้คุม (การ์ด 0031) · สั่งในหน้าเว็บนี้ไม่ได้"]
    if site not in SITES and not (site.startswith("https://") and site_host(site)):
        return [
            f"site ต้องเป็นชื่อในรายการเว็บ ({', '.join(sorted(set(SITES) - SYSTEM_BROWSER_SITES))}) หรือ https://…"
        ]
    return []


def on_site(site: str, url: str) -> bool:
    """หน้าที่เปิดอยู่เป็นเว็บของสกิลไหม (โดเมนเดียวกันหรือโดเมนย่อย เช่น m.youtube.com)."""
    want = site_host(site)
    host = (urlsplit(url).hostname or "").removeprefix("www.")
    return bool(want) and (host == want or host.endswith("." + want))


def _norm(text: str) -> str:
    from aipc.skills import command

    return command.normalize(text)


def match(text: str, skills: list, url: str) -> tuple[object | None, SiteCommand | None, bool]:
    """(สกิล, คำสั่ง, ตรงเป๊ะไหม) ของหน้าที่เปิดอยู่ · ไม่ตรงและไม่ใกล้ = (None, None, False).

    ตรง = ข้อความเท่ากับคำพูดในสกิลหลังตัดช่องว่าง/คำสุภาพ ·
    ใกล้ = ความคล้ายเสียง ≥ NEAR_MIN (ต้องยืนยันก่อน · การ์ด 0045)
    """
    from aipc.skills.voice_phrases import NEAR_MIN, _sound

    here = [s for s in skills if getattr(s, "site", "") and on_site(s.site, url)]
    key = _norm(text)
    if not key:
        return None, None, False
    for s in here:
        for c in s.commands:
            if any(_norm(p) == key for p in c.phrases):
                return s, c, True
    sound, best, score = _sound(text), (None, None), 0.0
    for s in here:
        for c in s.commands:
            for p in c.phrases:
                r = SequenceMatcher(None, sound, _sound(p)).ratio()
                if r > score:
                    best, score = (s, c), r
    return (*best, False) if score >= NEAR_MIN else (None, None, False)
