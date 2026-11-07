"""วัด R2 ของการ์ด 0079: ความจำ 100,000 ข้อ ค้นเร็วแค่ไหน (ต้องรันบน Pi 5 จึงอ้างได้).

    python -m aipc.spikes.memory_bench --n 100000 --out docs/benchmarks/<วันที่>-memory/r2.json

สร้างฐานข้อมูลชั่วคราว (ไม่แตะความจำจริงของผู้ใช้) · ข้อความสังเคราะห์จากคำไทยทั่วไป สุ่มด้วย seed คงที่ ·
วัด: เวลาเปิดไฟล์ · เวลาค้น 200 ครั้ง (median · p95) · ขนาดไฟล์
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

from aipc.chat import memory

WORDS = ("ฉัน ชอบ ไม่ชอบ แพ้ กิน ดื่ม กาแฟ ชา นม ข้าว ไก่ หมู กุ้ง ปู ผัก ผลไม้ แม่ พ่อ ลูก น้อง พี่ เพื่อน "
         "วันเกิด เดือน มีนาคม เมษายน บ้าน รถ สี แดง เขียว น้ำเงิน แมว หมา ทำงาน โรงเรียน หมอ ยา ทุกเช้า "
         "ตอนเย็น วิ่ง ว่ายน้ำ เพลง หนัง หนังสือ ร้าน ตลาด เชียงใหม่ ขอนแก่น ทะเล ภูเขา").split()  # fmt: skip
QUERIES = ("ฉันแพ้อะไร", "ลูกเรียนที่ไหน", "วันเกิดแม่วันไหน", "รถฉันสีอะไร", "ฉันชอบดื่มอะไร",
           "แมวชื่ออะไร", "ร้านที่ชอบอยู่ไหน", "ตอนเย็นทำอะไร")  # fmt: skip


def build(path: Path, n: int, seed: int = 7) -> None:
    rnd = random.Random(seed)
    m = memory.Memory(path, free_bytes=lambda: 10**12)
    db = m._conn()
    batch = []
    for i in range(1, n + 1):
        text = "".join(rnd.choice(WORDS) for _ in range(rnd.randint(4, 9)))
        batch.append((i, text))
        if len(batch) == 5000 or i == n:
            db.executemany(
                "INSERT INTO facts(id, text, created) VALUES (?, ?, '2026-11-07')", batch
            )
            db.executemany("INSERT INTO facts_fts(rowid, grams) VALUES (?, ?)",
                           [(j, memory._tokens(memory._grams(t))) for j, t in batch])  # fmt: skip
            db.commit()
            batch = []
    m.close()


def run(n: int, rounds: int = 200) -> dict:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "memory.db"
        t0 = time.perf_counter()
        build(path, n)
        built = time.perf_counter() - t0
        t0 = time.perf_counter()
        m = memory.Memory(path)
        m.count()  # เปิดไฟล์ + สร้างตารางถ้ายังไม่มี (สิ่งที่แอปทำตอนเริ่ม)
        opened = (time.perf_counter() - t0) * 1000
        times = []
        for i in range(rounds):
            t0 = time.perf_counter()
            m.search(QUERIES[i % len(QUERIES)])
            times.append((time.perf_counter() - t0) * 1000)
        m.close()
        size = path.stat().st_size
    times.sort()
    return {
        "n": n, "rounds": rounds, "build_s": round(built, 1), "open_ms": round(opened, 1),
        "search_median_ms": round(statistics.median(times), 2),
        "search_p95_ms": round(times[int(0.95 * len(times)) - 1], 2),
        "db_mb": round(size / 1024**2, 1),
    }  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.spikes.memory_bench")
    ap.add_argument("--n", type=int, default=100_000)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    res = run(a.n)
    print(json.dumps(res, ensure_ascii=False))
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
