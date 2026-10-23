"""การ์ด 0061: ภาพหน้าตั้งค่าทุกหมวด (ธีม/ขนาดตัวอักษร) + คำเตือน QML · ไม่ต้องมีจอ.

python -m aipc.spikes.settings_shots <โฟลเดอร์ผล> [--theme dark] [--scale 1.0] [--size 1920x1080]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--theme", default="dark")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--size", default="1920x1080")
    # การ์ด 0061 รอบ 2: ภาพการ์ด Claude ตอนเชื่อมต่อแล้ว (ใช้ไป $spent วันนี้ · ไม่เรียก Claude จริง)
    ap.add_argument("--cloud-spent", type=float)
    a = ap.parse_args(argv)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("AIPC_CLOUD", "0")
    tmp = Path(tempfile.mkdtemp(prefix="aipc-shots-"))
    os.environ["XDG_DATA_HOME"] = os.environ["XDG_CONFIG_HOME"] = str(tmp)
    (tmp / "aipc").mkdir()
    prefs = json.dumps({"theme": a.theme, "font_scale": a.scale})
    (tmp / "aipc" / "ui.json").write_text(prefs, encoding="utf-8")
    from PySide6.QtCore import QCoreApplication

    from aipc.ui import app as uiapp

    opts = uiapp.Options(screen="shell", page="settings", software=True,
                         settings_path=tmp / "aipc" / "ui.json")  # fmt: skip
    app, engine, warnings = uiapp.build(opts)
    win = engine.rootObjects()[0]
    w, h = (int(v) for v in a.size.split("x"))
    win.setWidth(w)
    win.setHeight(h)
    page = win.findChild(object, "settingsPage")
    if a.cloud_spent is not None:
        usage = engine._backends["cloudUsage"]
        if usage._b is not None:
            usage._b.record(a.cloud_spent, "chat")
            usage._available = True
            usage.changed.emit()
    a.out.mkdir(parents=True, exist_ok=True)
    report = {}
    for sid in ("look", "face", "voice", "ai", "privacy", "backup"):
        before = len(warnings)
        page.setProperty("section", sid)
        end = time.monotonic() + 0.4  # รอภาพเคลื่อนไหว (200 ms) จบก่อนถ่าย
        while time.monotonic() < end:
            QCoreApplication.processEvents()
        name = f"settings-{a.theme}-{int(a.scale * 100)}-{sid}.png"
        win.grabWindow().save(str(a.out / name))
        report[sid] = [str(x) for x in warnings[before:]]
    print(json.dumps(report, ensure_ascii=False, indent=1))
    uiapp.shutdown(engine)
    return 0 if not any(report.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
