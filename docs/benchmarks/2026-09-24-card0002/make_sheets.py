# ถ่ายภาพตรวจการ์ด 0002 ข้อ 8: ทุกหน้า × 2 ธีม × ตัวอักษร 100% / 200% แล้วรวมเป็นแผ่นเดียวต่อชุด
import json, os, sys, tempfile
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp()
from PySide6.QtCore import QEventLoop, QTimer, QCoreApplication
from PySide6.QtGui import QImage, QPainter, QColor, QFont
from aipc.ui import app as uiapp
out = Path(sys.argv[1])
def settle(ms=700):
    l = QEventLoop(); QTimer.singleShot(ms, l.quit); l.exec()
cases = [("login", "workspace")] + [("shell", p) for p in uiapp.PAGES]
for theme in ("light", "dark"):
    for scale in (1.0, 2.0):
        imgs = []
        for screen, page in cases:
            d = Path(tempfile.mkdtemp()); (d / "ui.json").write_text(json.dumps({"theme": theme, "font_scale": scale}))
            app, engine, warns = uiapp.build(uiapp.Options(screen=screen, page=page, software=True, settings_path=d / "ui.json"))
            settle()
            win = engine.rootObjects()[0]
            imgs.append((f"{screen}/{page}", win.grabWindow(), list(warns)))
            win.close(); engine.deleteLater(); QCoreApplication.processEvents()
        w, h = imgs[0][1].width(), imgs[0][1].height()
        sheet = QImage(w * 2, h * 4, QImage.Format_RGB32); sheet.fill(QColor("#888"))
        p = QPainter(sheet)
        for i, (name, im, warns) in enumerate(imgs):
            x, y = (i % 2) * w, (i // 2) * h
            p.drawImage(x, y, im)
            p.setPen(QColor("red")); f = QFont(); f.setPointSize(28); p.setFont(f)
            p.drawText(x + 300, y + h - 20, f"{name} {theme} {int(scale*100)}%" + (f" WARN {len(warns)}" if warns else ""))
        p.end()
        sheet.scaled(w, h * 2).save(str(out / f"sheet-{theme}-{int(scale*100)}.png"))
        print(theme, scale, "warnings:", sum(len(x[2]) for x in imgs))
