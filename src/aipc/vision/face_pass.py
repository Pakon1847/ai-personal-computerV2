"""aipc-face-pass: ตัวที่ PAM ของหน้า Login เรียก (pam_exec) · การ์ด 0015 หัวข้อ 12.

อยู่ใน `/etc/pam.d/greetd` **ไฟล์เดียว** (sudo, SSH, หน้าจอล็อกไม่มี):

    auth    [success=done default=ignore] pam_exec.so quiet /usr/local/sbin/aipc-face-pass
    session optional                      pam_exec.so quiet /usr/local/sbin/aipc-face-pass

pam_exec ส่งชื่อบัญชีมาใน PAM_USER และขั้นตอนใน PAM_TYPE:
- auth → ขอใช้ตั๋วจาก visiond · มีตั๋ว = exit 0 (เข้าได้เลย) · ไม่มี/visiond ไม่ตอบ/ผิดพลาดอะไรก็ตาม = exit 1
  แล้ว PAM ไปถามรหัสผ่านตามเดิม (ใบหน้าเสีย = รหัสผ่านยังใช้ได้เสมอ)
- open_session → บอก visiond ว่าเข้าระบบสำเร็จ (ปลดล็อกการสแกนที่ผิด 5 ครั้ง) · exit 0 เสมอ
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

ROOT = Path("/run/aipc/visiond-root.sock")
TIMEOUT_S = 3.0


def ask(req: dict, path: Path = ROOT) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(TIMEOUT_S)
        s.connect(str(path))
        s.sendall(json.dumps(req).encode() + b"\n")
        data = b""
        while b"\n" not in data and len(data) < 4096:
            chunk = s.recv(1024)
            if not chunk:
                break
            data += chunk
    reply = json.loads(data.split(b"\n", 1)[0])
    return reply if isinstance(reply, dict) else {}


def run(env: dict, ask=ask) -> int:
    kind, user = env.get("PAM_TYPE", ""), env.get("PAM_USER", "")
    try:
        if kind == "auth" and user:
            return 0 if ask({"op": "consume", "username": user}).get("ok") is True else 1
        if kind == "open_session":
            ask({"op": "login-ok"})
            return 0
    except (OSError, ValueError):
        pass
    return 0 if kind == "open_session" else 1


def main() -> int:
    return run(dict(os.environ))


if __name__ == "__main__":
    sys.exit(main())
