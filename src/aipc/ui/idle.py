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


# วงแหวนรหัสผ่านของ swaylock ให้เข้าชุดกับจอล็อกและธีมดำของแอป (Pakon 2026-10-23 · แนวทาง ui-ux-pro-max:
# เรียบ คอนทราสต์สูง สีเน้นเดียว) · ค่าสีจาก Theme.qml โหมดมืด · RRGGBB[AA] · 00000000 = โปร่งใส
RING = {
    "inside": "111113", "ring": "3F3F48", "line": "00000000", "separator": "00000000",
    "key-hl": "A5B4FC", "bs-hl": "F0B45C", "text": "F2F2F4",
    "inside-clear": "111113", "ring-clear": "3F3F48", "line-clear": "00000000",
    "text-clear": "A1A1AA",
    "inside-ver": "1C1D38", "ring-ver": "A5B4FC", "line-ver": "00000000", "text-ver": "C7D2FE",
    "inside-wrong": "33181A", "ring-wrong": "F28B80", "line-wrong": "00000000",
    "text-wrong": "F6B8B0",
}  # fmt: skip
BG = "050506"


def lock_command(image: Path | None) -> list[str]:
    """swaylock: -f กลับทันทีหลังล็อก (swayidle ไม่ค้าง) · -e Enter ว่างไม่นับเป็นรหัสผิด · -k บอกผังแป้นตอนพิมพ์ ·
    วงแหวนขึ้นตลอด (ผู้ใช้รู้ว่าพิมพ์รหัสตรงไหน) · สีตามธีม."""
    cmd = ["swaylock", "-f", "-e", "-k", "-l", "-c", BG, "--indicator-idle-visible",
           "--indicator-radius", "84", "--indicator-thickness", "8"]  # fmt: skip
    for k, v in RING.items():
        cmd += [f"--{k}-color", v]
    if image is not None:
        cmd += ["-i", str(image), "-s", "fill"]
    return cmd


def current_command_file() -> Path:
    return runtime_dir() / "lock-command.json"


def current_lock_command() -> list[str]:
    """คำสั่งล็อกที่ตั้งไว้ล่าสุด (gtklock รุ่น 2 หรือ swaylock รุ่น 1) · ใช้ร่วมกันทั้งล็อกเมื่อไม่ได้ใช้ ·
    สั่งเสียง "ล็อกหน้าจอ" · ตัวตรวจด้วยกล้อง · ยังไม่ได้ตั้ง/อ่านไม่ได้ = swaylock สีพื้น (ล็อกได้เสมอ · H1)."""
    import json

    try:
        cmd = json.loads(current_command_file().read_text(encoding="utf-8"))
        if isinstance(cmd, list) and cmd and all(isinstance(a, str) for a in cmd):
            return cmd
    except (OSError, ValueError, AttributeError):
        pass
    return lock_command(None)


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
    elif lock_min <= 0:  # ปิดล็อกตามเวลา · ล็อกเพราะสั่งเอง (ปุ่ม/เสียง)
        why = f"{who}ล็อกหน้าจอแล้ว"
        out = keep
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
        "พิมพ์รหัสผ่าน แล้วกด Enter",
        "แป้นเป็นภาษาไทยอยู่? กดปุ่ม ~ เพื่อสลับเป็นอังกฤษก่อน",
        out,
    ]


