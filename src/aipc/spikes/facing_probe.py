"""การ์ด 0058 ขั้น 0 (ก่อนสร้าง): หันเข้าจอ vs หันข้าง มุมหน้า (yaw) ต่างกันชัดไหม ·
YuNet 5 ภาพ/วิ ใช้ CPU เท่าไร.

    AIPC_MODEL_DIR=/opt/aipc-v2/models python -m aipc.spikes.facing_probe [--out ผล.json]

รันในเซสชันของผู้ใช้ที่นั่งหน้าจอ · ติ๊กต่ำสองครั้ง = เปลี่ยนท่า · ติ๊กสูง = ทำท่านั้นค้างไว้ 3 วิ ·
รอบแรก หันหน้าเข้าจอ · รอบสอง หันไปด้านข้างเหมือนคุยกับคนข้าง ๆ · ไม่เก็บภาพ (เก็บแค่มุมและเวลา) ·
มุม = quality.estimate_pose (ค่าคร่าว ๆ จาก 5 จุดของ YuNet) ·
CPU = เวลา CPU ของโปรเซสนี้ / เวลาจริง (1.0 = 1 คอร์เต็ม)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from aipc.vision import camera, config, models, quality


def main(argv: list[str] | None = None) -> int:
    from aipc.ui.handsfree import beep

    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--hold", type=float, default=3.0)
    ap.add_argument("--fps", type=float, default=5.0)
    ap.add_argument("--lead", type=float, default=15.0)
    ap.add_argument("--size", default="", help="ขนาดภาพ เช่น 640x480 (ว่าง = ค่าของ open_camera)")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cfg = config.load(None)
    det = models.Detector(cfg.min_detect_score)
    cap = camera.open_camera()
    if a.size:  # รอบ 2: ภาพเล็กลง = ถอดรหัสเร็วขึ้น (YuNet ย่อเหลือด้านยาว 640 อยู่แล้ว)
        import cv2

        w, h = (int(v) for v in a.size.split("x"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    rows, cpu_parts = [], []
    try:
        for _ in camera.frames(cap, camera.WARMUP_SECONDS):  # กล้องปรับแสง
            pass
        time.sleep(max(0.0, a.lead - camera.WARMUP_SECONDS))
        for pose in ("front", "side"):
            beep(False)
            time.sleep(0.4)
            beep(False)
            time.sleep(2.5)
            for k in range(a.rounds):
                beep(True)
                time.sleep(0.3)
                yaws, seen, n = [], 0, 0
                w0, c0 = time.monotonic(), time.process_time()
                next_at = w0
                while time.monotonic() - w0 < a.hold:
                    # รอบ 2: grab() = ดึงภาพจากกล้องโดยไม่ถอดรหัส MJPG · ถอดเฉพาะภาพที่ใช้ (รอบ 1 ถอดทุกภาพ
                    # ~30 ภาพ/วิ ที่ 1280×720 → CPU 52% ของ 1 คอร์)
                    if not cap.grab():
                        break
                    if time.monotonic() < next_at:
                        continue  # ทิ้งภาพที่ไม่ใช้ ให้ภาพที่ตรวจเป็นภาพล่าสุดเสมอ
                    next_at += 1.0 / a.fps
                    ok, frame = cap.retrieve()
                    if not ok:
                        break
                    n += 1
                    found = [r for r in det.detect(frame) if float(r[14]) >= cfg.min_detect_score]
                    if found:
                        seen += 1
                        face = quality.Face.from_yunet(found[0])
                        yaws.append(round(quality.estimate_pose(face.landmarks)[0], 1))
                wall, cpu = time.monotonic() - w0, time.process_time() - c0
                cpu_parts.append(cpu / wall if wall else 0.0)
                yaws.sort()
                med = yaws[len(yaws) // 2] if yaws else None
                share = cpu / wall if wall else 0.0
                rows.append({"pose": pose, "round": k + 1, "frames": n, "seen": seen,
                             "yaw_median": med, "yaws": yaws,
                             "cpu_core": round(share, 3)})  # fmt: skip
                print(f"{pose} {k + 1}: เห็นหน้า {seen}/{n} · yaw ค่ากลาง {med} · "
                      f"CPU {share:.0%} ของ 1 คอร์", flush=True)  # fmt: skip
                time.sleep(1.0)
        beep(False)
    finally:
        cap.release()

    def abs_meds(pose):
        return sorted(
            abs(r["yaw_median"]) for r in rows if r["pose"] == pose and r["yaw_median"] is not None
        )

    summary = {"front_abs_yaw": abs_meds("front"), "side_abs_yaw": abs_meds("side"),
               "side_not_seen": sum(r["yaw_median"] is None for r in rows if r["pose"] == "side"),
               "cpu_core_mean": round(sum(cpu_parts) / len(cpu_parts), 3) if cpu_parts else None,
               "fps": a.fps}  # fmt: skip
    print(json.dumps(summary, ensure_ascii=False))
    if a.out:
        doc = json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1)
        a.out.write_text(doc, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
