"""python -m aipc.ui [ตัวเลือก]

--screen login|signup|shell     หน้าที่เปิดเป็นหน้าแรก (ค่าเริ่มต้น login)
--page workspace|files|...      หน้าย่อยเมื่อ --screen shell
--theme light|dark              บังคับธีม (ไม่บันทึกทับค่าที่ผู้ใช้ตั้ง)
--dev                           โหมดพัฒนา: เดินหน้าจอได้ครบโดยยังไม่มี backend จริง
--demo-scan found|scanning|unknown|manual   ดูหน้าตาสถานะการสแกนหน้า (เปิดโหมดพัฒนาด้วย)
--screenshot ไฟล์.png           ถ่ายภาพหน้าจอแล้วปิดเอง
--software                      วาดด้วย CPU แทน GPU
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from aipc.ui import app as uiapp


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m aipc.ui")
    p.add_argument("--screen", choices=uiapp.SCREENS, default="login")
    p.add_argument("--page", choices=uiapp.PAGES, default="workspace")
    p.add_argument("--theme", choices=("light", "dark"))
    p.add_argument("--dev", action="store_true")
    p.add_argument("--demo-scan", choices=("found", "scanning", "unknown", "manual"))
    p.add_argument("--signup-step", type=int, default=0, help="0–5 เปิดหน้าสมัครที่ขั้นนี้")
    p.add_argument("--screenshot", type=Path)
    p.add_argument("--software", action="store_true")
    a = p.parse_args(argv)

    if a.screenshot and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"  # ถ่ายภาพได้โดยไม่เปิดหน้าต่างจริง
    opts = uiapp.Options(
        screen=a.screen,
        page=a.page,
        theme=a.theme,
        dev=a.dev,
        demo_scan=a.demo_scan,
        signup_step=a.signup_step,
        software=a.software or bool(a.screenshot),
    )
    app, engine, warnings = uiapp.build(opts, sys.argv[:1])
    if not engine.rootObjects():
        print("\n".join(warnings) or "โหลด QML ไม่สำเร็จ", file=sys.stderr)
        return 1
    if a.screenshot:
        uiapp.screenshot(engine, a.screenshot)
    code = app.exec()
    for w in warnings:
        print("QML:", w, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
