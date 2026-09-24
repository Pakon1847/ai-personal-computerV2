"""ค่าตั้งของระบบใบหน้า · ทุกค่าตัดสินผ่าน/ไม่ผ่านอยู่ที่นี่ที่เดียว (การ์ด 0005 ข้อ 6).

ค่าเริ่มต้นเป็น "จุดเริ่ม" ไม่ใช่ค่าที่พิสูจน์แล้ว · threshold/margin ต้อง calibrate จาก evaluate.py
ค่าเกณฑ์คุณภาพ (blur, ความสว่าง) ต้องตรวจกับกล้องจริงบน Pi
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path


@dataclass(frozen=True)
class FaceConfig:
    # --- quality gate (ข้อกำหนดที่ Pakon ส่งมา) ---
    min_face_px: int = 112  # ด้านสั้นของกล่องหน้า ≥ ขนาดที่โมเดลรับ ไม่ต้องขยายภาพ
    min_sharpness: float = 60.0  # Laplacian variance ของหน้า · ต่ำ = เบลอ (จุดเริ่ม ต้องตรวจกับกล้องจริง)
    min_brightness: float = 60.0  # ค่าเฉลี่ยความสว่าง 0–255 ของหน้า
    max_brightness: float = 200.0
    max_yaw_deg: float = 25.0  # หันซ้าย/ขวา
    max_pitch_deg: float = 25.0  # ก้ม/เงย
    # --- ตรวจหน้า / PAD ---
    min_detect_score: float = 0.8  # ความมั่นใจของ YuNet
    liveness_threshold: float = 0.8  # คะแนน "หน้าจริง" ของ MiniFASNet · ต่ำกว่า = ปฏิเสธทันที
    # --- หลายเฟรม ---
    min_frames: int = 3
    max_frames: int = 5
    # --- จับคู่ ---
    match_threshold: float = 0.363  # cosine · ค่าเริ่มต้นของ OpenCV SFace (BRIEF: ใช้เป็นจุดเริ่มเท่านั้น)
    match_margin: float = 0.05  # ต้องห่างจากคนอันดับสองอย่างน้อยเท่านี้ ไม่งั้น "ไม่แน่ใจ"
    # --- ลงทะเบียน (การ์ด 0010) ---
    # ผู้ใช้ทำครบ 5 ท่าเสมอ แต่แม่แบบใช้เฉพาะท่านี้ · เพิ่มเงย/ก้มได้หลังผลเทียบ 3 vs 5 ท่าเท่านั้น
    template_poses: tuple = ("front", "left", "right")

    def validate(self) -> FaceConfig:
        checks = [
            (self.min_face_px >= 32, "min_face_px ต้อง ≥ 32"),
            (0 <= self.min_brightness < self.max_brightness <= 255, "ช่วงความสว่างต้องอยู่ใน 0–255"),
            (0 < self.max_yaw_deg <= 90 and 0 < self.max_pitch_deg <= 90, "มุมต้องอยู่ใน 0–90"),
            (0 <= self.min_detect_score <= 1, "min_detect_score ต้องอยู่ใน 0–1"),
            (0 <= self.liveness_threshold <= 1, "liveness_threshold ต้องอยู่ใน 0–1"),
            (1 <= self.min_frames <= self.max_frames, "ต้อง 1 ≤ min_frames ≤ max_frames"),
            (-1 <= self.match_threshold <= 1, "match_threshold ต้องอยู่ใน -1–1"),
            (0 <= self.match_margin <= 2, "match_margin ต้องอยู่ใน 0–2"),
            (
                "front" in self.template_poses
                and set(self.template_poses) <= {"front", "left", "right", "up", "down"},
                "template_poses ต้องมี front และใช้ได้แค่ front/left/right/up/down",
            ),
        ]
        bad = [msg for ok, msg in checks if not ok]
        if bad:
            raise ValueError("ค่าตั้งใบหน้าไม่ถูกต้อง: " + " · ".join(bad))
        return self


def load(path: Path | None) -> FaceConfig:
    """อ่านไฟล์ JSON ที่ใส่เฉพาะค่าที่อยากเปลี่ยน · ไม่มีไฟล์ = ค่าเริ่มต้น.

    ชื่อที่ไม่รู้จักถือว่าผิด (พิมพ์ชื่อผิดแล้วเงียบ = ค่าที่คิดว่าตั้งไว้ไม่มีผลจริง)
    """
    cfg = FaceConfig()
    if path is None or not path.exists():
        return cfg
    data = json.loads(path.read_text(encoding="utf-8"))
    known = {f.name: f.type for f in fields(FaceConfig)}
    unknown = sorted(set(data) - set(known))
    if unknown:
        raise ValueError(f"ไม่รู้จักค่าตั้ง: {', '.join(unknown)}")
    casts = {"int": int, "float": float, "tuple": lambda v: tuple(str(x) for x in v)}
    cast = {k: casts[known[k]](v) for k, v in data.items()}
    return replace(cfg, **cast).validate()


def to_dict(cfg: FaceConfig) -> dict:
    return asdict(cfg)
