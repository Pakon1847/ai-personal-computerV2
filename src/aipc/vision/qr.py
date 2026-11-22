"""อ่าน QR จากภาพ (การ์ด 0080) · ใช้ทั้งรูปในไฟล์ของฉัน และกล้องของ visiond · คืนแค่ข้อความ ไม่เก็บภาพ."""

from __future__ import annotations

from collections.abc import Iterable

# กล้องส่งกลับเฉพาะ QR ของสกิล · QR อื่นในห้อง (ลิงก์ รหัส Wi-Fi) ต้องไม่ถึงโปรแกรมของผู้ใช้
SKILL_PREFIXES = ("AIPC1:", "AIPC2:")


def read_frame(img) -> str:
    """ข้อความใน QR ของภาพนี้ · ไม่เจอ = ""."""
    import cv2

    # ตัวอ่านแบบ Aruco ก่อน: ตัวอ่านปกติของ OpenCV 5.0 อ่าน QR ที่ตัวเองสร้างไม่ได้ 34/211 รูป
    # (ชุดสกิลของการ์ด 0074 · แม้ QR เล็ก) · Aruco อ่านได้ 210/211 (วัด 2026-11-07 บนวินโดวส์)
    for detector in (cv2.QRCodeDetectorAruco(), cv2.QRCodeDetector()):
        text, _points, _ = detector.detectAndDecode(img)
        if text:
            return text
    return ""


def scan(frames: Iterable) -> str:
    """ภาพจากกล้องทีละภาพ → ข้อความของ QR สกิลตัวแรกที่อ่านได้ · หมดเวลาแล้วไม่เจอ = ""."""
    for frame in frames:
        try:
            text = read_frame(frame)
        except Exception:  # noqa: BLE001 · ภาพเสียภาพเดียวต้องไม่ทำให้ visiond ล้ม
            continue
        if text.startswith(SKILL_PREFIXES):
            return text
    return ""
