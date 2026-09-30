"""ภาพสดตอนลงทะเบียนผ่าน visiond (EnrollView) · Pakon ขอให้เห็นหน้าตัวเอง 2026-09-30."""

import base64
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtGui import QGuiApplication, QImage

    from aipc.ui.enrollview import EnrollPreviewProvider, EnrollView
except ImportError:  # pragma: no cover
    EnrollView = None


def jpeg_b64(w=48, h=27) -> str:
    img = QImage(w, h, QImage.Format.Format_RGB888)
    img.fill(0x336699)
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "JPG")
    return base64.b64encode(bytes(data)).decode("ascii")


@unittest.skipIf(EnrollView is None, "ไม่มี PySide6")
class EnrollViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_frame_from_visiond_becomes_image_and_guides(self):
        v = EnrollView()
        v.update({"hint": "หันซ้ายเล็กน้อย", "poses": {"front": 2}, "pose": "left", "reach": 0.5,
                  "box": [0.1, 0.2, 0.3, 0.4], "jpeg": jpeg_b64()})  # fmt: skip
        self.assertEqual(v.previewSerial, 1)
        self.assertEqual((v.currentPose, v.reach, v.advice), ("left", 0.5, "หันซ้ายเล็กน้อย"))
        self.assertEqual(v.faceBox, [0.1, 0.2, 0.3, 0.4])
        img = EnrollPreviewProvider(v).requestImage("1", None, None)
        self.assertEqual((img.width(), img.height()), (48, 27))

    def test_bad_image_is_ignored_and_clear_forgets_the_face(self):
        v = EnrollView()
        v.update({"jpeg": jpeg_b64()})
        v.update({"jpeg": "ไม่ใช่ base64"})
        self.assertEqual(v.previewSerial, 1, "ภาพเสียไม่เปลี่ยนภาพที่แสดง")
        v.clear()
        self.assertEqual(v.previewSerial, 0)
        self.assertIsNone(v.image())
        img = EnrollPreviewProvider(v).requestImage("0", None, None)
        self.assertEqual((img.width(), img.height()), (1, 1), "หลังจบงานไม่มีภาพหน้าค้าง")


if __name__ == "__main__":
    unittest.main()
