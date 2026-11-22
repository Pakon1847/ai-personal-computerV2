"""บัญชี Claude ใช้ครบโควตา → ข้อความบอกผู้ใช้ตรง ๆ (การ์ด 0084 · H5).

ระบบไม่มีเพดานของตัวเองแล้ว (ลบเพดานรายวันและต่อครั้ง) · ขีดจำกัดเดียวคือของบัญชี Claude
ใช้ร่วมกันทั้งถาม Claude (`cloud.ask`) และสร้างสกิล (`skills.forge`) · แยกไฟล์เพราะ ask import forge อยู่แล้ว

รูปแบบข้อความ "ใช้ครบ" ของ `claude -p` ไม่มีในเอกสารทางการ · คำในรายการมาจากรายงานบั๊ก
("API Error: Rate limit reached" ทั้งที่ exit code 0 · "You're out of extra usage" + 429) ·
ดู `is_error` เท่านั้น ไม่ดู exit code หรือ subtype · ข้อความต้นฉบับของ Claude แสดงด้วยเสมอ
→ จัดผิดก็ยังเห็นของจริง
"""

from __future__ import annotations

WORDS = ("limit", "usage", "quota", "429")
MAX_CLAUDE_CHARS = 200


def account_limit_message(data: dict) -> str:
    """ผล JSON ของ `claude -p` → ข้อความผู้ใช้เมื่อบัญชีใช้ครบ · ไม่ใช่กรณีนี้ = ""."""
    if not data.get("is_error"):
        return ""
    text = " ".join(str(data.get("result") or "").split())
    if not any(w in text.lower() for w in WORDS):
        return ""
    said = text[:MAX_CLAUDE_CHARS]
    return f"บัญชี Claude ใช้ครบโควตาแล้ว · AI ในเครื่องยังใช้ได้ · Claude แจ้งว่า: “{said}”"
