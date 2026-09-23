"""Align: หมุน/ย่อ/เลื่อนภาพให้ตา จมูก ปาก ไปอยู่ตำแหน่งมาตรฐานในภาพ 112×112 (การ์ด 0005).

โมเดลจดจำหน้า (SFace) ฝึกมากับหน้าที่ถูกจัดตำแหน่งแบบนี้ · ไม่จัดก่อน = คะแนนเพี้ยน
ใช้ similarity transform (หมุน + ย่อขยายเท่ากันทุกทิศ + เลื่อน) ไม่บิดสัดส่วนหน้า
"""

from __future__ import annotations

import numpy as np

SIZE = 112
# ตำแหน่งมาตรฐาน 5 จุดในภาพ 112×112 (ชุดเดียวกับ ArcFace และ OpenCV SFace alignCrop)
# ลำดับเดียวกับ YuNet: ตาขวา(ซ้ายภาพ), ตาซ้าย, จมูก, มุมปากขวา, มุมปากซ้าย
TEMPLATE = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.4648],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


def transform(landmarks) -> np.ndarray:
    """เมทริกซ์ 2×3 ที่ย้าย 5 จุดของภาพไปใกล้ TEMPLATE ที่สุด (least squares).

    เขียนด้วย numpy (วิธี Umeyama) ไม่พึ่ง OpenCV จึงเทสต์ได้ทุกเครื่อง
    """
    src = np.asarray(landmarks, dtype=np.float64).reshape(5, 2)
    dst = TEMPLATE.astype(np.float64)
    src_mean, dst_mean = src.mean(0), dst.mean(0)
    s, d = src - src_mean, dst - dst_mean
    cov = d.T @ s / len(src)
    u, sig, vt = np.linalg.svd(cov)
    sign = np.eye(2)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        sign[1, 1] = -1  # กันการพลิกภาพเป็นกระจก
    rot = u @ sign @ vt
    var = (s**2).sum() / len(src)
    if var < 1e-9:
        raise ValueError("จุดบนหน้าซ้อนกันหมด · จัดตำแหน่งไม่ได้")
    scale = np.trace(np.diag(sig) @ sign) / var
    m = np.zeros((2, 3))
    m[:, :2] = scale * rot
    m[:, 2] = dst_mean - scale * rot @ src_mean
    return m


def apply(m: np.ndarray, points) -> np.ndarray:
    p = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    return p @ m[:, :2].T + m[:, 2]


def crop(frame: np.ndarray, landmarks) -> np.ndarray:
    """ภาพหน้า 112×112 ที่จัดตำแหน่งแล้ว (ใช้ OpenCV warpAffine)."""
    import cv2

    return cv2.warpAffine(frame, transform(landmarks).astype(np.float32), (SIZE, SIZE))
