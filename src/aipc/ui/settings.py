"""ค่าหน้าจอที่ผู้ใช้ตั้งเอง (ธีม ขนาดตัวอักษร) และการบันทึกลงไฟล์.

บันทึกแบบ atomic ตาม BRIEF 5.9 ข้อ 9: เขียนไฟล์ชั่วคราว → fsync → rename ทับของเดิม
ถ้าไฟดับกลางคัน จะเหลือไฟล์เก่าครบหรือไฟล์ใหม่ครบอย่างใดอย่างหนึ่ง ไม่มีครึ่ง ๆ
เพราะ rename บน Linux เป็นการสลับชื่อครั้งเดียวจบ (atomic)

ไฟล์อยู่ใน home ของผู้ใช้ (~/.config/aipc/ui.json) ซึ่งเข้ารหัสและเป็นของผู้ใช้คนนั้น
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

THEMES = ("light", "dark")
FONT_SCALES = (1.0, 1.25, 1.5, 1.75, 2.0)  # BRIEF 5.7: 100–200%


def default_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "aipc" / "ui.json"


@dataclass
class UiPrefs:
    theme: str = "light"
    font_scale: float = 1.0

    def cleaned(self) -> UiPrefs:
        """ค่าที่อ่านจากไฟล์อาจถูกแก้มือหรือเสีย → ถอยไปค่าเริ่มต้นแทนการ crash."""
        theme = self.theme if self.theme in THEMES else "light"
        scale = self.font_scale if self.font_scale in FONT_SCALES else 1.0
        return UiPrefs(theme, scale)


def load(path: Path | None = None) -> UiPrefs:
    path = path or default_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return UiPrefs(
            theme=str(data.get("theme", "light")), font_scale=float(data.get("font_scale", 1.0))
        ).cleaned()
    except (OSError, ValueError, TypeError, AttributeError):
        return UiPrefs()


def save(prefs: UiPrefs, path: Path | None = None) -> None:
    path = path or default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(asdict(prefs.cleaned()), f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())  # บังคับให้ข้อมูลลงการ์ดจริงก่อน rename
    os.replace(tmp, path)  # os.replace = rename ที่เขียนทับได้ทั้งบน Linux และวินโดวส์
