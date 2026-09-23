"""ถ่ายภาพตรวจการ์ด 0002 ข้อ 8: ทุกหน้า × 2 ธีม × ตัวอักษร 100% / 200% รวมเป็นแผ่นเดียวต่อชุด.

รันจาก root ของ repo: python docs/benchmarks/2026-09-24-card0002/make_sheets.py <โฟลเดอร์ผลลัพธ์>
นับเฉพาะ warning ตอนโหลดหน้า (warning ตอนปิดหน้าต่างเป็นปัญหาอีกเรื่อง ดู README ในโฟลเดอร์นี้)
"""

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp()

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter  # noqa: E402

from aipc.ui import app as uiapp  # noqa: E402


def settle(ms: int = 700) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def shoot(screen: str, page: str, theme: str, scale: float):
    d = Path(tempfile.mkdtemp())
    (d / "ui.json").write_text(json.dumps({"theme": theme, "font_scale": scale}))
    opts = uiapp.Options(screen=screen, page=page, software=True, settings_path=d / "ui.json")
    app, engine, warnings = uiapp.build(opts)
    settle()
    win = engine.rootObjects()[0]
    shot = (f"{screen}/{page}", win.grabWindow(), list(warnings))
    win.close()
    uiapp.shutdown(engine)
    QCoreApplication.processEvents()
    return shot


def main(out: Path) -> None:
    cases = [("login", "workspace")] + [("shell", p) for p in uiapp.PAGES]
    for theme in ("light", "dark"):
        for scale in (1.0, 2.0):
            shots = [shoot(screen, page, theme, scale) for screen, page in cases]
            w, h = shots[0][1].width(), shots[0][1].height()
            sheet = QImage(w * 2, h * 4, QImage.Format_RGB32)
            sheet.fill(QColor("#888"))
            p = QPainter(sheet)
            font = QFont()
            font.setPointSize(28)
            p.setFont(font)
            p.setPen(QColor("red"))
            for i, (name, img, warnings) in enumerate(shots):
                x, y = (i % 2) * w, (i // 2) * h
                p.drawImage(x, y, img)
                label = f"{name} {theme} {int(scale * 100)}%"
                label += f" WARN {len(warnings)}" if warnings else ""
                p.drawText(x + 300, y + h - 20, label)
            p.end()
            sheet.scaled(w, h * 2).save(str(out / f"sheet-{theme}-{int(scale * 100)}.png"))
            print(theme, scale, "warnings:", sum(len(s[2]) for s in shots))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
