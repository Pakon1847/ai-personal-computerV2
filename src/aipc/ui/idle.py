"""ล็อกจอเมื่อไม่ได้ใช้เครื่อง แล้วออกจากระบบเอง (ขั้น A · Pakon 2026-10-06).

ทำไม: ลืมกด "ออก" แล้วลุกไป = คนต่อไปเห็นงาน แชท และบัญชีเว็บ (Gmail/YouTube) ที่ login ค้างไว้
วิธี: swayidle (ตรวจว่าไม่มีคีย์บอร์ด/เมาส์ · labwc รองรับ ext-idle-notify) →
  ครบ lock_min นาที  → swaylock (ext-session-lock: บังทุกหน้าต่างรวม Chromium · ปลดด้วยรหัสผ่านผ่าน PAM ของระบบ)
  ครบอีก logout_min → labwc --exit (คำสั่งเดียวกับปุ่ม "ออก" · KillUserProcesses ปิดทุกโปรเซสของผู้ใช้)
ทั้งสองโปรแกรมมากับ Raspberry Pi OS อยู่แล้ว (ตรวจบน Pi 5 2026-10-06: swaylock 1.8.2 · swayidle 1.8.0 · labwc 0.20.1)
ใช้กล้องตรวจว่ามีคนอยู่ (ขั้น C) ทำหลังผลวัดขั้น B ผ่านเกณฑ์เท่านั้น
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

EXIT_CMD = "labwc --exit"


def lock_command(image: Path | None) -> list[str]:
    """swaylock: -f กลับทันทีหลังล็อก (swayidle ไม่ค้าง) · -e Enter ว่างไม่นับเป็นรหัสผิด · -k บอกผังแป้นตอนพิมพ์."""
    cmd = ["swaylock", "-f", "-e", "-k", "-l", "-c", "1d1d1b"]
    if image is not None:
        cmd += ["-i", str(image), "-s", "fill"]
    return cmd


def swayidle_args(lock_s: int, logout_s: int, lock_cmd: list[str]) -> list[str] | None:
    """ไม่ใช้เครื่อง lock_s วินาที → ล็อก · ไม่ใช้ต่ออีก logout_s วินาที (นับจากครั้งสุดท้ายที่ใช้) → ออกจากระบบ.

    lock_s ≤ 0 = ปิด (คืน None) · -w = รอคำสั่งจบก่อนรับเหตุการณ์ถัดไป
    """
    if lock_s <= 0:
        return None
    return ["swayidle", "-w",
            "timeout", str(lock_s), shlex.join(lock_cmd),
            "timeout", str(lock_s + max(logout_s, 1)), EXIT_CMD]  # fmt: skip


def lock_lines(name: str, lock_min: int, logout_min: int) -> list[str]:
    """ข้อความบนจอล็อก (ผู้ใช้ทั่วไป/ผู้สูงอายุต้องรู้ว่าต้องทำอะไร ไม่ใช่เห็นจอสีดำเฉย ๆ)."""
    who = f"{name} · " if name else ""
    return [
        "หน้าจอล็อกอยู่",
        f"{who}ไม่ได้ใช้เครื่องเกิน {lock_min} นาที",
        "เจ้าของบัญชี: พิมพ์รหัสผ่านแล้วกด Enter เพื่อกลับเข้าใช้ (ถ้าเป็นแป้นไทย กดปุ่ม ~ เพื่อสลับเป็นอังกฤษ)",
        f"ถ้าไม่ปลดล็อกภายใน {logout_min} นาที ระบบจะออกจากระบบให้เอง · งานที่ยังไม่บันทึกจะหาย",
    ]


def render_lock_image(path: Path, lines: list[str], size: tuple[int, int] = (1920, 1080),
                      family: str = "IBM Plex Sans Thai") -> Path:  # fmt: skip
    """วาดข้อความลงภาพ PNG ให้ swaylock ใช้เป็นพื้นหลัง (swaylock แสดงข้อความเองไม่ได้) · ใช้ฟอนต์ไทยที่มากับแอป."""
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter

    w, h = size
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor("#1d1d1b"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    title, *rest = lines
    p.setPen(QColor("#ffffff"))
    p.setFont(QFont(family, max(24, h // 18), QFont.Weight.DemiBold))
    p.drawText(QRect(0, int(h * 0.10), w, int(h * 0.12)), Qt.AlignmentFlag.AlignCenter, title)
    p.setFont(QFont(family, max(14, h // 45)))
    p.setPen(QColor("#d9d8d2"))
    # กลางจอเป็นวงแหวนของ swaylock → ข้อความอยู่บนกับล่าง
    p.drawText(QRect(0, int(h * 0.22), w, int(h * 0.08)), Qt.AlignmentFlag.AlignCenter, rest[0])
    box = QRect(int(w * 0.08), int(h * 0.66), int(w * 0.84), int(h * 0.26))
    p.drawText(box, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
               "\n\n".join(rest[1:]))  # fmt: skip
    p.end()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not img.save(str(path), "PNG"):
        raise OSError(f"บันทึกภาพจอล็อกไม่ได้: {path}")
    return path


def runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(base) / "aipc"


class IdleLock:
    """ดูแล swayidle ของเซสชันนี้ 1 ตัว · เริ่มใหม่เมื่อค่าเปลี่ยน · ไม่มี swayidle/swaylock = ไม่ทำ (บอกผ่าน status)."""

    def __init__(self, spawn=None, which=shutil.which, image_dir: Path | None = None, render=render_lock_image):
        self._spawn = spawn or (lambda args: subprocess.Popen(  # noqa: S603 · list args ไม่ผ่าน shell
            args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        self._which = which
        self._dir = image_dir
        self._render = render
        self._proc = None
        self._applied: tuple | None = None
        self.status = ""  # "" = ทำงานตามค่า · ข้อความ = เหตุที่ไม่ได้ทำ

    def apply(self, lock_min: int, logout_min: int, name: str = "", size=(1920, 1080)) -> list[str] | None:
        """ใช้ค่าใหม่ · ค่าเดิม = ไม่ทำอะไร · คืนคำสั่ง swayidle ที่เริ่ม (None = ปิด/ทำไม่ได้)."""
        key = (lock_min, logout_min, name)
        if key == self._applied:
            return None
        self.stop()
        self._applied = key
        if lock_min <= 0:
            self.status = "ปิดอยู่"
            return None
        missing = [t for t in ("swayidle", "swaylock") if self._which(t) is None]
        if missing:
            self.status = "เครื่องนี้ไม่มี " + " ".join(missing)
            return None
        image = None
        try:
            image = self._render((self._dir or runtime_dir()) / "lock.png",
                                 lock_lines(name, lock_min, logout_min), size)  # fmt: skip
        except Exception:  # noqa: BLE001 · วาดภาพไม่ได้ ยังล็อกได้ (จอสีพื้น) · ความปลอดภัยสำคัญกว่าหน้าตา
            image = None
        args = swayidle_args(lock_min * 60, logout_min * 60, lock_command(image))
        self._proc = self._spawn(args)
        self.status = ""
        return args

    def stop(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except Exception:  # noqa: BLE001
                self._proc.kill()
        self._proc = None
        self._applied = None


def clear_orphans(run=subprocess.run) -> None:
    """หน้าจอ V2 ล่มแล้วเปิดใหม่ (aipc-shell-loop) = swayidle ตัวเก่ายังรันอยู่ → ปิดของผู้ใช้คนนี้ก่อนเริ่มตัวใหม่."""
    try:
        run(["pkill", "-u", str(os.getuid()), "-x", "swayidle"], check=False, capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass
