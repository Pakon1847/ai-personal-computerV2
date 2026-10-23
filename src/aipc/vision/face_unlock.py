"""ตัวตรวจใบหน้าที่ PAM ของจอล็อกเรียก (การ์ด 0055) — /etc/pam.d/gtklock → pam_exec expose_authtok.

รันเป็นผู้ใช้เจ้าของจอล็อก (gtklock ไม่ใช่ root) · รหัสที่พิมพ์มาทาง stdin (จบด้วย NUL):
- พิมพ์รหัสมา = ออกทันที (exit 1) → PAM ไปตรวจรหัสผ่านตามเดิม ไม่เสียเวลาเปิดกล้อง
- ช่องว่าง = ขอ visiond สแกน (คำขอ unlock · เจ้าของบัญชีเท่านั้น · มี liveness) → ผ่าน = exit 0 (ปลดล็อก)
ไม่แน่ใจ/visiond ไม่ตอบ/ชื่อไม่ตรงผู้รัน = exit 1 (ใช้รหัสผ่าน) · ไม่ปลดให้ใครโดยไม่ได้ตรวจ (H1)
"""

from __future__ import annotations

import os
import sys

REQUEST_TIMEOUT_S = 15.0


def decide(typed: bytes, pam_user: str, me: str, ask) -> int:
    """0 = ปลด · 1 = ไม่ปลด (ให้ PAM ตรวจรหัสผ่านต่อ) · แยกจาก main() เพื่อเทสต์ได้ทุกระบบ."""
    if typed.rstrip(b"\0").strip():
        return 1
    if not pam_user or pam_user != me:
        return 1
    r = ask({"op": "unlock", "username": pam_user})
    return 0 if r.get("ok") and r.get("user") == pam_user else 1


def main() -> int:
    import pwd

    from aipc.vision import client

    typed = sys.stdin.buffer.read(4096) if not sys.stdin.isatty() else b""
    me = pwd.getpwuid(os.getuid()).pw_name
    return decide(typed, os.environ.get("PAM_USER", ""), me,
                  lambda req: client.request(req, timeout=REQUEST_TIMEOUT_S))  # fmt: skip


if __name__ == "__main__":
    sys.exit(main())
