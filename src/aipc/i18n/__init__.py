"""แปลข้อความที่ผู้ใช้เห็นเป็นภาษาอังกฤษ (การ์ด 0039 ระยะ A).

วิธี: ตาราง en.json = {ข้อความไทยต้นฉบับ: คำแปลอังกฤษ} · ข้อความไทยเป็นกุญแจ จึงอ่านโค้ดแล้วรู้ทันทีว่าหน้าจอแสดงอะไร
และไม่ต้องตั้งชื่อกุญแจเพิ่ม · ภาษาไทย หรือยังไม่มีคำแปล = คืนข้อความไทยเดิม (ไม่มีช่องว่างโผล่ · H5)
ข้อความที่มีค่าแทรก ใช้รูปแบบ {ชื่อ} แล้วแทนค่าหลังแปล: tr("อีก {n} วัน", n=3)
QML ใช้ตารางเดียวกันผ่าน Tr.qml (ค่า Tr.table มาจาก table())
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path

LANGS = ("th", "en")
_lang = "th"


@cache
def table() -> dict[str, str]:
    try:
        data = json.loads((Path(__file__).with_name("en.json")).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str) and v}


def set_lang(lang: str) -> None:
    global _lang
    _lang = lang if lang in LANGS else "th"


def lang() -> str:
    return _lang


def tr(text: str, ctx: str = "", **values) -> str:
    """ข้อความในภาษาปัจจุบัน · ค่าแทรก {ชื่อ} แทนหลังแปล (ลำดับคำในประโยคอังกฤษต่างจากไทยได้) ·
    ctx = คำเดียวกันแต่ความหมายต่างกัน → กุญแจ "ข้อความ#บริบท" (เหมือน Tr.t ใน QML)."""
    out = table().get(f"{text}#{ctx}" if ctx else text, text) if _lang == "en" else text
    return out.format(**values) if values else out


# ---------- ข้อความที่สร้างตอนทำงาน (การ์ดคำตอบ · การเตือน) ----------
# ข้อความในการ์ดประกอบจาก f-string ("อีก 3 วันถึงวันปิยมหาราช") จึงหาแบบตรงตัวไม่เจอ →
# กุญแจในตารางเขียนเป็นแม่แบบ "อีก {0} วันถึง{1}" แล้วแปลงเป็นรูปแบบจับข้อความ · ค่าที่จับได้แปลซ้ำ (ชื่อวันหยุด) ·
# ข้อมูลของผู้ใช้ (ชื่อนัด ชื่อไฟล์) ไม่มีในตาราง = คงเดิม · แปลตอนแสดง (QML: Tr.x) ไม่แก้ข้อมูลที่เก็บ
THAI = re.compile(r"[฀-๿]")  # ตัวอักษรไทย
_SLOT = re.compile(r"\{(\w+)\}")


@cache
def _templates() -> list[tuple[re.Pattern, str, list[str]]]:
    out = []
    for key, en in table().items():
        if not _SLOT.search(key):
            continue
        names, parts = [], []
        for piece in re.split(r"(\{\w+\})", key):
            m = _SLOT.fullmatch(piece)
            if m:
                names.append(m.group(1))
                parts.append(f"(?P<g{len(names) - 1}>.+?)")
            else:
                parts.append(re.escape(piece))
        literal = len(_SLOT.sub("", key))
        out.append((literal, re.compile("".join(parts), re.S), en, names))
    out.sort(key=lambda x: -x[0])  # แม่แบบที่มีข้อความตายตัวยาวกว่า = เจาะจงกว่า ลองก่อน
    return [(rx, en, names) for _, rx, en, names in out]


def tr_text(text: str, depth: int = 0) -> str:
    """แปลข้อความที่สร้างตอนทำงานเป็นอังกฤษ: ตรงตัว → แม่แบบ → แยกตาม " · " · ไม่เจอ = คงเดิม."""
    if not text or not THAI.search(text) or depth > 3:
        return text
    exact = table().get(text)
    if exact:
        return exact
    for rx, en, names in _templates():
        m = rx.fullmatch(text)
        if m:
            vals = {n: tr_text(m.group(f"g{i}"), depth + 1) for i, n in enumerate(names)}
            return _SLOT.sub(lambda s, v=vals: v.get(s.group(1), s.group(0)), en)
    for sep in (" · ", ", "):  # รายการต่อกัน ("ไฟเลี้ยง, อุณหภูมิ, พัดลม") แปลทีละชิ้น
        if sep in text:
            parts = text.split(sep)
            done = [tr_text(p, depth + 1) for p in parts]
            if done != parts:
                return sep.join(done)
    return text
