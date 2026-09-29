"""รายการสกิลที่ AI ในเครื่องเลือกได้ (tool calling ของ llama-server).

ใช้ทั้งแอปจริงและตัววัด (spikes.skill_select)

สร้างจากไฟล์สกิลทุกครั้ง = เพิ่มสกิลแล้ว AI รู้จักทันที · ไม่มีพารามิเตอร์: AI บอกได้แค่ว่าใช้สกิลไหน
โค้ดทำงานกับข้อความเดิมของผู้ใช้เอง (H8)
"""

from __future__ import annotations

from aipc.skills.manifest import Manifest

# ไม่ให้ AI เลือก "สั่งงานเครื่อง": ต้องใช้ชื่อแอป/เว็บที่แน่นอน ให้ตัวแปลคำสั่งแบบกฎทำ
NOT_FOR_AI = frozenset({"system-command"})
SYSTEM = "คุณคือผู้ช่วย AI ภาษาไทยที่ทำงานในเครื่องของผู้ใช้ ตอบเป็นภาษาไทย กระชับ ถูกต้อง ถ้าไม่รู้ให้บอกว่าไม่รู้"
# ข้อความคงที่ทุกครั้ง = ส่วนต้นของ prompt ซ้ำเดิม llama-server จึงจำส่วนที่อ่านแล้วไว้ได้ (cache_prompt)
TOOLS_HINT = " · ถ้าคำขอตรงกับเครื่องมือที่มี ให้เรียกเครื่องมือนั้นโดยไม่ต้องตอบเอง ถ้าไม่ตรงให้ตอบเองตามปกติ"


def tools(skills: list[Manifest], available: set[str]) -> list[dict]:
    out = []
    for s in skills:
        if s.id in NOT_FOR_AI or any(n not in available for n in s.needs):
            continue
        desc = f"{s.name}: {s.description} (ตัวอย่าง: {' · '.join(s.examples[:3])})"
        fn = {"name": s.id, "description": desc, "parameters": {"type": "object", "properties": {}}}
        out.append({"type": "function", "function": fn})
    return out
