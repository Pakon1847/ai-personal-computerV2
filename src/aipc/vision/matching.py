"""เลือกเฟรม เฉลี่ย embedding และจับคู่ 1:N (การ์ด 0005 ข้อ 6).

embedding = เวกเตอร์ตัวเลขที่ SFace สรุปจากใบหน้า · หน้าคนเดียวกัน → เวกเตอร์ชี้ทางใกล้กัน
ทำให้ยาวเท่ากับ 1 (L2-normalize) แล้ว cosine similarity = ผลคูณจุด (dot) ธรรมดา
ช่วงค่า -1 ถึง 1 · ยิ่งสูงยิ่งเหมือน

1:N ใช้สองเงื่อนไข (BRIEF): คะแนนอันดับหนึ่ง ≥ threshold **และ** ห่างจากอันดับสอง ≥ margin
ข้อสองกันกรณีสองบัญชีหน้าคล้ายกัน (เช่น พี่น้อง) ที่คะแนนผ่านทั้งคู่ → ไม่เดา ให้ผู้ใช้พิมพ์ชื่อแทน
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def l2_normalize(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(v))
    if n < 1e-12 or not np.isfinite(n):
        raise ValueError("embedding เป็นศูนย์หรือไม่ใช่ตัวเลข · ใช้จับคู่ไม่ได้")
    return v / n


def average(vectors) -> np.ndarray:
    """เฉลี่ยหลายเฟรม: normalize ทีละตัวก่อน (ให้ทุกเฟรมมีน้ำหนักเท่ากัน) แล้ว normalize ผลรวมอีกครั้ง."""
    vs = [l2_normalize(v) for v in vectors]
    if not vs:
        raise ValueError("ไม่มี embedding ให้เฉลี่ย")
    if len({v.shape for v in vs}) != 1:
        raise ValueError("embedding ขนาดไม่เท่ากัน")
    return l2_normalize(np.mean(vs, axis=0))


def cosine(a, b) -> float:
    return float(np.dot(l2_normalize(a), l2_normalize(b)))


def select_best(items, key, k_min: int, k_max: int) -> list:
    """เลือกของที่ดีที่สุด k_max ชิ้นตาม key · ได้ไม่ถึง k_min = คืน [] (ยังไม่พอตัดสิน)."""
    ranked = sorted(items, key=key, reverse=True)[:k_max]
    return ranked if len(ranked) >= k_min else []


@dataclass(frozen=True)
class Match:
    account: str | None  # None = ไม่ระบุตัว
    score: float  # คะแนนอันดับหนึ่ง
    second: float  # คะแนนอันดับสอง (ไม่มี = -1)
    reason: str  # matched | no_templates | below_threshold | ambiguous

    @property
    def ok(self) -> bool:
        return self.account is not None


def match(query, templates: dict[str, np.ndarray], threshold: float, margin: float) -> Match:
    """หาเจ้าของหน้าจากแม่แบบทุกบัญชี · ไม่เจอหรือไม่แน่ใจ = account None พร้อมเหตุผล."""
    if not templates:
        return Match(None, -1.0, -1.0, "no_templates")
    q = l2_normalize(query)
    scores = sorted(((cosine(q, t), name) for name, t in templates.items()), reverse=True)
    best, who = scores[0]
    second = scores[1][0] if len(scores) > 1 else -1.0
    if best < threshold:
        return Match(None, best, second, "below_threshold")
    if best - second < margin:
        return Match(None, best, second, "ambiguous")
    return Match(who, best, second, "matched")
