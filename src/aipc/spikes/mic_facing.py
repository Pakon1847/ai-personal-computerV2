"""การ์ด 0056 (ต่อ): หันหน้าเข้าไมค์ vs หันไปด้านข้าง เสียงเบาลงกี่ dB · ประตูใกล้ไมค์ (NEAR_DB) ตัดได้ไหม.

    python -m aipc.spikes.mic_facing [--rounds 5] [--seconds 4] [--out ผล.json]

รันในเซสชันของผู้ใช้ที่นั่งหน้าจอ (ต้องใช้ไมค์ของเซสชันนั้น) · ติ๊กสูง = พูด · ติ๊กต่ำสองครั้ง = เปลี่ยนท่า ·
รอบแรก "หันหน้าเข้าไมค์" · รอบสอง "หันไปด้านข้าง (เหมือนคุยกับคนข้าง ๆ)" · พูดประโยคเดิมทุกครั้ง ·
ไม่เก็บเสียง: อัดลงไฟล์ชั่วคราวใน XDG_RUNTIME_DIR แล้วลบทันทีหลังคำนวณความดัง · ผลมีแค่ตัวเลข
ความดัง = RMS ช่องละ 30 ms แบบเดียวกับ Endpointer · ยอด = ค่าเฉลี่ย 3 ช่องที่ดังสุด (เหมือน _peak)
"""

from __future__ import annotations

import argparse
import array
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

from aipc.voice.stt import NEAR_DB, Endpointer

FRAME = Endpointer.FRAME


def levels(pcm: bytes) -> list[float]:
    a = array.array("h")
    a.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    return [
        (sum(x * x for x in a[i : i + FRAME]) / FRAME) ** 0.5
        for i in range(0, len(a) - FRAME + 1, FRAME)
    ]


def peak_and_floor(lv: list[float]) -> tuple[float, float]:
    """ยอดเสียงพูด (เฉลี่ย 3 ช่องติดกันที่ดังสุด) · พื้นเสียงรอบข้าง (ค่ากลางของ 0.3 วิแรก)."""
    if len(lv) < 13:
        return 0.0, 0.0
    peak = max(sum(lv[i : i + 3]) / 3 for i in range(len(lv) - 2))
    floor = sorted(lv[:10])[5]
    return peak, floor


def db(x: float) -> float:
    return 20 * math.log10(max(x, 1e-9))


def record(seconds: float, folder: Path) -> bytes:
    path = folder / f"facing-{os.getpid()}-{time.monotonic_ns()}.wav"
    cmd = ["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16", str(path)]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(seconds)
    finally:
        p.send_signal(2)
        p.wait(timeout=3)
    try:
        with wave.open(str(path)) as w:
            return w.readframes(w.getnframes())
    finally:
        path.unlink(missing_ok=True)  # ไม่เก็บเสียง


def main(argv: list[str] | None = None) -> int:
    from aipc.ui.handsfree import beep

    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--seconds", type=float, default=4.0)
    ap.add_argument("--lead", type=float, default=15.0, help="รอก่อนเริ่ม (วิ) ให้ผู้ใช้เตรียมตัว")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not shutil.which("pw-record"):
        print("ไม่มี pw-record")
        return 1
    folder = Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir())
    time.sleep(a.lead)
    rows = []
    for pose in ("front", "side"):
        beep(False)
        time.sleep(0.4)
        beep(False)
        time.sleep(2.5)  # ให้เวลาหันตัว
        for k in range(a.rounds):
            beep(True)
            time.sleep(0.15)  # ไม่ให้เสียงติ๊กเข้าไปปนช่วงวัดพื้นเสียง
            peak, floor = peak_and_floor(levels(record(a.seconds, folder)))
            rows.append({"pose": pose, "round": k + 1, "peak_db": round(db(peak), 1),
                         "floor_db": round(db(floor), 1)})  # fmt: skip
            print(
                f"{pose} {k + 1}: ยอด {rows[-1]['peak_db']} dB · พื้น {rows[-1]['floor_db']} dB",
                flush=True,
            )
            time.sleep(1.5)
    beep(False)
    front = sorted(r["peak_db"] for r in rows if r["pose"] == "front")
    ref = front[len(front) // 2]
    side = [r for r in rows if r["pose"] == "side"]
    drops = [round(ref - r["peak_db"], 1) for r in side]
    summary = {"front_median_peak_db": ref, "side_drops_db": drops, "near_db": NEAR_DB,
               "side_cut_by_gate": sum(d >= NEAR_DB for d in drops), "side_n": len(side),
               "floor_median_db": sorted(r["floor_db"] for r in rows)[len(rows) // 2]}  # fmt: skip
    print(json.dumps(summary, ensure_ascii=False))
    if a.out:
        doc = json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1)
        a.out.write_text(doc, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
