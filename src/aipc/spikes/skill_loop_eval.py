"""วงจรเรียนรู้สกิล (การ์ด 0083): ครั้งแรก AI ในเครื่องให้ Claude สร้างสกิล · ครั้งที่สองเครื่องทำเองโดยไม่เรียก Claude.

ขับแอปตัวจริงด้วย AppDriver (การ์ด 0022) · ทางเดียวกับหน้าจอ · ชุดข้อมูลเป็นข้อความธรรมดาให้ Pakon กรอกได้:

    ข้อ 1
    คำสั่ง: <ประโยคที่พิมพ์สั่งเครื่อง>
    ผลที่ถูก: <เครื่องควรทำอะไร>

บรรทัดที่ขึ้นต้นด้วย # = คำอธิบาย ไม่อ่าน · ชุดทดสอบของ Pakon ตัววัดอ่านเอง ผู้ช่วยไม่เปิด (H9)
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict

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


def recording_forge(forge: Callable) -> tuple[Callable, list[dict]]:
    """ห่อตัวสร้างสกิล: เก็บผลของ Claude ทุกครั้ง (ไฟล์สกิล · ผลทดลองเส้นทาง · ข้อผิดพลาด) แม้ติดตั้งไม่ได้.

    บทเรียน 2026-10-08: ตัววัดเดิมไม่เก็บ trial และไฟล์สกิลเมื่อไม่ผ่าน → หาสาเหตุไม่ได้ (เกณฑ์ L5)
    """
    records: list[dict] = []

    def run(request, **kw):
        p = forge(request, **kw)
        records.append(asdict(p))
        return p

    return run, records


def unconfirmed(turn, user_ids: set[str]) -> int:
    """คำสั่งเครื่องที่ทำในเทิร์นของสกิลผู้ใช้ (หรือตอนสร้าง) โดยไม่มีการ์ดยืนยันในเทิร์นนั้น (เกณฑ์ L4)."""
    route = turn.route
    by_user = route == "create" or (route.startswith("skill:") and route[6:] in user_ids)
    if not by_user or not turn.plans:
        return 0
    return 0 if any(c.get("confirmToken") for c in turn.cards) else len(turn.plans)


def run_item(drv, store, ledger, records: list[dict], item: dict) -> dict:
    """หนึ่งข้อ: ครั้งแรก (AI ในเครื่องให้ Claude สร้างไหม · ติดตั้งได้ไหม) → ติดตั้งได้ = ครั้งที่สอง (ledger ต้องไม่เพิ่ม).

    drv = AppDriver (หรือตัวปลอมที่มี say(text) → Turn) · store = UserSkills · ledger = Ledger ·
    records = รายการจาก recording_forge (ส่วนที่เพิ่มระหว่างข้อนี้ = ของข้อนี้)
    """
    before = {s.id for s in store.load_all()}
    n_rec, n_led = len(records), len(ledger.entries())
    first = drv.say(item["text"])
    skills = store.load_all()
    new = [s for s in skills if s.id not in before]
    sid = new[0].id if new else ""
    user_ids = {s.id for s in skills}
    forging = any(c.get("kind") == "forging" for c in first.cards)
    row = {
        "id": item["id"], "text": item["text"], "expect": item["expect"],
        "asked_create": first.route == "create" or forging,
        "installed": bool(sid), "skill_id": sid, "skill_md": store.current_md(sid) if sid else "",
        "forge": records[n_rec:], "first_route": first.route, "first_plans": first.plans,
        "first_text": first.text, "first_seconds": first.seconds,
        "first_ledger_added": len(ledger.entries()) - n_led,
        "unconfirmed": unconfirmed(first, user_ids),
    }  # fmt: skip
    if sid:
        n2 = len(ledger.entries())
        again = drv.say(item["text"])
        by_name = again.route.endswith(":" + new[0].name)
        row.update({
            "again_route": again.route, "again_plans": again.plans, "again_text": again.text,
            "again_seconds": again.seconds, "again_ledger_added": len(ledger.entries()) - n2,
            # ทางแชท: AI เลือกสกิล = skill:<id> · กฎเลือกสกิลจากชื่อ = rule:<ชนิด>:<ชื่อสกิล> (แบบการ์ด 0022)
            "again_new_skill": again.route == f"skill:{sid}" or by_name,
        })  # fmt: skip
        row["unconfirmed"] += unconfirmed(again, user_ids)
    return row
