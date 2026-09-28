"""เขียนไฟล์ข้อมูลของผู้ใช้แบบ atomic (H1) · ใช้ร่วมกันทุกที่ที่เก็บข้อมูล.

ลำดับ: เขียนไฟล์ชั่วคราว (สิทธิ์ 0600 ตั้งแต่สร้าง) → fsync ไฟล์ → rename ทับของเดิม → fsync โฟลเดอร์
ไฟดับตรงไหนก็ตาม ไฟล์เดิมยังอ่านได้ครบ หรือได้ไฟล์ใหม่ครบ ไม่มีครึ่ง ๆ
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def fsync_dir(folder: Path) -> None:
    """ให้การเปลี่ยนชื่อไฟล์ลงดิสก์จริง · วินโดวส์ไม่มี ข้ามได้."""
    if os.name != "posix":
        return
    fd = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_json(path: Path, data, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    fsync_dir(path.parent)
