"""ทดลองระบบใบหน้ากับกล้องจริงจาก terminal (การ์ด 0005) · ยังไม่ต่อหน้าจอ QML.

    python -m aipc.vision.camera test [--snap F]  ทดสอบกล้องอย่างเดียว ไม่ต้องมีโมเดล (การ์ด 0011)
    python -m aipc.vision.camera check            เปิดกล้อง ดูว่าเห็นหน้าไหม และคำแนะนำของ quality gate
    python -m aipc.vision.camera enroll           ลงทะเบียนหน้าตัวเอง 5 ท่า (ถามความยินยอมก่อน)
    python -m aipc.vision.camera compare          เทียบแม่แบบ 3 ท่า กับ 5 ท่า (การ์ด 0010 · ไม่บันทึกแม่แบบ)
    python -m aipc.vision.camera scan [--times N] สแกนเทียบแม่แบบของตัวเอง · จับเวลาจริงตั้งแต่เปิดกล้อง
    python -m aipc.vision.camera delete           ลบแม่แบบใบหน้า (PDPA)

ใช้กับบัญชีของตัวเองเท่านั้น (แม่แบบอยู่ใน home ของผู้ที่รัน) · ต้องยืนยันตัวตนแล้ว = login เข้าเครื่องแล้ว
ไม่บันทึกภาพ · log ผลการสแกนที่ ~/.local/state/aipc/face-scans.log (ไม่มีภาพ ไม่มี embedding)
(ยกเว้น test --snap ที่สั่งบันทึกภาพ 1 ใบเอง)
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


ENROLL_SECONDS = 40.0  # 5 ท่า (การ์ด 0010) · เดิม 3 ท่า 20 วิ
ENROLL_HINT = "มองตรง แล้วค่อย ๆ หันซ้าย หันขวา เงยหน้า และก้มหน้า เล็กน้อยทีละท่า"


def log_path(name: str = "face-scans.log") -> Path:
    base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / "aipc" / name


def enroll_log_path() -> Path:
    return log_path("face-enroll.log")


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
        try:
            ok, frame = cap.read()
        except Exception as e:  # noqa: BLE001 · cv2.error
            # T11 บน Pi 5 (2026-09-30 21:43–00:22): กล้องส่งภาพ MJPG ว่าง → cv2.error
            # "!buf.empty()" หลุดออกไป
            # คำขอสแกนตายกลางทาง ผู้เรียกได้แค่ "unavailable" → แปลงเป็น RuntimeError =
            # "ใช้กล้องไม่ได้" ตามปกติ
            raise RuntimeError(f"กล้องส่งภาพเสีย ({type(e).__name__})") from e
        if not ok:
            return
        yield frame


WARMUP_SECONDS = 1.0  # ช่วงกล้องปรับแสงอัตโนมัติ · ไม่นับในผลวัด
DARK, BRIGHT = 50, 205  # ความสว่างเฉลี่ย 0–255 ที่ถือว่ามืด/สว่างเกิน


def _fourcc(cap) -> str:
    """รูปแบบภาพที่กล้องส่งจริง เช่น MJPG · อ่านไม่ได้ = "?"."""
    import cv2

    code = int(cap.get(cv2.CAP_PROP_FOURCC)) if hasattr(cap, "get") else 0
    text = "".join(chr((code >> 8 * i) & 0xFF) for i in range(4))
    return text if text.isprintable() and text.strip() else "?"


def cmd_test(cap, seconds: float, snap: Path | None = None, out=print, clock=time.monotonic) -> int:
    """ทดสอบกล้องอย่างเดียว (การ์ด 0011) · รายงานค่าที่กล้องให้จริง · ไม่เขียนดิสก์ถ้าไม่สั่ง --snap."""
    import cv2

    skipped = sum(1 for _ in frames(cap, WARMUP_SECONDS, clock))
    n, last, start = 0, None, clock()
    for frame in frames(cap, seconds, clock):
        n, last = n + 1, frame
    elapsed = clock() - start
    if last is None:
        out(
            f"กล้องเปิดได้แต่ไม่ได้ภาพเลย (อุ่นเครื่องได้ {skipped} เฟรม) · "
            "ลองถอดเสียบใหม่ หรือปิดโปรแกรมอื่นที่ใช้กล้องอยู่"
        )
        return 1
    h, w = last.shape[:2]
    brightness = float(last.mean())
    out(f"ภาพ {w}×{h} · {_fourcc(cap)} · ทิ้ง {skipped} เฟรมแรก (ปรับแสง)")
    out(f"อ่าน {n} เฟรมใน {elapsed:.1f} วิ = {n / elapsed if elapsed > 0 else 0:.1f} ภาพ/วิ")
    note = (
        " · มืดไป เปิดไฟหรือหันกล้องออกจากหน้าต่าง"
        if brightness < DARK
        else (" · สว่างเกิน" if brightness > BRIGHT else "")
    )
    out(f"ความสว่างเฉลี่ย {brightness:.0f}/255{note}")
    if snap is not None:
        try:
            if not cv2.imwrite(str(snap), last):
                raise OSError("OpenCV เขียนไฟล์ไม่ได้ (นามสกุลต้องเป็น .jpg/.png)")
            out(f"บันทึกภาพ 1 ใบที่ {snap} · ลบเองเมื่อไม่ใช้แล้ว")
        except OSError as e:
            out(f"บันทึกภาพไม่ได้: {e}")
    return 0


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
    out(ENROLL_HINT)
    t0 = time.monotonic()
    res = scanner.enroll(frames(cap, seconds))
    pipeline.EnrollLog(enroll_log_path()).write(res, time.monotonic() - t0)
    if isinstance(res, pipeline.Rejected):
        out(f"ลงทะเบียนไม่สำเร็จ: {res.advice}")
        return 1
    fs.save(res.vector, res.frames, res.created, store.Consent(given))
    out(f"ลงทะเบียนแล้ว ({res.frames} เฟรม) · ลบได้ด้วยคำสั่ง delete")
    return 0


COMPARE_SETS = {"3": ("front", "left", "right"), "5": ("front", "left", "right", "up", "down")}


def cmd_compare(cap, scanner, cfg, times: int, seconds: float, ask=input, out=print) -> int:
    """การ์ด 0010 ข้อ 8: ลงทะเบียน 5 ท่าครั้งเดียว → แม่แบบ 3 ท่า และ 5 ท่า ในหน่วยความจำ →
    สแกน `times` ครั้ง ให้คะแนนการสแกนครั้งเดียวกันกับทั้งสองแม่แบบ · log เฉพาะคะแนน ไม่บันทึกแม่แบบ
    """
    import json

    from aipc.vision import matching

    if ask(CONSENT_TEXT).strip() != "ยินยอม":
        out("ไม่ได้ยินยอม · ไม่ได้เก็บอะไร")
        return 1
    out(ENROLL_HINT)
    res = scanner.enroll(frames(cap, ENROLL_SECONDS))
    if isinstance(res, pipeline.Rejected) or any(p not in res.by_pose for p in COMPARE_SETS["5"]):
        out("ต้องได้ครบ 5 ท่าจึงจะเทียบได้ · ลองใหม่")
        return 1
    tpl = {k: matching.average([e for p in poses for e in res.by_pose[p]])
           for k, poses in COMPARE_SETS.items()}  # fmt: skip
    rows = []
    for i in range(times):
        r = scanner.scan(frames(cap, seconds), {"me": tpl["3"]})
        if r.probe is None:
            out(f"[{i + 1}/{times}] สแกนไม่ได้: {r.advice}")
            rows.append({"i": i + 1, "s3": None, "s5": None, "reason": r.reason})
            continue
        s = {k: round(matching.cosine(r.probe, v), 4) for k, v in tpl.items()}
        rows.append({"i": i + 1, "s3": s["3"], "s5": s["5"], "reason": r.reason})
        out(f"[{i + 1}/{times}] 3 ท่า {s['3']:.3f} · 5 ท่า {s['5']:.3f}")
    done = [x for x in rows if x["s3"] is not None]
    summary = {}
    for k in COMPARE_SETS:
        scores = [x[f"s{k}"] for x in done]
        summary[k] = {
            "matched": sum(v >= cfg.match_threshold for v in scores),
            "mean": round(sum(scores) / len(scores), 4) if scores else None,
        }
    use5 = bool(done) and (summary["5"]["matched"] >= summary["3"]["matched"]
                           and summary["5"]["mean"] >= summary["3"]["mean"])  # fmt: skip
    entry = {
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scans": rows,
        "summary": summary,
        "threshold": cfg.match_threshold,
        "five_not_worse": use5,
    }
    path = log_path("face-compare.log")
    pipeline._append_line(path, json.loads(json.dumps(entry)))
    for k in COMPARE_SETS:
        out(f"{k} ท่า: รู้จัก {summary[k]['matched']}/{len(done)} · คะแนนเฉลี่ย {summary[k]['mean']}")
    out("ผล: 5 ท่า ไม่แย่กว่า 3 ท่า" if use5 else "ผล: 5 ท่า แย่กว่า 3 ท่า → แม่แบบใช้ 3 ท่าต่อ")
    out(f"log: {path}")
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
        # --who ในโหมดเทียบตัวเอง = ชื่อของแม่แบบด้วย → ป้ายใน log ตรงกัน (report นับถูกคน/ผิดคนได้)
        templates = {subject or getpass.getuser(): stored.vector}
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
    ap.add_argument("action", choices=("test", "check", "enroll", "scan", "delete", "compare"))
    ap.add_argument("--camera", type=int, help="เลขกล้อง (ไม่ใส่ = หาเอง)")
    ap.add_argument("--seconds", type=float, help="เวลาสูงสุดต่อครั้ง (test 3 วิ · อื่น ๆ 5 วิ)")
    ap.add_argument("--times", type=int, default=10, help="จำนวนครั้งที่สแกน")
    ap.add_argument("--config", type=Path)
    ap.add_argument("--snap", type=Path, help="test: บันทึกภาพสุดท้าย 1 ใบ (ไม่ใส่ = ไม่เขียนดิสก์)")
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
    if a.action == "test":
        try:
            cap = open_camera(a.camera)
        except RuntimeError as e:
            print(f"ใช้กล้องไม่ได้: {e}")
            return 1
        try:
            return cmd_test(cap, a.seconds or 3.0, a.snap)
        finally:
            cap.release()
    a.seconds = a.seconds or 5.0
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
            return cmd_enroll(cap, scanner, fs, max(a.seconds, ENROLL_SECONDS))
        if a.action == "compare":
            return cmd_compare(cap, scanner, cfg, a.times, a.seconds)
        templates = load_templates(a.against) if a.against and not a.id else None
        return cmd_scan(cap, scanner, fs, a.times, a.seconds, templates=templates, subject=a.who)
    finally:
        cap.release()


if __name__ == "__main__":
    sys.exit(main())
