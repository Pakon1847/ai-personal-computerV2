"""Quality gate: ตรวจภาพก่อนส่งเข้าโมเดล (การ์ด 0005 ข้อ 6).

ภาพที่ไม่ผ่านไม่ถูกส่งต่อ และผู้ใช้ได้คำแนะนำที่ทำตามได้จริง เช่น "ขยับเข้ามาใกล้อีกนิด"
ไม่ใช่แค่ "ไม่ผ่าน" (H5) · เหตุผลเก็บเป็นรหัสภาษาอังกฤษสั้น ๆ เพื่อ log และเทสต์ ส่วนข้อความไทยแยกไว้

มุมหน้า (yaw/pitch) ประมาณจาก 5 จุดของ YuNet เท่านั้น = **ค่าคร่าว ๆ** ไม่ใช่การวัดมุมจริง
พอสำหรับคัด "หันมากเกินไป" แต่ต้องตรวจกับภาพที่รู้มุมจริงก่อนอ้างตัวเลของศาในเล่ม
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from aipc.vision.config import FaceConfig

# ข้อความถึงผู้ใช้ · เรียงตามลำดับที่ควรแก้ก่อน (แก้ข้อแรกแล้วข้ออื่นมักหายตาม)
ADVICE = {
    "no_face": "ไม่พบใบหน้า · มองมาที่กล้อง",
    "outside": "ใบหน้าอยู่ขอบภาพ · ขยับมาตรงกลาง",
    "too_small": "ขยับเข้ามาใกล้อีกนิด",
    "too_dark": "แสงน้อยเกินไป · หาที่สว่างขึ้น",
    "too_bright": "แสงจ้าเกินไป · หลบแสงที่ส่องหน้า",
    "turned": "หันหน้าตรงเข้าหากล้อง",
    "blurry": "อยู่นิ่ง ๆ สักครู่ · ภาพยังเบลอ",
}
ORDER = list(ADVICE)

# ตำแหน่งจมูกตอนหน้าตรง (สัดส่วนจากเส้นตาถึงเส้นปาก) · ค่ากลางจาก LFW 2,000 ภาพ = 0.568
# (5 จุดของ YuNet · 2026-09-24) · ตรงกับกล้องจริงบน Pi 4 คนนั่งหน้าตรง = 0.58
NEUTRAL_NOSE = 0.57
# วัดความคมบนภาพหน้าที่ย่อเป็นขนาดนี้เสมอ → ค่าไม่ขึ้นกับความละเอียดกล้องหรือระยะนั่ง
SHARP_SIZE = 112


@dataclass(frozen=True)
class Face:
    """หน้าที่ YuNet หาเจอ · landmarks = 5 จุดตามลำดับของ YuNet:
    ตาขวา, ตาซ้าย, ปลายจมูก, มุมปากขวา, มุมปากซ้าย (ขวา/ซ้ายของเจ้าของหน้า = ซ้าย/ขวาของภาพ)
    """

    box: tuple[float, float, float, float]  # x, y, กว้าง, สูง (พิกเซล)
    landmarks: tuple[tuple[float, float], ...]
    score: float = 1.0

    @staticmethod
    def from_yunet(row) -> Face:
        """แถวผลลัพธ์ของ cv2.FaceDetectorYN: [x, y, w, h, 5×(x, y), score]."""
        r = [float(v) for v in row]
        return Face(tuple(r[0:4]), tuple((r[4 + 2 * i], r[5 + 2 * i]) for i in range(5)), r[14])


@dataclass(frozen=True)
class Quality:
    ok: bool
    reasons: tuple[str, ...] = ()
    sharpness: float = 0.0
    brightness: float = 0.0
    yaw: float = 0.0
    pitch: float = 0.0
    size: float = 0.0
    extra: dict = field(default_factory=dict)

    @property
    def advice(self) -> str:
        """คำแนะนำข้อแรกที่ควรทำ · ผ่านแล้ว = ''."""
        return ADVICE[self.reasons[0]] if self.reasons else ""

    @property
    def score(self) -> float:
        """ใช้เลือกเฟรมดีสุด: คมกว่า + ตรงกว่า = ดีกว่า (ใช้เทียบเฟรมของคนเดียวกันเท่านั้น)."""
        return self.sharpness / (1.0 + abs(self.yaw) + abs(self.pitch))


def estimate_pose(landmarks) -> tuple[float, float]:
    """(yaw, pitch) เป็นองศาโดยประมาณ · 0, 0 = หน้าตรง.

    yaw: หน้าตรง จมูกอยู่กึ่งกลางระหว่างตา · หันไป จมูกเลื่อนไปทางที่หัน
         ใช้ระยะเลื่อนเทียบระยะห่างตา แล้วแปลงเป็นมุมด้วย asin (จมูกยื่นจากหน้า ~0.5 เท่าของระยะตา)
    pitch: หน้าตรง จมูกอยู่ราว 57% ของทางจากเส้นตาลงไปเส้นปาก · เงย = จมูกขึ้น ก้ม = จมูกลง
           (NEUTRAL_NOSE ปรับจากข้อมูลจริง · เดิมเดา 45% ทำให้หน้าตรงถูกนับว่าก้ม 17°)
    """
    (rex, rey), (lex, ley), (nx, ny), (rmx, rmy), (lmx, lmy) = landmarks
    eye_mid_x, eye_mid_y = (rex + lex) / 2, (rey + ley) / 2
    eye_dist = math.hypot(lex - rex, ley - rey)
    mouth_mid_y = (rmy + lmy) / 2
    if eye_dist < 1e-6 or mouth_mid_y - eye_mid_y < 1e-6:
        return 90.0, 90.0  # จุดซ้อนกัน/กลับหัว = วัดไม่ได้ ถือว่าหันมาก
    yaw = math.degrees(math.asin(max(-1.0, min(1.0, (nx - eye_mid_x) / (0.5 * eye_dist)))))
    ratio = (ny - eye_mid_y) / (mouth_mid_y - eye_mid_y)
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, (ratio - NEUTRAL_NOSE) / 0.45))))
    return yaw, pitch


def _gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img.astype(np.float64)
    b, g, r = img[..., 0], img[..., 1], img[..., 2]  # OpenCV เรียงสีเป็น BGR
    return 0.114 * b + 0.587 * g + 0.299 * r


def sharpness(gray: np.ndarray) -> float:
    """Laplacian variance: ภาพคม = ขอบชัด = ค่าต่างระหว่างพิกเซลข้างเคียงมาก = variance สูง.

    เขียนด้วย numpy (kernel 4 ทิศ แบบเดียวกับ cv2.Laplacian ksize=1) เพื่อเทสต์ได้โดยไม่พึ่ง OpenCV
    """
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    c = gray[1:-1, 1:-1]
    lap = gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:] - 4 * c
    return float(lap.var())


def _resize(gray: np.ndarray, size: int) -> np.ndarray:
    """ย่อ/ขยายเป็น size×size แบบเฉลี่ยพื้นที่ (OpenCV) · หน้าขนาดต่างกันจึงเทียบความคมกันได้."""
    import cv2

    if gray.shape[0] < 2 or gray.shape[1] < 2:
        return gray
    return cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)


def check(frame: np.ndarray, face: Face | None, cfg: FaceConfig) -> Quality:
    """ตรวจคุณภาพของหน้าเดียวในเฟรม · คืนเหตุผลทุกข้อที่ไม่ผ่าน เรียงตามที่ควรแก้ก่อน."""
    if face is None:
        return Quality(False, ("no_face",))
    h_img, w_img = frame.shape[:2]
    x, y, w, h = face.box
    reasons = []

    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(w_img, int(x + w)), min(h_img, int(y + h))
    inside = (x1 - x0) * (y1 - y0) / max(1.0, w * h)
    if inside < 0.9:  # หน้าหลุดขอบภาพเกิน 10%
        reasons.append("outside")
    size = min(w, h)
    if size < cfg.min_face_px:
        reasons.append("too_small")

    crop = _gray(frame[y0:y1, x0:x1]) if x1 > x0 and y1 > y0 else np.zeros((1, 1))
    bright = float(crop.mean())
    if bright < cfg.min_brightness:
        reasons.append("too_dark")
    elif bright > cfg.max_brightness:
        reasons.append("too_bright")

    yaw, pitch = estimate_pose(face.landmarks)
    if abs(yaw) > cfg.max_yaw_deg or abs(pitch) > cfg.max_pitch_deg:
        reasons.append("turned")

    sharp = sharpness(_resize(crop, SHARP_SIZE))
    if sharp < cfg.min_sharpness:
        reasons.append("blurry")

    reasons.sort(key=ORDER.index)
    return Quality(not reasons, tuple(reasons), sharp, bright, yaw, pitch, size)
