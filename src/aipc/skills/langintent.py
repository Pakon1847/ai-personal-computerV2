"""กฎแน่นอนก่อนถึง AI: คำขอแปล/สรุปที่ชัดเจน (Pakon เลือกข้อ ก. 2026-10-01).

ที่มา: Gemma 4 E2B ไม่เรียกสกิลแปลเลย (ชุดปรับ 0/8 ทุกแบบที่ลองปรับคำอธิบาย ·
docs/benchmarks/2026-10-01-skill-desc)
→ จับเฉพาะรูปที่ชัด ส่วนที่เหลือยังให้ AI ตัดสินเหมือนเดิม
ชุดอิสระ tests/data/lang_rule_heldout2.json (Claude เขียน · commit ก่อนเขียนกฎ) ·
ผล docs/benchmarks/2026-10-01-lang-rule

หลัก: แยก "หัว" (คำสั่ง) กับ "เนื้อ" (ข้อความที่วางมาหลัง ":") ·
มีเนื้อยาว → ดูคำสั่งในหัว · ไม่มีเนื้อ → ต้องขึ้นต้นด้วยคำสั่งแปล
หรือมีข้อความภาษาอังกฤษ/ในเครื่องหมายคำพูดพร้อมคำถามความหมาย
"""

from __future__ import annotations

import re

PAYLOAD_MIN = 25  # เนื้อหลัง ":" สั้นกว่านี้ไม่นับเป็นข้อความที่วางมา
SUMMARY_LEN_MIN = 80  # ไม่มี ":" แต่ขึ้นต้นด้วย "สรุป/ย่อ" และยาวพอ = วางข้อความต่อท้าย

TRANSLATE = r"แปล(?![กง])|translat"
TR_HEAD = re.compile(
    rf"{TRANSLATE}|เป็น\s*(ภาษา)?\s*(อังกฤษ|ไทย)|(ภาษา)?อังกฤษ\s*(พูด|เขียน)?\s*ว่า", re.I
)
SUM_HEAD = re.compile(
    r"สรุป(?!แล้ว|ว่า)|ย่อ(?!มาจาก|หน้า|ย)|ใจความ|ประเด็น|tl;?dr|summar|พูดถึง(เรื่อง)?อะไร|"
    r"ว่าด้วย(เรื่อง)?อะไร|บอกอะไร|สั้นลง|สั้น\s*ๆ|ต้องทำอะไร",
    re.I,
)
# ไม่มีเนื้อ: คำสั่งแปลขึ้นต้นประโยค
TR_START = re.compile(
    rf"^(ช่วย|ขอ|รบกวน|อยากให้)?\s*({TRANSLATE})|^(please\s+|can you\s+)?translate", re.I
)
# ข้อความภาษาอังกฤษหรือในเครื่องหมายคำพูด + ถามความหมาย / ถามว่าพูดเป็นอีกภาษาว่าอะไร
QUOTED = re.compile(r"[A-Za-z]{2,}|['\"‘“][^'\"’”]{2,}['\"’”]")
# "translat" ภาษาอังกฤษไม่นับตรงนี้ ("Google Translate แม่นไหม" ไม่ใช่คำขอแปล)
# คำสั่ง translate อยู่ใน TR_START
# "หมายถึงอะไร" ไม่นับ: ตัวย่อ/ศัพท์ ("RPG หมายถึงอะไร") เป็นคำถามความรู้ ไม่ใช่งานแปล
MEANING = re.compile(
    r"แปล(?![กง])|ภาษาไทย(ว่า|คือ|เรียกว่า)|\bmean\b|ไทย\s*(จะ)?\s*(พูด|เรียก)\s*ว่า|"
    r"(ภาษา)?(อังกฤษ|ไทย)\s*(พูด|เขียน|เรียก)?\s*ว่า\s*(อะไร|ยังไง|ไง|อย่างไร)|"
    r"เป็น\s*(ภาษา)?\s*(อังกฤษ|ไทย)\s*(แบบ\S+\s*)?(ว่า)?\s*(อะไร|ยังไง|ไง|อย่างไร)",
    re.I,
)
# รูปถามว่าพูดเป็นอีกภาษาว่าอะไร ชัดพอโดยไม่ต้องมีเครื่องหมายคำพูด
ASK_HOW = re.compile(
    r"(พูด|เขียน)\s*เป็น\s*(ภาษา)?\s*(อังกฤษ|ไทย)\s*(แบบ\S+\s*)?ว่า\s*(อะไร|ยังไง|ไง|อย่างไร)|"
    r"(ภาษา)?อังกฤษ\s*(พูด|เขียน|เรียก)\s*ว่า\s*(อะไร|ยังไง|ไง|อย่างไร)"
)
SUM_START = re.compile(r"^(ช่วย|ขอ|รบกวน)?\s*(สรุป(?!แล้ว|ว่า)|ย่อ(?!มาจาก|หน้า)|summar|tl;?dr)", re.I)
BARE = re.compile(r"(ช่วย|ขอ|รบกวน)?\s*(แปล|สรุป|ย่อ)\s*(ให้)?\s*(หน่อย|ที)?\s*(ครับ|ค่ะ|คะ|นะ)?\s*")


def split(text: str) -> tuple[str, str]:
    """หัวคำสั่ง, เนื้อที่วางมาหลัง ":" ตัวแรก (ไม่มี = เนื้อว่าง)."""
    m = re.search(r"[:：]", text)
    if not m:
        return text, ""
    return text[: m.start()], text[m.end() :].strip()


def lang_intent(text: str) -> str | None:
    """ "translate" / "summarize" / None (ให้ AI ตัดสินตามเดิม)."""
    t = text.strip()
    if BARE.fullmatch(t):  # "แปล" เฉย ๆ ไม่มีอะไรให้แปล → ให้ AI ถามกลับ
        return None
    head, body = split(t)
    if len(body) >= PAYLOAD_MIN:
        if TR_HEAD.search(head):
            return "translate"
        if SUM_HEAD.search(head):
            return "summarize"
        return None
    if TR_START.search(t):
        return "translate"
    if ASK_HOW.search(t) or (QUOTED.search(t) and MEANING.search(t)):
        return "translate"
    if SUM_START.search(t) and len(t) >= SUMMARY_LEN_MIN:
        return "summarize"
    return None
