"""ใบหน้าในหน้าตั้งค่า (การ์ด 0006, 0010): ลงทะเบียน · ทดลองสแกน · ลบ · สำหรับเจ้าของเซสชันเท่านั้น.

กล้องและโมเดลทำงานในเธรดแยก หน้าจอไม่ค้าง (นาฬิกายังเดิน) · ผลส่งกลับเธรดหลักผ่าน signal
(Qt ต่อแบบ queued ให้เองเมื่อส่งจากเธรดอื่น) · หน้าจอไม่ได้ embedding (H7)

ภาพสดขณะลงทะเบียน (การ์ด 0010): ใช้เฟรมเดียวกับที่ pipeline วิเคราะห์ ไม่เปิดกล้องซ้ำ · ย่อกว้าง 480 px
กลับซ้ายขวาเหมือนกระจก · เก็บแค่ภาพล่าสุด 1 ภาพในหน่วยความจำ ไม่เขียนดิสก์ · จบงานแล้วล้างทิ้งทันที
QML ดึงภาพผ่าน image://face/<previewSerial> (FacePreviewProvider)

- ไม่ยินยอม = ไม่เปิดกล้องเลย (PDPA ม.26, H3)
- เสร็จ/ยกเลิก/กล้องหลุด = ปิดกล้องและปล่อยโมเดลทันที (คืน RAM ~130 MB · H4)
- ยกเลิกหรือกล้องหลุดกลางทาง = ไม่บันทึกอะไร
- ไม่มีโมดูลใบหน้า (ไม่ได้ติดตั้ง extra "vision") หรืออยู่ในหน้า Login → state "unavailable" ไม่ล่ม
"""

from __future__ import annotations

import ctypes
import gc
import getpass
import sys
import threading
import time
from datetime import datetime

from PySide6.QtCore import Property, QObject, QSize, Signal, Slot
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider

POSES = ("front", "left", "right", "up", "down")  # ลำดับที่บอกผู้ใช้ (ตรงกับ pipeline.ENROLL_POSES)
POSE_PROMPT = {
    "front": "มองตรงมาที่กล้อง",
    "left": "หันซ้ายเล็กน้อย",
    "right": "หันขวาเล็กน้อย",
    "up": "เงยหน้าเล็กน้อย",
    "down": "ก้มหน้าเล็กน้อย",
}
PER_POSE = 2  # เท่ากับค่าเริ่มต้นของ pipeline.enroll
PREVIEW_WIDTH = 480


