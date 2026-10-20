"""Claude สอน AI ในเครื่อง (การ์ด 0047): คำถามที่ส่ง Claude แล้ว → ความรู้เป็นสกิลในเครื่อง ·
ครั้งหน้าตอบเองไม่ใช้เน็ต.

ส่วนที่เป็นโค้ด (H6) ไม่ใช่ AI:
- เรื่องที่เปลี่ยนตามเวลา (ราคา ข่าว อากาศ ผลกีฬา …) ห้ามจำ → is_volatile
- คำถามนี้เคยถาม Claude แล้วไหม → repeat_of (ป้ายหัวข้อที่ Claude ติดมากับคำตอบ + ความคล้ายของตัวอักษร)
- ป้ายหัวข้อ: บรรทัดท้ายคำตอบของ Claude "หัวข้อ: dog-bite-first-aid" → split_topic ตัดออกก่อนแสดง
  (Claude ติดมากับคำตอบที่ส่งอยู่แล้ว · ไม่ส่งคำถามเก่าออกไปเทียบ)
"""

from __future__ import annotations

import re

KIND = "knowledge"
MAX_KNOWLEDGE = 800  # ตัวอักษรของคำสั่งให้ AI ในสกิลความรู้ (การ์ดหัวข้อ 2) · Pi อ่าน prompt ~22 token/วิ
# ข้อมูลสด = หมวดในคำอธิบาย ask-cloud (catalog.py: ข่าว ราคา อากาศ ผลกีฬา อัตราแลกเปลี่ยน เหตุการณ์ปัจจุบัน) ·
# "เหตุการณ์ปัจจุบัน" = คำบอกเวลาสัมพัทธ์ (คำตอบเปลี่ยนตามวัน) · ไม่ได้เพิ่มคำจากชุดทดสอบ
VOLATILE = re.compile(
    r"ข่าว|ราคา|อากาศ|ฝนตก|พยากรณ์|ผลบอล|ผลการแข่ง|ใครชนะ|อัตราแลกเปลี่ยน|ค่าเงิน|"
    r"วันนี้|เมื่อวาน|เมื่อคืน|พรุ่งนี้|ตอนนี้|ล่าสุด|สัปดาห์นี้|เดือนนี้|ปีนี้"
)
# คำถาม/คำเชื่อมที่เหมือนกันได้แม้คนละเรื่อง ("…ต้องทำอะไรทันที") · ตัดออกก่อนเทียบ (ตั้งจากชุดพัฒนา)
_STOP = re.compile(
    r"อะไร|ยังไง|อย่างไร|ไหม|มั้ย|เท่าไหร่|เท่าไร|กี่|ได้|บ้าง|ทำไม|คือ|หรือเปล่า|จริง|ต้อง|ทำ|ให้|ที่|"
    r"ของ|แล้ว|เป็น|เพราะ|วิธี|การ|ครั้งแรก"
)
# ความคล้ายขั้นต่ำ (0–1) · ตั้งจากชุดพัฒนา tests/data/teach_pairs.json "dev": เรื่องเดียวกัน 8/10 · ต่างเรื่อง 0/10
SIM_MIN = 0.52
_TOPIC = re.compile(r"\n*[ \t]*\[?หัวข้อ\s*[:：]\s*([A-Za-z0-9][A-Za-z0-9 _-]{1,60})\]?[ \t]*\s*$")
TOPIC_HINT = (
    "บรรทัดสุดท้ายของคำตอบเขียน “หัวข้อ: <ป้าย>” โดยป้ายเป็นคำภาษาอังกฤษตัวเล็ก 2–5 คำคั่นด้วยขีด "
    "บอกเรื่องที่ถาม (เช่น หัวข้อ: dog-bite-first-aid) · คำถามเรื่องเดียวกันใช้ป้ายเดียวกัน"
)


HEAD = "[ความรู้ที่ Claude สอนไว้"  # หัวที่ระบบเติมหน้าคำสั่งให้ AI ของสกิลความรู้ (mdskill)


def header(learned: str) -> str:
    """หัวคงที่ของสกิลความรู้ (ระบบเขียน ไม่ใช่ Claude) · บอกที่มา + บังคับให้ตอบเฉพาะเรื่องนี้."""
    when = f" เมื่อ {learned}" if learned else ""
    return (f"{HEAD}{when}] ตอบจากความรู้ข้างล่างนี้เท่านั้น ภาษาไทย สั้น ชัด · "
            "ถ้าคำถามไม่ใช่เรื่องนี้หรือความรู้ไม่พอ ให้ตอบว่าไม่รู้ ห้ามเดา\n")  # fmt: skip


