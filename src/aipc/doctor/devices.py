"""รายการอุปกรณ์ที่ต่อกับเครื่อง (การ์ด 0051 ข้อ 4.4) — อ่านอย่างเดียว ไม่แก้อะไรบนเครื่อง.

ทำไม: ผู้ใช้เสียบไมค์/กล้อง/หูฟังแล้วไม่รู้ว่าระบบเห็นหรือยัง · ก่อนนี้หน้าสุขภาพเครื่องบอกแค่กล้องกับการ์ดเสียง
อ่านจากที่ที่ Linux บอกเอง (H6 · ไม่ให้ AI เดา):
  USB      /sys/bus/usb/devices/*/product (ข้ามฮับ)
  กล้อง     /sys/class/video4linux/*/name (ข้ามโหนดของชิป · ชุดเดียวกับ hardware.check_camera)
  ไมค์/ลำโพง `wpctl status` (PipeWire ของ Raspberry Pi OS)
  Bluetooth `bluetoothctl devices Connected`
  จอ        /sys/class/drm/card*-*/status
อ่านไม่ได้ = None ("ตรวจไม่ได้") ไม่ใช่รายการว่าง ("ไม่มี") — สองอย่างนี้ต่างกัน (H5)
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from pathlib import Path

from aipc.doctor.hardware import SOC_VIDEO_NODES

KINDS = ("display", "usb", "camera", "audio_out", "audio_in", "bluetooth")
LABELS = {
    "display": "จอ",
    "usb": "USB",
    "camera": "กล้อง",
    "audio_out": "ลำโพง/หูฟัง",
    "audio_in": "ไมค์",
    "bluetooth": "Bluetooth",
}
HUB_CLASS = "09"  # bDeviceClass ของฮับ USB (รวมฮับในบอร์ด) · ไม่ใช่อุปกรณ์ที่ผู้ใช้เสียบ

Run = Callable[[list[str]], str | None]


def run_output(args: list[str]) -> str | None:
    """รันคำสั่งแบบ list (ไม่ผ่าน shell) · ไม่มีโปรแกรม/ล้ม/ช้าเกิน 3 วิ = None."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def usb(root: Path) -> list[str] | None:
    base = root / "sys/bus/usb/devices"
    if not base.is_dir():
        return None
    names = []
    for d in sorted(base.iterdir()):
        if ":" in d.name or _read(d / "bDeviceClass") == HUB_CLASS:
            continue  # ":" = interface ของอุปกรณ์ ไม่ใช่ตัวอุปกรณ์
        product = _read(d / "product")
        if product:
            maker = _read(d / "manufacturer")
            names.append(f"{product} ({maker})" if maker and maker not in product else product)
    return names


def cameras(root: Path) -> list[str] | None:
    base = root / "sys/class/video4linux"
    if not base.is_dir():
        return None
    names = []
    for d in sorted(base.iterdir()):
        name = _read(d / "name")
        if name and not name.startswith(SOC_VIDEO_NODES) and name not in names:
            names.append(name)  # กล้อง USB ตัวเดียวมักมี 2 โหนด (ภาพ + ข้อมูลกำกับ) ชื่อเดียวกัน
    return names


def displays(root: Path) -> list[str] | None:
    base = root / "sys/class/drm"
    if not base.is_dir():
        return None
    out = []
    for d in sorted(base.glob("card*-*")):
        if _read(d / "status") == "connected":
            out.append(d.name.split("-", 1)[1])  # card1-HDMI-A-1 → HDMI-A-1
    return out


AUDIO_LINE = re.compile(r"^[\s│├└─]*(\*)?\s*\d+\.\s+(.+?)(?:\s+\[vol:.*\])?\s*$")


def audio(text: str | None) -> tuple[list[str] | None, list[str] | None]:
    """ผล `wpctl status` → (ลำโพง, ไมค์) · ตัวที่ใช้อยู่ (มี *) ขึ้นก่อนและกำกับว่า "ใช้อยู่"."""
    if text is None:
        return None, None
    section, found = "", {"Sinks:": [], "Sources:": []}
    in_audio = False
    for line in text.splitlines():
        head = line.strip(" │├└─")
        if head in ("Audio", "Video", "Settings"):
            in_audio = head == "Audio"
            section = ""
            continue
        if not in_audio:
            continue
        if head.endswith(":"):
            section = head
            continue
        m = AUDIO_LINE.match(line)
        if m and section in found:
            if m[1]:
                found[section].insert(0, m[2] + " · ใช้อยู่")
            else:
                found[section].append(m[2])
    return found["Sinks:"], found["Sources:"]


def bluetooth(text: str | None) -> list[str] | None:
    if text is None:
        return None
    return [ln.split(" ", 2)[2] for ln in text.splitlines()
            if ln.startswith("Device ") and len(ln.split(" ", 2)) == 3]  # fmt: skip


def scan(root: Path = Path("/"), run: Run = run_output) -> dict[str, list[str] | None]:
    """ทุกชนิดในครั้งเดียว · ค่า None = ตรวจไม่ได้ (ไม่มีโปรแกรม/ไม่มีไฟล์ระบบ) · [] = ตรวจแล้วไม่มี."""
    out, inp = audio(run(["wpctl", "status"]))
    return {
        "display": displays(root),
        "usb": usb(root),
        "camera": cameras(root),
        "audio_out": out,
        "audio_in": inp,
        "bluetooth": bluetooth(run(["bluetoothctl", "devices", "Connected"])),
    }


def summary(found: dict[str, list[str] | None]) -> list[str]:
    """บรรทัดละชนิด สำหรับการ์ดคำตอบและเสียงอ่าน · เช่น "ไมค์: USB PnP Sound Device · ใช้อยู่"."""
    lines = []
    for kind in KINDS:
        items = found.get(kind)
        if items is None:
            text = "ตรวจไม่ได้"
        elif not items:
            text = "ไม่มี"
        else:
            text = ", ".join(items)
        lines.append(f"{LABELS[kind]}: {text}")
    return lines
