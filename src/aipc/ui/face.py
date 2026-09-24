"""ใบหน้าในหน้าตั้งค่า (การ์ด 0006): ลงทะเบียน · ทดลองสแกน · ลบ · สำหรับเจ้าของเซสชันเท่านั้น.

กล้องและโมเดลทำงานในเธรดแยก หน้าจอไม่ค้าง (นาฬิกายังเดิน) · ผลส่งกลับเธรดหลักผ่าน signal
(Qt ต่อแบบ queued ให้เองเมื่อส่งจากเธรดอื่น) · หน้าจอได้แค่ข้อความ/สถานะ ไม่ได้ภาพหรือ embedding (H7)

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

from PySide6.QtCore import Property, QObject, Signal, Slot

POSES = ("front", "left", "right")


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

    def __init__(self, active: bool = True, fs=None, open_camera=None, build_scanner=None,
                 enroll_seconds: float = 40.0, scan_seconds: float = 5.0,
                 enroll_log=None):  # fmt: skip
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
        self._thread: threading.Thread | None = None
        self._enroll_seconds, self._scan_seconds = enroll_seconds, scan_seconds
        self._progress.connect(self._on_progress)
        self._done.connect(self._on_done)
        self._fs = fs
        self._open_camera = open_camera
        self._build_scanner = build_scanner
        self._enroll_log_path = enroll_log
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
            stored = self._fs.load()
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
            yield frame

    def _enroll_log(self):
        from aipc.vision import pipeline

        return pipeline.EnrollLog(self._enroll_log_path)

    def _report(self, r, counts) -> None:
        self._progress.emit(r.advice or "ดีมาก · ค้างไว้อย่างนี้", dict(counts))

    def _enroll_job(self, scanner, cap, given: str):
        from aipc.vision import pipeline, store

        t0 = time.monotonic()
        res = scanner.enroll(self._frames(cap, self._enroll_seconds), progress=self._report)
        cut = "cancelled" if self._stop.is_set() else "camera_lost" if self._camera_lost else ""
        # log ทุกครั้ง รวมที่ไม่สำเร็จ พร้อมเหตุผล (การ์ด 0010 ข้อ 5) · ไม่มีภาพ ไม่มี embedding
        self._enroll_log().write(None if cut else res, time.monotonic() - t0, cut)
        if cut == "cancelled":
            return False, "ยกเลิกแล้ว · ไม่ได้บันทึกอะไร"
        if cut == "camera_lost":
            return False, "กล้องหลุด · ไม่ได้บันทึกอะไร"
        if isinstance(res, pipeline.Rejected):
            return False, f"ลงทะเบียนไม่สำเร็จ: {res.advice}"
        self._fs.save(res.vector, res.frames, res.created, store.Consent(given))
        return True, f"ลงทะเบียนแล้ว ({res.frames} เฟรม)"

    def _scan_job(self, scanner, cap, stored):
        from aipc.vision import camera, pipeline

        who = getpass.getuser()
        res = scanner.scan(self._frames(cap, self._scan_seconds), {who: stored.vector},
                           progress=self._report)  # fmt: skip
        if self._stop.is_set():
            return False, "ยกเลิกแล้ว"
        if self._camera_lost:
            return False, "กล้องหลุด · ลองใหม่เมื่อต่อกล้องแล้ว"
        pipeline.ScanLog(camera.log_path()).write(res)
        if res.account:
            return True, f"รู้จัก · คะแนน {res.score:.2f} · {res.total_ms / 1000:.1f} วิ"
        return False, f"ไม่ผ่าน: {res.advice}"

    # ---------- กลับมาที่เธรดหลัก ----------
    def _on_progress(self, advice: str, counts: dict) -> None:
        self._advice, self._poses = advice, counts
        self.changed.emit()

    def _on_done(self, ok: bool, message: str) -> None:
        self._busy, self._advice, self._poses = False, "", {}
        self.refresh()
        self._finish_now(ok, message)

    def _finish_now(self, ok: bool, message: str) -> None:
        self._message = message
        self.changed.emit()
        self.finished.emit(ok, message)

    def wait(self, timeout: float = 10.0) -> None:
        """สำหรับเทสต์: รอเธรดงานจบ (ผลยังต้องให้ event loop ส่งกลับเธรดหลัก)."""
        if self._thread is not None:
            self._thread.join(timeout)
