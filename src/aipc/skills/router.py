"""เลือกว่าข้อความนี้ควรใช้สกิลไหน (BRIEF 5.8 ข้อ 2 และ docs/SKILLS.md "การเลือกสกิล").

ลำดับ:
1. คำสั่งเครื่อง: ตัวแปลแบบกำหนดแน่นอนลองก่อน ถ้าตรงก็ใช้เลย ไม่ผ่าน LLM
2. นัดหมาย: ประโยคที่ไม่ใช่คำถาม และมีคำของสกิลนัดหมาย หรือบอกวัน/เวลาชัดเจน → สกิลนัดหมาย
   (สกิลนี้ถามยืนยันก่อนบันทึกเสมอ ถ้าเลือกผิดผู้ใช้กดยกเลิกได้)
   เพิ่ม 2026-09-28: เดิมประโยคนัด 40 ข้อถึงสกิลนัดหมายแค่ 13 ข้อ
   เพราะหลายประโยคไม่มีคำว่า "เตือน/นัด" และบางคำชนกับสกิลอื่น
3. สกิลอื่น: ให้คะแนนจากคำสำคัญของแต่ละสกิล แล้วคัดเหลือไม่เกิน 3 ตัว
   · เมื่อมี LLM แล้ว LLM จะเป็นผู้เลือกจาก 3 ตัวนี้ (หรือเลือก "ไม่ใช้สกิล")
   · ตอนนี้ยังไม่มี LLM จึงใช้ตัวที่คะแนนสูงสุด — เป็นขั้นคัดกรอง ไม่ใช่ตัวตัดสินสุดท้าย
4. ไม่ตรงสกิลใด = คุยกับ AI ตามปกติ

การเทียบคำสำคัญ: ภาษาไทยไม่มีช่องว่างระหว่างคำ จึงเทียบแบบ "มีอยู่ในประโยค"
แต่ไม่นับเมื่อหน้าคำมีสระ เ แ โ ใ ไ เพราะสระพวกนี้เป็นส่วนหน้าของพยางค์เดียวกัน
("ช้า" ใน "เช้า" คือคนละคำ) · คำภาษาอังกฤษต้องเป็นคำเต็ม ("ram" ≠ "program")

สกิลที่ต้องใช้สิ่งที่ระบบยังไม่มี (เช่น LLM หรือกล้อง) ถูกเลือกได้ แต่ผลบอกชัดว่ายังขาดอะไร
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from aipc.skills import command, when
from aipc.skills.manifest import Manifest

MAX_CANDIDATES = 3
LEADING_VOWELS = "เแโใไ"
# คำถามไม่ใช่การสั่งให้จดนัด ("พรุ่งนี้ประชุมกี่โมง") · ส่งต่อให้คะแนนคำสำคัญตามปกติ
QUESTION_WORDS = ("ไหม", "มั้ย", "หรือเปล่า", "หรือยัง", "อะไร", "ทำไม", "เท่าไร", "เท่าไหร่", "กี่",
                  "ยังไง", "อย่างไร", "ที่ไหน", "เมื่อไร", "เมื่อไหร่", "ใคร", "?")  # fmt: skip


@dataclass
class Route:
    kind: str  # command | skill | needs | chat
    skill: Manifest | None = None
    reason: str = ""
    command: command.Command | None = None
    missing: list[str] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)
    tied: list[str] = field(default_factory=list)  # สกิลที่คะแนนเท่ากับตัวที่ชนะ (≥ 2 ตัว = ต้องถามผู้ใช้)


def has_keyword(text: str, keyword: str) -> bool:
    """ประโยคมีคำสำคัญนี้เป็น "คำ" ไหม (ไม่ใช่แค่ตัวอักษรที่บังเอิญซ้อนอยู่ในคำอื่น)."""
    k = keyword.lower().replace(" ", "")
    if k.isascii():
        return re.search(rf"(?<![a-z]){re.escape(k)}(?![a-z])", text.lower()) is not None
    t = text.lower().replace(" ", "")
    start = 0
    while (i := t.find(k, start)) != -1:
        if i == 0 or t[i - 1] not in LEADING_VOWELS:
            return True
        start = i + 1
    return False


def score(text: str, m: Manifest) -> int:
    return sum(1 for k in m.keywords if has_keyword(text, k))


def is_question(text: str) -> bool:
    return any(w in text for w in QUESTION_WORDS)


def reminder_reason(text: str, m: Manifest) -> str:
    """เหตุผลที่ประโยคนี้เป็นนัดหมาย · "" = ไม่ใช่ (ลำดับข้อ 2 ในคำอธิบายด้านบน)."""
    if is_question(text):
        return ""
    hit = next((k for k in m.keywords if has_keyword(text, k)), None)
    if hit:
        return f"เพราะมีคำว่า “{hit}”"
    if when.mentions_time(text, part_of_day=False):
        return "เพราะประโยคบอกวันหรือเวลา"
    return ""


def command_route(text: str, by_id: dict[str, Manifest]) -> Route | None:
    """ข้อ 1: คำสั่งเครื่องที่ตัวแปลแบบกำหนดแน่นอนแปลได้ · None = ไม่ใช่คำสั่ง."""
    cmd = command.parse(text)
    if cmd and "system-command" in by_id:
        return Route("command", by_id["system-command"], f"ตรงกับคำสั่ง “{cmd.plan.summary}”", cmd)
    return None


def route_ai_first(text: str, manifests: list[Manifest]) -> Route:
    """แบบผสม (ผู้ใช้เลือก 2026-09-30) ใช้เมื่อ AI ในเครื่องพร้อม: คำสั่งเครื่อง (ข้อ 1) ทำเลย ·
    ที่เหลือ = Route("chat") ให้ AI เลือกจากรายการสกิลเอง ไม่ผ่านกฎให้คะแนนคำสำคัญ
    ผลวัด Pi 5 (docs/benchmarks/2026-09-29-skill-select-pi5 · Typhoon2.5 4B): แบบนี้ถูก 50/58
    เรียกสกิลผิด 0/18 · กฎก่อนถูก 41/58 ผิด 7/18 (ประโยคหลอก 6 ข้อกฎตัดสินผิดหมดก่อนถึง AI)
    spikes.skill_select --mode ai-first เรียกฟังก์ชันนี้ตัวเดียวกับแอป
    """
    return command_route(text, {m.id: m for m in manifests}) or Route("chat")


def route(text: str, manifests: list[Manifest], available: set[str]) -> Route:
    """กฎก่อน (ลำดับข้อ 1–4 ด้านบน) · แอปใช้ตอน AI ในเครื่องยังไม่พร้อม."""
    by_id = {m.id: m for m in manifests}

    if r := command_route(text, by_id):
        return r

    reminder = by_id.get("reminder")
    if reminder and (why := reminder_reason(text, reminder)):
        missing = [n for n in reminder.needs if n not in available]
        return Route("needs" if missing else "skill", reminder, why, missing=missing,
                     candidates=["reminder"])  # fmt: skip

    ranked = sorted(
        ((score(text, m), m) for m in manifests if m.id != "system-command"),
        key=lambda x: x[0],
        reverse=True,
    )
    ranked = [(s, m) for s, m in ranked if s > 0][:MAX_CANDIDATES]
    if not ranked:
        return Route("chat")

    best = ranked[0][1]
    # คะแนนเท่ากัน: เดิมตัวที่โหลดก่อนชนะเงียบ ๆ · ตอนนี้บอกหน้าจอให้ถามผู้ใช้ (ข้อเสนอ 2026-09-29 งานข้อ ④)
    tied = [m.id for s, m in ranked if s == ranked[0][0]]
    hits = [k for k in best.keywords if has_keyword(text, k)]
    reason = "เพราะมีคำว่า " + ", ".join(f"“{k}”" for k in hits[:2])
    missing = [n for n in best.needs if n not in available]
    kind = "needs" if missing else "skill"
    return Route(kind, best, reason, missing=missing, candidates=[m.id for _, m in ranked],
                 tied=tied if len(tied) > 1 else [])  # fmt: skip
