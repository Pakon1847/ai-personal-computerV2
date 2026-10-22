"""ตัวต่อ visiond ฝั่งหน้าจอ (หน้า Login และหน้าตั้งค่า) · การ์ด 0015 · ดูโปรโตคอลใน aipc.vision.daemon.

ไม่มี visiond (ยังไม่ติดตั้ง/ล่ม) = ตอบ {"ok": False, "state": "unavailable"} · หน้าจอใช้รหัสผ่านต่อได้เสมอ
"""

from __future__ import annotations

import json
import socket
from collections.abc import Callable
from pathlib import Path

PUBLIC = Path("/run/aipc-vision/visiond.sock")
UNAVAILABLE = {"ok": False, "state": "unavailable", "message": "ระบบใบหน้าไม่พร้อม · ใช้รหัสผ่านได้เลย"}


def available(path: Path = PUBLIC) -> bool:
    return hasattr(socket, "AF_UNIX") and path.exists()


def request(req: dict, on_progress: Callable[[dict], None] | None = None, path: Path = PUBLIC,
            timeout: float = 60.0) -> dict:  # fmt: skip
    """ส่งคำขอ 1 ก้อน · บรรทัดที่มี "state" แต่ไม่มี "ok" = สถานะระหว่างทาง · บรรทัดที่มี "ok" = ผลสุดท้าย."""
    if not available(path):
        return dict(UNAVAILABLE)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(str(path))
            s.sendall(json.dumps(req, ensure_ascii=False).encode() + b"\n")
            buf = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    return dict(UNAVAILABLE)
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    msg = json.loads(line)
                    if not isinstance(msg, dict):
                        continue
                    if "ok" in msg:
                        return msg
                    if on_progress:
                        on_progress(msg)
    except (OSError, ValueError):
        return dict(UNAVAILABLE)


def watch(user: str, on_seen: Callable[[dict], None], stop, seconds: float = 60.0,
          path: Path = PUBLIC) -> dict:  # fmt: skip
    """ตัวตรวจว่าเจ้าของยังอยู่ (การ์ด 0051 ทาง ก) · เรียก on_seen ทุกผลจาก visiond ·
    stop (threading.Event) ตั้ง = ปิดการเชื่อมต่อ → visiond ปล่อยกล้อง · คืนผลสุดท้าย/สาเหตุที่หยุด."""
    if not available(path):
        return dict(UNAVAILABLE)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(str(path))
            req = {"op": "watch", "username": user, "seconds": seconds}
            s.sendall(json.dumps(req, ensure_ascii=False).encode() + b"\n")
            buf = b""
            while not stop.is_set():
                try:
                    chunk = s.recv(4096)
                except TimeoutError:
                    continue
                if not chunk:
                    return dict(UNAVAILABLE)
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    msg = json.loads(line)
                    if not isinstance(msg, dict):
                        continue
                    if "ok" in msg:
                        return msg
                    on_seen(msg)
            return {"ok": True, "state": "stopped"}
    except (OSError, ValueError):
        return dict(UNAVAILABLE)
