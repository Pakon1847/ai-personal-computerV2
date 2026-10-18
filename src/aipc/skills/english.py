"""แปลงคำสั่งภาษาอังกฤษเป็นรูปภาษาไทยที่ตัวแปลเดิมเข้าใจ (การ์ด 0039 ระยะ C) · กฎล้วน ไม่ใช้ LLM (H6).

ทำไมแปลงแทนการเขียนตัวแปลใหม่: ตัวแปลไทย (คำสั่งเครื่อง · วันเวลานัด · ถามนัด) วัดผลมาแล้ว ·
แปลงคำอังกฤษเป็นคำไทยที่ตรงกันด้วยตาราง แล้วใช้ตัวแปลเดิม = กติกาวันเวลาเป็นโค้ดชุดเดียว ·
ชื่อนัด/คำที่ผู้ใช้พิมพ์คงภาษาเดิม ("remind me to call mom" → "เตือน call mom ...")

to_thai(text) → ข้อความไทย หรือ None (ไม่ใช่คำสั่งในขอบเขต → แอปส่งข้อความเดิมให้ AI ตอบเป็นอังกฤษ)
ทุกกฎต้องตรงทั้งประโยค (fullmatch) · ไม่รู้จักเป้าหมาย/วันเวลา = None ไม่เดา
"""

from __future__ import annotations

import re

from aipc.skills.catalog import is_english

# ---------- ตารางคำ ----------
SITES = {  # ชื่ออังกฤษ → คำไทยที่ command.parse รู้จัก (เปิดเว็บ/แอป/หน้าในระบบ)
    "youtube": "ยูทูบ", "gmail": "จีเมล", "my email": "จีเมล", "email": "จีเมล",
    "google": "กูเกิล", "wikipedia": "วิกิพีเดีย", "google maps": "กูเกิลแมพ", "maps": "กูเกิลแมพ",
    "facebook": "เฟซบุ๊ก", "instagram": "อินสตาแกรม", "google calendar": "ปฏิทินกูเกิล",
    "google drive": "กูเกิลไดรฟ์", "browser": "เบราว์เซอร์", "web browser": "เบราว์เซอร์",
    "chromium": "เบราว์เซอร์", "terminal": "เทอร์มินัล", "file manager": "ตัวจัดการไฟล์",
    "files app": "ตัวจัดการไฟล์", "settings": "หน้าตั้งค่า", "calendar": "ปฏิทิน", "my calendar": "ปฏิทิน",
    "my files": "หน้าไฟล์ของฉัน", "files": "หน้าไฟล์ของฉัน", "computer health": "หน้าสุขภาพเครื่อง",
    "health": "หน้าสุขภาพเครื่อง", "system health": "หน้าสุขภาพเครื่อง", "skills": "หน้าสกิล",
    "privacy": "หน้าความเป็นส่วนตัว", "privacy settings": "หน้าความเป็นส่วนตัว",
    "assistant": "หน้าผู้ช่วย", "chat": "หน้าผู้ช่วย",
}  # fmt: skip
WEEKDAYS = {"monday": "จันทร์", "tuesday": "อังคาร", "wednesday": "พุธ", "thursday": "พฤหัสบดี",
            "friday": "ศุกร์", "saturday": "เสาร์", "sunday": "อาทิตย์"}  # fmt: skip
_WD = r"(?:mon|tues|tue|wednes|wed|thurs|thu|fri|satur|sat|sun)(?:day)?"
MONTHS = {"jan": "มกราคม", "feb": "กุมภาพันธ์", "mar": "มีนาคม", "apr": "เมษายน", "may": "พฤษภาคม",
          "jun": "มิถุนายน", "jul": "กรกฎาคม", "aug": "สิงหาคม", "sep": "กันยายน", "oct": "ตุลาคม",
          "nov": "พฤศจิกายน", "dec": "ธันวาคม"}  # fmt: skip
_MON = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
           "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30,
           "forty": 40, "forty-five": 45, "sixty": 60}  # fmt: skip
_NUM = r"(?:\d{1,3}|" + "|".join(sorted(NUMBERS, key=len, reverse=True)) + ")"
_ORD = r"(?:st|nd|rd|th)?"

# คำขอนำหน้า/ท้ายที่ไม่เปลี่ยนความหมาย ("please open youtube for me")
_LEAD = re.compile(
    r"(?i)^(?:(?:hey|hi|ok|okay|please|can you|could you|would you|will you|i want you to"
    r"|i'd like you to)[,!]?\s+)+"
)
_TAIL = re.compile(r"(?i)(?:\s+(?:please|for me|thanks|thank you|now|right now))+$")


