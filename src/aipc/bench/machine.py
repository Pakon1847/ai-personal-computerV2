"""เก็บสภาพเครื่องตอนวัด ตาม BRIEF หัวข้อ 9 "วิธีวัดประสิทธิภาพ".

ตัวเลขที่ไม่รู้ว่าวัดบนเครื่องไหน ร้อนไหม ไฟตกไหม และโค้ดเวอร์ชันไหน
คือตัวเลขที่ตรวจย้อนไม่ได้ จึงใช้ในบทที่ 4 ไม่ได้

ทุกฟังก์ชันในไฟล์นี้ **อ่านอย่างเดียว** ไม่เขียนหรือแก้อะไรบนเครื่อง
ถ้าอ่านค่าไหนไม่ได้ (เช่น รันบนวินโดวส์ที่ไม่มี /proc) จะได้ None แทนการ crash
เพื่อให้เครื่องมือเดียวกันรันได้ทั้งบนเครื่องพัฒนาและบน Pi

พารามิเตอร์ root กับ run มีไว้ให้เทสต์ส่งไฟล์ปลอมและคำสั่งปลอมเข้ามาได้
ตอนใช้งานจริงไม่ต้องส่ง ค่าเริ่มต้นคือเครื่องจริง
"""

from __future__ import annotations

import platform
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# ความหมายของแต่ละบิตใน `vcgencmd get_throttled` ตามเอกสารของ Raspberry Pi
# บิต 0–3 = "ตอนนี้กำลังเกิด" · บิต 16–19 = "เคยเกิดตั้งแต่บูต"
THROTTLE_BITS = {
    0: "ไฟตก (under-voltage) ตอนนี้",
    1: "ความถี่ CPU ถูกจำกัด ตอนนี้",
    2: "กำลังถูกลดความเร็ว (throttled) ตอนนี้",
    3: "ถึงขีดอุณหภูมิแบบนุ่ม ตอนนี้",
    16: "เคยไฟตกตั้งแต่บูต",
    17: "เคยถูกจำกัดความถี่ตั้งแต่บูต",
    18: "เคยถูกลดความเร็วตั้งแต่บูต",
    19: "เคยถึงขีดอุณหภูมิแบบนุ่มตั้งแต่บูต",
}

Runner = Callable[[list[str]], str | None]


def run_command(args: list[str]) -> str | None:
    """รันคำสั่งแบบส่งเป็น list (ไม่ผ่าน shell) แล้วคืนข้อความที่พิมพ์ออกมา.

    ไม่ใช้ shell=True เพราะ BRIEF 5.6 ข้อ 5 ห้าม และเพราะแบบ list
    ไม่มีทางที่ข้อความแปลก ๆ ในพารามิเตอร์จะกลายเป็นคำสั่งอื่นได้
    คำสั่งไม่มี / ล้ม / ค้างเกิน 10 วิ → คืน None
    """
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0:
        return None
    return done.stdout.strip()


def _read(root: Path, path: str) -> str | None:
    try:
        return (root / path.lstrip("/")).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def board_model(root: Path = Path("/")) -> str | None:
    """ชื่อรุ่นบอร์ดจาก device tree เช่น 'Raspberry Pi 5 Model B Rev 1.0'."""
    text = _read(root, "/proc/device-tree/model")
    return text.rstrip("\x00\n ") if text else None


def board_class(model: str | None) -> str:
    """จัดกลุ่มเครื่องเป็น pi5 / pi4 / other.

    สำคัญมาก เพราะ BRIEF หัวข้อ 9 ให้ระดับหลักฐาน 4 ได้เฉพาะผลที่วัดบน Pi 5
    """
    if model and model.startswith("Raspberry Pi 5"):
        return "pi5"
    if model and model.startswith("Raspberry Pi 4"):
        return "pi4"
    return "other"


def ram_total_mb(root: Path = Path("/")) -> int | None:
    text = _read(root, "/proc/meminfo")
    if not text:
        return None
    for line in text.splitlines():
        if line.startswith("MemTotal:"):
            return int(line.split()[1]) // 1024  # ค่าใน meminfo เป็น kB
    return None


def os_pretty_name(root: Path = Path("/")) -> str | None:
    text = _read(root, "/etc/os-release")
    if not text:
        return None
    for line in text.splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip().strip('"')
    return None


def cpu_temp_c(root: Path = Path("/")) -> float | None:
    """อุณหภูมิ CPU จาก sysfs (หน่วยในไฟล์เป็นมิลลิองศา)."""
    text = _read(root, "/sys/class/thermal/thermal_zone0/temp")
    try:
        return int(text.strip()) / 1000 if text else None
    except ValueError:
        return None


def throttled_raw(run: Runner = run_command) -> int | None:
    """อ่านค่า get_throttled เป็นตัวเลข เช่น 'throttled=0x50005' → 0x50005."""
    out = run(["vcgencmd", "get_throttled"])
    if not out or "=" not in out:
        return None
    try:
        return int(out.split("=", 1)[1], 16)
    except ValueError:
        return None


def decode_throttled(value: int) -> list[str]:
    """แปลงตัวเลขเป็นรายการปัญหาภาษาคน · 0 = ไม่มีปัญหา = รายการว่าง."""
    return [text for bit, text in THROTTLE_BITS.items() if value & (1 << bit)]


def git_commit(repo: Path, run: Runner = run_command) -> tuple[str | None, bool | None]:
    """คืน (commit, มีไฟล์ที่ยังไม่ commit ไหม).

    BRIEF หัวข้อ 9 บอกว่าหลักฐานผูกกับ commit ถ้าวัดตอนมีไฟล์ค้างแก้อยู่
    ตัวเลขนั้นไม่ได้ผูกกับ commit ใดจริง ๆ runner จะเตือนเรื่องนี้
    """
    commit = run(["git", "-C", str(repo), "rev-parse", "HEAD"])
    status = run(["git", "-C", str(repo), "status", "--porcelain"])
    dirty = None if status is None else bool(status.strip())
    return commit, dirty


@dataclass
class MachineInfo:
    collected_at: str
    hostname: str
    board_model: str | None
    board_class: str
    ram_total_mb: int | None
    os: str | None
    kernel: str
    python: str
    cpu_temp_c: float | None
    throttled: int | None
    throttled_problems: list[str] = field(default_factory=list)
    git_commit: str | None = None
    git_dirty: bool | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def collect(
    repo: Path | None = None, root: Path = Path("/"), run: Runner = run_command
) -> MachineInfo:
    model = board_model(root)
    throttled = throttled_raw(run)
    commit, dirty = git_commit(repo, run) if repo else (None, None)
    return MachineInfo(
        collected_at=datetime.now(UTC).isoformat(timespec="seconds"),
        hostname=platform.node(),
        board_model=model,
        board_class=board_class(model),
        ram_total_mb=ram_total_mb(root),
        os=os_pretty_name(root) or platform.platform(),
        kernel=platform.release(),
        python=platform.python_version(),
        cpu_temp_c=cpu_temp_c(root),
        throttled=throttled,
        throttled_problems=decode_throttled(throttled) if throttled is not None else [],
        git_commit=commit,
        git_dirty=dirty,
    )
