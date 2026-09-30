"""เพดานค่าใช้จ่าย Claude ต่อวัน (ไฮบริดการ์ด 0016 + สกิลอัตโนมัติการ์ด 0017) · ต่อผู้ใช้หนึ่งคน.

ค่าใช้จ่ายมาจาก `total_cost_usd` ที่ `claude -p` รายงาน = ราคาอ้างอิง (บัญชี Pro/Max ไม่ถูกคิดเงินเพิ่มตามนี้ แต่ใช้โควตา ·
บัญชี Console คิดเงินจริง) · ครบเพดาน = ไม่เรียก Claude อีกจนถึงวันใหม่ (เวลาเครื่อง) · AI ในเครื่องยังใช้ได้ตามปกติ
ไฟล์ ~/.local/share/aipc/cloud-usage.json · เก็บย้อนหลัง 31 วัน · เขียนแบบ os.replace · ไฟล์เสีย = เริ่มนับใหม่ (ไม่ล้มแอป)
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import date
from pathlib import Path

LIMITS = (0.5, 1.0, 2.0, 5.0)  # USD ต่อวัน ที่ให้เลือกในหน้าตั้งค่า
DEFAULT_LIMIT = 1.0
KEEP_DAYS = 31


def default_path() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "aipc" / "cloud-usage.json"


class Budget:
    def __init__(self, path: Path | None = None, today=date.today):
        self.path = path or default_path()
        self._today = today
        self._lock = threading.Lock()  # ถาม Claude กับสร้างสกิลอาจบันทึกพร้อมกันจากคนละเธรด
        self._data = self._read()

    def _read(self) -> dict:
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) and isinstance(d.get("days", {}), dict) else {}
        except (OSError, ValueError):
            return {}

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".cloud-usage.")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    @property
    def limit(self) -> float:
        v = self._data.get("limit_usd", DEFAULT_LIMIT)
        return float(v) if v in LIMITS else DEFAULT_LIMIT

    def set_limit(self, usd: float) -> None:
        if usd in LIMITS:
            with self._lock:
                self._data["limit_usd"] = usd
                self._write()

    def _day(self) -> dict:
        return (self._data.get("days") or {}).get(self._today().isoformat()) or {}

    def spent(self) -> float:
        return round(float(self._day().get("usd", 0.0)), 4)

    def calls(self) -> int:
        return int(self._day().get("calls", 0))

    def allow(self) -> bool:
        return self.spent() < self.limit

    def blocked_message(self) -> str:
        return (f"ใช้ Claude วันนี้ครบเพดาน ${self.limit:.2f} แล้ว (ราคาอ้างอิง ${self.spent():.2f}) · "
                "AI ในเครื่องยังใช้ได้ · เพิ่มเพดานได้ที่หน้าตั้งค่า หรือรอวันใหม่")  # fmt: skip

    def record(self, usd: float, kind: str) -> None:
        with self._lock:
            days = self._data.setdefault("days", {})
            key = self._today().isoformat()
            d = days.setdefault(key, {"usd": 0.0, "calls": 0})
            d["usd"] = round(float(d.get("usd", 0)) + max(0.0, float(usd or 0)), 6)
            d["calls"] = int(d.get("calls", 0)) + 1
            d[kind] = int(d.get(kind, 0)) + 1
            for old in sorted(days)[:-KEEP_DAYS]:
                del days[old]
            self._write()
