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
    r"(?:(?P<rep>every\s*day|daily|every\s+weekday|on\s+weekdays|weekdays"
    r"|(?:every|on)\s+(?:the\s+)?weekends?|weekends"
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
    (re.compile(r"unmute(?:\s+(?:the\s+)?(?:sound|audio|volume|computer|speakers?))?"
                rf"|turn\s+(?:(?:back\s+)?on\s+the\s+{_SOUND}|the\s+{_SOUND}\s+(?:back\s+)?on)"),
     "เปิดเสียง"),
    (re.compile(r"(?:volume\s+up|louder|turn\s+(?:it|the\s+(?:volume|sound))\s+up"
                r"|turn\s+up\s+the\s+(?:volume|sound)|(?:increase|raise)\s+(?:the\s+)?(?:volume|sound))"
                r"(?:\s+a\s+(?:bit|little))?"), "เพิ่มเสียง"),
    (re.compile(r"(?:it'?s\s+)?too\s+quiet|(?:it'?s\s+)?too\s+soft"), "เพิ่มเสียง"),
    (re.compile(r"(?:it'?s\s+)?too\s+loud"), "ลดเสียง"),
    (re.compile(r"(?:volume\s+down|quieter|lower\s+the\s+(?:volume|sound)"
                r"|turn\s+(?:it|the\s+(?:volume|sound))\s+down|turn\s+down\s+the\s+(?:volume|sound)"
                r"|(?:decrease|reduce)\s+(?:the\s+)?(?:volume|sound))(?:\s+a\s+(?:bit|little))?"),
     "ลดเสียง"),
]  # fmt: skip
_SET_VOL = re.compile(
    r"(?:(?:set|change|put|turn)\s+(?:the\s+)?)?(?:volume|sound)\s+(?:(?:to|at)\s+)?(\d{1,3})"
    r"\s*(?:%|percent)?"
)
# "too loud, turn it down" = บ่นแล้วสั่ง · ตัดคำบ่นออกก่อนจับรูปคำสั่งเสียง (C1 รอบ 2 ข้อ C12)
_VOL_PRE = re.compile(r"(?:it'?s\s+|that'?s\s+)?too\s+(?:loud|quiet|soft)[,.!]?\s+")
_OPEN = re.compile(
    r"(?:open|launch|start|go\s+to|show(?:\s+me)?|take\s+me\s+to|bring\s+up|pull\s+up|visit"
    r"|fire\s+up|load)\s+(?:up\s+)?(?:the\s+)?(.+?)(?:\s+(?:page|app|website|site|screen))?"
)
_TIME_Q = re.compile(
    r"what(?:'s|\s+is)?\s+(?:the\s+)?(?:current\s+)?time(?:\s+is\s+it)?(?:\s+now)?"
    r"|what\s+time\s+is\s+it(?:\s+now)?|tell\s+me\s+the\s+(?:current\s+)?time|current\s+time|time\s+now"
    r"|(?:(?:do\s+you\s+know|tell\s+me)\s+)?what\s+time\s+it\s+is(?:\s+now)?"
)
_RANGE = (r"(?P<r>today|tomorrow|this\s+week|next\s+week"
          rf"|(?:on\s+)?(?:(?P<nx>next|this)\s+)?(?P<wd>{_WD}))")  # fmt: skip
_AGENDA = [
    re.compile(
        r"(?:what(?:'s|\s+is|\s+do\s+i\s+have)?(?:\s+(?:on|in))?(?:\s+my)?"
        r"(?:\s+(?:schedule|agenda|calendar|plan|plans))?"
        r"|(?:do\s+i\s+have\s+)?any\s+(?:appointments?|meetings?|events?|plans?|reminders?)"
        r"|(?:do\s+i\s+have|is\s+there|have\s+i\s+got)\s+(?:anything|something)"
        r"(?:\s+(?:planned|scheduled|on))?|(?:anything|something)\s+(?:planned|scheduled)"
        r"|what(?:'s|\s+is)\s+(?:planned|scheduled|coming\s+up)"
        r"|(?:show|list)(?:\s+me)?\s+(?:my\s+)?(?:schedule|agenda|appointments?|events?)"
        rf"|am\s+i\s+(?:busy|free))(?:\s+(?:for|on))?\s+{_RANGE}"
    ),
    re.compile(rf"{_RANGE}'?s?\s+(?:schedule|agenda|appointments?)"),
]
_NEXT = re.compile(
    r"(?:what(?:'s|\s+is)\s+)?(?:my\s+)?next\s+(?:appointment|meeting|event|reminder)"
    r"|when\s+is\s+my\s+next\s+(?:appointment|meeting|event)"
    # "what's coming up next on my calendar" · ต้องมี "on my calendar"
    # ("what's next?" เฉย ๆ อาจเป็นเรื่องอื่น)
    r"|what(?:'s|\s+is)\s+(?:coming\s+up\s+(?:next\s+)?|next\s+)on\s+my\s+(?:calendar|schedule|agenda)"
)
_ORD_WORDS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth",
              "tenth", "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth",
              "seventeenth", "eighteenth", "nineteenth", "twentieth"]  # fmt: skip
_ORD_N = {w: i + 1 for i, w in enumerate(_ORD_WORDS)}
_ORD_N |= {f"twenty-{w}": 20 + i + 1 for i, w in enumerate(_ORD_WORDS[:9])}
_ORD_N |= {"thirtieth": 30, "thirty-first": 31}
# "on the first" · "November third" → ตัวเลข (D1: ตัวถอดเสียงสะกดลำดับที่เป็นคำ) · เฉพาะหลัง the/ชื่อเดือน
_ORD_RE = re.compile(
    rf"(?i)\b(the|{_MON})\s+(" + "|".join(sorted(_ORD_N, key=len, reverse=True)) + r")\b"
)


