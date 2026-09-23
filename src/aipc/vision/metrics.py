"""ตัวเลขประเมินการจับคู่ใบหน้า: FAR, FRR, EER, threshold ที่ FAR เป้าหมาย, ROC (การ์ด 0005 ข้อ 9).

นิยาม (ใช้ในเล่ม):
- คู่ genuine = ภาพสองภาพของคนเดียวกัน · คู่ impostor = คนละคน
- ที่ threshold t ระบบตอบ "คนเดียวกัน" เมื่อคะแนน ≥ t
- FAR(t) = สัดส่วนคู่ impostor ที่คะแนน ≥ t   (รับคนผิดเข้า — ด้านความปลอดภัย)
- FRR(t) = สัดส่วนคู่ genuine ที่คะแนน < t    (ปฏิเสธเจ้าของ — ด้านความสะดวก)
- EER   = จุดที่ FAR = FRR (ใช้เทียบระบบ ไม่ใช่จุดที่ควรใช้งานจริง)
- ROC   = TAR (= 1 − FRR) เทียบ FAR ทุก threshold

ใช้ numpy ล้วน · เทสต์ด้วยข้อมูลที่รู้คำตอบได้
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Curve:
    thresholds: np.ndarray  # เรียงจากน้อยไปมาก
    far: np.ndarray
    frr: np.ndarray

    @property
    def tar(self) -> np.ndarray:
        return 1.0 - self.frr


def curve(genuine, impostor) -> Curve:
    """คำนวณ FAR/FRR ที่ทุกคะแนนที่มีจริง (ไม่ประมาณด้วยช่วงคงที่)."""
    g = np.sort(np.asarray(genuine, dtype=np.float64))
    i = np.sort(np.asarray(impostor, dtype=np.float64))
    if len(g) == 0 or len(i) == 0:
        raise ValueError("ต้องมีทั้งคู่ genuine และ impostor")
    t = np.unique(np.concatenate([g, i, [np.inf]]))  # inf = ปฏิเสธทุกคู่ (FAR 0, FRR 1)
    # นับจำนวนคู่แล้วค่อยหาร (ไม่ใช้ 1 − สัดส่วน ที่ทำให้ 0.001 กลายเป็น 0.0010000000000000009)
    far = (len(i) - np.searchsorted(i, t, side="left")) / len(i)  # คะแนน ≥ t
    frr = np.searchsorted(g, t, side="left") / len(g)  # คะแนน < t
    return Curve(t, far, frr)


def eer(c: Curve) -> tuple[float, float]:
    """(EER, threshold) · FAR ลดลงและ FRR เพิ่มขึ้นตาม t → หาจุดตัดแล้วประมาณเส้นตรงระหว่างสองจุด."""
    diff = c.far - c.frr  # เริ่มบวก (FAR สูง) แล้วลดลงเป็นลบ
    k = int(np.argmax(diff <= 0))
    if k == 0:
        return float((c.far[0] + c.frr[0]) / 2), float(c.thresholds[0])
    d0, d1 = diff[k - 1], diff[k]
    a = d0 / (d0 - d1) if d0 != d1 else 0.0
    rate = c.far[k - 1] + a * (c.far[k] - c.far[k - 1])
    t1 = c.thresholds[k] if np.isfinite(c.thresholds[k]) else c.thresholds[k - 1]
    return float(rate), float(c.thresholds[k - 1] + a * (t1 - c.thresholds[k - 1]))


def at_far(c: Curve, target: float) -> tuple[float, float, float]:
    """threshold ต่ำสุดที่ FAR ≤ target → (threshold, FAR จริง, FRR ที่จุดนั้น).

    ต่ำสุด = ปฏิเสธเจ้าของน้อยที่สุดโดยยังรักษา FAR ไว้ · ถ้าคู่ impostor น้อยเกิน 1/target
    ค่าที่ได้จะหยาบ (FAR ขั้นละ 1/จำนวนคู่) → รายงานจำนวนคู่ประกอบเสมอ
    """
    ok = np.nonzero(c.far <= target)[0]
    k = int(ok[0])
    return float(c.thresholds[k]), float(c.far[k]), float(c.frr[k])


def rates_at(genuine, impostor, threshold: float) -> tuple[float, float]:
    """(FAR, FRR) ที่ threshold ที่กำหนด (เช่น ค่าใน config ที่ใช้งานจริง)."""
    g = np.asarray(genuine)
    i = np.asarray(impostor)
    far = np.count_nonzero(i >= threshold) / len(i)
    frr = np.count_nonzero(g < threshold) / len(g)
    return float(far), float(frr)


def best_threshold(scores, same) -> float:
    """threshold ที่ถูกมากที่สุด (ตอบ "คนเดียวกัน" เมื่อคะแนน ≥ t) · ลองทุกจุดกึ่งกลางระหว่างคะแนน."""
    s = np.asarray(scores, dtype=np.float64)
    y = np.asarray(same, dtype=bool)
    u = np.unique(s)
    cands = np.concatenate([[u[0] - 1e-6], (u[:-1] + u[1:]) / 2, [u[-1] + 1e-6]])
    acc = [np.mean((s >= t) == y) for t in cands]
    return float(cands[int(np.argmax(acc))])


def kfold_accuracy(scores, same, folds) -> tuple[float, float, list[float]]:
    """ความแม่นยำแบบ k-fold ตามวิธีของ LFW: หา threshold จากชุดอื่น แล้ววัดกับชุดที่เว้นไว้.

    คืน (ค่าเฉลี่ย, ส่วนเบี่ยงเบนมาตรฐาน, threshold ของแต่ละ fold)
    ไม่เลือก threshold จากข้อมูลที่ใช้วัด (ถ้าเลือกจากชุดเดียวกัน ตัวเลขจะดีเกินจริง)
    """
    s = np.asarray(scores, dtype=np.float64)
    y = np.asarray(same, dtype=bool)
    f = np.asarray(folds)
    accs, ths = [], []
    for k in np.unique(f):
        test = f == k
        t = best_threshold(s[~test], y[~test])
        ths.append(t)
        accs.append(float(np.mean((s[test] >= t) == y[test])))
    return float(np.mean(accs)), float(np.std(accs)), ths