def make_preview(frame, box):
    """เฟรม BGR (numpy) → (QImage ย่อ กลับซ้ายขวา, กรอบหน้าเป็นสัดส่วน 0–1 หลังกลับด้าน หรือ []).

    สร้างใน QImage ที่ copy ข้อมูลแล้ว (ไม่อ้างหน่วยความจำของ numpy ที่จะถูกทิ้ง) · ไม่มีการเขียนไฟล์
    """
    import cv2

    h, w = frame.shape[:2]
    small_h = max(1, round(h * PREVIEW_WIDTH / w))
    small = cv2.resize(frame, (PREVIEW_WIDTH, small_h), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(cv2.flip(small, 1), cv2.COLOR_BGR2RGB)
    img = QImage(rgb.data, PREVIEW_WIDTH, small_h, 3 * PREVIEW_WIDTH, QImage.Format.Format_RGB888)
    frac = []
    if box is not None:
        x, y, bw, bh = (float(v) for v in box)
        frac = [(w - x - bw) / w, y / h, bw / w, bh / h]  # กลับซ้ายขวาให้ตรงกับภาพ
    return img.copy(), frac


def pose_reach(pose: str, yaw: float, pitch: float) -> float:
    """หันไปทางท่าเป้าหมายได้แค่ไหน 0–1 (1 = ถึงเกณฑ์นับท่าแล้ว) · ใช้วาดแถบบนจอเท่านั้น ไม่ได้ใช้ตัดสิน.

    ทิศเดียวกับ pipeline.pose_of: yaw > 0 = ผู้ใช้หันซ้าย · pitch > 0 = ก้ม
    """
    from aipc.vision.pipeline import POSE_SPLIT_DEG as split

    along = {"left": yaw, "right": -yaw, "up": -pitch, "down": pitch}
    if pose == "front":  # อยู่ในกรอบ ±split = เต็ม · หันเกินออกไปเท่าไร แถบลดลงเท่านั้น
        return max(0.0, min(1.0, 2 - max(abs(yaw), abs(pitch)) / split))
    return max(0.0, min(1.0, along.get(pose, 0.0) / split))


def next_pose(counts: dict) -> str:
    """ท่าถัดไปที่ยังไม่ครบ ตามลำดับที่บอกผู้ใช้ · ครบหมด = "" ."""
    return next((p for p in POSES if counts.get(p, 0) < PER_POSE), "")


def release_memory() -> None:
    """คืนหน่วยความจำที่ปล่อยแล้วให้ระบบ (Linux).

    วัดจริงบน Pi 4 (การ์ด 0006): โหลดโมเดลในเธรดแยกแล้วปล่อย โมเดลถูกลบจริง แต่ RSS ไม่ลด
    เพราะ glibc เก็บหน่วยความจำที่คืนแล้วไว้ใน pool ของเธรดนั้น · malloc_trim(0) สั่งให้คืนระบบ
    (ผลทดลอง: 139 → 96 MB และนิ่งทุกรอบ) · เครื่องอื่นที่ไม่ใช่ glibc = ไม่ทำอะไร
    """
    gc.collect()
    if not sys.platform.startswith("linux"):
        return
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):  # libc อื่น (เช่น musl) ไม่มีฟังก์ชันนี้
        pass