def _clean(text: str) -> str:
    """ตัดคำขอสุภาพ/ช่องว่างซ้ำ · คงตัวพิมพ์เดิม (ชื่อนัด "Tom" ต้องไม่กลายเป็น "tom")."""
    t = re.sub(r"\s+", " ", text.strip()).strip(" .!?")
    t = _LEAD.sub("", t.replace("’", "'"))
    return _TAIL.sub("", t).strip(" ,.!?")


def _keep(m: re.Match, raw: str, name: str) -> str:
    """ข้อความของผู้ใช้ในช่อง name ตามตัวพิมพ์เดิม (จับคู่บนตัวพิมพ์เล็ก แล้วตัดจากข้อความเดิมตำแหน่งเดียวกัน)."""
    a, b = m.span(name)
    return (raw[a:b] if len(raw) == len(m.string) else m.group(name)).strip()


def _weekday(word: str) -> str:
    return next(th for full, th in WEEKDAYS.items() if full.startswith(word[:3]))


def _month(word: str) -> str:
    return MONTHS[word[:3]]


def _num(word: str) -> int:
    return int(word) if word.isdigit() else NUMBERS[word]


# ---------- เวลา/วัน (ส่วน "when" ของนัด) ----------
_TIME_RE = re.compile(
    r"(?:at\s+)?(?P<h>\d{1,2})(?:[:.](?P<m>\d{2}))?\s*(?P<ap>a\.?m\.?|p\.?m\.?|o'?clock)?"
    r"|(?:at\s+)?(?P<noon>noon|midday|midnight)"
)
_REL_RE = re.compile(rf"in\s+(?P<n>{_NUM}|half an)\s+(?P<u>minutes?|mins?|hours?|hrs?)")
_DAY_RE = re.compile(
    r"(?:(?P<rep>every\s*day|daily|every\s+weekday|on\s+weekdays|weekdays|every\s+weekend"
    rf"|every\s+(?P<rwd>{_WD}))"
    r"|(?P<d>today|tonight|tomorrow|the day after tomorrow|day after tomorrow)"
    rf"|(?:on\s+)?(?P<nx>next|this)?\s*(?P<wd>{_WD})"
    rf"|(?:on\s+)?(?:the\s+)?(?P<dd>\d{{1,2}}){_ORD}(?:\s+of)?\s+(?P<mn>{_MON})"
    rf"|(?:on\s+)?(?P<mn2>{_MON})\s+(?P<dd2>\d{{1,2}}){_ORD}"
    r"|on\s+the\s+(?P<dd3>\d{1,2})(?:st|nd|rd|th))"
    r"(?:\s+(?:morning|afternoon|evening|night|in the (?:morning|afternoon|evening)))?"
)


def _time_th(m: re.Match, part: str = "") -> str | None:
    """part = วลีวันที่พูดคู่กัน ("tomorrow evening" · "tonight") ·
    ไม่บอก am/pm แต่บอกบ่าย/เย็น/คืน = บวก 12 ชม. ·
    ไม่บอกอะไรเลย = "3 โมง" ตามกติกาไทยเดิม (ตีความแล้วบอกผู้ใช้)."""
    if m.group("noon"):
        return "00:00" if m.group("noon") == "midnight" else "12:00"
    h, mi = int(m.group("h")), int(m.group("m") or 0)
    ap = (m.group("ap") or "").replace(".", "")
    if h > 23 or mi > 59:
        return None
    plain = not ap.startswith(("a", "p")) and 1 <= h <= 11
    if ap.startswith("p") and h < 12:
        h += 12
    elif ap.startswith("a") and h == 12:
        h = 0
    elif plain and re.search(r"afternoon|evening|night", part):
        h += 12
    elif plain and "morning" not in part:
        if not m.group("m"):
            return f"{h} โมง"  # ตัวแปลไทยตีความ (1–6 = บ่าย · 7–12 = เช้า/เที่ยง) และบอกผู้ใช้ในการ์ด
        h += 12 if h <= 6 else 0  # "at 3:30" = กติกาเดียวกับ "3 โมง" (บ่าย)
    return f"{h:02d}:{mi:02d}"


def _day_th(m: re.Match) -> str:
    g = m.groupdict()
    if g["rep"]:
        if g["rwd"]:
            return "ทุกวัน" + _weekday(g["rwd"])
        if "weekend" in g["rep"]:
            return "ทุกเสาร์อาทิตย์"
        return "วันธรรมดา" if "weekday" in g["rep"] else "ทุกวัน"
    if g["d"]:
        return {"today": "วันนี้", "tonight": "คืนนี้", "tomorrow": "พรุ่งนี้"}.get(g["d"], "มะรืนนี้")
    if g["wd"]:
        return "วัน" + _weekday(g["wd"]) + ("หน้า" if g["nx"] == "next" else "นี้")
    if g["dd"] or g["dd2"]:
        return f"{int(g['dd'] or g['dd2'])} {_month(g['mn'] or g['mn2'])}"
    return f"วันที่ {int(g['dd3'])}"


