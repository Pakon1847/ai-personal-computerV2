"""วงจรเรียนรู้สกิล (การ์ด 0083): ครั้งแรก AI ในเครื่องให้ Claude สร้างสกิล · ครั้งที่สองเครื่องทำเองโดยไม่เรียก Claude.

ขับแอปตัวจริงด้วย AppDriver (การ์ด 0022) · ทางเดียวกับหน้าจอ · ชุดข้อมูลเป็นข้อความธรรมดาให้ Pakon กรอกได้:

    ข้อ 1
    คำสั่ง: <ประโยคที่พิมพ์สั่งเครื่อง>
    ผลที่ถูก: <เครื่องควรทำอะไร>

บรรทัดที่ขึ้นต้นด้วย # = คำอธิบาย ไม่อ่าน · ชุดทดสอบของ Pakon ตัววัดอ่านเอง ผู้ช่วยไม่เปิด (H9)
"""

from __future__ import annotations

import re

_ITEM = re.compile(r"^ข้อ\s*(\d+)\s*$")
_FIELD = re.compile(r"^(คำสั่ง|ผลที่ถูก)\s*:\s*(.*)$")
_KEYS = {"คำสั่ง": "text", "ผลที่ถูก": "expect"}


def parse_items(text: str) -> list[dict]:
    """ข้อความชุดข้อมูล → [{id, text, expect}].

    ข้อที่กรอกไม่ครบ = ValueError บอกเลขข้อ · ว่างทั้งไฟล์ = ValueError "ยังไม่ได้กรอก".
    """
    blocks: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if m := _ITEM.match(line):
            blocks.append({"id": m.group(1), "text": "", "expect": ""})
        elif (m := _FIELD.match(line)) and blocks:
            blocks[-1][_KEYS[m.group(1)]] = m.group(2).strip()
        else:
            raise ValueError(f"อ่านบรรทัดนี้ไม่ได้: {line!r} (ต้องเป็น ข้อ N / คำสั่ง: / ผลที่ถูก:)")
    if not any(b["text"] or b["expect"] for b in blocks):
        raise ValueError("ชุดข้อมูลยังไม่ได้กรอก (ไม่มีข้อที่มีคำสั่ง)")
    for b in blocks:  # กรอกแล้วบางข้อ = ทุกข้อต้องครบ (ไม่ข้ามข้อว่างเงียบ ๆ)
        for key, name in (("text", "คำสั่ง"), ("expect", "ผลที่ถูก")):
            if not b[key]:
                raise ValueError(f"ข้อ {b['id']}: ยังไม่ได้กรอก “{name}”")
    return blocks
