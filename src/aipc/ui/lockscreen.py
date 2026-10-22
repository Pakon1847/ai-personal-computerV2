"""จอล็อกรุ่น 2 ด้วย gtklock (การ์ด 0055 · Pakon อนุมัติ 2026-10-23).

ทำไม gtklock: นาฬิกาเดินจริง · แต่งด้วย CSS ได้ · ตรวจรหัสผ่าน PAM (ใส่การปลดด้วยใบหน้าได้) ·
ล็อกแบบ ext-session-lock เหมือน swaylock (ตัวล็อกตาย = จอยังล็อก) ·
ไม่มี gtklock ในเครื่อง = กลับไปใช้ swaylock รุ่น 1 (aipc.ui.idle)

เตรียมไฟล์ในโฟลเดอร์ชั่วคราวของผู้ใช้ (ไม่แตะ /etc):
- layout (gtklock.ui) จากแม่แบบ + ข้อความไทย · สไตล์ gtklock.css (ธีมดำ)
- fonts.conf: ให้ GTK เห็นฟอนต์ไทยที่มากับแอป (Raspberry Pi OS ไม่มีฟอนต์ไทยในระบบ · ตรวจ 2026-10-23)
- locale th_TH ของผู้ใช้เอง (localedef → LOCPATH) · วันที่ "วันศุกร์ที่ 23 ตุลาคม พ.ศ. 2569"
  เดินตามจริงแม้ล็อกข้ามคืน ·
  สร้างไม่ได้ = วันที่ตัวเลข (ไม่เดา)
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "lock"
FONTS = HERE / "fonts"
# userinfo-module ไม่ใช้: ทำ protocol error เมื่อใช้คู่กับฟอนต์ไทยของแอป (ทดสอบบน Pi 5 2026-10-23 · ซ้ำ 2/2) →
# วาดชื่อ + วงกลมอักษรแรกเองใน layout แทน
MODULES = ("playerctl-module",)
TIME_FORMAT = "%H:%M"
DATE_THAI = "วัน%Aที่ %e %B %EC %Ey"
DATE_PLAIN = "%d/%m/%Y"
LOCALE = "th_TH.UTF-8"

TEXT = {
    "face_hint": "มองกล้อง แล้วกด Enter เพื่อปลดด้วยใบหน้า",
    "placeholder": "รหัสผ่าน · หรือกด Enter ว่าง ๆ ใช้ใบหน้า",
    "password": "รหัสผ่าน",
    "unlock": "ปลดล็อก",
    "hint": "แป้นเป็นภาษาไทยอยู่? กดปุ่ม ~ เพื่อสลับเป็นอังกฤษก่อนพิมพ์รหัส",
}


def available(which=shutil.which) -> bool:
    return which("gtklock") is not None


def build_locale(folder: Path, run=subprocess.run) -> Path | None:
    """locale ไทยของผู้ใช้ (ครั้งเดียว · ~1 วิ) · ไม่มี localedef/ไฟล์ต้นทาง = None."""
    target = folder / LOCALE
    if (target / "LC_TIME").exists():
        return folder
    folder.mkdir(parents=True, exist_ok=True)  # localedef ไม่สร้างโฟลเดอร์แม่ให้ (พบบน Pi 5)
    try:
        r = run(["localedef", "-i", "th_TH", "-f", "UTF-8", str(target)],
                capture_output=True, timeout=30, check=False)  # fmt: skip
    except (OSError, subprocess.TimeoutExpired):
        return None
    return folder if r.returncode == 0 and (target / "LC_TIME").exists() else None


def fonts_conf(path: Path, font_dir: Path | None = None) -> Path:
    font_dir = font_dir or FONTS
    path.write_text(
        '<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n'
        "<fontconfig>\n"
        '  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>\n'
        f"  <dir>{escape(str(font_dir))}</dir>\n"
        "</fontconfig>\n",
        encoding="utf-8",
    )
    return path


def layout(path: Path, keep: str, warn: bool, name: str = "") -> Path:
    s = (ASSETS / "gtklock.ui.in").read_text(encoding="utf-8")
    values = {**TEXT, "keep": ("! " if warn else "✓ ") + keep,
              "keep_class": "warn" if warn else "keep",
              "name": name, "initial": (name.strip()[:1] or "?").upper()}  # fmt: skip
    for k, v in values.items():
        s = s.replace("{" + k + "}", escape(v, {'"': "&quot;"}))
    path.write_text(s, encoding="utf-8")
    return path


def prepare(folder: Path, keep: str, warn: bool, name: str = "", run=subprocess.run) -> list[str]:
    """เขียนไฟล์ทั้งหมดใน folder แล้วคืนคำสั่ง (ยังไม่รัน) · เรียกตอนตั้งค่าล็อก ไม่ใช่ตอนล็อก (ล็อกต้องเร็ว)."""
    folder.mkdir(parents=True, exist_ok=True)
    ui = layout(folder / "gtklock.ui", keep, warn, name)
    conf = fonts_conf(folder / "fonts.conf")
    loc = build_locale(folder / "locale", run)
    env = [f"FONTCONFIG_FILE={conf}"]
    if loc is not None:
        env += [f"LOCPATH={loc}", f"LC_ALL={LOCALE}"]
    cmd = ["env", *env, "gtklock", "-d",
           "-s", str(ASSETS / "gtklock.css"), "-x", str(ui),
           "-t", TIME_FORMAT, "-D", DATE_THAI if loc is not None else DATE_PLAIN]  # fmt: skip
    for m in MODULES:
        cmd += ["-m", m]
    return cmd
