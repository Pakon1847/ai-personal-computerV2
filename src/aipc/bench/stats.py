"""สถิติที่ BRIEF หัวข้อ 9 บังคับให้รายงาน: median และ p95.

ทำไมไม่ใช้ค่าเฉลี่ย (mean): ถ้ามีรอบเดียวที่ช้าผิดปกติ (เช่น เครื่องไปทำงานอื่นแทรก)
ค่าเฉลี่ยจะถูกดึงขึ้นทั้งชุด ส่วน median คือ "ค่าตรงกลาง" ไม่สนว่าค่าสุดโต่งไกลแค่ไหน

p95 คือ "95% ของรอบเร็วกว่าหรือเท่ากับค่านี้" ใช้บอกกรณีแย่ที่ผู้ใช้เจอได้จริง
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


def percentile_nearest_rank(values: list[float], pct: float) -> float:
    """หา percentile แบบ nearest-rank ซึ่งเป็นวิธีที่อธิบายง่ายที่สุด.

    เรียงค่าจากน้อยไปมาก แล้วหยิบตัวที่ลำดับ ceil(pct/100 × n)
    ตัวอย่าง: 5 ค่า, p95 → ceil(4.75) = ลำดับที่ 5 = ค่ามากสุด
    แปลว่าวัดแค่ 5 รอบ p95 ก็คือค่าที่แย่ที่สุดนั่นเอง ต้องเขียนไว้ในเล่มด้วย

    เลือกวิธีนี้เพราะผลเป็นค่าที่วัดได้จริงเสมอ ไม่ใช่ค่าที่ประมาณขึ้นระหว่างสองค่า
    กรรมการตรวจย้อนจากไฟล์ค่าดิบได้ด้วยมือ
    """
    if not values:
        raise ValueError("ต้องมีค่าอย่างน้อย 1 ค่า")
    if not 0 < pct <= 100:
        raise ValueError("pct ต้องอยู่ระหว่าง 0 (ไม่รวม) ถึง 100")
    ordered = sorted(values)
    rank = math.ceil(pct / 100 * len(ordered))
    return ordered[rank - 1]


@dataclass(frozen=True)
class Summary:
    n: int
    median: float
    p95: float
    minimum: float
    maximum: float


def summarize(values: list[float]) -> Summary:
    return Summary(
        n=len(values),
        median=statistics.median(values),
        p95=percentile_nearest_rank(values, 95),
        minimum=min(values),
        maximum=max(values),
    )
