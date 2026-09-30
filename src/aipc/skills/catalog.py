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
# ไฮบริด (การ์ด 0016): เครื่องมือพิเศษที่ AI ในเครื่องเลือกได้ = ส่งคำถามต่อให้ Claude (ค้นเว็บได้)
ASK_CLOUD = "ask-cloud"
ASK_CLOUD_DESC = ("ถามผู้ช่วยบน cloud ที่ค้นเว็บได้: ใช้เมื่อคำถามต้องใช้ข้อมูลสดหรือล่าสุด (อากาศ ข่าว ราคา "
                  "ผลกีฬา อัตราแลกเปลี่ยน เหตุการณ์ปัจจุบัน) หรือเป็นคำถามยาก คิดหลายขั้น คำนวณซับซ้อน "
                  "หรือคุณไม่แน่ใจคำตอบ")  # fmt: skip
# ข้อเท็จจริงเกี่ยวกับตัวระบบ (กรรมการสอบถามได้ · ชุดสอบจบกลุ่ม H) · ต้องตรงกับของจริงเสมอ
ABOUT = (
    "เกี่ยวกับระบบนี้: ทำงานบน Raspberry Pi 5 RAM 8 GB · "
    "AI ในเครื่องคิดบน CPU ของ Pi จึงตอบราว 4 คำต่อวินาที · "
    "แชท นัด และไฟล์เก็บในโฟลเดอร์ของผู้ใช้แต่ละคนในเครื่องนี้ ผู้ใช้อื่นเปิดไม่ได้ · "
    "สกิลคือไฟล์ .md บอกขั้นตอน Claude ช่วยสร้างสกิลใหม่แล้ว AI ในเครื่องเรียกใช้ · "
    "เข้าเครื่องด้วยใบหน้าได้เมื่อเจ้าของบัญชีเปิดเอง สะดวกแต่ไม่ปลอดภัยเท่ารหัสผ่าน งานสำคัญยังใช้รหัสผ่าน · "
    "ลืมรหัสผ่านใช้ PIN กู้คืนที่หน้า Login · บันทึกไฟล์แบบไม่เสียเมื่อไฟดับ"
)
RULES = ("กติกา: ตอบภาษาไทย กระชับ ไม่เกินประมาณ 6 บรรทัด เว้นแต่ผู้ใช้ขอรายละเอียด · ถ้าไม่รู้ให้บอกว่าไม่รู้ · "
         "คุณไม่มีข้อมูลสด (อากาศ ข่าว ราคา ผลกีฬา เหตุการณ์ล่าสุด) ห้ามเดาตัวเลขหรือข้อเท็จจริงเหล่านี้ "
         "ให้บอกตรง ๆ ว่าไม่มีข้อมูลสด · ปฏิเสธคำขอที่ผิดกฎหมายหรืออันตราย")  # fmt: skip


def system_prompt(today=None, cloud: bool = False, model: str = "") -> str:
    """system prompt ของแชท (แอปและตัววัดใช้ตัวเดียวกัน) · เปลี่ยนแค่วันละครั้ง แคชของ llama-server จึงใช้ได้ทั้งวัน.

    today = วันที่ของเครื่อง (ตอบเรื่องวันเวลาได้) · cloud = มีทางส่งต่อ Claude (การ์ด 0016)
    """
    from datetime import date

    from aipc.ui.thaidate import BE_OFFSET, DAYS, MONTHS

    d = today or date.today()
    day = f"{d.day} {MONTHS[d.month - 1]} พ.ศ. {d.year + BE_OFFSET} (ค.ศ. {d.year})"
    when = f"วันนี้คือวัน{DAYS[d.weekday()]}ที่ {day}"
    parts = [SYSTEM, when, RULES, ABOUT]
    if model:
        parts.append(f"โมเดลภาษาในเครื่องคือ {model}")
    if cloud:
        parts.append(f"ถ้าต้องใช้ข้อมูลสด หรือคำถามยากหรือไม่แน่ใจ ให้เรียกเครื่องมือ {ASK_CLOUD} แทนการเดา "
                     "(ส่งเฉพาะคำถามออกนอกเครื่อง)")  # fmt: skip
    return "\n".join(parts)


# ข้อความคงที่ทุกครั้ง = ส่วนต้นของ prompt ซ้ำเดิม llama-server จึงจำส่วนที่อ่านแล้วไว้ได้ (cache_prompt)
TOOLS_HINT = " · ถ้าคำขอตรงกับเครื่องมือที่มี ให้เรียกเครื่องมือนั้นโดยไม่ต้องตอบเอง ถ้าไม่ตรงให้ตอบเองตามปกติ"


def tools(skills: list[Manifest], available: set[str], cloud: bool = False) -> list[dict]:
    out = []
    if cloud:  # ไว้หน้าสุด: รายการเครื่องมือคงที่ แคชของ llama-server จึงใช้ส่วนต้นซ้ำได้
        fn = {"name": ASK_CLOUD, "description": ASK_CLOUD_DESC,
              "parameters": {"type": "object", "properties": {}}}  # fmt: skip
        out.append({"type": "function", "function": fn})
    for s in skills:
        if s.id in NOT_FOR_AI or any(n not in available for n in s.needs):
            continue
        desc = f"{s.name}: {s.description} (ตัวอย่าง: {' · '.join(s.examples[:3])})"
        fn = {"name": s.id, "description": desc, "parameters": {"type": "object", "properties": {}}}
        out.append({"type": "function", "function": fn})
    return out
