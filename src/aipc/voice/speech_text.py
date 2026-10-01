"""ข้อความคำตอบ → คำอ่านภาษาไทยก่อนส่งให้ Piper (การ์ด 0019 · อ่านออกเสียงอย่างเดียว).

ทำไมต้องแปลงเอง (ลองกับ Piper th_TH-tsync2 บน Pi 5 จริง 2026-10-01):
ตัวอักษรอังกฤษถูกตัดทิ้งเงียบ ๆ ("เปิด YouTube" ได้ยินแค่ "เปิด") · "ต.ค." อ่านว่า "ต่อ คอ" · "14:30" อ่านเป็นเลขแยก
→ แปลงเป็นคำไทยที่นี่ให้แน่นอนและเทสต์ได้ (tests/data/tts_normalize.json เขียนก่อนโค้ด)
ข้อจำกัด: คำอังกฤษที่ไม่อยู่ใน WORDS และไม่ใช่ตัวย่อตัวพิมพ์ใหญ่ = ตัดทิ้ง
"""

from __future__ import annotations

import re
import unicodedata

DIGIT = ["ศูนย์", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
PLACE = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน"]
LETTERS = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                   ["เอ", "บี", "ซี", "ดี", "อี", "เอฟ", "จี", "เอช", "ไอ", "เจ", "เค", "แอล", "เอ็ม",
                    "เอ็น", "โอ", "พี", "คิว", "อาร์", "เอส", "ที", "ยู", "วี", "ดับเบิลยู", "เอ็กซ์",
                    "วาย", "แซด"], strict=True))  # fmt: skip
# คำอังกฤษที่เจอบ่อยในคำตอบของแอป (ชื่อแอป/เว็บในตัวแปลคำสั่ง · หน่วย · ชื่อระบบ) · ตัวพิมพ์เล็กทั้งหมด
WORDS = {
    "youtube": "ยูทูบ", "google": "กูเกิล", "chrome": "โครม", "chromium": "โครเมียม",
    "firefox": "ไฟร์ฟอกซ์",
    "facebook": "เฟซบุ๊ก", "line": "ไลน์", "gmail": "จีเมล", "email": "อีเมล", "claude": "คลอด",
    "gemma": "เจมมา", "python": "ไพทอน", "wi-fi": "ไวไฟ", "wifi": "ไวไฟ", "ok": "โอเค",
    "okay": "โอเค",
    "ram": "แรม", "app": "แอป", "raspberry": "ราสเบอร์รี", "pi": "พาย", "linux": "ลินุกซ์",
    "gb": "กิกะไบต์", "mb": "เมกะไบต์", "kb": "กิโลไบต์", "tb": "เทระไบต์", "ghz": "กิกะเฮิรตซ์",
    "skill": "สกิล", "online": "ออนไลน์", "offline": "ออฟไลน์", "login": "ล็อกอิน", "logout": "ล็อกเอาต์",
    "pin": "พิน", "cloud": "คลาวด์", "spotify": "สปอติฟาย", "netflix": "เน็ตฟลิกซ์", "zoom": "ซูม",
}  # fmt: skip
MONTHS = {"ม.ค.": "มกราคม", "ก.พ.": "กุมภาพันธ์", "มี.ค.": "มีนาคม", "เม.ย.": "เมษายน",
          "พ.ค.": "พฤษภาคม",
          "มิ.ย.": "มิถุนายน", "ก.ค.": "กรกฎาคม", "ส.ค.": "สิงหาคม", "ก.ย.": "กันยายน", "ต.ค.": "ตุลาคม",
          "พ.ย.": "พฤศจิกายน", "ธ.ค.": "ธันวาคม"}  # fmt: skip
ABBR = {**MONTHS, "พ.ศ.": "พุทธศักราช", "ค.ศ.": "คริสต์ศักราช", "กม.": "กิโลเมตร", "ซม.": "เซนติเมตร",
        "มม.": "มิลลิเมตร", "กก.": "กิโลกรัม", "ชม.": "ชั่วโมง", "จ.": "จังหวัด",
        "อ.": "อำเภอ"}  # fmt: skip
SYMBOLS = {"°C": " องศาเซลเซียส ", "°": " องศา ", "%": " เปอร์เซ็นต์ ", "&": " และ ", "+": " บวก ",
           "=": " เท่ากับ ", "฿": " บาท "}  # fmt: skip

THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
URL_RE = re.compile(r"(https?://|www\.)\S+")
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
TIME_RE = re.compile(r"(?<![\d.])(\d{1,2})(?::(\d{2})(?:\s*น\.)?|\.(\d{2})\s*น\.)(?![\d])")
NUM_RE = re.compile(r"(?:(?<=\s)|^)-(?=\d)|(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?![\d])")
LATIN_RE = re.compile(r"[A-Za-z][A-Za-z\-']*[A-Za-z]|[A-Za-z]")
MAX_CHARS = 1500  # คำตอบยาวกว่านี้อ่านแค่ส่วนต้น (เกิน ~2 นาที)


def number_words(n: int) -> str:
    """จำนวนเต็มเป็นคำอ่านไทย · 11 → สิบเอ็ด · 21 → ยี่สิบเอ็ด · 101 → หนึ่งร้อยเอ็ด · 1,000,000 → หนึ่งล้าน."""
    if n < 0:
        return "ลบ" + number_words(-n)
    if n == 0:
        return DIGIT[0]
    if n >= 1_000_000:
        high, low = divmod(n, 1_000_000)
        return number_words(high) + "ล้าน" + (_below_million(low, high > 0) if low else "")
    return _below_million(n, False)


def _below_million(n: int, has_higher: bool) -> str:
    digits = str(n)[::-1]
    out = []
    for place, ch in enumerate(digits):
        d = int(ch)
        if d == 0:
            continue
        if place == 0 and d == 1 and (len(digits) > 1 or has_higher):
            word = "เอ็ด"
        elif place == 1 and d == 1:
            word = ""
        elif place == 1 and d == 2:
            word = "ยี่"
        else:
            word = DIGIT[d]
        out.append(word + PLACE[place])
    return "".join(reversed(out))


def _number(m: re.Match) -> str:
    if m.group(1) is None:  # เครื่องหมายลบหน้าตัวเลข
        return " ลบ"
    words = number_words(int(m.group(1).replace(",", "")))
    if m.group(2):
        words += "จุด" + "".join(DIGIT[int(c)] for c in m.group(2)[1:])
    return f" {words} "


def _time(m: re.Match) -> str:
    h, mm = int(m.group(1)), int(m.group(2) or m.group(3))
    if h > 24 or mm > 59:
        return m.group(0)
    return f" {number_words(h)}นาฬิกา" + (f" {number_words(mm)}นาที " if mm else " ")


def _latin(m: re.Match) -> str:
    w = m.group(0)
    if w.lower() in WORDS:
        return f" {WORDS[w.lower()]} "
    if w.isupper() and 2 <= len(w) <= 5 and w.isalpha():
        return " " + "".join(LETTERS[c] for c in w) + " "
    return " "  # Piper อ่านไม่ได้อยู่แล้ว (ตัดทิ้งเงียบ ๆ) · ตัดเองให้ช่องว่างไม่เพี้ยน


def _plain(text: str) -> str:
    text = MD_LINK_RE.sub(r"\1", text)
    text = URL_RE.sub(" ", text)
    text = re.sub(r"(?m)^\s*(?:[-*•]|#+)\s+", " ", text)  # หัวข้อ/รายการ markdown
    text = re.sub(r"[*_`~>|#]", " ", text)
    return text


def to_speech(text: str) -> str:
    """ข้อความ (อาจมี markdown) → คำอ่านภาษาไทยบรรทัดเดียว · ว่าง = ไม่มีอะไรให้อ่าน."""
    text = _plain(text[:MAX_CHARS]).translate(THAI_DIGITS)
    text = TIME_RE.sub(_time, text)
    for abbr, word in sorted(ABBR.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(abbr, f" {word} ")
    for sym, word in SYMBOLS.items():
        text = text.replace(sym, word)
    text = LATIN_RE.sub(_latin, text)
    text = NUM_RE.sub(_number, text)
    # อีโมจิและสัญลักษณ์อื่น ๆ (Piper ไม่มีเสียงให้) · วรรคตอนเหลือแค่ช่องว่าง
    text = "".join(c if unicodedata.category(c)[0] in "LMN" or c.isspace() else " " for c in text)
    return re.sub(r"\s+", " ", text).strip()


def sentences(text: str, max_chars: int = 160) -> list[str]:
    """แบ่งข้อความที่แปลงแล้วเป็นท่อน ≤ max_chars ตามช่องว่าง · ท่อนแรกสั้นเพื่อให้เริ่มพูดเร็ว."""
    words, out, cur = text.split(), [], ""
    limit = min(60, max_chars)  # ท่อนแรกสั้น ~3 วิ = เริ่มพูดเร็ว
    for w in words:
        if cur and len(cur) + 1 + len(w) > limit:
            out.append(cur)
            cur, limit = w, max_chars
        else:
            cur = f"{cur} {w}" if cur else w
    if cur:
        out.append(cur)
    return out
