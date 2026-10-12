"""Chrome DevTools Protocol ทาง pipe (การ์ด 0024).

Chromium ที่เปิดด้วย `--remote-debugging-pipe` อ่านคำสั่งจาก fd 3 และตอบทาง fd 4 · ข้อความเป็น JSON คั่นด้วย \\0 ·
ไม่เปิดพอร์ตเครือข่าย: เฉพาะโปรเซสที่เปิด Chromium (แอปของผู้ใช้คนนี้) คุมได้ (พอร์ต 9222 = ทุกโปรแกรม/ทุกบัญชีในเครื่องต่อได้)
"""

from __future__ import annotations

import json
import os
import subprocess
import threading


class CdpError(RuntimeError):
    pass


class PipeClient:
    """คุยกับ Chromium ทาง fd สองตัว · call() รอคำตอบ (เรียกจากหลายเธรดได้) · ปิด pipe = closed."""

    def __init__(self, read_fd: int, write_fd: int):
        self._r = os.fdopen(read_fd, "rb", buffering=0)
        self._w = os.fdopen(write_fd, "wb", buffering=0)
        self._lock = threading.Lock()
        self._next = 0
        self._waiting: dict[int, list] = {}
        self.closed = False
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        buf = b""
        try:
            while chunk := self._r.read(65536):
                buf += chunk
                while b"\0" in buf:
                    raw, buf = buf.split(b"\0", 1)
                    try:
                        msg = json.loads(raw)
                    except ValueError:
                        continue
                    slot = self._waiting.get(msg.get("id", -1))
                    if slot is not None:  # เหตุการณ์ (ไม่มี id) ไม่ได้ใช้
                        slot[1] = msg
                        slot[0].set()
        except OSError:
            pass
        self.closed = True
        for slot in list(self._waiting.values()):  # Chromium ปิด = ปลุกทุกคนที่รออยู่
            slot[0].set()

    def call(self, method: str, params: dict | None = None, session: str = "", timeout=15.0):
        if self.closed:
            raise CdpError("เบราว์เซอร์ปิดไปแล้ว")
        with self._lock:
            self._next += 1
            mid = self._next
            slot = [threading.Event(), None]
            self._waiting[mid] = slot
            msg = {"id": mid, "method": method, "params": params or {}}
            if session:
                msg["sessionId"] = session
            try:
                self._w.write(json.dumps(msg).encode() + b"\0")
            except OSError as e:
                self._waiting.pop(mid, None)
                self.closed = True
                raise CdpError("เบราว์เซอร์ปิดไปแล้ว") from e
        ok = slot[0].wait(timeout)
        self._waiting.pop(mid, None)
        if not ok:
            raise CdpError(f"เบราว์เซอร์ไม่ตอบ ({method})")
        reply = slot[1]
        if reply is None:
            raise CdpError("เบราว์เซอร์ปิดไปแล้ว")
        if "error" in reply:
            raise CdpError(reply["error"].get("message", str(reply["error"])))
        return reply.get("result", {})

    def close(self) -> None:
        for f in (self._w, self._r):
            try:
                f.close()
            except OSError:
                pass


def launch(argv: list[str], env: dict | None = None) -> tuple[subprocess.Popen, PipeClient]:
    """เปิด Chromium ให้ fd 3 = คำสั่งจากเรา · fd 4 = คำตอบถึงเรา (sh ย้าย fd ให้ · ไม่ใช้ preexec_fn ในแอป Qt)."""
    to_r, to_w = os.pipe()
    from_r, from_w = os.pipe()
    script = f'exec "$@" 3<&{to_r} 4>&{from_w} {to_r}<&- {from_w}>&-'
    proc = subprocess.Popen(
        ["sh", "-c", script, "sh", *argv],
        pass_fds=(to_r, from_w),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        start_new_session=True,  # แอปปิดด้วย Ctrl+C ไม่ฆ่าเบราว์เซอร์กลางหน้า
    )
    os.close(to_r)
    os.close(from_w)
    return proc, PipeClient(from_r, to_w)
