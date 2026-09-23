"""วัดเวลาแต่ละขั้นของระบบใบหน้าและ RAM บนเครื่องที่รัน (การ์ด 0005 ข้อ 8).

    python -m aipc.vision.bench <โฟลเดอร์ภาพ> [--limit 200] [--rounds 5] [--out ผล.json]

ใช้ภาพจากไฟล์ (ไม่ใช่กล้อง) เพื่อให้ทุกเครื่องได้งานเดียวกันทุกภาพ → เทียบ Pi 4 / Pi 5 ได้
รอบแรกเป็น warm-up ไม่นับ (BRIEF หัวข้อ 9) · รายงาน median/p95 ต่อขั้น + RAM สูงสุดของโปรเซส
อุณหภูมิและ throttle อ่านจาก aipc.bench.machine (ค่าเดียวกับเครื่องมือวัดหลัก)
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

import numpy as np

from aipc.bench import machine
from aipc.vision import align, evaluate, models, quality
from aipc.vision.config import FaceConfig


def peak_rss_mb() -> float | None:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    return None


def pct(values, q):
    return round(float(np.percentile(values, q)), 1) if values else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.vision.bench")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--limit", type=int, default=200, help="จำนวนภาพ")
    ap.add_argument("--rounds", type=int, default=5, help="จำนวนรอบที่นับ (ไม่รวม warm-up 1 รอบ)")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--sface", choices=("fp32", "int8"), default="fp32", help="รุ่นของ SFace")
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    import cv2

    cfg = FaceConfig()
    paths = [p for ps in evaluate.list_people(a.folder).values() for p in ps][: a.limit]
    images = [img for img in (cv2.imread(str(p)) for p in paths) if img is not None]
    rss_before = peak_rss_mb()
    t = time.perf_counter()
    det, live = models.Detector(cfg.min_detect_score), models.Liveness()
    emb = models.Embedder(a.sface)
    load_ms = (time.perf_counter() - t) * 1000
    rss_models = peak_rss_mb()

    steps = {k: [] for k in ("detect", "quality", "liveness", "align", "embed", "total")}
    temps = []
    for rnd in range(a.rounds + 1):
        for img in images:
            t0 = time.perf_counter()
            rows = det.detect(img)
            t1 = time.perf_counter()
            if not rows:
                continue
            f = quality.Face.from_yunet(rows[0])
            quality.check(img, f, cfg)
            t2 = time.perf_counter()
            live.score(img, f.box)
            t3 = time.perf_counter()
            crop = align.crop(img, f.landmarks)
            t4 = time.perf_counter()
            emb.embed(crop)
            t5 = time.perf_counter()
            if rnd == 0:
                continue  # warm-up
            spans = ((t0, t1), (t1, t2), (t2, t3), (t3, t4), (t4, t5), (t0, t5))
            for k, (s, e) in zip(steps, spans, strict=True):
                steps[k].append((e - s) * 1000)
        temps.append(machine.cpu_temp_c())

    res = {
        "machine": f"{platform.machine()} · {machine.board_model() or platform.platform()}",
        "python": sys.version.split()[0], "opencv": cv2.__version__,
        "sface": a.sface, "images": len(images), "rounds_counted": a.rounds, "warmup_rounds": 1,
        "per_frame_ms": {k: {"median": round(statistics.median(v), 1), "p95": pct(v, 95)}
                         for k, v in steps.items() if v},
        "model_load_ms": round(load_ms, 1),
        "peak_rss_mb": {"before_models": rss_before, "after_models": rss_models,
                        "end": peak_rss_mb()},
        "cpu_temp_c_per_round": temps,
        "throttled": machine.throttled_raw(),
        "note": "ต่อเฟรมเดียว · การสแกนจริงใช้ 3–5 เฟรม + เวลาเปิดกล้อง · ภาพจากไฟล์ ไม่ใช่กล้อง",
    }  # fmt: skip
    text = json.dumps(res, ensure_ascii=False, indent=2)
    if a.out:
        a.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