def when_th(phrase: str) -> str | None:
    """แปลงวลีวันเวลา: "tomorrow at 2 pm" → "พรุ่งนี้ 14:00" · วัน+เวลาสลับลำดับได้ · ไม่ตรงทั้งวลี = None."""
    p = re.sub(r"\s+", " ", phrase.strip().lower())
    if m := _REL_RE.fullmatch(p):
        if m.group("n") == "half an":
            return "อีก 30 นาที"
        unit = "ชั่วโมง" if m.group("u").startswith("h") else "นาที"
        return f"อีก {_num(m.group('n'))} {unit}"
    if m := _DAY_RE.fullmatch(p):
        return _day_th(m)
    if m := _TIME_RE.fullmatch(p):
        return _time_th(m)
    words = p.split(" ")
    for i in range(1, len(words)):  # แบ่งเป็น วัน|เวลา หรือ เวลา|วัน
        left, right = " ".join(words[:i]), " ".join(words[i:])
        for day_part, time_part in ((left, right), (right, left)):
            d, tm = _DAY_RE.fullmatch(day_part), _TIME_RE.fullmatch(time_part)
            if d and tm and (t := _time_th(tm, day_part)):
                return f"{_day_th(d)} {t}"
    return None


# ---------- รูปประโยคคำสั่ง ----------
_SOUND = r"(?:sound|audio)"
_VOLUME = [
    (re.compile(r"(?:mute|silence)(?:\s+(?:the\s+)?(?:sound|audio|volume|computer|speakers?))?"
                rf"|turn\s+(?:off\s+the\s+{_SOUND}|the\s+{_SOUND}\s+off)"), "ปิดเสียง"),
    (re.compile(r"unmute(?:\s+(?:the\s+)?(?:sound|audio|computer))?"
                rf"|turn\s+(?:(?:back\s+)?on\s+the\s+{_SOUND}|the\s+{_SOUND}\s+(?:back\s+)?on)"),
     "เปิดเสียง"),
    (re.compile(r"(?:volume\s+up|louder|turn\s+(?:it|the\s+(?:volume|sound))\s+up"
                r"|turn\s+up\s+the\s+(?:volume|sound)|(?:increase|raise)\s+(?:the\s+)?(?:volume|sound))"
                r"(?:\s+a\s+(?:bit|little))?"), "เพิ่มเสียง"),
    (re.compile(r"(?:volume\s+down|quieter|lower\s+the\s+(?:volume|sound)"
                r"|turn\s+(?:it|the\s+(?:volume|sound))\s+down|turn\s+down\s+the\s+(?:volume|sound)"
                r"|(?:decrease|reduce)\s+(?:the\s+)?(?:volume|sound))(?:\s+a\s+(?:bit|little))?"),
     "ลดเสียง"),
]  # fmt: skip
_SET_VOL = re.compile(
    r"(?:set|change|put|turn)\s+(?:the\s+)?(?:volume|sound)\s+(?:to|at)\s+(\d{1,3})\s*(?:%|percent)?"
)
_OPEN = re.compile(
    r"(?:open|launch|start|go\s+to|show(?:\s+me)?|take\s+me\s+to|bring\s+up)\s+(?:up\s+)?(?:the\s+)?(.+?)"
    r"(?:\s+(?:page|app|website|site|screen))?"
)
_TIME_Q = re.compile(
    r"what(?:'s|\s+is)?\s+(?:the\s+)?time(?:\s+is\s+it)?(?:\s+now)?|what\s+time\s+is\s+it(?:\s+now)?"
    r"|tell\s+me\s+the\s+time|current\s+time|time\s+now"
)
_RANGE = (r"(?P<r>today|tomorrow|this\s+week|next\s+week"
          rf"|(?:on\s+)?(?:(?P<nx>next|this)\s+)?(?P<wd>{_WD}))")  # fmt: skip
