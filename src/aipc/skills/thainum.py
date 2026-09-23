"""อ่านตัวเลขในประโยค ทั้งเลขอารบิก เลขไทย (๔๐) และคำอ่าน (สี่สิบ).

ใช้กับคำสั่งเสียง เพราะระบบถอดเสียงอาจให้ผลเป็นคำ เช่น "ปรับเสียงสี่สิบ" แทน "40"
รองรับ 0–999 ซึ่งพอสำหรับเปอร์เซ็นต์เสียงและนาที · เกินกว่านั้นคืน None ไม่เดา
"""

from __future__ import annotations

import re

DIGITS = {"ศูนย์": 0, "หนึ่ง": 1, "เอ็ด": 1, "สอง": 2, "ยี่": 2, "สาม": 3, "สี่": 4,
          "ห้า": 5, "หก": 6, "เจ็ด": 7, "แปด": 8, "เก้า": 9}  # fmt: skip
THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
WORD_RE = re.compile("(" + "|".join(sorted([*DIGITS, "สิบ", "ร้อย"], key=len, reverse=True)) + ")+")


def words_to_int(words: str) -> int | None:
    """ "สี่สิบห้า" → 45 · "ยี่สิบ" → 20 · "สิบเอ็ด" → 11 · "ร้อยห้าสิบ" → 150."""
    tokens = re.findall("|".join(sorted([*DIGITS, "สิบ", "ร้อย"], key=len, reverse=True)), words)
    if not tokens or "".join(tokens) != words:
        return None
    total, current = 0, None
    for tok in tokens:
        if tok == "ร้อย":
            total += (current if current is not None else 1) * 100
            current = None
        elif tok == "สิบ":
            total += (current if current is not None else 1) * 10
            current = None
        else:
            if current is not None:  # ตัวเลขสองตัวติดกัน เช่น "สี่ห้า" — ไม่ใช่รูปแบบที่ถูก
                return None
            current = DIGITS[tok]
    return total + (current or 0)


def find_number(text: str) -> int | None:
    """ตัวเลขตัวแรกในประโยค · "ครึ่ง" = 50 (ใช้บ่อยกับเสียง: "เสียงครึ่งหนึ่ง")."""
    text = text.translate(THAI_DIGITS)
    m = re.search(r"\d+", text)
    if m:
        return int(m.group())
    # ตรวจ "ครึ่ง" ก่อนคำอ่านตัวเลข ไม่งั้น "ครึ่งหนึ่ง" จะถูกอ่านเป็น 1 จากคำว่า "หนึ่ง"
    if "ครึ่ง" in text:
        return 50
    m = WORD_RE.search(text)
    if m:
        return words_to_int(m.group())
    return None