def _ordinals(text: str) -> str:
    def digits(m: re.Match) -> str:
        n = _ORD_N[m.group(2).lower()]
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10 if n not in (11, 12, 13) else 0, "th")
        return f"{m.group(1)} {n}{suffix}"

    return _ORD_RE.sub(digits, text)


_DOCS = r"(?:files|documents|docs)"
_EDITED = r"(?:edited|modified|changed|worked\s+on|saved|updated)"
_FILE_WHEN = r"(?P<w>today|yesterday|this\s+week)"
_FILES = [
    # "show me the files I edited today" · "files changed this week"
    re.compile(rf"(?:(?:show|list|find|get)(?:\s+me)?\s+)?(?:the\s+|my\s+|all\s+)?{_DOCS}"
               rf"\s+(?:that\s+)?(?:i\s+|were\s+|i've\s+|i\s+have\s+)?{_EDITED}\s+{_FILE_WHEN}"),
    # "what files did I change yesterday?" · "which documents have I edited this week"
    re.compile(rf"(?:what|which)\s+{_DOCS}\s+(?:did\s+i|have\s+i|i)\s+"
               rf"(?:edit|modify|change|work\s+on|save|update|edited|modified|changed|worked\s+on|saved)"
               rf"\s+{_FILE_WHEN}"),
]  # fmt: skip
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
_REMIND_HEAD = re.compile(rf"(?:remind\s+me|{_SET_REMINDER})\s+(?:to|about|for)\s+")


def _split_remind(t: str, raw: str) -> tuple[str, str] | None:
    """แยก "remind me to <ชื่อนัด> <วันเวลา>" · ลองทุกจุดตัดจากชื่อนัดสั้นไปยาว ·
    เอาจุดแรกที่ส่วนท้ายเป็นวันเวลาทั้งวลี ("go to the dentist friday 2:30" · C1 รอบ 2 ข้อ C17) ·
    คืน (ชื่อนัดตามตัวพิมพ์เดิม, วันเวลาไทย)."""
    m = _REMIND_HEAD.match(t)
    if m is None:
        return None
    starts = [w.start() for w in re.finditer(r"\S+", t[m.end() :])][1:]
    for s in starts:
        if when := when_th(t[m.end() + s :]):
            return raw[m.end() : m.end() + s].strip(), when
    return None


# ชื่อนัดที่ยังมีคำบอกวัน/ตัวเลข = ตัวแปลงตัดวันเวลาผิดที่ ("dentist friday 2:30" เคยได้ "วันนี้" · C1 รอบ 2 ข้อ C17)
# → ไม่เดา ส่งข้อความเดิมให้ AI (ใช้ชื่อเต็มเท่านั้น: "may" "sat" เป็นคำทั่วไปได้)
_DAY_LEFT = re.compile(
    r"\b(?:(?:mon|tues|wednes|thurs|fri|satur|sun)day|january|february|march|april|june|july"
    r"|august|september|october|november|december|today|tonight|tomorrow|weekends?|weekdays?"
    r"|noon|midnight|\d+(?::\d\d)?\s*(?:am|pm|a\.m\.|p\.m\.)?)\b"
)


def to_thai(text: str) -> str | None:
    """ประโยคอังกฤษที่เป็นคำสั่งในขอบเขต → ข้อความไทยสำหรับตัวแปลเดิม · ไม่ใช่ = None."""
    if not is_english(text):
        return None
    raw = _ordinals(_clean(text))
    t = raw.lower()
    tv = _VOL_PRE.sub("", t, count=1) if _VOL_PRE.match(t) else t
    for rx, th in _VOLUME:
        if rx.fullmatch(tv):
            return th
    if m := _SET_VOL.fullmatch(tv):
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
    if m := next((m for rx in _FILES if (m := rx.fullmatch(t))), None):
        return "ไฟล์ที่แก้" + {"today": "วันนี้", "yesterday": "เมื่อวาน"}.get(m.group("w"), "สัปดาห์นี้")
    if _CANCEL_ALL.fullmatch(t):
        return "ยกเลิกนัดทั้งหมด"
    if m := next((m for rx in _CANCEL if (m := rx.fullmatch(t))), None):
        return f"ยกเลิกนัด {_keep(m, raw, 'w')}"
    found = _split_remind(t, raw)  # ชื่อนัดก่อนวันเวลา ("remind me to … at 9")
    for rx in () if found else _REMIND:  # วันเวลาก่อนชื่อนัด ("remind me at 9 to …")
        if (m := rx.fullmatch(t)) and (when := when_th(m.group("when"))):
            found = _keep(m, raw, "what"), when
            break
    if found:
        what, when = found
        if _DAY_LEFT.search(what.lower()):
            return None
        if what and not re.search(r"\b(?:to|about)\s*$", what):
            return f"เตือน {what} {when}"
    if m := _REMIND_NO_TIME.fullmatch(t):  # ไม่บอกเวลา = การ์ดถามเวลาเหมือนพิมพ์ไทย ("เตือนซื้อนม")
        what = _keep(m, raw, "what")
        return None if _DAY_LEFT.search(what.lower()) else f"เตือน {what}"
    if m := _OPEN.fullmatch(t):
        name = m.group(1).strip()
        if site := SITES.get(name) or SITES.get(name.removeprefix("my ")):  # "open my gmail"
            return f"เปิด{site}"
    return None
