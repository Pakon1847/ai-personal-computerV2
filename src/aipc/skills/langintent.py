"""กฎแน่นอนก่อนถึง AI: คำขอแปล/สรุปที่ชัดเจน (Pakon เลือกข้อ ก. 2026-10-01).

ที่มา: Gemma 4 E2B ไม่เรียกสกิลแปลเลย (ชุดปรับ 0/8 ทุกแบบที่ลองปรับคำอธิบาย ·
docs/benchmarks/2026-10-01-skill-desc) → จับเฉพาะรูปที่ชัด ส่วนที่เหลือยังให้ AI ตัดสินเหมือนเดิม
ผลชุดอิสระทุกรอบ: docs/benchmarks/2026-10-01-lang-rule

หลัก: แยก "หัว" (คำสั่ง) กับ "เนื้อ" (ข้อความที่วางมาหลัง ":" หรือขึ้นบรรทัดใหม่)
- มีเนื้อ → ดูคำสั่งในหัว
- ไม่มีเนื้อ → แปล: ขึ้นต้นด้วยคำสั่งแปล หรือมีข้อความภาษาอังกฤษ/ในเครื่องหมายคำพูดพร้อมถามความหมาย ·
  สรุป: ข้อความยาวที่ช่วงต้นมีทั้งคำสั่งสรุปและคำที่ชี้ข้อความที่วาง (ข่าว อีเมล ประกาศ …)
รอบ 2 (ชุดอิสระรอบ 2 พลาด): วางข้อความขึ้นบรรทัดใหม่ไม่ใช้ ":" · "แปลผล" / "Google Translate" /
"ยังเป็นภาษาไทยอยู่" ไม่ใช่คำขอแปล · "ภาษาอังกฤษใช้คำว่าอะไร" / "ต้องพูดว่าไง" เป็นคำขอแปล
"""

from __future__ import annotations

import re

PAYLOAD_MIN = 25  # เนื้อสั้นกว่านี้ไม่นับเป็นข้อความที่วางมา
SUMMARY_LEN_MIN = 80  # ไม่มีตัวแบ่ง แต่ยาวพอ = วางข้อความต่อท้ายคำสั่ง
LEAD = 60  # ช่วงต้นของข้อความยาวที่ใช้หาคำสั่ง (เนื้อข่าวข้างหลังอาจมีคำว่า "สรุป" เอง)

# "แปลก" "แปลง" "แปลผล" ไม่ใช่การแปลภาษา · "นักแปล" คืออาชีพ
VERB = r"(?<!นัก)แปล(?![กงผ])"
BRANDS = re.compile(r"google\s*translate|กูเกิล\s*แปลภาษา|กูเกิลทรานสเลท", re.I)
ASKQ = r"(อะไร|ยังไง|ไง|อย่างไร)"
TR_HEAD = re.compile(rf"{VERB}|translat|เป็น\s*(ภาษา)?\s*อังกฤษ|in english|into english", re.I)
TO_THAI = re.compile(r"(เป็น|ให้เป็น)\s*(ภาษา)?\s*ไทย")
SUM_STRONG = re.compile(r"สรุป(?!แล้ว|ว่า)|ย่อ(?!มาจาก|หน้า|ย)|ใจความ|ประเด็น|tl;?dr|summar", re.I)
# คำอ่อน: นับเมื่อหัวไม่ได้สั่งให้เขียน/แก้งานใหม่ ("เขียนแคปชันสั้น ๆ: …" ไม่ใช่สรุป)
SUM_WEAK = re.compile(
    r"กลั่น|(พูดถึง|เกี่ยวกับ|ว่าด้วย)(เรื่อง)?อะไร|บอกอะไร|สั้นลง|สั้น\s*ๆ|"
    r"(ต้อง|ให้|อยากให้)\s*(เรา|ฉัน|ผม|หนู)?\s*ทำอะไร"
)
CREATE = re.compile(r"เขียน|แต่ง|ร่าง|ตอบกลับ|ตอบ(อีเมล|เมล|ข้อความ)|แก้|ตรวจ|ตั้งชื่อ|ปรับ|เรียบเรียง")


def summary_cue(head: str) -> bool:
    return bool(SUM_STRONG.search(head) or (SUM_WEAK.search(head) and not CREATE.search(head)))


