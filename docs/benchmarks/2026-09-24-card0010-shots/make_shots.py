"""ภาพตรวจการ์ด 0010: หน้าตั้งค่าขณะลงทะเบียน (จำลองสถานะ ไม่เปิดกล้อง) · 2 ธีม · ท่าซ้าย/เงย."""

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp()

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, QTimer  # noqa: E402

from aipc.ui import app as uiapp  # noqa: E402
from aipc.ui import face as face_mod  # noqa: E402


def settle(ms=500):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def fake_frame():
    img = np.full((720, 1280, 3), (90, 110, 130), np.uint8)
    cv2.ellipse(
        img, (560, 360), (130, 170), 0, 0, 360, (150, 180, 215), -1
    )  # หน้า (อยู่ซ้ายของภาพกล้อง)
    for ex in (515, 605):
        cv2.circle(img, (ex, 320), 12, (40, 40, 40), -1)
    return img


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
for theme in ("light", "dark"):
    for pose in ("left", "up"):
        d = Path(tempfile.mkdtemp())
        (d / "ui.json").write_text(json.dumps({"theme": theme, "font_scale": 1.0}))
        opts = uiapp.Options(
            screen="shell", page="settings", software=True, settings_path=d / "ui.json"
        )
        app, engine, warnings = uiapp.build(opts)
        settle()
        win = engine.rootObjects()[0]
        face = engine.rootContext().contextProperty("face")
        img, frac = face_mod.make_preview(fake_frame(), (430, 190, 260, 340))
        counts = {
            "front": 2,
            "left": 1 if pose == "left" else 2,
            "right": 0 if pose == "left" else 2,
            "up": 0,
            "down": 0,
        }
        face._busy, face._preview_on, face._preview_img = True, True, img
        face._preview_serial, face._face_box, face._poses = 1, frac, counts
        face._advice = face_mod.POSE_PROMPT[pose]
        face.changed.emit()
        face.previewChanged.emit()
        settle(300)
        panel = win.findChild(QObject, "facePanel")
        # เลื่อนหน้าให้เห็นแผงใบหน้า
        flick = panel.parentItem()
        while flick is not None and flick.property("contentY") is None:
            flick = flick.parentItem()
        if flick is not None:
            y = panel.mapToItem(flick.property("contentItem"), 0, 0).y()
            flick.setProperty("contentY", max(0.0, y - 20))
        settle(300)
        win.grabWindow().save(str(out / f"enroll-{theme}-{pose}.png"))
        print(theme, pose, "warnings:", len(warnings), warnings[:3])
        face._busy = False
        face._clear_preview()
        win.close()
        uiapp.shutdown(engine)
        QCoreApplication.processEvents()