class FaceController(QObject):
    changed = Signal()
    finished = Signal(bool, str)
    # ส่งจากเธรดงาน → เธรดหลัก (ห้ามแตะสถานะที่ QML อ่านจากเธรดงานตรง ๆ)
    _progress = Signal(str, "QVariantMap")
    _done = Signal(bool, str)
    _preview = Signal(list, float)
    previewChanged = Signal()  # แยกจาก changed: เปลี่ยนทุกเฟรม ไม่ต้องให้ทุกอย่างบนหน้าคำนวณใหม่

    def __init__(self, active: bool = True, fs=None, open_camera=None, build_scanner=None,
                 enroll_seconds: float = 40.0, scan_seconds: float = 5.0,
                 enroll_log=None, scan_log=None):  # fmt: skip
        super().__init__()
        self._active = active
        self._state = "unavailable"
        self._problem = ""
        self._enrolled_at = ""
        self._consent_version = ""
        self._busy = False
        self._advice = ""
        self._poses: dict = {}
        self._message = ""
        self._stop = threading.Event()
        self._camera_lost = False
        self._lock = threading.Lock()
        self._last_frame = None  # เฟรมล่าสุดที่เธรดงานอ่าน (ใช้ทำภาพสด) · ล้างเมื่องานจบ
        self._preview_on = False
        self._preview_img: QImage | None = None
        self._preview_serial = 0
        self._face_box: list = []
        self._reach = 0.0
        self._frames_seen = 0
        self._thread: threading.Thread | None = None
        self._enroll_seconds, self._scan_seconds = enroll_seconds, scan_seconds
        self._progress.connect(self._on_progress)
        self._done.connect(self._on_done)
        self._preview.connect(self._on_preview)
        self._fs = fs
        self._open_camera = open_camera
        self._build_scanner = build_scanner
        self._enroll_log_path = enroll_log
        self._scan_log_path = scan_log
        if active:
            self._setup()
        self.refresh()

    def _setup(self) -> None:
        try:
            from aipc.vision import camera, config, store
        except ImportError as e:  # ไม่ได้ติดตั้ง extra "vision"
            self._active = False
            self._problem = f"ยังใช้ไม่ได้ในเครื่องนี้ (ไม่มีโมดูลใบหน้า: {e.name})"
            return
        self._fs = self._fs or store.FaceStore()
        self._enroll_log_path = self._enroll_log_path or camera.enroll_log_path()
        self._scan_log_path = self._scan_log_path or camera.log_path()
        self._open_camera = self._open_camera or camera.open_camera
        if self._build_scanner is None:
            self._build_scanner = lambda: camera.build_scanner(config.load(None))

    # ---------- สถานะที่ QML อ่าน ----------
    @Property(str, notify=changed)
    def state(self) -> str:
        return self._state

    @Property(str, notify=changed)
    def problem(self) -> str:
        return self._problem

    @Property(str, notify=changed)
    def enrolledAt(self) -> str:  # noqa: N802
        return self._enrolled_at

    @Property(str, notify=changed)
    def consentVersion(self) -> str:  # noqa: N802
        return self._consent_version

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=changed)
    def advice(self) -> str:
        return self._advice

    @Property("QVariantMap", notify=changed)
    def poses(self) -> dict:
        return self._poses

    @Property(str, notify=changed)
    def message(self) -> str:
        return self._message

    @Property(str, notify=changed)
    def currentPose(self) -> str:  # noqa: N802
        return next_pose(self._poses) if self._busy and self._preview_on else ""

    @Property(int, notify=previewChanged)
    def previewSerial(self) -> int:  # noqa: N802
        return self._preview_serial

    @Property(list, notify=previewChanged)
    def faceBox(self) -> list:  # noqa: N802
        return self._face_box

    @Property(float, notify=previewChanged)
    def reach(self) -> float:
        """ความคืบหน้าไปยังท่าปัจจุบัน 0–1 (ให้ผู้ใช้รู้ว่าต้องหัน/ก้มอีกแค่ไหน)."""
        return self._reach

    def preview_image(self) -> QImage | None:
        """ภาพล่าสุด (เรียกจาก ImageProvider) · ไม่มี = None."""
        with self._lock:
            return self._preview_img

    @Property(str, constant=True)
    def consentText(self) -> str:  # noqa: N802
        try:
            from aipc.vision.camera import CONSENT_TEXT
        except ImportError:
            return ""
        return CONSENT_TEXT.rsplit("\n", 1)[0]  # ตัดบรรทัด "พิมพ์ ยินยอม" (หน้าจอใช้ปุ่มแทน)

    # ---------- คำสั่งจาก QML ----------
    @Slot()
    def refresh(self) -> None:
        if not self._active:
            self._state = "unavailable"
        else:
            try:
                stored = self._fs.load()
            except Exception as e:  # noqa: BLE001 — หน้าจอต้องเปิดได้เสมอ แม้ไฟล์แม่แบบแปลกแค่ไหน (พบ 2026-09-28)
                self._state, self._problem = "broken", f"อ่านแม่แบบใบหน้าไม่ได้ ({e}) · ลงทะเบียนใหม่ได้"
                self.changed.emit()
                return
            if stored is not None:
                self._state = "enrolled"
                self._enrolled_at = stored.created
                self._consent_version = stored.consent.version
                self._problem = ""
            elif self._fs.problem:
                self._state, self._problem = "broken", self._fs.problem
            else:
                self._state, self._enrolled_at, self._consent_version = "none", "", ""
        self.changed.emit()

    @Slot(bool, result=bool)
    def startEnroll(self, consented: bool) -> bool:  # noqa: N802
        if self._busy or not self._active:
            return False
        if not consented:
            self._finish_now(False, "ไม่ได้ยินยอม · ไม่ได้เปิดกล้องและไม่ได้เก็บอะไร")
            return False
        given = datetime.now().astimezone().isoformat(timespec="seconds")
        return self._start(self._enroll_job, given)

    @Slot(result=bool)
    def tryScan(self) -> bool:  # noqa: N802
        if self._busy or self._state != "enrolled":
            return False
        return self._start(self._scan_job, self._fs.load())

    @Slot()
    def cancel(self) -> None:
        self._stop.set()

    @Slot(result=bool)
    def deleteTemplate(self) -> bool:  # noqa: N802
        if self._busy or not self._active:
            return False
        removed = self._fs.delete()
        self.refresh()
        self._finish_now(True, "ลบแม่แบบใบหน้าแล้ว" if removed else "ไม่มีแม่แบบใบหน้าให้ลบ")
        return removed

    # ---------- งานในเธรดแยก ----------
    def _start(self, job, arg) -> bool:
        self._busy, self._message, self._advice, self._poses = True, "", "กำลังเปิดกล้อง…", {}
        self._stop.clear()
        self._camera_lost = False
        self._preview_on = job == self._enroll_job  # ภาพสดเฉพาะตอนลงทะเบียน (การ์ด 0010)
        self._frames_seen = 0
        self.changed.emit()
        self._thread = threading.Thread(target=self._run, args=(job, arg), daemon=True)
        self._thread.start()
        return True

    def _run(self, job, arg) -> None:
        cap = scanner = None
        try:
            scanner = self._build_scanner()
            cap = self._open_camera()
            ok, msg = job(scanner, cap, arg)
        except Exception as e:  # noqa: BLE001 — ทุกความผิดพลาดต้องกลับมาบอกผู้ใช้ ไม่ใช่เธรดตายเงียบ (H2)
            ok, msg = False, f"ใช้ใบหน้าไม่ได้: {e}"
        finally:
            if cap is not None:
                cap.release()
            self._last_frame = None  # ไม่ถือภาพจากกล้องค้างไว้หลังงานจบ
            del scanner  # ปล่อยโมเดล
            release_memory()  # แล้วคืนหน่วยความจำให้ระบบจริง (H4)
        self._done.emit(ok, msg)

    def _frames(self, cap, seconds: float):
        end = time.monotonic() + seconds
        while time.monotonic() < end and not self._stop.is_set():
            ok, frame = cap.read()
            if not ok:
                self._camera_lost = True
                return
            self._last_frame = frame
            self._frames_seen += 1
            yield frame

    def _enroll_log(self):
        from aipc.vision import pipeline

        return pipeline.EnrollLog(self._enroll_log_path)

    def _report(self, r, counts) -> None:
        # เฟรมผ่านแล้ว = บอกท่าถัดไป · ไม่ผ่าน = บอกวิธีแก้จาก quality gate
        if r.advice:
            advice = r.advice
        elif self._preview_on:
            advice = POSE_PROMPT.get(next_pose(counts)) or "ดีมาก · ค้างไว้อย่างนี้"
        else:
            advice = "ดีมาก · ค้างไว้อย่างนี้"
        self._progress.emit(advice, dict(counts))
        frame = self._last_frame
        if self._preview_on and frame is not None:
            img, frac = make_preview(frame, getattr(r, "box", None))
            q = getattr(r, "quality", None)
            target = next_pose(counts)
            reach = pose_reach(target, q.yaw, q.pitch) if q is not None and frac else 0.0
            with self._lock:
                self._preview_img = img
            self._preview.emit(frac, reach)

    def _enroll_job(self, scanner, cap, given: str):
        from aipc.vision import pipeline, store

        t0 = time.monotonic()
        res = scanner.enroll(self._frames(cap, self._enroll_seconds), progress=self._report)
        cut = "cancelled" if self._stop.is_set() else "camera_lost" if self._camera_lost else ""

        # log ทุกครั้ง รวมที่ไม่สำเร็จ พร้อมเหตุผล (การ์ด 0010 ข้อ 5) · ไม่มีภาพ ไม่มี embedding
        # เขียนหลังรู้ผลจริงเท่านั้น: เดิมเขียน "enrolled" ก่อนบันทึกแม่แบบ (พบ 2026-09-28)
        def log(result, how=""):
            try:
                self._enroll_log().write(result, time.monotonic() - t0, how, self._frames_seen)
            except OSError:
                pass  # log เขียนไม่ได้ต้องไม่ทำให้การลงทะเบียนที่สำเร็จแล้วเสีย

        if cut == "cancelled":
            log(None, cut)
            return False, "ยกเลิกแล้ว · ไม่ได้บันทึกอะไร"
        if cut == "camera_lost":
            log(None, cut)
            return False, "กล้องหลุด · ไม่ได้บันทึกอะไร"
        if isinstance(res, pipeline.Rejected):
            log(res)
            return False, f"ลงทะเบียนไม่สำเร็จ: {res.advice}"
        try:
            self._fs.save(res.vector, res.frames, res.created, store.Consent(given))
        except OSError as e:
            log(res, "save_failed")
            return False, f"ลงทะเบียนไม่สำเร็จ: บันทึกแม่แบบไม่ได้ ({e.strerror or e})"
        log(res)
        return True, f"ลงทะเบียนแล้ว ({res.frames} เฟรม)"

    def _scan_job(self, scanner, cap, stored):
        from aipc.vision import pipeline

        who = getpass.getuser()
        res = scanner.scan(self._frames(cap, self._scan_seconds), {who: stored.vector},
                           progress=self._report)  # fmt: skip
        if self._stop.is_set():
            return False, "ยกเลิกแล้ว"
        if self._camera_lost:
            return False, "กล้องหลุด · ลองใหม่เมื่อต่อกล้องแล้ว"
        pipeline.ScanLog(self._scan_log_path).write(res)
        if res.account:
            return True, f"รู้จัก · คะแนน {res.score:.2f} · {res.total_ms / 1000:.1f} วิ"
        return False, f"ไม่ผ่าน: {res.advice}"

    # ---------- กลับมาที่เธรดหลัก ----------
    def _on_progress(self, advice: str, counts: dict) -> None:
        self._advice, self._poses = advice, counts
        self.changed.emit()

    def _on_preview(self, frac: list, reach: float) -> None:
        if not self._busy:  # ภาพที่มาถึงหลังงานจบแล้ว ไม่ต้องแสดง
            return
        self._preview_serial += 1
        self._face_box, self._reach = frac, reach
        self.previewChanged.emit()

    def _clear_preview(self) -> None:
        with self._lock:
            self._preview_img = None
        self._preview_serial, self._face_box, self._preview_on, self._reach = 0, [], False, 0.0
        self.previewChanged.emit()

    def _on_done(self, ok: bool, message: str) -> None:
        self._busy, self._advice, self._poses = False, "", {}
        self._clear_preview()
        self.refresh()
        self._finish_now(ok, message)

    def _finish_now(self, ok: bool, message: str) -> None:
        self._message = message
        self.changed.emit()
        self.finished.emit(ok, message)

    def image_provider(self) -> FacePreviewProvider:
        return FacePreviewProvider(self)

    def wait(self, timeout: float = 10.0) -> None:
        """สำหรับเทสต์: รอเธรดงานจบ (ผลยังต้องให้ event loop ส่งกลับเธรดหลัก)."""
        if self._thread is not None:
            self._thread.join(timeout)

    def shutdown(self, timeout: float = 3.0) -> None:
        """ตอนปิดแอป: สั่งหยุดงานกล้องแล้วรอเธรดจบ (ปิดกล้องใน finally ของเธรดเอง).

        เดิมไม่มีใครสั่งหยุด เธรด daemon จึงอาจยังอยู่ใน OpenCV ตอนโปรแกรมจบ (พบ 2026-09-28)
        """
        self._stop.set()
        self.wait(timeout)


class FacePreviewProvider(QQuickImageProvider):
    """ให้ QML ดึงภาพสดด้วย image://face/<เลขภาพ> · ไม่มีภาพ = ภาพดำ 1×1 (ไม่ใช่ภาพเก่า)."""

    def __init__(self, face: FaceController):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._face = face

    def requestImage(self, image_id: str, size: QSize, requested: QSize) -> QImage:  # noqa: N802
        img = self._face.preview_image()
        if img is None:
            img = QImage(1, 1, QImage.Format.Format_RGB888)
            img.fill(0)
        return img
