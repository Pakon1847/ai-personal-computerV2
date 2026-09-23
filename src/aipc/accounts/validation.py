"""กฎตรวจข้อมูลตอนสมัครบัญชี (BRIEF 5.1 ข้อ 3–4).

แยกไว้เป็น Python ล้วน ไม่ผูกกับหน้าจอ เพราะ:
1. เทสต์ได้โดยไม่ต้องเปิดหน้าจอ
2. เฟส 1 ตัวสร้างบัญชีจริง (authd) ต้องตรวจซ้ำด้วยกฎชุดเดียวกัน
   — หน้าจอไม่ใช่ที่ตัดสินสิทธิ์ (BRIEF หัวข้อ 7 ข้อ 1) หน้าจอตรวจเพื่อบอกผู้ใช้เร็ว ๆ เท่านั้น
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass

# ชื่อผู้ใช้กลายเป็นชื่อ Linux user (BRIEF หัวข้อ 4: 1 บัญชี = 1 Linux user)
# จึงใช้กฎที่ปลอดภัยกับเครื่องมือของ Linux ทุกตัว: ขึ้นต้นด้วยตัวอักษร a–z
# ตามด้วย a–z 0–9 หรือ - รวม 3–32 ตัว (useradd รับยาวสุด 32)
USERNAME_RE = re.compile(r"^[a-z][a-z0-9-]{2,31}$")

# ชื่อที่ระบบใช้อยู่แล้ว ห้ามสมัครซ้ำ (ตัวอย่างที่ชนบ่อย ไม่ใช่รายการครบ —
# ตัวสร้างบัญชีจริงต้องเช็กกับ /etc/passwd อีกครั้งเสมอ)
RESERVED = {
    "root",
    "admin",
    "daemon",
    "bin",
    "sys",
    "sync",
    "games",
    "man",
    "lp",
    "mail",
    "news",
    "uucp",
    "proxy",
    "www-data",
    "backup",
    "list",
    "irc",
    "nobody",
    "systemd-network",
    "systemd-resolve",
    "messagebus",
    "sshd",
    "postgres",
    "greeter",
    "guest",
    "pi",
}

MIN_PASSWORD = 10


@dataclass(frozen=True)
class Result:
    ok: bool
    message: str


def check_username(name: str) -> Result:
    if not name:
        return Result(False, "ใส่ชื่อผู้ใช้")
    if name != name.lower():
        return Result(False, "ใช้ตัวพิมพ์เล็กเท่านั้น")
    if not USERNAME_RE.match(name):
        return Result(False, "ขึ้นต้นด้วย a–z แล้วตามด้วย a–z 0–9 หรือ - รวม 3–32 ตัว")
    if name in RESERVED:
        return Result(False, "ชื่อนี้ระบบใช้อยู่แล้ว")
    return Result(True, "ใช้ได้")


def password_strength(password: str) -> int:
    """คะแนน 0–4 · อธิบายได้ในประโยคเดียว: ยาวพอไหม และผสมตัวอักษรกี่แบบ.

    ไม่ได้ตั้งใจเป็นตัววัดความปลอดภัยที่ละเอียด (เช่น zxcvbn) เพราะต้องเพิ่มไลบรารี
    และอธิบายกรรมการยาก · ใช้แค่เพื่อบอกผู้ใช้คร่าว ๆ ว่ารหัสอ่อนไป
    """
    if len(password) < MIN_PASSWORD:
        return 0 if len(password) < 6 else 1
    kinds = sum(
        bool(re.search(p, password)) for p in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9]")
    )
    score = 2 + (kinds >= 3) + (len(password) >= 14)
    return min(score, 4)


STRENGTH_LABELS = ["สั้นเกินไป", "อ่อน", "พอใช้", "ดี", "ดีมาก"]


def check_password(password: str, confirm: str) -> Result:
    if len(password) < MIN_PASSWORD:
        return Result(False, f"อย่างน้อย {MIN_PASSWORD} ตัวอักษร")
    if password != confirm:
        return Result(False, "รหัสผ่านสองช่องไม่ตรงกัน")
    return Result(True, "ตรงกัน")


# ตัวอักษรของรหัสกู้คืน: Crockford base32 ตัด I L O U ออก
# เพราะคนจดด้วยมือแล้วสับสนกับ 1 0 V ได้ง่าย
RECOVERY_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_recovery_code(groups: int = 6, size: int = 4) -> str:
    """รหัสกู้คืนแบบสุ่ม เช่น 7K2Q-9XMA-4TPE-8WRD-3HJN-6CFB.

    ใช้ `secrets` ไม่ใช่ `random` เพราะ random เดาได้ถ้ารู้ค่าเริ่มต้น
    ส่วน secrets ใช้ตัวสุ่มของระบบปฏิบัติการที่ออกแบบมาสำหรับความลับ
    6 กลุ่ม × 4 ตัว × 5 บิต = 120 บิต — เดาสุ่มไม่ได้ในทางปฏิบัติ
    """
    chars = [secrets.choice(RECOVERY_ALPHABET) for _ in range(groups * size)]
    return "-".join("".join(chars[i : i + size]) for i in range(0, len(chars), size))
