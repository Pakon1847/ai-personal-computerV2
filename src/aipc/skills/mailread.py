"""อ่านกล่องจดหมาย Gmail ด้วยเสียง (การ์ด 0071) · จับประโยคด้วยโค้ด (H6) · คำตอบประกอบจากแถวในหน้าจริง (H5).

แถวมาจาก control.INBOX_JS (หน้า Gmail ที่เปิดในเบราว์เซอร์ของผู้ช่วย) · เนื้อหาเมลไม่ส่งให้ AI หรือ Claude (H3) ·
ข้อความในเมลเป็นข้อมูลที่อ่านออกเสียงเท่านั้น ไม่ใช่คำสั่ง (H8)
"""

from __future__ import annotations

import re

from aipc.browser.textclick import norm

_MAIL = r"(?:อี\s*)?เมล์?"
_LEAD = r"^(?:(?:ช่วย|ขอ|ลอง|รบกวน)\s*)*"
_TAIL = (
    r"(?:\s*(?:ให้ฟัง|ให้หน่อย|หน่อย|ให้ที|ที|ครับ|ค่ะ|คะ|นะ|ด้วย|บ้าง|ไหม|มั้ย|หรือเปล่า|รึเปล่า|ป่าว"
    r"|มีอะไร|คืออะไร))*\s*$"
)
_UNREAD = re.compile(
    _LEAD + r"(?:(?:อ่าน|เช็[คก])\s*)?(?:มี\s*)?" + _MAIL
    + r"\s*(?:ใหม่|(?:ที่\s*)?ยังไม่(?:ได้)?อ่าน)" + _TAIL
)  # fmt: skip
_LATEST = re.compile(
    _LEAD + r"(?:อ่าน\s*" + _MAIL + r"(?:\s*(?:ล่าสุด|ทั้งหมด|ในกล่อง(?:จดหมาย)?))?|"
    + _MAIL + r"\s*ล่าสุด)" + _TAIL
)  # fmt: skip
_FROM = re.compile(
    _LEAD + r"(?:(?:อ่าน|มี)\s*)?" + _MAIL + r"\s*(?:ที่\s*)?(?:มา\s*)?จาก\s*(?P<who>.+?)" + _TAIL
)
MAX_READ = 3


def parse(text: str) -> tuple[str, str] | None:
    """(ชนิด, ชื่อผู้ส่ง) · ชนิด = latest | unread | from · ไม่ใช่เรื่องอ่านเมล = None."""
    t = (text or "").strip()
    if m := _FROM.match(t):
        return "from", m.group("who").strip()
    if _UNREAD.match(t):
        return "unread", ""
    if _LATEST.match(t):
        return "latest", ""
    return None


def _line(i: int, r: dict, mark_unread: bool) -> str:
    who = r.get("sender") or r.get("email") or "ไม่ทราบชื่อ"
    subject = r.get("subject") or "(ไม่มีหัวเรื่อง)"
    when = f" ({r['time']})" if r.get("time") else ""
    new = " · ยังไม่อ่าน" if mark_unread and r.get("unread") else ""
    return f"{i}. จาก {who} เรื่อง {subject}{when}{new}"


def answer(kind: str, who: str, rows: list[dict]) -> str:
    """ข้อความที่อ่านออกเสียง · บอกเสมอว่าอ่านจากหน้าแรกของกล่องจดหมาย (ไม่ใช่ทั้งกล่อง)."""
    if not rows:
        return "ไม่เห็นรายการเมลบนจอ · เปิดกล่องจดหมายของ Gmail ให้เห็นรายการก่อน แล้วพูดอีกครั้ง"
    where = "ในหน้าแรกของกล่องจดหมาย"
    if kind == "unread":
        pick = [r for r in rows if r.get("unread")]
        if not pick:
            return f"ไม่มีเมลที่ยังไม่อ่าน{where} · {len(rows)} ฉบับที่เห็นอ่านแล้วทั้งหมด"
        head = f"เมลยังไม่อ่าน {len(pick)} ฉบับ ({where})"
    elif kind == "from":
        w = norm(who)
        hit = lambda r: w in norm(r.get("sender", "")) or w in norm(r.get("email", ""))  # noqa: E731
        pick = [r for r in rows if w and hit(r)]
        if not pick:
            return f"ไม่เห็นเมลจาก “{who}” {where}"
        head = f"เมลจาก {who} {len(pick)} ฉบับ ({where})"
    else:
        pick = rows
        head = "เมลล่าสุด"
    lines = [_line(i, r, kind != "unread") for i, r in enumerate(pick[:MAX_READ], 1)]
    more = f" · และอีก {len(pick) - MAX_READ} ฉบับ" if len(pick) > MAX_READ else ""
    return f"{head}: " + " · ".join(lines) + more