def render_lock_image(path: Path, lines: list[str], size: tuple[int, int] = (1920, 1080),
                      family: str = "IBM Plex Sans Thai") -> Path:  # fmt: skip
    """วาดจอล็อกเป็นภาพ PNG ให้ swaylock ใช้เป็นพื้นหลัง (swaylock แสดงข้อความเองไม่ได้).

    หน้าตา (Pakon 2026-10-23: "ทำให้สวยขึ้น" · แนวทาง ui-ux-pro-max: คอลัมน์เดียว ตัวใหญ่ ·
    เว้นที่ว่าง · คอนทราสต์สูง ·
    ไม่ใช้ไล่สีม่วงแบบ "AI"): ไอคอนกุญแจ → หัวเรื่องตัวใหญ่ → เหตุที่ล็อก → [วงแหวนรหัสผ่านของ swaylock กลางจอ] →
    การ์ดวิธีปลด + บรรทัดบอกว่างานยังอยู่ (สีเขียว + เครื่องหมายถูก) หรือจะออกเอง (สีส้ม + เครื่องหมายเตือน ·
    ไม่ใช้สีอย่างเดียวบอกความหมาย) · ขนาดทุกอย่างคิดจากความสูงจอ
    """
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import (
        QColor,
        QFont,
        QImage,
        QPainter,
        QPainterPath,
        QPen,
        QRadialGradient,  # fmt: skip
    )

    w, h = size
    k = h / 1080
    title, why, how, hint, keep = (lines + [""] * 5)[:5]
    warn = "จะหาย" in keep or "ออกจากระบบให้เอง" in keep

    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor("#" + BG))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    # แสงนุ่ม ๆ หลังวงแหวน (สีเทาเย็น ไม่ใช่ม่วง) · ให้กลางจอเด่นโดยไม่รก
    glow = QRadialGradient(QPointF(w / 2, h / 2), h * 0.55)
    glow.setColorAt(0.0, QColor("#15161C"))
    glow.setColorAt(1.0, QColor("#" + BG))
    p.fillRect(0, 0, w, h, glow)

    def font(px: float, weight=QFont.Weight.Normal) -> QFont:
        f = QFont(family)
        f.setPixelSize(max(10, round(px * k)))
        f.setWeight(weight)
        return f

    center = Qt.AlignmentFlag.AlignHCenter

    def text(y: float, hgt: float, s: str, px: float, color: str, weight=QFont.Weight.Normal,
             x: float = 0, width: float | None = None, align=center):  # fmt: skip
        p.setFont(font(px, weight))
        p.setPen(QColor(color))
        r = QRectF(x, y * k, w if width is None else width, hgt * k)
        p.drawText(r, align | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap, s)

    # ไอคอนกุญแจ (วาดเอง · เส้น 24×24 แบบเดียวกับ Icons.qml)
    cx, top, u = w / 2, 150 * k, 2.6 * k
    p.setPen(QPen(QColor("#A5B4FC"), 1.9 * u, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(cx - 8 * u, top + 10 * u, 16 * u, 12 * u), 2.5 * u, 2.5 * u)
    shackle = QPainterPath(QPointF(cx - 5 * u, top + 10 * u))
    shackle.lineTo(cx - 5 * u, top + 6 * u)
    shackle.arcTo(QRectF(cx - 5 * u, top + 1 * u, 10 * u, 10 * u), 180, -180)
    shackle.lineTo(cx + 5 * u, top + 10 * u)
    p.drawPath(shackle)

    text(222, 96, title, 72, "#F2F2F4", QFont.Weight.Bold)
    text(320, 44, why, 26, "#A1A1AA")

    # การ์ดใต้วงแหวน (วงแหวนของ swaylock อยู่กลางจอ รัศมี 84 + เส้น 8)
    cw, cy, ch = min(w - 64 * k, 900 * k), 650 * k, 250 * k
    card = QRectF((w - cw) / 2, cy, cw, ch)
    p.setPen(QPen(QColor("#26262C"), 1.5 * k))
    p.setBrush(QColor("#111113"))
    p.drawRoundedRect(card, 24 * k, 24 * k)
    pad = 40 * k
    text(cy / k + 30, 52, how, 34, "#F2F2F4", QFont.Weight.DemiBold)
    text(cy / k + 84, 40, hint, 22, "#A1A1AA")
    p.setPen(QPen(QColor("#26262C"), 1.5 * k))
    p.drawLine(QPointF(card.left() + pad, cy + 146 * k), QPointF(card.right() - pad, cy + 146 * k))
    # บรรทัดสุดท้าย: งานยังอยู่ (เขียว ✓) หรือจะออกเอง (ส้ม !) · มีไอคอนกำกับ ไม่ใช่สีอย่างเดียว
    tone = QColor("#F0B45C" if warn else "#6CCB7E")
    iy, ix, r = cy + 198 * k, card.left() + pad + 14 * k, 13 * k
    p.setPen(QPen(tone, 2.6 * k, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                  Qt.PenJoinStyle.RoundJoin))  # fmt: skip
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(ix, iy), r, r)
    if warn:
        p.drawLine(QPointF(ix, iy - 6 * k), QPointF(ix, iy + 1.5 * k))
        p.drawPoint(QPointF(ix, iy + 6 * k))
    else:
        mark = QPainterPath(QPointF(ix - 6 * k, iy))
        mark.lineTo(ix - 1.5 * k, iy + 4.5 * k)
        mark.lineTo(ix + 6.5 * k, iy - 4.5 * k)
        p.drawPath(mark)
    tx = ix + r + 16 * k
    text(cy / k + 176, 46, keep, 22, tone.name(), x=tx, width=card.right() - pad - tx,
         align=Qt.AlignmentFlag.AlignLeft)  # fmt: skip

    text(1010, 40, "AI PC", 18, "#636978", QFont.Weight.DemiBold, x=48 * k, width=300 * k,
         align=Qt.AlignmentFlag.AlignLeft)  # fmt: skip
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
        gtklock=None,
        prepare=None,
    ):
        self._spawn = spawn or (
            lambda args: subprocess.Popen(  # noqa: S603 · list args ไม่ผ่าน shell
                args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        )
        self._which = which
        self._dir = image_dir
        self._render = render
        from aipc.ui import lockscreen

        self._gtklock = gtklock or (lambda: lockscreen.available(self._which))

        def default_prepare(folder, keep, warn, name, height, auto):
            return lockscreen.prepare(folder, keep, warn, name, screen_height=height, auto=auto)

        self._prepare = prepare or default_prepare
        self._proc = None
        self._monitor = None  # ตัวตรวจด้วยกล้อง (ขั้น C)
        self._applied: tuple | None = None
        self.status = ""  # "" = ทำงานตามค่า · ข้อความ = เหตุที่ไม่ได้ทำ

    def apply(self, lock_min: int, logout_min: int, name: str = "", size=(1920, 1080),
              presence: tuple[int, int] | None = None,
              auto_unlock: bool = False) -> list[str] | None:  # fmt: skip
        """ใช้ค่าใหม่ · ค่าเดิม = ไม่ทำอะไร · คืนคำสั่ง swayidle ที่เริ่ม (None = ปิด/ทำไม่ได้).

        presence = (วินาทีไม่เห็นเจ้าของก่อนล็อก, วินาทีหลังล็อกก่อนออก) →
        เริ่มตัวตรวจด้วยกล้อง (ขั้น C) · None = ไม่ใช้กล้อง
        """
        key = (lock_min, logout_min, name, presence, auto_unlock)
        if key == self._applied:
            return None
        self.stop()
        self._applied = key
        # เตรียมคำสั่งล็อกก่อนเสมอ แม้ปิดล็อกตามเวลา: สั่งเสียง "ล็อกหน้าจอ" ใช้ตัวเดียวกัน
        # (พบบน Pi 5 2026-10-23: Pakon ปิดล็อกตามเวลา → คำสั่งเสียงได้ swaylock รุ่น 1 แทน gtklock รุ่น 2)
        rdir = self._dir or runtime_dir()
        lines = lock_lines(name, lock_min, logout_min, presence[1] if presence else None)
        cmd = None
        if self._gtklock():  # การ์ด 0055: จอล็อกรุ่น 2 (นาฬิกา · ปลดด้วยใบหน้า) · ไม่มี = รุ่น 1
            try:
                keep = lines[-1]
                warn = "จะหาย" in keep
                cmd = self._prepare(rdir / "gtklock", keep, warn, name, size[1], auto_unlock)
            except Exception:  # noqa: BLE001 · เตรียมรุ่น 2 ไม่ได้ = ใช้รุ่น 1 (ล็อกได้เสมอ)
                cmd = None
        if cmd is None:
            image = None
            try:
                image = self._render(rdir / "lock.png", lines, size)
            except Exception:  # noqa: BLE001 · วาดภาพไม่ได้ ยังล็อกได้ (จอสีพื้น) · ความปลอดภัยสำคัญกว่าหน้าตา
                image = None
            cmd = lock_command(image)
        _remember_command(rdir / "lock-command.json", cmd)
        if lock_min <= 0 and presence is None:
            self.status = "ปิดอยู่"
            return None
        missing = [t for t in ("swayidle",) if self._which(t) is None]
        if self._which("swaylock") is None and not self._gtklock():
            missing.append("swaylock")
        if missing:
            self.status = "เครื่องนี้ไม่มี " + " ".join(missing)
            return None
        flag = rdir / "input-idle" if presence else None
        args = swayidle_args(lock_min * 60, logout_min * 60, cmd, idle_flag=flag)
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


def _remember_command(path: Path, cmd: list[str]) -> None:
    import json

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


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
