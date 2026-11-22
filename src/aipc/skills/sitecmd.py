"""สกิลประจำเว็บ (การ์ด 0046): หัวข้อ "## คำสั่ง" ในไฟล์สกิล .md · คำพูด → กดคีย์ลัด / คลิกปุ่ม ในหน้าเว็บนั้น
· หรือ → ทำคำสั่งของระบบ (คำพ้อง · การ์ด 0066).

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
    - เข้าสู่ระบบ | ล็อกอิน → กดปุ่มที่เขียนว่า เข้าสู่ระบบ|Log in|Sign in   ← การ์ด 0069
    - ยกเลิกสมัครสมาชิก → คลิก … · ยืนยันก่อน
    - เพิ่มอีกหนึ่งแถบ | ขออีกแท็บ → ทำคำสั่ง เปิดยูทูบอีกแท็บ

กติกา (โค้ดตรวจ · ไฟล์เป็นข้อมูลจาก Claude ไม่ใช่คำสั่ง · H8 · ADR-011):
- ทำได้แค่ "กดคีย์" (คีย์ลัดในรายการ ไม่พิมพ์ข้อความ) กับ "คลิก" (ตัวเลือก CSS เขียนตายตัว) ·
  "กดปุ่มที่เขียนว่า" (การ์ด 0069: ป้ายบนปุ่ม คั่น | · โค้ดหาปุ่มที่มองเห็นบนหน้าจริง · ไม่ต้องเดา CSS) ·
  ทำงานเฉพาะเมื่อหน้าที่เปิดอยู่เป็นเว็บของสกิล
- "ทำคำสั่ง" (การ์ด 0066): ประโยคคำสั่งเว็บของระบบ แปลด้วยตัวแปลเดียวกับเสียง (browse.parse) ได้ 1–3 คำสั่ง ·
  ทุกคำสั่งต้องอยู่ใน ALIAS_KINDS (ไม่ส่งข้อความออก ไม่ปิดทุกแท็บ) · ตรวจซ้ำตอนทำ (handsfree.runSite · H7)
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
    # "+" = ซูมแผนที่/ขยาย (การ์ด 0074 รอบ 2: ผู้เขียนอิสระ 2 คนใช้คีย์นี้ในสกิลดี · Google Maps)
    r"(?:(?:Shift|Ctrl|Alt)\+)*(?:[A-Za-z0-9]|" + "|".join(_SPECIAL) + r"|[,./;'\[\]=<>?+-])"
)
# คีย์ของตัวเบราว์เซอร์ (ปิดแท็บ/หน้าต่าง เปิดหน้าต่างใหม่ พิมพ์ ที่อยู่) ไม่ใช่คีย์ลัดของเว็บ → ห้าม
BROWSER_KEYS = set(
    "ctrl+w ctrl+shift+w ctrl+q ctrl+shift+q ctrl+t ctrl+shift+t ctrl+n ctrl+shift+n ctrl+l ctrl+p "
    "ctrl+s ctrl+o ctrl+h ctrl+j ctrl+u ctrl+shift+i ctrl+shift+j ctrl+shift+delete alt+f4".split()
)
# ช่องบัตร (การ์ด 0074 · S1 b10 หลุด: cardNumber · cc-exp · cc-csc ไม่มีคำที่ห้ามเดิม)
# = ชื่อมาตรฐาน autocomplete ของ HTML
_BAD_SELECTOR = re.compile(
    r"javascript:|[{};`]|passw|checkout|payment|credit|cvv|cvc|billing"
    r"|card[-_]?(number|num|holder)|cc-(number|name|exp|csc|type)|csc|security[-_]?code|(?<![a-z])otp",
    re.I,
)
_LINE = re.compile(r"\s*-\s+(.+?)\s*(?:→|->)\s*(กดคีย์|กดปุ่มที่เขียนว่า|คลิก|ทำคำสั่ง)\s+(.+?)\s*")
# คำพ้อง (การ์ด 0066): คำสั่งของระบบที่สกิลเรียกได้ · ค้นเว็บ/ค้นในเว็บ (ส่งข้อความออก · H3) · ปิดทุกแท็บ (H2) ·
# เข้าสู่ระบบ · ลิงก์ · กดคีย์/คลิก (ใช้บรรทัดของมันเอง) = ไม่ได้
ALIAS_KINDS = frozenset(
    {
        "site",
        "open",
        "back",
        "forward",
        "reload",
        "scroll",
        "media",
        "fullscreen",
        "skip_ad",
        "close",
        "app",
    }
)
MAX_ALIAS = 60
MAX_ALIAS_STEPS = 3
_CONFIRM = re.compile(r"(.*?)\s*·\s*ยืนยันก่อน")
# คำสั่งหลายขั้น (การ์ด 0048): "คลิก A แล้ว กดคีย์ k" · ทำทีละขั้น ขั้นไหนไม่สำเร็จ = หยุด
MAX_STEPS = 5
_VERBS = "กดคีย์|กดปุ่มที่เขียนว่า|คลิก"
_STEP = re.compile(rf"({_VERBS})\s+(.+)")
_THEN = re.compile(rf"\s+แล้ว\s+(?=(?:{_VERBS})\s)")
_KINDS = {"กดคีย์": "key", "คลิก": "click", "ทำคำสั่ง": "system", "กดปุ่มที่เขียนว่า": "click_text"}


@dataclass(frozen=True)
class SiteCommand:
    phrases: tuple[str, ...]
    kind: str  # key | click | system (การ์ด 0066) | click_text (การ์ด 0069) | steps (การ์ด 0048)
    arg: str  # คีย์ เช่น "Shift+N" · ตัวเลือก CSS · ประโยคคำสั่งของระบบ เช่น "เปิดยูทูบอีกแท็บ"
    confirm: bool = False


def alias_commands(arg: str) -> tuple[list, str]:
    """ประโยคคำสั่งของระบบ → (คำสั่งเว็บ, "") · ใช้ไม่ได้ → ([], เหตุผล) · ตัวตรวจและตอนทำใช้ตัวเดียวกัน (H7)."""
    from aipc.skills import browse

    if not arg or len(arg) > MAX_ALIAS:
        return [], f"คำสั่งปลายทางต้องมีและยาวไม่เกิน {MAX_ALIAS} ตัวอักษร"
    cmds = browse.parse(arg)
    if not cmds:
        return [], f"“{arg}” ไม่ใช่คำสั่งเว็บของระบบ (ใช้ประโยคที่ระบบรู้จัก เช่น เปิดยูทูบอีกแท็บ · หยุดคลิป)"
    if len(cmds) > MAX_ALIAS_STEPS:
        return [], f"“{arg}” มี {len(cmds)} คำสั่ง · ได้ไม่เกิน {MAX_ALIAS_STEPS}"
    bad = [
        c for c in cmds if c.kind not in ALIAS_KINDS or (c.kind == "close" and c.direction == "all")
    ]
    if bad:
        what = ", ".join("ปิดทุกแท็บ" if c.kind == "close" else c.kind for c in bad)
        return [], f"“{arg}” มีคำสั่งที่สกิลเรียกไม่ได้ ({what} · ค้นหา/ส่งข้อความออก/ปิดทุกแท็บ/เข้าสู่ระบบ)"
    return cmds, ""


def _check_action(kind: str, arg: str) -> list[str]:
    """ปัญหาของการกระทำ 1 อย่าง (กดคีย์ · คลิก · กดปุ่มที่เขียนว่า)."""
    errors = []
    if " แล้ว ทำคำสั่ง " in f" {arg} ":
        errors.append("คำสั่งหลายขั้นใช้ “ทำคำสั่ง” ไม่ได้")
    if kind == "key" and arg.lower() in BROWSER_KEYS:
        errors.append(f"คีย์ “{arg}” เป็นคีย์ของตัวเบราว์เซอร์ (ปิดแท็บ เปิดหน้าต่างใหม่ ฯลฯ) ใช้ไม่ได้")
    elif kind == "key" and not KEY_RE.fullmatch(arg):
        errors.append(
            f"คีย์ “{arg}” ไม่อยู่ในรายการ (ตัวอักษร ตัวเลข ลูกศร Space Enter Escape Tab + Shift/Ctrl/Alt)"
        )
    if kind == "click" and (len(arg) > MAX_SELECTOR or _BAD_SELECTOR.search(arg) or not arg):
        errors.append(f"ตัวเลือก “{arg[:60]}” ใช้ไม่ได้ (ยาวเกิน/มีอักขระต้องห้าม/แตะรหัสผ่านหรือชำระเงิน)")
    words = [w.strip() for w in arg.split("|")]
    if kind == "click_text" and (
        not all(words) or any(len(w) > MAX_PHRASE or _BAD_SELECTOR.search(w) for w in words)
    ):
        why = f"ว่าง/ยาวเกิน {MAX_PHRASE}/มีอักขระต้องห้าม"
        errors.append(f"ป้ายปุ่ม “{arg[:60]}” ใช้ไม่ได้ ({why})")
    return errors


def parse_steps(arg: str) -> tuple[list[tuple[str, str]], list[str]]:
    """ "คลิก A แล้ว กดคีย์ k" → ([("click", "A"), ("key", "k")], ปัญหา) · ตรวจทุกขั้นเหมือนคำสั่งขั้นเดียว."""
    parts = [p.strip() for p in _THEN.split(arg.strip())]
    steps: list[tuple[str, str]] = []
    errors: list[str] = []
    for part in parts:
        m = _STEP.fullmatch(part)
        if not m:
            errors.append(f"ขั้น “{part[:40]}” ไม่ถูกรูป (ใช้ได้: คลิก · กดคีย์ · กดปุ่มที่เขียนว่า)")
            continue
        kind, value = _KINDS[m.group(1)], m.group(2).strip()
        if kind == "key":
            value = re.sub(r"(?i)(^|\+)esc$", r"\1Escape", value)
        steps.append((kind, value))
        errors += _check_action(kind, value)
    if len(parts) > MAX_STEPS:
        errors.append(f"มี {len(parts)} ขั้น · ได้ไม่เกิน {MAX_STEPS} ขั้น")
    return steps, errors


def parse_section(rows: list[tuple[int, str]]) -> tuple[list[SiteCommand], list[str]]:
    """บรรทัดในหัวข้อ "## คำสั่ง" → (คำสั่ง, ปัญหา)."""
    out: list[SiteCommand] = []
    errors: list[str] = []
    known = []  # บรรทัดคำพ้องที่ระบบทำเองได้ทุกคำ (ตัดทิ้ง)
    for n, line in rows:
        if not line.strip():
            continue
        m = _LINE.fullmatch(line)
        if not m:
            errors.append(
                f"บรรทัด {n}: คำสั่งต้องเป็นรูป “- คำพูด | คำพูด → กดคีย์ <คีย์>” · “→ คลิก <ตัวเลือก>” "
                "หรือ “→ ทำคำสั่ง <ประโยคคำสั่งของระบบ>”"
            )
            continue
        phrases = tuple(p.strip() for p in m.group(1).split("|") if p.strip())
        arg, confirm = m.group(3), False
        if c := _CONFIRM.fullmatch(arg):
            arg, confirm = c.group(1).strip(), True
        # "Esc" = ชื่อที่คนเขียนบ่อย · เบราว์เซอร์รู้จักแค่ "Escape" (การ์ด 0074 รอบ 3 g21)
        if m.group(2) == "กดคีย์":
            arg = re.sub(r"(?i)(^|\+)esc$", r"\1Escape", arg)
        kind = _KINDS[m.group(2)]
        whole = f"{m.group(2)} {arg}"
        if kind != "system" and _THEN.search(whole):  # คำสั่งหลายขั้น (การ์ด 0048)
            kind, arg = "steps", whole
        if not phrases or any(len(p) > MAX_PHRASE for p in phrases):
            errors.append(f"บรรทัด {n}: คำพูดต้องมีและยาวไม่เกิน {MAX_PHRASE} ตัวอักษร")
        if kind == "steps":
            errors += [f"บรรทัด {n}: {e}" for e in parse_steps(arg)[1]]
        else:
            errors += [f"บรรทัด {n}: {e}" for e in _check_action(kind, arg)]
        if kind == "system":
            _cmds, why = alias_commands(arg)
            if why:
                errors.append(f"บรรทัด {n}: {why}")
            # คำที่ระบบรู้จักอยู่แล้ว (ทำเองก่อนเสมอ) ไม่มีวันถึงสกิล → ตัดออก แสดงเฉพาะคำที่ใช้ได้ (H5) ·
            # เดิมปฏิเสธทั้งสกิล: ชุดพัฒนา A3 (2026-10-27) Claude ใส่คำพ้องถูก แต่แถม "โหลดใหม่"
            # "กลับหน้าเมื่อกี้" "ขอคลิปต่อไป" (ระบบรู้จักแล้ว) → ตก 3/9 · Claude เดาไม่ได้ว่าตัวแปลรู้จักคำไหน (H6) ·
            # ตัดแล้วไม่เหลือ = ไม่รับ · เฉพาะบรรทัดคำพ้อง (สกิลเดิมแบบกดคีย์ไม่ถูกแตะ · H2)
            from aipc.skills import browse

            live = tuple(p for p in phrases if not browse.parse(p))
            if not live:
                # ทั้งบรรทัดระบบทำเองอยู่แล้ว = ตัดบรรทัดทิ้ง ไม่ปฏิเสธทั้งสกิล (การ์ด 0074 รอบ 2 g22) ·
                # ไม่เหลือคำสั่งเลย = ไม่รับ ด้านล่าง
                known.append(n)
                continue
            phrases = live
        # คำสั่งหลายขั้นดูคำเสี่ยงในป้าย/ตัวเลือกของทุกขั้นด้วย (ตัวเลือกมาจากหน้าเว็บที่บันทึก)
        said = [*phrases, arg] if kind == "steps" else phrases
        if not confirm and any(w in p.lower() for p in said for w in RISKY):
            errors.append(
                f"บรรทัด {n}: คำสั่ง “{phrases[0]}” ย้อนไม่ได้หรือแตะบัญชี ต้องลงท้ายด้วย “· ยืนยันก่อน”"
            )
        out.append(SiteCommand(phrases, kind, arg, confirm))
    if not out and not errors:
        errors.append(
            f"บรรทัด {known[0]}: คำพูดทุกคำระบบรู้จักอยู่แล้ว (ทำเองก่อนเสมอ · ไม่ต้องใส่เป็นคำพ้อง)"
            if known
            else "หัวข้อ “## คำสั่ง” ว่าง"
        )
    if len(out) > MAX_COMMANDS:
        errors.append(f"คำสั่งมากเกิน {MAX_COMMANDS} ข้อ")
    return out, errors


def site_host(site: str) -> str:
    """โดเมนของเว็บในสกิล · "" = ใช้ไม่ได้."""
    from aipc.skills.actions import SITES

    if site.startswith("https://"):
        return (urlsplit(site).hostname or "").removeprefix("www.")
    return (urlsplit(SITES[site][1]).hostname or "").removeprefix("www.") if site in SITES else ""


# เว็บบัญชี Google: เดิมเปิดในหน้าต่างบัญชีที่ระบบไม่ได้คุม (การ์ด 0031) · การ์ด 0064 ย้ายมาเบราว์เซอร์ของผู้ช่วยแล้ว
# แต่สกิลประจำเว็บ (กดคีย์/คลิกในอีเมล เอกสาร ไฟล์) ยังไม่ได้วัดผลและอยู่นอกขอบเขต 0064 → ยังไม่รับ (ชุดวัด W4 x07)
NO_SITE_SKILL: frozenset[str] = frozenset({"gmail", "calendar", "drive", "docs"})


def check_site(site: str) -> list[str]:
    from aipc.skills.actions import SITES

    if site in NO_SITE_SKILL:
        return [f"เว็บ {site} เป็นบัญชี Google · ยังไม่รับสกิลประจำเว็บนี้ (การ์ด 0064 หัวข้อ 9)"]
    if site not in SITES and not (site.startswith("https://") and site_host(site)):
        return [
            f"site ต้องเป็นชื่อในรายการเว็บ ({', '.join(sorted(set(SITES) - NO_SITE_SKILL))}) หรือ https://…"
        ]
    return []


def on_site(site: str, url: str) -> bool:
    """หน้าที่เปิดอยู่เป็นเว็บของสกิลไหม (โดเมนเดียวกันหรือโดเมนย่อย เช่น m.youtube.com)."""
    want = site_host(site)
    parts = urlsplit(url)
    host = (parts.hostname or "").removeprefix("www.")
    # maps.google.com ส่งต่อไป www.google.com/maps (การ์ด 0048)
    if site == "maps" and host == "google.com" and parts.path.startswith("/maps"):
        return True
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
