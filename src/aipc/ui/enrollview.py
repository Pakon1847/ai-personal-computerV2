"""ภาพสดตอนลงทะเบียนใบหน้าผ่าน visiond (หน้าสมัคร และสวิตช์ในหน้าตั้งค่า) · Pakon ขอ 2026-09-30.

visiond ส่งสถานะทีละเฟรม (aipc.vision.daemon.enroll_status): คำแนะนำ ท่าที่ได้ ท่าถัดไป หันถึงแค่ไหน
กรอบหน้า และภาพย่อ JPEG แบบกระจก · ที่นี่แปลงเป็น property ให้ QML วาดแบบเดียวกับหน้าตั้งค่า (การ์ด 0010)
เก็บแค่ภาพล่าสุด 1 ภาพในหน่วยความจำ · ไม่เขียนดิสก์ · clear() ล้างทิ้งเมื่องานจบ
QML ดึงภาพด้วย image://<ชื่อ provider>/<previewSerial>
"""

from __future__ import annotations

import base64
import binascii

from PySide6.QtCore import Property, QObject, QSize, Signal
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider


class EnrollView(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self._img: QImage | None = None
        self.clear()

    def clear(self) -> None:
        self._img = None
        self._serial = 0
        self._box: list = []
        self._pose = ""
        self._reach = 0.0
        self._poses: dict = {}
        self._advice = ""
        self.changed.emit()

    def update(self, msg: dict) -> None:
        """เรียกในเธรดหลักเท่านั้น (ผู้เรียกส่งข้ามเธรดด้วย signal มาก่อน)."""
        self._advice = str(msg.get("hint", ""))
        self._poses = dict(msg.get("poses") or {})
        self._pose = str(msg.get("pose", ""))
        self._reach = float(msg.get("reach", 0.0) or 0.0)
        box = msg.get("box") or []
        self._box = [float(v) for v in box] if len(box) == 4 else []
        data = msg.get("jpeg")
        if isinstance(data, str) and data:
            try:
                img = QImage.fromData(base64.b64decode(data, validate=True), "JPG")
            except (binascii.Error, ValueError):
                img = QImage()
            if not img.isNull():
                self._img = img
                self._serial += 1
        self.changed.emit()

    def image(self) -> QImage | None:
        return self._img

    @Property(int, notify=changed)
    def previewSerial(self) -> int:  # noqa: N802
        return self._serial

    @Property(list, notify=changed)
    def faceBox(self) -> list:  # noqa: N802
        return self._box

    @Property(str, notify=changed)
    def currentPose(self) -> str:  # noqa: N802
        return self._pose

    @Property(float, notify=changed)
    def reach(self) -> float:
        return self._reach

    @Property("QVariantMap", notify=changed)
    def poses(self) -> dict:
        return self._poses

    @Property(str, notify=changed)
    def advice(self) -> str:
        return self._advice


class EnrollPreviewProvider(QQuickImageProvider):
    """image://<ชื่อ>/<เลขภาพ> · ไม่มีภาพ = ภาพดำ 1×1 (ไม่ใช่ภาพเก่า)."""

    def __init__(self, view: EnrollView):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._view = view

    def requestImage(self, image_id: str, size: QSize, requested: QSize) -> QImage:  # noqa: N802
        img = self._view.image()
        if img is None:
            img = QImage(1, 1, QImage.Format.Format_RGB888)
            img.fill(0)
        return img
