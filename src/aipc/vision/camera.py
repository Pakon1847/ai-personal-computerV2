"""ทดลองระบบใบหน้ากับกล้องจริงจาก terminal (การ์ด 0005) · ยังไม่ต่อหน้าจอ QML.

    python -m aipc.vision.camera check            เปิดกล้อง ดูว่าเห็นหน้าไหม และคำแนะนำของ quality gate
    python -m aipc.vision.camera enroll           ลงทะเบียนหน้าตัวเอง (ถามความยินยอมก่อน)
    python -m aipc.vision.camera scan [--times N] สแกนเทียบแม่แบบของตัวเอง · จับเวลาจริงตั้งแต่เปิดกล้อง
    python -m aipc.vision.camera delete           ลบแม่แบบใบหน้า (PDPA)

ใช้กับบัญชีของตัวเองเท่านั้น (แม่แบบอยู่ใน home ของผู้ที่รัน) · ต้องยืนยันตัวตนแล้ว = login เข้าเครื่องแล้ว
ไม่บันทึกภาพ · log ผลการสแกนที่ ~/.local/state/aipc/face-scans.log (ไม่มีภาพ ไม่มี embedding)
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from aipc.vision import config, models, pipeline, store

CONSENT_TEXT = """\
ขอความยินยอมเก็บแม่แบบใบหน้า (ข้อมูลชีวภาพ ตาม พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคล มาตรา 26)
- เก็บ: ตัวเลข 128 ค่าที่สรุปจากใบหน้า · ไม่เก็บภาพ
- ใช้ทำ: ระบุบัญชีของคุณที่หน้า Login · รหัสผ่านยังเป็นกุญแจเสมอ
- ที่เก็บ: ไฟล์ใน home ของคุณ อ่านได้เฉพาะคุณ
- ถอนความยินยอม/ลบได้ทุกเมื่อ: python -m aipc.vision.camera delete · ใช้รหัสผ่านเข้าเครื่องได้ตามปกติ
พิมพ์ ยินยอม เพื่อยืนยัน: """


CAPTURE_SIZE = (1280, 720)


def log_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / "aipc" / "face-scans.log"


def find_camera(root: Path) -> int | None:
    """เลขของกล้องตัวแรกที่ไม่ใช่โหนดของชิป (เกณฑ์เดียวกับ aipc.doctor) · ไม่มี = None."""
    from aipc.doctor.hardware import SOC_VIDEO_NODES

    devs = sorted((root / "sys/class/video4linux").glob("video*"),
                  key=lambda d: int(d.name.removeprefix("video") or 0))  # fmt: skip
    for dev in devs:
        name = (dev / "name").read_text().strip() if (dev / "name").exists() else ""
        if name and not name.startswith(SOC_VIDEO_NODES):
            return int(dev.name.removeprefix("video"))
    return None


def open_camera(index: int | None = None):
    """เปิดกล้อง USB/CSI ตัวแรกที่ไม่ใช่โหนดของชิป (ใช้ตัวตรวจเดียวกับ aipc.doctor)."""
    import cv2

    if index is None:
        index = 0
        if sys.platform.startswith("linux"):
            index = find_camera(Path("/"))
            if index is None:
                raise RuntimeError("ไม่พบกล้อง (มีแต่โหนดวิดีโอของชิป) · ต่อกล้อง USB แล้วลองใหม่")
    api = cv2.CAP_V4L2 if sys.platform.startswith("linux") else cv2.CAP_ANY
    cap = cv2.VideoCapture(index, api)
    if not cap.isOpened():
        raise RuntimeError(f"เปิดกล้อง {index} ไม่ได้")
    # ขอ 1280×720 แบบ MJPG (กล้อง USB ส่วนใหญ่ส่งได้เร็วกว่า YUYV มาก) · กล้องไม่รองรับ = ได้ค่าที่กล้องเลือกเอง
    # ที่ 640×480 หน้าคนนั่งระยะปกติเล็กกว่า 112 px (วัดจริงบน Pi 4: 111 px) → ต้องนั่งใกล้เกินไป
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_SIZE[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_SIZE[1])
    return cap


def frames(cap, seconds: float, clock=time.monotonic) -> Iterator:
    """อ่านเฟรมจนหมดเวลา · กล้องให้เฟรมไม่ได้ = หยุด (ไม่วนค้าง)."""
    end = clock() + seconds
    while clock() < end:
        ok, frame = cap.read()
        if not ok:
            return
        yield frame


def build_scanner(cfg: config.FaceConfig) -> pipeline.FaceScanner:
    return pipeline.FaceScanner(models.Detector(cfg.min_detect_score), models.Liveness(),
                                models.Embedder(), cfg)  # fmt: skip


def cmd_check(cap, scanner, seconds: float, out=print) -> int:
    seen = ok = 0
    advice: dict[str, int] = {}
    for frame in frames(cap, seconds):
        seen += 1
        r = scanner.process(frame)
        if r.ok:
            ok += 1
        else:
            advice[r.advice] = advice.get(r.advice, 0) + 1
    out(f"อ่าน {seen} เฟรมใน {seconds:.0f} วิ · ผ่านครบทุกขั้น {ok} เฟรม")
    for text, n in sorted(advice.items(), key=lambda kv: -kv[1]):
        out(f"  {n:4d} × {text}")
    return 0 if seen else 1


def cmd_enroll(cap, scanner, fs: store.FaceStore, seconds: float, ask=input, out=print) -> int:
    answer = ask(CONSENT_TEXT).strip()
    if answer != "ยินยอม":
        out("ไม่ได้ยินยอม · ไม่ได้เก็บอะไร")
        return 1
    given = datetime.now().astimezone().isoformat(timespec="seconds")
    out("มองกล้องตรง ๆ แล้วค่อย ๆ หันซ้ายเล็กน้อย และขวาเล็กน้อย")
    res = scanner.enroll(frames(cap, seconds))
    if isinstance(res, pipeline.Rejected):
        out(f"ลงทะเบียนไม่สำเร็จ: {res.advice}")
        return 1
    fs.save(res.vector, res.frames, res.created, store.Consent(given))
    out(f"ลงทะเบียนแล้ว ({res.frames} เฟรม) · ลบได้ด้วยคำสั่ง delete")
    return 0


def load_templates(folder: Path, out=print) -> dict:
    """แม่แบบทุกคนในโฟลเดอร์ทดสอบ (<รหัส>.json) → {รหัส: เวกเตอร์} · ไฟล์ที่ใช้ไม่ได้ข้ามพร้อมบอก."""
    templates = {}
    for p in sorted(folder.glob("*.json")):
        fs = store.FaceStore(p)
        s = fs.load()
        if s is None:
            out(f"ข้าม {p.name}: {fs.problem}")
        else:
            templates[p.stem] = s.vector
    return templates


def cmd_scan(cap, scanner, fs: store.FaceStore, times: int, seconds: float, out=print,
             templates: dict | None = None, subject: str | None = None) -> int:  # fmt: skip
    """templates = None → เทียบแม่แบบของตัวเอง (1:1) · มี → เทียบทุกคนในชุดทดสอบ (1:N)."""
    if templates is None:
        stored = fs.load()
        if stored is None:
            out(fs.problem or "ยังไม่ได้ลงทะเบียนใบหน้า · ใช้คำสั่ง enroll ก่อน")
            return 1
        templates = {getpass.getuser(): stored.vector}
    if not templates:
        out("ไม่มีแม่แบบให้เทียบ")
        return 1
    log = pipeline.ScanLog(log_path())
    for i in range(times):
        t0 = time.perf_counter()
        res = scanner.scan(frames(cap, seconds), templates)
        wall = (time.perf_counter() - t0) * 1000
        log.write(res, subject)
        verdict = f"รู้จัก: {res.account}" if res.account else f"ไม่ผ่าน: {res.advice}"
        out(f"[{i + 1}/{times}] {verdict} · คะแนน {res.score:.3f} · {res.frames_used} เฟรม · "
            f"เวลาจริง {wall:.0f} ms")  # fmt: skip
    out(f"log: {log.path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.vision.camera")
    ap.add_argument("action", choices=("check", "enroll", "scan", "delete"))
    ap.add_argument("--camera", type=int, help="เลขกล้อง (ไม่ใส่ = หาเอง)")
    ap.add_argument("--seconds", type=float, default=5.0, help="เวลาสูงสุดต่อครั้ง")
    ap.add_argument("--times", type=int, default=10, help="จำนวนครั้งที่สแกน")
    ap.add_argument("--config", type=Path)
    # สำหรับแผนทดสอบกับคนจริง (docs/evaluation/face-protocol.md) · ไม่ใช้ในการใช้งานปกติ
    ap.add_argument("--id", help="enroll: เก็บแม่แบบเป็น <รหัส>.json ในโฟลเดอร์ --against (เช่น P01)")
    ap.add_argument("--against", type=Path, help="โฟลเดอร์แม่แบบของผู้เข้าร่วมทดสอบ (1:N)")
    ap.add_argument("--who", help="scan: รหัสผู้ที่กำลังสแกนจริง บันทึกลง log")
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    if a.id and not a.against:
        print("--id ต้องใช้คู่กับ --against <โฟลเดอร์ทดสอบ>")
        return 2
    fs = store.FaceStore(a.against / f"{a.id}.json") if a.id else store.FaceStore()
    if a.action == "delete":
        print("ลบแม่แบบใบหน้าแล้ว" if fs.delete() else "ไม่มีแม่แบบใบหน้าให้ลบ")
        return 0
    cfg = config.load(a.config)
    try:
        scanner = build_scanner(cfg)
        cap = open_camera(a.camera)
    except (models.ModelError, RuntimeError) as e:
        print(f"ใช้ใบหน้าไม่ได้: {e}")
        return 1
    try:
        if a.action == "check":
            return cmd_check(cap, scanner, a.seconds)
        if a.action == "enroll":
            return cmd_enroll(cap, scanner, fs, max(a.seconds, 15.0))
        templates = load_templates(a.against) if a.against and not a.id else None
        return cmd_scan(cap, scanner, fs, a.times, a.seconds, templates=templates, subject=a.who)
    finally:
        cap.release()


if __name__ == "__main__":
    sys.exit(main())
