"""เลือกว่าข้อความนี้ควรใช้สกิลไหน (BRIEF 5.8 ข้อ 2 และ docs/SKILLS.md "การเลือกสกิล").

ลำดับ:
1. คำสั่งเครื่อง: ตัวแปลแบบกำหนดแน่นอนลองก่อน ถ้าตรงก็ใช้เลย ไม่ผ่าน LLM
2. สกิลอื่น: ให้คะแนนจากคำสำคัญของแต่ละสกิล แล้วคัดเหลือไม่เกิน 3 ตัว
   · เมื่อมี LLM แล้ว LLM จะเป็นผู้เลือกจาก 3 ตัวนี้ (หรือเลือก "ไม่ใช้สกิล")
   · ตอนนี้ยังไม่มี LLM จึงใช้ตัวที่คะแนนสูงสุด — เป็นขั้นคัดกรอง ไม่ใช่ตัวตัดสินสุดท้าย
3. ไม่ตรงสกิลใด = คุยกับ AI ตามปกติ

สกิลที่ต้องใช้สิ่งที่ระบบยังไม่มี (เช่น LLM หรือกล้อง) ถูกเลือกได้ แต่ผลบอกชัดว่ายังขาดอะไร
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aipc.skills import command
from aipc.skills.manifest import Manifest

MAX_CANDIDATES = 3


@dataclass
class Route:
    kind: str  # command | skill | needs | chat
    skill: Manifest | None = None
    reason: str = ""
    command: command.Command | None = None
    missing: list[str] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)


def score(text: str, m: Manifest) -> int:
    t = text.lower().replace(" ", "")
    return sum(1 for k in m.keywords if k.lower().replace(" ", "") in t)


def route(text: str, manifests: list[Manifest], available: set[str]) -> Route:
    by_id = {m.id: m for m in manifests}

    cmd = command.parse(text)
    if cmd and "system-command" in by_id:
        return Route("command", by_id["system-command"], f"ตรงกับคำสั่ง “{cmd.plan.summary}”", cmd)

    ranked = sorted(
        ((score(text, m), m) for m in manifests if m.id != "system-command"),
        key=lambda x: x[0],
        reverse=True,
    )
    ranked = [(s, m) for s, m in ranked if s > 0][:MAX_CANDIDATES]
    if not ranked:
        return Route("chat")

    best = ranked[0][1]
    hits = [k for k in best.keywords if k.lower().replace(" ", "") in text.lower().replace(" ", "")]
    reason = "เพราะมีคำว่า " + ", ".join(f"“{k}”" for k in hits[:2])
    missing = [n for n in best.needs if n not in available]
    kind = "needs" if missing else "skill"
    return Route(kind, best, reason, missing=missing, candidates=[m.id for _, m in ranked])
