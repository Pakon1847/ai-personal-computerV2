"""แชร์สกิลด้วย QR (การ์ด 0080 ทาง ค · QR ก่อน) · ไม่มีเซิร์ฟเวอร์ ไม่ออกเน็ต.

ส่ง: ไฟล์ .md ของสกิล → บีบอัด (zlib) → base64 → ข้อความ "AIPC1:…" → รูป QR
  (OpenCV มีตัวสร้าง/อ่าน QR อยู่แล้ว · ไม่เพิ่ม dependency)
รับ: รูปที่มี QR (ถ่ายจากจอเพื่อน หรือไฟล์ PNG ที่ได้มา) → อ่านกลับเป็น .md →
  **ผ่านด่านและหน้าตรวจก่อนติดตั้งเหมือนไฟล์ทุกครั้ง** (H1 · การ์ด 0074)
QR ใส่ได้ ~2,300 ตัวอักษร (ระดับแก้ผิด M) · สกิลทั่วไป ~1,800 ไบต์ บีบแล้วเหลือ ~800 ตัวอักษร
"""

from __future__ import annotations

import base64
import binascii
import zlib
from pathlib import Path

PREFIX = "AIPC1:"  # รุ่นของรูปแบบ · เปลี่ยนวิธีเข้ารหัสเมื่อไหร่ = AIPC2
MAX_PAYLOAD = 2300  # ตัวอักษรใน QR (ความจุสูงสุดของ QR รุ่น 40 ระดับ M ≈ 2,331 ไบต์)
MAX_MD = 64 * 1024  # แตกไฟล์ได้ไม่เกินนี้ (กันข้อมูลที่บีบมาให้แตกเป็นไฟล์ใหญ่มาก)
SCALE = 8  # 1 จุดของ QR = 8 พิกเซล


class ShareError(ValueError):
    """เหตุผลภาษาคน."""


def encode(skill_md: str) -> str:
    packed = base64.urlsafe_b64encode(zlib.compress(skill_md.encode("utf-8"), 9)).decode("ascii")
    text = PREFIX + packed
    if len(text) > MAX_PAYLOAD:
        raise ShareError(
            f"สกิลนี้ใหญ่เกิน QR 1 รูป ({len(text)} จาก {MAX_PAYLOAD} ตัวอักษร) · ใช้ “ส่งออกเป็นไฟล์” แทน"
        )
    return text


def decode(text: str) -> str:
    if not text.startswith(PREFIX):
        raise ShareError("QR นี้ไม่ใช่สกิลของผู้ช่วย")
    try:
        # validate=True: ตัวอักษรนอกชุด base64 = เสีย (ค่าเริ่มต้นของ Python ทิ้งเงียบ ๆ แล้วได้ข้อมูลว่าง)
        raw = base64.b64decode(text[len(PREFIX) :].encode("ascii"), altchars=b"-_", validate=True)
        d = zlib.decompressobj()
        md = d.decompress(raw, MAX_MD)
        if d.unconsumed_tail:
            raise ShareError("สกิลใน QR ใหญ่ผิดปกติ · ไม่อ่านต่อ")
        if not md or not d.eof:
            raise ValueError("ข้อมูลไม่ครบ")
        return md.decode("utf-8")
    except (binascii.Error, zlib.error, UnicodeError, ValueError) as e:
        if isinstance(e, ShareError):
            raise
        raise ShareError("อ่าน QR ได้แต่ข้อมูลเสีย · ให้เพื่อนสร้าง QR ใหม่") from e


def qr_image(skill_md: str):
    """รูป QR (numpy · ขาวดำ · มีขอบขาว 4 จุดตามมาตรฐาน)."""
    import cv2

    p = cv2.QRCodeEncoder_Params()
    p.correction_level = cv2.QRCODE_ENCODER_CORRECT_LEVEL_M  # แก้ผิดได้ ~15% (ถ่ายจากจอ/ภาพเบลอเล็กน้อย)
    img = cv2.QRCodeEncoder.create(p).encode(encode(skill_md))
    img = cv2.resize(img, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_NEAREST)
    pad = 4 * SCALE
    return cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)


def write_png(skill_md: str, path: Path) -> None:
    import cv2

    ok, buf = cv2.imencode(".png", qr_image(skill_md))
    if not ok:
        raise ShareError("สร้างรูป QR ไม่ได้")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.tobytes())  # ไม่ใช้ cv2.imwrite: วินโดวส์เขียน path ภาษาไทยไม่ได้


def read_image(path: Path) -> str:
    """รูปที่มี QR → ไฟล์ .md ของสกิล · ไม่เจอ/ไม่ใช่ = ShareError."""
    import cv2
    import numpy as np

    data = np.frombuffer(Path(path).read_bytes(), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ShareError("เปิดรูปนี้ไม่ได้")
    # ตัวอ่านแบบ Aruco ก่อน: ตัวอ่านปกติของ OpenCV 5.0 อ่าน QR ที่ตัวเองสร้างไม่ได้ 34/211 รูป
    # (ชุดสกิลของการ์ด 0074 · แม้ QR เล็ก) · Aruco อ่านได้ 210/211 (วัด 2026-11-07 บนวินโดวส์)
    text = ""
    for detector in (cv2.QRCodeDetectorAruco(), cv2.QRCodeDetector()):
        text, _points, _ = detector.detectAndDecode(img)
        if text:
            break
    if not text:
        raise ShareError("ไม่พบ QR ในรูปนี้ · ถ่ายให้เห็น QR ทั้งรูป ชัด ๆ แล้วลองใหม่")
    return decode(text)
