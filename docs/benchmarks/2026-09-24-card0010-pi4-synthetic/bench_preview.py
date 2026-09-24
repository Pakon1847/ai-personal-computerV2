"""การ์ด 0010: ต้นทุนของภาพสดบน Pi — ไม่เปิดกล้อง ไม่ใช้หน้าคนจริง (ใช้ภาพ LFW แทนกล้อง).

    cd ~/aipc && QT_QPA_PLATFORM=offscreen ./.venv/bin/python <ไฟล์นี้> <โฟลเดอร์ภาพ LFW>

ส่วน A: ต่อเฟรม — เวลา pipeline.process เทียบกับเวลา make_preview (งานที่ภาพสดเพิ่ม)
ส่วน B: FaceController จริง + โมเดลจริง + "กล้อง" ที่ส่งภาพ LFW ทุก 33 ms (เหมือนกล้อง 30 ภาพ/วิ)
        ลงทะเบียน 10 วิ (ภาพหน้าตรงอย่างเดียว จึงไม่ครบ 5 ท่า → วิ่งจนหมดเวลา) · นับภาพสด/วิ และ RSS
        **PAD ถูกข้ามเฉพาะส่วน B:** รอบแรก PAD ปฏิเสธภาพ LFW (ภาพถ่ายขยาย) ว่าไม่ใช่หน้าจริงใน 3 เฟรม
        ซึ่งถูกต้อง แต่ทำให้วัดอัตราภาพไม่ได้ · ยังรันโมเดล PAD ทุกเฟรมเท่าเดิม แค่ไม่ใช้ผลตัดสิน
        แม่แบบ/log ทั้งหมดอยู่ในโฟลเดอร์ชั่วคราว ไม่แตะของผู้ใช้
"""

import json
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication

from aipc.ui import face as face_mod
from aipc.vision import camera, config, store


def rss_mb() -> float:
    for line in open("/proc/self/status"):
        if line.startswith("VmRSS"):
            return int(line.split()[1]) / 1024
    return -1.0


def canvas(path: Path) -> np.ndarray:
    """ภาพ LFW 250×250 → ขยาย 2.4 เท่า วางกลางภาพ 1280×720 (หน้ากว้าง ~200 px เหมือนนั่งหน้ากล้อง)."""
    img = cv2.imread(str(path))
    big = cv2.resize(img, (600, 600))
    out = np.full((720, 1280, 3), 90, np.uint8)
    out[60:660, 340:940] = big
    return out


def median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2]


class AlwaysLive:
    """ห่อ PAD จริง: ยังรันโมเดลทุกเฟรม (เวลาเท่าเดิม) แต่คืนค่า "หน้าจริง" เสมอ · ใช้วัดผลเท่านั้น."""

    def __init__(self, real):
        self.real = real

    def score(self, frame, box):
        self.real.score(frame, box)
        return 1.0


class ReplayCap:
    def __init__(self, frames, period=1 / 30):
        self.frames, self.period, self.i = frames, period, 0

    def read(self):
        time.sleep(self.period)
        self.i += 1
        return True, self.frames[self.i % len(self.frames)]

    def release(self):
        pass


def main(folder: Path) -> None:
    frames = [canvas(p) for p in sorted(folder.glob("*.jpg"))[:20]]
    result = {"frames": len(frames)}

    # ---------- A: ต่อเฟรม ----------
    scanner = camera.build_scanner(config.load(None))
    for f in frames[:3]:  # warm-up
        scanner.process(f)
    proc, prev, ok = [], [], 0
    for _ in range(5):
        for f in frames:
            t = time.perf_counter()
            r = scanner.process(f)
            proc.append((time.perf_counter() - t) * 1000)
            ok += r.ok
            t = time.perf_counter()
            face_mod.make_preview(f, r.box)
            prev.append((time.perf_counter() - t) * 1000)
    result["A"] = {
        "process_ms_median": round(median(proc), 1),
        "preview_ms_median": round(median(prev), 2),
        "preview_share_pct": round(100 * median(prev) / median(proc), 1),
        "frames_ok": ok,
        "n": len(proc),
    }
    del scanner
    face_mod.release_memory()

    # ---------- B: FaceController จริง ----------
    app = QGuiApplication.instance() or QGuiApplication([])
    tmp = Path(tempfile.mkdtemp(prefix="aipc-0010-"))
    fs = store.FaceStore(tmp / "face.json")

    def build():
        sc = camera.build_scanner(config.load(None))
        sc.liveness = AlwaysLive(sc.liveness)
        return sc

    fc = face_mod.FaceController(fs=fs, open_camera=lambda: ReplayCap(frames), build_scanner=build,
                                 enroll_seconds=10, enroll_log=tmp / "enroll.log",
                                 scan_log=tmp / "scans.log")  # fmt: skip
    serials, peak = [], 0.0

    def on_preview():
        if fc.previewSerial:
            serials.append(time.monotonic())

    fc.previewChanged.connect(on_preview)
    before = rss_mb()
    fc.startEnroll(True)
    while fc.busy:
        QCoreApplication.processEvents()
        peak = max(peak, rss_mb())
        time.sleep(0.02)
    for _ in range(20):
        QCoreApplication.processEvents()
        time.sleep(0.02)
    after = rss_mb()
    span = serials[-1] - serials[0] if len(serials) > 1 else 0
    log = json.loads((tmp / "enroll.log").read_text(encoding="utf-8").splitlines()[-1])
    result["B"] = {
        "previews": len(serials),
        "preview_fps": round((len(serials) - 1) / span, 2) if span else 0,
        "enroll_log": log,
        "rss_before_mb": round(before, 1),
        "rss_peak_mb": round(peak, 1),
        "rss_after_mb": round(after, 1),
        "template_written": fs.path.exists(),
        "message": fc.message,
    }
    print(json.dumps(result, ensure_ascii=False, indent=1))
    app.quit()


if __name__ == "__main__":
    main(Path(sys.argv[1]))