# คำที่ชี้ว่ามีข้อความวางมา (ใช้กับข้อความยาวที่ไม่มีตัวแบ่ง)
PASTED = re.compile(r"ข่าว|ข้อความ|อีเมล|เมล|ประกาศ|บทความ|เนื้อหา|แชท|โพสต์|จดหมาย|ต่อไปนี้|ข้างล่าง")
# "แปลว่า…" ขึ้นต้นประโยคในภาษาพูด = "หมายความว่า" ไม่ใช่คำสั่ง (ถ้ามีคำอังกฤษจะเข้า QUOTED+MEANING เอง)
TR_START = re.compile(
    rf"^(ช่วย|ขอ|รบกวน|อยากให้)?\s*{VERB}(?!ว่า)|^(please\s+|can you\s+)?translate", re.I
)
QUOTED = re.compile(r"[A-Za-z]{2,}|['\"‘“][^'\"’”]{2,}['\"’”]")
MEANING = re.compile(
    rf"{VERB}|ภาษาไทย(ว่า|คือ|เรียกว่า)|\bmean\b|ไทย\s*(จะ)?\s*(พูด|เรียก)\s*ว่า|"
    rf"(ภาษา)?(อังกฤษ|ไทย)\s*(พูด|เขียน|เรียก)?\s*ว่า\s*{ASKQ}|"
    rf"เป็น\s*(ภาษา)?\s*(อังกฤษ|ไทย)\s*(แบบ\S+\s*)?(ว่า)?\s*{ASKQ}",
    re.I,
)
# ถามว่าพูดเป็นภาษาอังกฤษว่าอะไร ชัดพอโดยไม่ต้องมีเครื่องหมายคำพูด
ASK_HOW = re.compile(
    rf"(ภาษา)?อังกฤษ.{{0,15}}?(พูด|เขียน|เรียก|ใช้คำ)\s*ว่า\s*{ASKQ}|"
    rf"(พูด|เขียน)\s*เป็น\s*(ภาษา)?\s*(อังกฤษ|ไทย)\s*(แบบ\S+\s*)?ว่า\s*{ASKQ}"
)
# ข้อความยาวไม่มีตัวแบ่ง: "สรุป/ย่อ" ต้องตามด้วยคำขอ (ให้ หน่อย ที) หรือคำที่ชี้ข้อความที่วาง
# ("สรุปสูตรพื้นที่วงกลมให้หน่อย …" = ถามความรู้ ไม่ใช่สรุปข้อความ)
SUM_START = re.compile(
    r"^(ช่วย|ขอ|รบกวน)?\s*(สรุป(?!แล้ว|ว่า)|ย่อ(?!มาจาก|หน้า))(ความ)?\s*"
    r"(ให้|หน่อย|ที|เป็นข้อ|สั้น|ข่าว|ข้อความ|อีเมล|เมล|ประกาศ|บทความ|เนื้อหา|แชท|โพสต์|จดหมาย|เรื่องนี้|นี้)"
    r"|^(summar|tl;?dr)",
    re.I,
)
BARE = re.compile(r"(ช่วย|ขอ|รบกวน)?\s*(แปล|สรุป|ย่อ)\s*(ให้)?\s*(หน่อย|ที)?\s*(ครับ|ค่ะ|คะ|นะ)?\s*")


def split(text: str) -> tuple[str, str]:
    """หัวคำสั่ง, เนื้อที่วางมาหลัง ":" หรือบรรทัดแรก (ตัวไหนมาก่อน) · ไม่มี = เนื้อว่าง."""
    m = re.search(r"[:：\n]", text)
    if not m:
        return text, ""
    return text[: m.start()], text[m.end() :].strip()


def _latin_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(c.isascii() for c in letters) / len(letters) if letters else 0.0


def lang_intent(text: str) -> str | None:
    """ "translate" / "summarize" / None (ให้ AI ตัดสินตามเดิม)."""
    t = BRANDS.sub("แอป", text.strip())
    if BARE.fullmatch(t):  # "แปล" เฉย ๆ ไม่มีอะไรให้แปล → ให้ AI ถามกลับ
        return None
    head, body = split(t)
    if len(body) >= PAYLOAD_MIN:
        # "เป็นภาษาไทย" นับเมื่อเนื้อเป็นภาษาอังกฤษ ("ปรับให้สุภาพ แต่ยังเป็นภาษาไทยอยู่: …" ไม่ใช่แปล)
        if TR_HEAD.search(head) or (TO_THAI.search(head) and _latin_share(body) > 0.5):
            return "translate"
        if summary_cue(head):
            return "summarize"
        return None
    if TR_START.search(t) or ASK_HOW.search(t) or (QUOTED.search(t) and MEANING.search(t)):
        return "translate"
    if len(t) >= SUMMARY_LEN_MIN:
        lead = t[:LEAD]
        if SUM_START.search(t) or (summary_cue(lead) and PASTED.search(lead)):
            return "summarize"
    return None
