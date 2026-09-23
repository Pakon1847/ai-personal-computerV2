"""ตัวต่อ greetd (การ์ดออกแบบ 0003) · หน้า Login ส่งชื่อ/รหัสผ่านให้ greetd แล้ว PAM ของ OS เป็นคนตรวจ.

โค้ดนี้ **ไม่ตรวจรหัสผ่านเอง** และไม่เก็บ/ไม่ log รหัสผ่าน · แค่ส่งข้อความไป-กลับตามโปรโตคอล greetd IPC:
แต่ละข้อความ = ความยาว 4 ไบต์ (u32, native endian) + JSON (UTF-8)

    create_session(username) → auth_message (PAM ถาม) | success | error
    post_auth_message_response(response) → เหมือนกัน (PAM อาจถามหลายรอบ)
    start_session(cmd, env) → success → greeter ต้องปิดตัวเอง แล้ว greetd เริ่มเซสชันของผู้ใช้
    cancel_session → success
"""

from __future__ import annotations

import json
import os
import socket
import struct
from dataclasses import dataclass, field

MAX_MESSAGE = 64 * 1024  # greetd ตอบสั้น ๆ เสมอ · ยาวกว่านี้ = ผิดรูปแบบ ไม่อ่านต่อ
GENERIC_FAIL = "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"  # ไม่บอกแยกว่าผิดที่ชื่อหรือรหัส (H3)


class ProtocolError(Exception):
    """greetd ตอบผิดรูปแบบ หรือ socket ปิดกลางคัน."""


@dataclass
class Reply:
    kind: str  # "prompt" | "success" | "error"
    prompt_type: str = ""  # visible | secret | info | error (เมื่อ kind == "prompt")
    text: str = ""
    error_type: str = ""  # auth_error | error (เมื่อ kind == "error")

    @staticmethod
    def parse(msg: dict) -> Reply:
        t = msg.get("type")
        if t == "success":
            return Reply("success")
        if t == "error":
            return Reply("error", text=str(msg.get("description", "")),
                         error_type=str(msg.get("error_type", "error")))  # fmt: skip
        if t == "auth_message":
            kind = msg.get("auth_message_type")
            if kind not in ("visible", "secret", "info", "error"):
                raise ProtocolError(f"auth_message_type ไม่รู้จัก: {kind!r}")
            return Reply("prompt", prompt_type=kind, text=str(msg.get("auth_message", "")))
        raise ProtocolError(f"type ไม่รู้จัก: {t!r}")


class Greetd:
    def __init__(self, sock: socket.socket):
        self._sock = sock

    @classmethod
    def connect(cls, path: str | None = None) -> Greetd:
        path = path or os.environ.get("GREETD_SOCK")
        if not path:
            raise ProtocolError("ไม่มี GREETD_SOCK (ไม่ได้รันจาก greetd)")
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(30)
        s.connect(path)
        return cls(s)

    def close(self) -> None:
        self._sock.close()

    # ---------- ระดับข้อความ ----------

    def _send(self, obj: dict) -> None:
        data = json.dumps(obj).encode("utf-8")
        self._sock.sendall(struct.pack("=I", len(data)) + data)

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ProtocolError("greetd ปิดการเชื่อมต่อกลางคัน")
            buf += chunk
        return buf

    def _recv(self) -> Reply:
        (length,) = struct.unpack("=I", self._recv_exact(4))
        if length > MAX_MESSAGE:
            raise ProtocolError(f"ข้อความยาวผิดปกติ ({length} ไบต์)")
        try:
            msg = json.loads(self._recv_exact(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ProtocolError(f"JSON ผิดรูปแบบ: {e}") from None
        if not isinstance(msg, dict):
            raise ProtocolError("ข้อความไม่ใช่ JSON object")
        return Reply.parse(msg)

    def _call(self, obj: dict) -> Reply:
        self._send(obj)
        return self._recv()

    def create_session(self, username: str) -> Reply:
        return self._call({"type": "create_session", "username": username})

    def answer(self, response: str | None) -> Reply:
        return self._call({"type": "post_auth_message_response", "response": response})

    def start(self, cmd: list[str], env: list[str] | None = None) -> Reply:
        return self._call({"type": "start_session", "cmd": cmd, "env": env or []})

    def cancel(self) -> Reply:
        return self._call({"type": "cancel_session"})


@dataclass
class LoginResult:
    ok: bool
    message: str = ""
    notes: list[str] = field(default_factory=list)  # ข้อความ info/error จาก PAM ที่ควรแสดงให้ผู้ใช้เห็น


def login(g: Greetd, username: str, password: str, cmd: list[str],
          env: list[str] | None = None) -> LoginResult:  # fmt: skip
    """เข้าสู่ระบบหนึ่งครั้ง: ส่งรหัสผ่านให้คำถาม secret ข้อแรกเท่านั้น.

    คำถามที่หน้าจอยังตอบไม่ได้ (เช่น ขอรหัสใหม่เพราะหมดอายุ หรือถามข้อความที่มองเห็น) →
    ยกเลิก แล้วบอกผู้ใช้ตามจริง ไม่เดาคำตอบ (H5)
    """
    if not username:
        return LoginResult(False, "กรุณาพิมพ์ชื่อผู้ใช้")
    notes: list[str] = []
    sent_password = False
    r = g.create_session(username)
    while r.kind == "prompt":
        if r.prompt_type in ("info", "error"):
            notes.append(r.text)
            r = g.answer(None)
        elif r.prompt_type == "secret" and not sent_password:
            sent_password = True
            r = g.answer(password)
        else:
            g.cancel()
            msg = f"ระบบถามเพิ่ม: “{r.text}” · หน้านี้ยังตอบไม่ได้ ใช้ Ctrl+Alt+F2"
            return LoginResult(False, msg, notes)
    if r.kind == "error":
        g.cancel()
        msg = GENERIC_FAIL if r.error_type == "auth_error" else f"เข้าสู่ระบบไม่ได้: {r.text}"
        return LoginResult(False, msg, notes)
    s = g.start(cmd, env)
    if s.kind != "success":
        g.cancel()
        return LoginResult(False, f"เริ่มเซสชันไม่ได้: {s.text}", notes)
    return LoginResult(True, "", notes)
