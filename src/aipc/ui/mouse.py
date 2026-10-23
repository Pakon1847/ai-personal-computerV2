"""ความเร็วเมาส์ของแต่ละผู้ใช้ (การ์ด 0060 · Pakon: "เมาส์ช้า · ปิดเครื่องแล้วไม่ต้องรีเซ็ต").

aipc-session คัดค่าตั้ง labwc ไปไว้ใน $XDG_RUNTIME_DIR/aipc-labwc แล้วบอกแอปทาง AIPC_LABWC_DIR ·
แอปเขียน <pointerSpeed> ลง rc.xml ในโฟลเดอร์นั้น แล้วสั่ง `labwc --reconfigure` = มีผลทันที ·
ค่าที่ผู้ใช้เลือกเก็บใน ui.json (settings.mouse_speed) → เข้าระบบครั้งหน้าแอปตั้งให้อีกครั้ง
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

_SPEED = re.compile(r"(<pointerSpeed>)\s*-?\d+(?:\.\d+)?\s*(</pointerSpeed>)")


def config_dir() -> Path | None:
    d = os.environ.get("AIPC_LABWC_DIR")
    return Path(d) if d else None


def apply(speed: float, folder: Path | None = None, run=subprocess.run) -> bool:
    """เขียนความเร็ว (-1.0 ถึง 1.0) ลงค่าตั้ง labwc ของเซสชันนี้แล้วให้ labwc โหลดใหม่ ·
    ไม่ได้อยู่ในเซสชันของเรา / ไฟล์ไม่มีช่องนี้ / เขียนไม่ได้ = False (ไม่ทำเป็นว่าเปลี่ยนแล้ว · H5)."""
    folder = folder or config_dir()
    if folder is None:
        return False
    rc = folder / "rc.xml"
    try:
        text = rc.read_text(encoding="utf-8")
        if not _SPEED.search(text):
            return False
        speed = max(-1.0, min(1.0, float(speed)))
        new = _SPEED.sub(rf"\g<1>{speed:.2f}\g<2>", text, count=1)
        tmp = rc.with_name("rc.xml.new")
        tmp.write_text(new, encoding="utf-8")
        os.replace(tmp, rc)
        run(["labwc", "--reconfigure"], timeout=5, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, check=False)  # fmt: skip
        return True
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
