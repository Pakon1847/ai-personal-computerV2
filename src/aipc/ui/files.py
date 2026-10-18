"""รายการไฟล์สำหรับหน้า "ไฟล์ของฉัน" · อ่านอย่างเดียวในรอบนี้ (ยังไม่มีลบ/ย้าย/ถังขยะ).

กฎสำคัญ (BRIEF 5.6 ข้อ 5): path ต้อง resolve แล้วอยู่ใน home ของผู้ใช้เท่านั้น
ต่อให้มีคนส่งชื่อแปลก ๆ เช่น "../../etc" หรือ symlink ที่ชี้ออกนอก home ก็ต้องออกไม่ได้
resolve() คือการแปลง path ให้เป็นตำแหน่งจริงบนดิสก์ (ตาม symlink และตัด .. ออก) ก่อนเทียบ
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from aipc.ui import thaidate


class OutsideHome(ValueError):
    """พยายามเปิด path ที่อยู่นอก home."""


@dataclass(frozen=True)
class Entry:
    name: str
    is_dir: bool
    size_text: str
    modified_text: str

    def to_dict(self) -> dict:
        return asdict(self)


def inside(root: Path, target: Path) -> Path:
    """คืน path จริงของ target ถ้าอยู่ใน root ไม่งั้นยกข้อผิดพลาด."""
    real_root = root.resolve()
    real = target.resolve()
    if real != real_root and real_root not in real.parents:
        raise OutsideHome(str(target))
    return real


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"  # pragma: no cover


def modified(ts: float, now: datetime | None = None) -> str:
    dt = datetime.fromtimestamp(ts)
    now = now or datetime.now()
    if dt.date() == now.date():
        return "วันนี้ " + thaidate.clock(dt)
    return f"{dt.day} {thaidate.month_short(dt.month)} {thaidate.year(dt)}"


def list_dir(root: Path, relative: str = "") -> list[Entry]:
    """รายการในโฟลเดอร์ · โฟลเดอร์มาก่อน แล้วเรียงตามชื่อ · ไม่แสดงไฟล์ซ่อน (ขึ้นต้นด้วย .)."""
    folder = inside(root, root / relative)
    out = []
    for p in folder.iterdir():
        if p.name.startswith("."):
            continue
        try:
            st = p.stat()
            is_dir = p.is_dir()
            inside(root, p)  # symlink ที่ชี้ออกนอก home จะไม่ถูกแสดง
        except (OSError, OutsideHome):
            continue
        size = "" if is_dir else human_size(st.st_size)
        out.append(Entry(p.name, is_dir, size, modified(st.st_mtime)))
    return sorted(out, key=lambda e: (not e.is_dir, e.name.lower()))
