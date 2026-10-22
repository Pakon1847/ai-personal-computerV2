"""ล็อกจอเมื่อไม่ได้ใช้เครื่อง แล้วออกจากระบบเอง (ขั้น A · Pakon 2026-10-06).

ทำไม: ลืมกด "ออก" แล้วลุกไป = คนต่อไปเห็นงาน แชท และบัญชีเว็บ (Gmail/YouTube) ที่ login ค้างไว้
วิธี: swayidle (ตรวจว่าไม่มีคีย์บอร์ด/เมาส์ · labwc รองรับ ext-idle-notify) →
  ครบ lock_min นาที  → swaylock (ext-session-lock: บังทุกหน้าต่างรวม Chromium ·
                       ปลดด้วยรหัสผ่านผ่าน PAM ของระบบ)
  ครบอีก logout_min → labwc --exit (คำสั่งเดียวกับปุ่ม "ออก" · KillUserProcesses ปิดทุกโปรเซสของผู้ใช้)
                       logout_min = 0 (ค่าเริ่มต้นตั้งแต่การ์ด 0051) = ล็อกอย่างเดียว ไม่ออกเอง แอปที่เปิดไว้ยังอยู่
ทั้งสองโปรแกรมมากับ Raspberry Pi OS อยู่แล้ว
(ตรวจบน Pi 5 2026-10-06: swaylock 1.8.2 · swayidle 1.8.0 · labwc 0.20.1)
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


def swayidle_args(
    lock_s: int,
    logout_s: int,
    lock_cmd: list[str],
    idle_flag: Path | None = None,
    flag_after_s: int = 10,
) -> list[str] | None:
    """ไม่ใช้เครื่อง lock_s วินาที → ล็อก · ไม่ใช้ต่ออีก logout_s วินาที (นับจากครั้งสุดท้ายที่ใช้) → ออกจากระบบ.

    lock_s ≤ 0 = ไม่ล็อกด้วยเวลา · logout_s ≤ 0 = ล็อกอย่างเดียว ไม่ออก (การ์ด 0051)
    idle_flag (ขั้น C) = ไม่แตะ flag_after_s วิ → สร้างไฟล์ธง · แตะ → ลบ
    (ตัวตรวจด้วยกล้องเปิดกล้องเฉพาะตอนมีธง) · ไม่มีทั้งสองอย่าง = คืน None · -w = รอคำสั่งจบก่อนรับเหตุการณ์ถัดไป
    """
    args = ["swayidle", "-w"]
    if idle_flag is not None:
        f = shlex.quote(str(idle_flag))
        args += ["timeout", str(flag_after_s), f"touch {f}", "resume", f"rm -f {f}"]
    if lock_s > 0:
        args += ["timeout", str(lock_s), shlex.join(lock_cmd)]
        if logout_s > 0:
            args += ["timeout", str(lock_s + logout_s), EXIT_CMD]
    return args if len(args) > 2 else None


def lock_lines(
    name: str, lock_min: int, logout_min: int, presence_logout_s: int | None = None
) -> list[str]:
    """ข้อความบนจอล็อก (ผู้ใช้ทั่วไป/ผู้สูงอายุต้องรู้ว่าต้องทำอะไร ไม่ใช่เห็นจอสีดำเฉย ๆ).

    presence_logout_s ไม่ใช่ None = เปิดขั้น C (ล็อกได้ทั้งเพราะไม่ได้ใช้ และเพราะกล้องไม่เห็นเจ้าของ) ·
    ค่าออก = 0 = ล็อกอย่างเดียว (การ์ด 0051) → บอกว่างานยังอยู่ ไม่ขู่ว่าจะหาย
    """
    who = f"{name} · " if name else ""
    keep = "ระบบจะไม่ออกจากระบบเอง · แอปและงานที่เปิดไว้ยังอยู่ครบหลังปลดล็อก"
    if presence_logout_s is not None:
        why = f"{who}ไม่ได้ใช้เครื่อง หรือกล้องไม่เห็นเจ้าของบัญชี"
        out = (
            f"ถ้าไม่มีใครอยู่หน้าเครื่อง ระบบจะออกจากระบบให้เองใน {presence_logout_s} วินาที · "
            "งานที่ยังไม่บันทึกจะหาย"
            if presence_logout_s > 0
            else keep
        )
    else:
        why = f"{who}ไม่ได้ใช้เครื่องเกิน {lock_min} นาที"
        out = (
            f"ถ้าไม่ปลดล็อกภายใน {logout_min} นาที ระบบจะออกจากระบบให้เอง · งานที่ยังไม่บันทึกจะหาย"
            if logout_min > 0
            else keep
        )
    return [
        "หน้าจอล็อกอยู่",
        why,
        "เจ้าของบัญชี: พิมพ์รหัสผ่านแล้วกด Enter เพื่อกลับเข้าใช้ (ถ้าเป็นแป้นไทย กดปุ่ม ~ เพื่อสลับเป็นอังกฤษ)",
        out,
    ]


def render_lock_image(path: Path, lines: list[str], size: tuple[int, int] = (1920, 1080),
                      family: str = "IBM Plex Sans Thai") -> Path:  # fmt: skip
    """วาดข้อความลงภาพ PNG ให้ swaylock ใช้เป็นพื้นหลัง (swaylock แสดงข้อความเองไม่ได้) ·
    ใช้ฟอนต์ไทยที่มากับแอป."""
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
    p.drawText(
        box,
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
        "\n\n".join(rest[1:]),
    )
    p.end()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not img.save(str(path), "PNG"):
        raise OSError(f"บันทึกภาพจอล็อกไม่ได้: {path}")
    return path


def runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(base) / "aipc"


class IdleLock:
    """ดูแล swayidle ของเซสชันนี้ 1 ตัว · เริ่มใหม่เมื่อค่าเปลี่ยน ·
    ไม่มี swayidle/swaylock = ไม่ทำ (บอกผ่าน status)."""

    def __init__(
        self,
        spawn=None,
        which=shutil.which,
        image_dir: Path | None = None,
        render=render_lock_image,
    ):
        self._spawn = spawn or (
            lambda args: subprocess.Popen(  # noqa: S603 · list args ไม่ผ่าน shell
                args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        )
        self._which = which
        self._dir = image_dir
        self._render = render
        self._proc = None
        self._monitor = None  # ตัวตรวจด้วยกล้อง (ขั้น C)
        self._applied: tuple | None = None
        self.status = ""  # "" = ทำงานตามค่า · ข้อความ = เหตุที่ไม่ได้ทำ

    def apply(self, lock_min: int, logout_min: int, name: str = "", size=(1920, 1080),
              presence: tuple[int, int] | None = None) -> list[str] | None:  # fmt: skip
        """ใช้ค่าใหม่ · ค่าเดิม = ไม่ทำอะไร · คืนคำสั่ง swayidle ที่เริ่ม (None = ปิด/ทำไม่ได้).

        presence = (วินาทีไม่เห็นเจ้าของก่อนล็อก, วินาทีหลังล็อกก่อนออก) →
        เริ่มตัวตรวจด้วยกล้อง (ขั้น C) · None = ไม่ใช้กล้อง
        """
        key = (lock_min, logout_min, name, presence)
        if key == self._applied:
            return None
        self.stop()
        self._applied = key
        if lock_min <= 0 and presence is None:
            self.status = "ปิดอยู่"
            return None
        missing = [t for t in ("swayidle", "swaylock") if self._which(t) is None]
        if missing:
            self.status = "เครื่องนี้ไม่มี " + " ".join(missing)
            return None
        rdir = self._dir or runtime_dir()
        image = None
        try:
            lines = lock_lines(name, lock_min, logout_min, presence[1] if presence else None)
            image = self._render(rdir / "lock.png", lines, size)
        except Exception:  # noqa: BLE001 · วาดภาพไม่ได้ ยังล็อกได้ (จอสีพื้น) · ความปลอดภัยสำคัญกว่าหน้าตา
            image = None
        flag = rdir / "input-idle" if presence else None
        args = swayidle_args(lock_min * 60, logout_min * 60, lock_command(image), idle_flag=flag)
        self._proc = self._spawn(args)
        if presence:
            import sys

            mon = [
                sys.executable,
                "-m",
                "aipc.ui.presence",
                "run",
                "--flag",
                str(flag),
                "--lock-after",
                str(presence[0]),
                "--logout-after",
                str(presence[1]),
            ]
            if image is not None:
                mon += ["--image", str(image)]
            self._monitor = self._spawn(mon)
        self.status = ""
        return args

    def stop(self) -> None:
        for proc in (self._proc, self._monitor):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except Exception:  # noqa: BLE001
                    proc.kill()
        self._proc = self._monitor = None
        self._applied = None


def clear_orphans(run=subprocess.run) -> None:
    """หน้าจอ V2 ล่มแล้วเปิดใหม่ (aipc-shell-loop) = swayidle ตัวเก่ายังรันอยู่ → ปิดของผู้ใช้คนนี้ก่อนเริ่มตัวใหม่."""
    try:
        run(
            ["pkill", "-u", str(os.getuid()), "-x", "swayidle"],
            check=False,
            capture_output=True,
            timeout=5,
        )
        run(
            ["pkill", "-u", str(os.getuid()), "-f", "aipc.ui.presence run"],
            check=False,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
