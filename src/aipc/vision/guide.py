"""ช่วยผู้ใช้ทำท่าตอนลงทะเบียนใบหน้า (การ์ด 0010) · ไม่ใช้ Qt → ใช้ได้ทั้งหน้าตั้งค่าและ visiond (การ์ด 0015).

ทุกอย่างที่นี่ใช้วาดหน้าจอเท่านั้น ไม่ได้ใช้ตัดสินว่าลงทะเบียนผ่านไหม (pipeline.enroll ตัดสิน)
"""

from __future__ import annotations

POSES = ("front", "left", "right", "up", "down")  # ลำดับที่บอกผู้ใช้ (ตรงกับ pipeline.ENROLL_POSES)
POSE_PROMPT = {
    "front": "มองตรงมาที่กล้อง",
    "left": "หันซ้ายเล็กน้อย",
    "right": "หันขวาเล็กน้อย",
    "up": "เงยหน้าเล็กน้อย",
    "down": "ก้มหน้าเล็กน้อย",
}
PER_POSE = 2  # เท่ากับค่าเริ่มต้นของ pipeline.enroll
PREVIEW_WIDTH = 480


def pose_reach(pose: str, yaw: float, pitch: float) -> float:
    """หันไปทางท่าเป้าหมายได้แค่ไหน 0–1 (1 = ถึงเกณฑ์นับท่าแล้ว).

    ทิศเดียวกับ pipeline.pose_of: yaw > 0 = ผู้ใช้หันซ้าย · pitch > 0 = ก้ม
    """
    from aipc.vision.pipeline import POSE_SPLIT_DEG as split

    along = {"left": yaw, "right": -yaw, "up": -pitch, "down": pitch}
    if pose == "front":  # อยู่ในกรอบ ±split = เต็ม · หันเกินออกไปเท่าไร แถบลดลงเท่านั้น
        return max(0.0, min(1.0, 2 - max(abs(yaw), abs(pitch)) / split))
    return max(0.0, min(1.0, along.get(pose, 0.0) / split))


def next_pose(counts: dict) -> str:
    """ท่าถัดไปที่ยังไม่ครบ ตามลำดับที่บอกผู้ใช้ · ครบหมด = "" ."""
    return next((p for p in POSES if counts.get(p, 0) < PER_POSE), "")


def advice(r, counts: dict) -> str:
    """เฟรมไม่ผ่าน = วิธีแก้จาก quality gate · ผ่าน = บอกท่าถัดไป."""
    if r.advice:
        return r.advice
    return POSE_PROMPT.get(next_pose(counts)) or "ดีมาก · ค้างไว้อย่างนี้"


def mirror(frame, box):
    """เฟรม BGR → (ภาพย่อกว้าง 480 กลับซ้ายขวาแบบกระจก (BGR), กรอบหน้าเป็นสัดส่วน 0–1 หลังกลับด้าน หรือ [])."""
    import cv2

    h, w = frame.shape[:2]
    small_h = max(1, round(h * PREVIEW_WIDTH / w))
    small = cv2.flip(cv2.resize(frame, (PREVIEW_WIDTH, small_h), interpolation=cv2.INTER_AREA), 1)
    frac = []
    if box is not None:
        x, y, bw, bh = (float(v) for v in box)
        frac = [(w - x - bw) / w, y / h, bw / w, bh / h]
    return small, frac


def preview_jpeg(frame, box, quality: int = 70) -> tuple[bytes, list]:
    """ภาพย่อสำหรับส่งข้าม socket (visiond → หน้าสมัคร) · อยู่ในหน่วยความจำ ไม่เขียนดิสก์."""
    import cv2

    small, frac = mirror(frame, box)
    ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return (buf.tobytes() if ok else b""), frac
