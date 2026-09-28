"""กฎตรวจข้อมูลตอนสมัครบัญชี (BRIEF 5.1 ข้อ 3–4).

แยกไว้เป็น Python ล้วน ไม่ผูกกับหน้าจอ เพราะ:
1. เทสต์ได้โดยไม่ต้องเปิดหน้าจอ
2. เฟส 1 ตัวสร้างบัญชีจริง (authd) ต้องตรวจซ้ำด้วยกฎชุดเดียวกัน
   — หน้าจอไม่ใช่ที่ตัดสินสิทธิ์ (BRIEF หัวข้อ 7 ข้อ 1) หน้าจอตรวจเพื่อบอกผู้ใช้เร็ว ๆ เท่านั้น
"""

from __future__ import annotations

import re
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
    # fullmatch ไม่ใช่ match: "$" ของ match ยอมให้มี "\n" ท้ายสตริง → "root\n" เคยผ่าน (พบ 2026-09-28)
    if not USERNAME_RE.fullmatch(name):
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


CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def check_password(password: str, confirm: str) -> Result:
    if len(password) < MIN_PASSWORD:
        return Result(False, f"อย่างน้อย {MIN_PASSWORD} ตัวอักษร")
    # ตัวควบคุม/ขึ้นบรรทัดทำให้รูปแบบ "ชื่อ:รหัส" ของ chpasswd เสีย (การ์ด 0012 ข้อ 6)
    if CONTROL.search(password):
        return Result(False, "มีตัวอักษรพิเศษที่ใช้ไม่ได้ (เช่น ขึ้นบรรทัดใหม่)")
    if password != confirm:
        return Result(False, "รหัสผ่านสองช่องไม่ตรงกัน")
    return Result(True, "ตรงกัน")


MAX_DISPLAY_NAME = 64


def check_display_name(name: str) -> Result:
    """ชื่อที่แสดงลงไปอยู่ในช่อง comment ของ /etc/passwd · ":" "," และตัวควบคุมทำให้ไฟล์นั้นเสีย."""
    name = name.strip()
    if not name:
        return Result(False, "ใส่ชื่อที่แสดง")
    if len(name) > MAX_DISPLAY_NAME:
        return Result(False, f"ยาวได้ไม่เกิน {MAX_DISPLAY_NAME} ตัวอักษร")
    if CONTROL.search(name) or any(c in name for c in ":,"):
        return Result(False, "ห้ามมีเครื่องหมาย : , หรือขึ้นบรรทัดใหม่")
    return Result(True, "ใช้ได้")


# PIN กู้คืนรหัสผ่าน (Pakon 2026-09-29: ตั้งเองจำง่ายกว่ารหัสสุ่ม 24 ตัว · การ์ด 0012 หัวข้อ 11)
# PIN เดาง่ายกว่ารหัสสุ่มมาก สิ่งที่กันการเดาจริงคือการหน่วงเมื่อผิดหลายครั้งในตัวช่วย root
# กฎนี้แค่ตัด PIN ที่คนเดาเป็นอันดับแรก ๆ ออก · วันเกิดตรวจไม่ได้ จึงเตือนที่หน้าจอแทน
MIN_PIN, MAX_PIN = 6, 12
THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
COMMON_PINS = {"112233", "001122", "147258", "258369", "159357", "159753", "741852", "963852",
               "789456", "142536", "102030", "010203"}  # fmt: skip


def normalize_pin(pin: str) -> str:
    """ไม่สนช่องว่าง · เลขไทย ๐–๙ = 0–9 (แป้นไทยพิมพ์เลขไทยได้)."""
    return re.sub(r"\s", "", pin).translate(THAI_DIGITS)


def _easy_pin(pin: str) -> bool:
    if pin in COMMON_PINS:
        return True
    steps = {(int(b) - int(a)) % 10 for a, b in zip(pin, pin[1:], strict=False)}
    if steps in ({0}, {1}, {9}):  # 000000 · 123456 · 987654 (รวมแบบวน เช่น 890123)
        return True
    # ซ้ำเป็นชุด: 121212 · 123123 · 12341234
    n = len(pin)
    return any(n % k == 0 and pin == pin[:k] * (n // k) for k in range(1, n // 2 + 1))


def check_pin(pin: str, confirm: str) -> Result:
    pin, confirm = normalize_pin(pin), normalize_pin(confirm)
    if not pin.isascii() or not pin.isdigit():
        return Result(False, "ใช้ตัวเลขเท่านั้น")
    if not MIN_PIN <= len(pin) <= MAX_PIN:
        return Result(False, f"ใช้ตัวเลข {MIN_PIN}–{MAX_PIN} หลัก")
    if _easy_pin(pin):
        return Result(False, "เดาง่ายเกินไป (เลขซ้ำ เลขเรียง หรือวนซ้ำ)")
    if pin != confirm:
        return Result(False, "PIN สองช่องไม่ตรงกัน")
    return Result(True, "ตรงกัน")
