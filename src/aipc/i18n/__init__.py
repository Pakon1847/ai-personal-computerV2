"""แปลข้อความที่ผู้ใช้เห็นเป็นภาษาอังกฤษ (การ์ด 0039 ระยะ A).

วิธี: ตาราง en.json = {ข้อความไทยต้นฉบับ: คำแปลอังกฤษ} · ข้อความไทยเป็นกุญแจ จึงอ่านโค้ดแล้วรู้ทันทีว่าหน้าจอแสดงอะไร
และไม่ต้องตั้งชื่อกุญแจเพิ่ม · ภาษาไทย หรือยังไม่มีคำแปล = คืนข้อความไทยเดิม (ไม่มีช่องว่างโผล่ · H5)
ข้อความที่มีค่าแทรก ใช้รูปแบบ {ชื่อ} แล้วแทนค่าหลังแปล: tr("อีก {n} วัน", n=3)
QML ใช้ตารางเดียวกันผ่าน Tr.qml (ค่า Tr.table มาจาก table())
"""

from __future__ import annotations

import json
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


def tr(text: str, **values) -> str:
    """ข้อความในภาษาปัจจุบัน · ค่าแทรก {ชื่อ} แทนหลังแปล (ลำดับคำในประโยคอังกฤษต่างจากไทยได้)."""
    out = table().get(text, text) if _lang == "en" else text
    return out.format(**values) if values else out
