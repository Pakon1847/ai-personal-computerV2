"""เตือนทุกข้อความให้เรียก skill ที่ตรงงาน โดยไม่ต้องรอสั่ง (Pakon ขอ 2026-11-09).

UserPromptSubmit · ข้อความนี้เข้าไปในบริบทของ Claude ทุกครั้งที่ Pakon ส่งข้อความ
ใช้แค่ไลบรารีมาตรฐาน (ไม่มี dependency) · ไม่อ่านข้อความของผู้ใช้
"""

import json

REMINDER = (
    "ก่อนตอบ: ดูตาราง \"ใช้ skill ไหนเมื่อไหร่\" ใน CLAUDE.md แล้วเรียก skill ทุกตัวที่ตรงงานนี้ทันที "
    "โดยไม่ต้องรอ Pakon สั่ง · skill ที่ไม่ตรงงานไม่ต้องเรียก · "
    "caveman เปิดตลอด เว้นแต่ Pakon พูด \"stop caveman\" หรือ \"normal mode\" ในบทสนทนานี้ "
    "(ยังตอบภาษาไทย · การสอนและรายงานจบงานตาม CLAUDE.md ต้องครบ)"
)

print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                         "additionalContext": REMINDER}}))
