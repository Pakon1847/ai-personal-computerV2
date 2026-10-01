"""บันทึกทุกครั้งที่ส่งข้อมูลออกนอกเครื่อง (ไปที่ Claude) · ต่อผู้ใช้หนึ่งคน.

ทำไม: จุดขายของเครื่องนี้คือ "ข้อมูลอยู่ในเครื่อง" (ชุดสอบจบ H03 "ข้อมูลที่คุยถูกส่งไปไหน") → ผู้ใช้ต้องตรวจเองได้ว่า
เคยส่งอะไรออกไปบ้าง เมื่อไหร่ ส่งเพราะอะไร · หน้าตั้งค่าแสดงรายการล่าสุดและล้างได้
เก็บข้อความที่ส่งจริงตามตัวอักษร (ไฟล์อยู่ในโฟลเดอร์ของผู้ใช้เอง สิทธิ์ 0600) · เก็บล่าสุด KEEP รายการ ·
ไฟล์เสีย = เริ่มใหม่ (ไม่ล้มแอป) · ~/.local/share/aipc/outbound.json
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path

KEEP = 200
KINDS = {"ask": "ถาม Claude", "skill": "ให้ Claude สร้างสกิล"}


def default_path() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "aipc" / "outbound.json"


class Ledger:
    def __init__(self, path: Path | None = None, now=datetime.now):
        self.path = path or default_path()
        self._now = now
        self._lock = threading.Lock()  # ถาม Claude กับสร้างสกิลบันทึกจากคนละเธรดได้

    def entries(self) -> list[dict]:
        """ใหม่สุดก่อน."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        items = data.get("items") if isinstance(data, dict) else None
        return list(reversed(items)) if isinstance(items, list) else []

    def record(self, kind: str, sent: str, cost_usd: float = 0.0, ok: bool = True,
               note: str = "") -> None:  # fmt: skip
        entry = {"time": self._now().isoformat(timespec="seconds"), "kind": kind, "sent": sent,
                 "chars": len(sent), "cost_usd": round(max(0.0, float(cost_usd or 0)), 6), "ok": ok,
                 "note": note}  # fmt: skip
        with self._lock:
            items = list(reversed(self.entries()))
            items.append(entry)
            self._write({"items": items[-KEEP:]})

    def clear(self) -> None:
        with self._lock:
            self._write({"items": []})

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".outbound.")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)
