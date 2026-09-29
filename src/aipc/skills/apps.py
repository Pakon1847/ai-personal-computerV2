"""แอปที่ติดตั้งจริงในเครื่อง จากไฟล์ .desktop (ข้อเสนอ 2026-09-29 งานข้อ ⑥).

ตัวติดตั้ง (apt, Flatpak, Add/Remove Software) วางไฟล์ .desktop ให้เองอยู่แล้ว (เมนูแอปของ Pi ก็อ่านจากไฟล์นี้)
ระบบจึงรู้จักแอปใหม่ได้โดยไม่ต้องตั้งค่า:
- อ่านเฉพาะ Name / Name[th] / ชื่อไฟล์ เป็นคำเรียก · ข้าม NoDisplay / Hidden / ที่ไม่ใช่ Application
- โฟลเดอร์เปลี่ยน (mtime ของโฟลเดอร์ขยับเมื่อมีไฟล์เพิ่ม/ลบ) = อ่านใหม่ตอนถูกถาม · ติดตั้งเสร็จแล้วสั่งเปิดได้ทันที
- เปิดด้วย `gtk-launch <ไฟล์ .desktop>` เท่านั้น · ไม่เอาบรรทัด Exec= มารันเอง · เปิดได้เฉพาะแอปที่อยู่ในรายชื่อนี้
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


def default_dirs() -> list[Path]:
    # AIPC_APP_DIRS (คั่นด้วย :) แทนโฟลเดอร์มาตรฐาน · ว่าง = ไม่หาแอปเลย (เทสต์ใช้ ให้ผลเหมือนกันทุกเครื่อง)
    if "AIPC_APP_DIRS" in os.environ:
        return [Path(p) for p in os.environ["AIPC_APP_DIRS"].split(":") if p]
    home = Path.home()
    data = Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share")
    # ลำดับ = ความสำคัญจากน้อยไปมาก (ตัวหลังทับตัวแรก): ระบบ → Flatpak → ของผู้ใช้เอง (ตาม XDG)
    return [
        Path("/usr/share/applications"),
        Path("/usr/local/share/applications"),
        Path("/var/lib/flatpak/exports/share/applications"),
        data / "flatpak" / "exports" / "share" / "applications",
        data / "applications",
    ]


@dataclass(frozen=True)
class App:
    desktop: str  # ชื่อไฟล์ เช่น libreoffice-writer.desktop (ใช้กับ gtk-launch)
    name: str  # ชื่อที่แสดง (ไทยก่อนถ้ามี)
    aliases: tuple[str, ...]  # คำเรียก · ตัวพิมพ์เล็ก ไม่มีช่องว่าง (รูปเดียวกับ command.normalize)


def _key(text: str) -> str:
    return re.sub(r"\s+", "", text.strip().lower())


def parse_desktop(path: Path) -> App | None:
    """อ่าน [Desktop Entry] · None = ไม่ใช่แอปที่ควรเปิดได้."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    entry: dict[str, str] = {}
    section = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            section = line
            continue
        if section == "[Desktop Entry]" and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            entry.setdefault(k.strip(), v.strip())
    if entry.get("Type") != "Application" or not entry.get("Exec"):
        return None
    if entry.get("NoDisplay", "").lower() == "true" or entry.get("Hidden", "").lower() == "true":
        return None
    name = entry.get("Name[th]") or entry.get("Name") or path.stem
    raw = [entry.get("Name", ""), entry.get("Name[th]", ""), path.stem]
    aliases = tuple(dict.fromkeys(a for a in (_key(x) for x in raw) if len(a) >= 3))
    return App(path.name, name, aliases) if aliases else None


class Registry:
    """แอปจากทุกโฟลเดอร์ · อ่านใหม่เมื่อโฟลเดอร์เปลี่ยน · ไฟล์ชื่อซ้ำ: โฟลเดอร์ของผู้ใช้ชนะของระบบ."""

    def __init__(self, dirs: list[Path] | None = None):
        self.dirs = dirs if dirs is not None else default_dirs()
        self._stamp: tuple | None = None
        self._apps: dict[str, App] = {}

    def _signature(self) -> tuple:
        sig = []
        for d in self.dirs:
            try:
                sig.append((str(d), d.stat().st_mtime_ns))
            except OSError:
                sig.append((str(d), None))
        return tuple(sig)

    def apps(self) -> dict[str, App]:
        sig = self._signature()
        if sig != self._stamp:
            found: dict[str, App] = {}
            for d in self.dirs:  # ลำดับ: ระบบ → ผู้ใช้ · ตัวหลังทับตัวแรก (XDG)
                if d.is_dir():
                    for p in sorted(d.glob("*.desktop")):
                        app = parse_desktop(p)
                        if app is not None:
                            found[app.desktop] = app
            self._apps, self._stamp = found, sig
        return self._apps


REGISTRY = Registry()
