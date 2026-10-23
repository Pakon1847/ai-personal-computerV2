"""หน้า "กำลังเปิด…" ระหว่างเข้าระบบ (Pakon 2026-10-23: สแกนหน้าผ่านแล้วจอดำ ~4 วิ ก่อนแอปขึ้น).

ช่วงนั้น labwc ยังไม่มีอะไรให้แสดง (Python + Qt ของแอปกำลังโหลด) · ทำให้เร็วกว่านี้มากไม่ได้ จึงแสดงภาพแทนจอดำ:
แอปวาดภาพนี้เก็บไว้ทุกครั้งที่เปิด (ขนาดจอจริง · ธีมที่ผู้ใช้ตั้ง · ฟอนต์ของแอป) →
ครั้งหน้า aipc-shell-loop ให้ swaybg แสดงทันทีที่ labwc เริ่ม (หน้าต่างแอปเต็มจอขึ้นมาทับเอง) ·
ยังไม่มีภาพ (เข้าครั้งแรก) = สีพื้นของธีม · ไม่มีข้อมูลส่วนตัวในภาพ (แค่ข้อความคงที่)
"""

from __future__ import annotations

import os
from pathlib import Path

# สีเดียวกับ Theme.qml (bg · ink · inkMuted · accent) · ธีมมืดเป็นค่าเริ่มต้นของแอป
COLORS = {"dark": ("#050506", "#F2F2F4", "#A1A1AA", "#A5B4FC"),
          "light": ("#F6F7F9", "#15171C", "#4B5160", "#4338CA")}  # fmt: skip
TITLE = "กำลังเปิด…"
SUBTITLE = "AI Personal Computer"


def path() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "aipc" / "splash.png"


def write(dest: Path, width: int, height: int, theme: str = "dark") -> Path:
    """วาดแล้วบันทึกแบบเขียนไฟล์ใหม่ก่อนค่อยแทนที่ (ไฟดับกลางคัน = ภาพเดิมยังใช้ได้)."""
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

    bg, ink, muted, accent = COLORS.get(theme, COLORS["dark"])
    img = QImage(max(1, width), max(1, height), QImage.Format.Format_RGB32)
    img.fill(QColor(bg))
    p = QPainter(img)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        unit = max(12, height // 36)
        # โลโก้: วงแหวนสีเน้นของระบบ + "AI" กลางวง (Pakon: "เพิ่มโลโก้ · ให้เข้ากับระบบของเรา")
        r = unit * 3
        cx, cy = width // 2, height // 2 - unit * 4
        p.setPen(QPen(QColor(accent), max(3, unit // 4)))
        p.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)
        p.setFont(QFont("IBM Plex Sans Thai", int(unit * 1.6), QFont.Weight.Bold))
        p.drawText(QRect(cx - r, cy - r, 2 * r, 2 * r), Qt.AlignmentFlag.AlignCenter, "AI")
        p.setPen(QColor(ink))
        p.setFont(QFont("IBM Plex Sans Thai", unit * 2, QFont.Weight.Medium))
        p.drawText(QRect(0, unit * 2, width, height), Qt.AlignmentFlag.AlignCenter, TITLE)
        p.setPen(QColor(muted))
        p.setFont(QFont("IBM Plex Sans Thai", unit))
        below = QRect(0, height // 2 + unit * 4, width, unit * 3)
        p.drawText(below, Qt.AlignmentFlag.AlignHCenter, SUBTITLE)
    finally:
        p.end()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + "-new.png")
    if not img.save(str(tmp), "PNG"):
        raise OSError(f"บันทึก {tmp} ไม่ได้")
    os.replace(tmp, dest)
    return dest


def refresh(theme: str) -> None:
    """เรียกจากแอปหลังเปิดเสร็จ (เซสชันจริงเท่านั้น) · ทำไม่ได้ = เงียบ (ไม่กระทบแอป · ครั้งหน้าใช้สีพื้นแทน)."""
    from PySide6.QtGui import QGuiApplication

    try:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        size = screen.size() * screen.devicePixelRatio()
        write(path(), size.width(), size.height(), theme)
    except (OSError, RuntimeError):
        pass