_AGENDA = [
    re.compile(
        r"(?:what(?:'s|\s+is|\s+do\s+i\s+have)?(?:\s+(?:on|in))?(?:\s+my)?"
        r"(?:\s+(?:schedule|agenda|calendar|plan|plans))?"
        r"|(?:do\s+i\s+have\s+)?any\s+(?:appointments?|meetings?|events?|plans?|reminders?)"
        r"|(?:show|list)(?:\s+me)?\s+(?:my\s+)?(?:schedule|agenda|appointments?|events?)"
        rf"|am\s+i\s+(?:busy|free))(?:\s+(?:for|on))?\s+{_RANGE}"
    ),
    re.compile(rf"{_RANGE}'?s?\s+(?:schedule|agenda|appointments?)"),
]
_NEXT = re.compile(
    r"(?:what(?:'s|\s+is)\s+)?(?:my\s+)?next\s+(?:appointment|meeting|event|reminder)"
    r"|when\s+is\s+my\s+next\s+(?:appointment|meeting|event)"
)
_FILES = re.compile(
    r"(?:show|list|find)(?:\s+me)?\s+(?:the\s+|my\s+)?files\s+(?:that\s+)?(?:i\s+)?"
    r"(?:edited|modified|changed|worked\s+on|saved)\s+(?P<w>today|yesterday|this\s+week)"
)
_CANCEL_ALL = re.compile(
    r"(?:cancel|delete|remove|clear)\s+(?:all\s+(?:of\s+)?(?:my\s+)?|every\s+)(?:reminders?|appointments?)"
)
_APPT = r"(?:reminder|appointment|meeting|event)"
_CANCEL = [
    re.compile(rf"(?:cancel|delete|remove)\s+(?:the\s+|my\s+)?{_APPT}s?"
               r"\s+(?:for\s+|about\s+|to\s+|called\s+|with\s+)?(?P<w>.+)"),
    re.compile(rf"(?:cancel|delete|remove)\s+(?:the\s+|my\s+)(?P<w>.+?)\s+{_APPT}"),
]  # fmt: skip
# ส่วน "when" ต้องขึ้นต้นด้วยคำบอกวันเวลา (กันชื่อนัดที่มีคำว่า "to" ปน)
_WHEN_START = (r"(?:at|on|in|today|tonight|tomorrow|the\s+day|day|next|this|every|daily|weekdays"
               r"|noon|midday|midnight|\d)")  # fmt: skip
_SET_REMINDER = r"(?:set|add|create|make)\s+(?:a\s+)?reminder"
_REMIND = [
    re.compile(rf"remind\s+me\s+(?:to|about)\s+(?P<what>.+?)\s+(?P<when>{_WHEN_START}.*)"),
    re.compile(r"remind\s+me\s+(?P<when>.+?)\s+(?:to|about)\s+(?P<what>.+)"),
    re.compile(rf"{_SET_REMINDER}\s+(?:to|for|about)\s+(?P<what>.+?)\s+(?P<when>{_WHEN_START}.*)"),
    re.compile(rf"{_SET_REMINDER}\s+(?:for\s+)?(?P<when>.+?)\s+(?:to|for|about)\s+(?P<what>.+)"),
]
_REMIND_NO_TIME = re.compile(rf"(?:remind\s+me|{_SET_REMINDER})\s+(?:to|about)\s+(?P<what>.+)")


def to_thai(text: str) -> str | None:
    """ประโยคอังกฤษที่เป็นคำสั่งในขอบเขต → ข้อความไทยสำหรับตัวแปลเดิม · ไม่ใช่ = None."""
    if not is_english(text):
        return None
    raw = _clean(text)
    t = raw.lower()
    for rx, th in _VOLUME:
        if rx.fullmatch(t):
            return th
    if m := _SET_VOL.fullmatch(t):
        n = int(m.group(1))
        return f"ปรับเสียงเป็น {n}" if 0 <= n <= 100 else None
    if _TIME_Q.fullmatch(t):
        return "ตอนนี้กี่โมง"
    if _NEXT.fullmatch(t):
        return "นัดถัดไปคืออะไร"
    if m := next((m for rx in _AGENDA if (m := rx.fullmatch(t))), None):
        if m.group("wd"):
            day = "วัน" + _weekday(m.group("wd")) + ("หน้า" if m.group("nx") == "next" else "นี้")
        else:
            r = re.sub(r"\s+", " ", m.group("r"))
            day = {"today": "วันนี้", "tomorrow": "พรุ่งนี้", "this week": "สัปดาห์นี้"}.get(r, "สัปดาห์หน้า")
        return f"{day}มีนัดอะไร"
    if m := _FILES.fullmatch(t):
        return "ไฟล์ที่แก้" + {"today": "วันนี้", "yesterday": "เมื่อวาน"}.get(m.group("w"), "สัปดาห์นี้")
    if _CANCEL_ALL.fullmatch(t):
        return "ยกเลิกนัดทั้งหมด"
    if m := next((m for rx in _CANCEL if (m := rx.fullmatch(t))), None):
        return f"ยกเลิกนัด {_keep(m, raw, 'w')}"
    for rx in _REMIND:
        if (m := rx.fullmatch(t)) and (when := when_th(m.group("when"))):
            what = _keep(m, raw, "what")
            if what and not re.search(r"\b(?:to|about)\s*$", what):
                return f"เตือน {what} {when}"
    if m := _REMIND_NO_TIME.fullmatch(t):  # ไม่บอกเวลา = การ์ดถามเวลาเหมือนพิมพ์ไทย ("เตือนซื้อนม")
        return f"เตือน {_keep(m, raw, 'what')}"
    if (m := _OPEN.fullmatch(t)) and (site := SITES.get(m.group(1).strip())):
        return f"เปิด{site}"
    return None