def learned_of(prompt: str) -> str | None:
    """prompt ของสกิลความรู้ → วันที่ที่สอน ("" = ไม่ระบุ) · ไม่ใช่สกิลความรู้ = None."""
    if not prompt.startswith(HEAD):
        return None
    m = re.match(re.escape(HEAD) + r"(?: เมื่อ ([^\]]+))?\]", prompt)
    return (m.group(1) or "") if m else ""


def is_volatile(text: str) -> bool:
    return bool(VOLATILE.search(text))


def split_topic(answer: str) -> tuple[str, str]:
    """คำตอบของ Claude → (คำตอบที่ตัดป้ายแล้ว, ป้าย) · ไม่มีป้าย = (เดิม, "")."""
    m = _TOPIC.search(answer)
    if not m:
        return answer, ""
    key = re.sub(r"[\s_]+", "-", m.group(1).strip().lower()).strip("-")
    return answer[: m.start()].rstrip(), key


def _norm(text: str) -> str:
    from aipc.skills import command

    t = _STOP.sub(" ", command.normalize(text).lower())
    return re.sub(r"\s+", "", t)


def _grams(t: str, n: int = 3) -> set[str]:
    return {t[i : i + n] for i in range(max(1, len(t) - n + 1))}


def similarity(a: str, b: str) -> float:
    """ส่วนที่ซ้ำกันของชิ้น 3 ตัวอักษร (หลังตัดคำถาม/คำเชื่อม) เทียบกับประโยคที่สั้นกว่า · 0–1."""
    ga, gb = _grams(_norm(a)), _grams(_norm(b))
    return len(ga & gb) / max(1, min(len(ga), len(gb)))


def same_topic(a: str, b: str) -> bool:
    """ป้ายหัวข้อสองอันเรื่องเดียวกันไหม: คำตรงกัน ≥ 2 คำ และ ≥ ครึ่งหนึ่งของป้ายที่สั้นกว่า
    (dog-bite ~ dog-bite-first-aid · cpr-adult ≠ cpr-infant)."""
    wa, wb = set(filter(None, a.split("-"))), set(filter(None, b.split("-")))
    return bool(wa and wb) and len(wa & wb) * 2 >= min(len(wa), len(wb)) and len(wa & wb) >= 2


def repeat_of(question: str, topic: str, earlier: list[tuple[str, str]]) -> str:
    """คำถามที่เคยถาม Claude แล้วเป็นเรื่องเดียวกัน (คืนคำถามเก่า) · ไม่ซ้ำ = "" · earlier = [(คำถาม, ป้าย)]."""
    for q, t in reversed(earlier):
        if (topic and t and same_topic(topic, t)) or similarity(question, q) >= SIM_MIN:
            return q
    return ""


def question_of(sent: str) -> str:
    """ข้อความที่ส่ง Claude (ask.build_input) → คำถาม (ตัดบริบทก่อนหน้าออก)."""
    return sent.rsplit("คำถาม:\n", 1)[-1].strip()


def request(question: str, answer: str, today: str) -> str:
    """คำขอให้ forge เขียนสกิลความรู้ · ส่งเฉพาะคำถาม + คำตอบที่ Claude ตอบไปแล้ว (ไม่มีข้อมูลผู้ใช้ใหม่)."""
    return (
        "สร้าง “สกิลความรู้” ให้ AI ในเครื่อง (โมเดลเล็ก ไม่มีเน็ต) ตอบเรื่องนี้เองครั้งหน้า · "
        f"คำถามของผู้ใช้: “{' '.join(question.split())[:300]}” · "
        f"คำตอบที่คุณตอบไว้เมื่อ {today}: “{' '.join(answer.split())[:1500]}” · "
        "ถ้าคำตอบเรื่องนี้เปลี่ยนตามเวลา (ราคา ข่าว อากาศ ผลกีฬา ตาราง สิ่งที่อัปเดตบ่อย) "
        'ห้ามสร้างสกิล ให้ตอบ JSON {"volatile": true, "note": "<เหตุผลสั้น ๆ>"} แทน'
    )
