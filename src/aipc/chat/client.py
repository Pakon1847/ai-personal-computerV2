"""คุยกับ llama-server ของผู้ใช้คนนั้น (การ์ด 0013 · ADR-008) · standard library อย่างเดียว.

ปกติคุยผ่าน Unix socket ที่ `$XDG_RUNTIME_DIR/aipc/llm.sock` — โฟลเดอร์นี้เป็นของผู้ใช้คนนั้น (0700)
ผู้ใช้อื่นจึงต่อไม่ได้ เพราะ OS กันให้ ไม่ต้องเขียนระบบสิทธิ์เอง · ตั้ง `AIPC_LLM_URL=http://127.0.0.1:8080`
เพื่อต่อ llama-server แบบ TCP ตอนพัฒนาบนวินโดวส์

คำตอบมาแบบ stream (Server-Sent Events): ทุกบรรทัด `data: {...}` คือ token ใหม่ · `data: [DONE]` = จบ
หยุด = ปิดการเชื่อมต่อ llama-server จะหยุดสร้างข้อความเอง
"""

from __future__ import annotations

import http.client
import json
import os
import socket
import threading
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

SAMPLING = {"temperature": 0.6, "top_p": 0.95}  # ค่าเดียวกับตอนวัดคุณภาพ (ADR-007)
MAX_TOKENS = 512


def socket_path() -> Path | None:
    run = os.environ.get("XDG_RUNTIME_DIR")
    return Path(run) / "aipc" / "llm.sock" if run else None


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, path: str, timeout: float):
        super().__init__("localhost", timeout=timeout)
        self._path = path

    def connect(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect(self._path)
        self.sock = s


@dataclass
class Target:
    url: str = ""  # http://host:port (พัฒนา) · ว่าง = ใช้ Unix socket
    sock: str = ""

    @staticmethod
    def from_env() -> Target:
        url = os.environ.get("AIPC_LLM_URL", "")
        if url:
            return Target(url=url)
        p = socket_path()
        return Target(sock=str(p) if p else "")

    def connect(self, timeout: float) -> http.client.HTTPConnection:
        if self.url:
            u = urlparse(self.url)
            return http.client.HTTPConnection(u.hostname, u.port or 80, timeout=timeout)
        if not self.sock or not hasattr(socket, "AF_UNIX"):
            raise ConnectionError("ไม่มีที่อยู่ของ AI")
        return _UnixConnection(self.sock, timeout)


def health(target: Target, timeout: float = 2.0) -> str:
    """ready = ตอบได้ · loading = กำลังโหลดโมเดล · down = ติดต่อไม่ได้."""
    try:
        conn = target.connect(timeout)
        conn.request("GET", "/health")
        code = conn.getresponse().status
        conn.close()
    except (OSError, http.client.HTTPException):
        return "down"
    return "ready" if code == 200 else "loading" if code == 503 else "down"


@dataclass
class Reply:
    text: str = ""
    reason: str = ""  # "" = จบปกติ · stopped · crashed · error
    detail: str = ""
    timings: dict = field(default_factory=dict)
    tool_call: str = ""  # สกิลที่ AI เลือก (ชื่อเครื่องมือ) · "" = ตอบเอง · ไม่มีอาร์กิวเมนต์ใด ๆ จาก AI


class Stream:
    """ถาม 1 ครั้ง · on_token ถูกเรียกทุก token (จากเธรดที่เรียก run) · abort() เรียกจากเธรดไหนก็ได้."""

    def __init__(self, target: Target, messages: list[dict], timeout: float = 600,
                 tools: list[dict] | None = None):  # fmt: skip
        self.target, self.messages, self.timeout = target, messages, timeout
        self.tools = tools or []  # สกิลที่ AI เลือกได้ (tool calling ของ llama-server · --jinja)
        self._conn: http.client.HTTPConnection | None = None
        self._sock: socket.socket | None = (
            None  # http.client ทิ้ง conn.sock เมื่อคำตอบเป็น stream จึงเก็บไว้เอง
        )
        self._stopped = threading.Event()

    def abort(self) -> None:
        self._stopped.set()
        sock = self._sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)  # ให้ readline ที่รออยู่หลุดทันที
            except OSError:
                pass

    def run(self, on_token) -> Reply:
        body = {"messages": self.messages, "stream": True, "cache_prompt": True,
                "max_tokens": MAX_TOKENS, **SAMPLING}  # fmt: skip
        if self.tools:
            body["tools"] = self.tools
            body["tool_choice"] = "auto"
        reply = Reply()
        try:
            self._conn = self.target.connect(self.timeout)
            self._conn.request("POST", "/v1/chat/completions", body=json.dumps(body),
                               headers={"Content-Type": "application/json"})  # fmt: skip
            self._sock = self._conn.sock
            resp = self._conn.getresponse()
            if resp.status != 200:
                reply.reason = "error"
                reply.detail = (
                    "AI กำลังโหลดโมเดล" if resp.status == 503 else f"AI ตอบรหัส {resp.status}"
                )
                return reply
            while True:
                if self._stopped.is_set():
                    reply.reason = "stopped"
                    return reply
                line = resp.readline()
                if not line:  # การเชื่อมต่อปิดก่อนได้ [DONE]
                    reply.reason = "stopped" if self._stopped.is_set() else "crashed"
                    return reply
                line = line.strip()
                if not line.startswith(b"data:"):
                    continue
                data = line[5:].strip()
                if data == b"[DONE]":
                    return reply
                chunk = json.loads(data)
                if chunk.get("timings"):
                    reply.timings = chunk["timings"]
                for choice in chunk.get("choices", []):
                    delta = choice.get("delta") or {}
                    for call in delta.get("tool_calls") or []:
                        name = (call.get("function") or {}).get("name")
                        if name and not reply.tool_call:  # สนแค่ชื่อ · อาร์กิวเมนต์ของ AI ไม่ถูกใช้ (H8)
                            reply.tool_call = name
                    token = delta.get("content") or ""
                    if token:
                        reply.text += token
                        on_token(token)
        except (OSError, http.client.HTTPException, ValueError) as e:
            reply.reason = "stopped" if self._stopped.is_set() else "crashed"
            reply.detail = str(e)
            return reply
        finally:
            if self._conn is not None:
                self._conn.close()


def fit_context(
    system: str, history: list[dict], budget_tokens: int = 3000
) -> tuple[list[dict], bool]:
    """ข้อความล่าสุดที่รวมแล้วไม่เกินงบ (ตัดข้อความเก่าสุดก่อน) · คืน (messages, ตัดไปไหม).

    ประมาณ token จากจำนวนตัวอักษร ÷ 2 (ภาษาไทยมักได้ 2–3 ตัวอักษรต่อ token · ประมาณแบบเผื่อไว้)
    context 4096 = ข้อความ 3000 + คำตอบ 512 + ที่เหลือเผื่อ system prompt
    """
    kept, used = [], len(system) // 2
    for m in reversed(history):
        cost = len(m["content"]) // 2 + 4
        if kept and used + cost > budget_tokens:
            break
        kept.append(m)
        used += cost
    kept.reverse()
    return [{"role": "system", "content": system}, *kept], len(kept) < len(history)
