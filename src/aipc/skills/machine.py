"""สกิล 5: ถามเครื่องว่าเป็นอะไร — อธิบายสถานะเครื่องจากค่าที่อ่านได้จริงเท่านั้น.

แบ่งงานสองชั้น:
1. **โค้ดอ่านค่าและตัดสินว่ามีปัญหาอะไร** (ไฟล์นี้) — ใช้ aipc.doctor ตัวเดียวกับหน้าสุขภาพเครื่อง
   และอ่าน RAM ว่างจาก /proc/meminfo · กฎตรงไปตรงมา ทดสอบได้ครบ
2. LLM (เมื่อมีแล้ว) เรียบเรียงผลของชั้นที่ 1 ให้เป็นประโยคที่อ่านลื่นขึ้นเท่านั้น
   ห้ามเพิ่มข้อเท็จจริงเอง · ตอนนี้ยังไม่มี LLM จึงใช้ประโยคที่เขียนไว้ในโค้ด

กติกา (docs/SKILLS.md สกิล 5): ค่าที่อ่านไม่ได้ต้องบอกว่า "ไม่รู้" ห้ามเดา
วิธีแก้ที่ต้องแตะไฟล์บูตให้เป็นคำแนะนำเท่านั้น ไม่มีปุ่มทำให้อัตโนมัติ
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from aipc.bench import machine as probe
from aipc.doctor import hardware as hw

HOT_C = 80.0  # Pi 5 เริ่มลดความเร็วเองแถว 80–85°C


@dataclass
class Finding:
    level: str  # ok | warn | danger | neutral
    text: str


@dataclass
class Diagnosis:
    headline: str
    findings: list[Finding] = field(default_factory=list)
    advice: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "headline": self.headline,
            "findings": [{"level": f.level, "text": f.text} for f in self.findings],
            "advice": self.advice,
            "unknown": self.unknown,
        }


def mem_available_mb(root: Path = Path("/")) -> int | None:
    try:
        text = (root / "proc/meminfo").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    return None


def has_default_route(root: Path = Path("/")) -> bool | None:
    """มีเส้นทางออกนอกเครื่อง (default route) ไหม · อ่านตาราง route เท่านั้น ไม่ส่งข้อมูลออกไปไหน (H3).

    True = ต่อเครือข่ายอยู่ (ไม่ได้แปลว่าถึงอินเทอร์เน็ตแน่ ๆ) · False = ไม่ได้ต่อ · None = อ่านไม่ได้
    """
    try:
        lines = (root / "proc/net/route").read_text(encoding="utf-8").splitlines()[1:]
    except OSError:
        return None
    for line in lines:
        cols = line.split()
        # คอลัมน์: Iface Destination Gateway Flags ...
        # Destination 00000000 = default · Flags bit 1 = UP
        if len(cols) > 3 and cols[1] == "00000000" and int(cols[3], 16) & 1:
            return True
    return False


def diagnose(checks: list[hw.Check], temp_c: float | None, avail_mb: int | None) -> Diagnosis:
    """ตัดสินจากค่าที่ได้รับเท่านั้น · แยกออกจากการอ่านค่า เพื่อเทสต์ด้วยสถานะจำลองได้ครบทุกแบบ."""
    by_id = {c.id: c for c in checks}
    d = Diagnosis(headline="")
    problems: list[str] = []

    power = by_id.get("power")
    if power and power.status == hw.FAIL:
        d.findings.append(Finding("danger", "เคยไฟตก"))
        d.advice.append("ใช้อะแดปเตอร์ 27W ของแท้ ต่อสายตรงไม่ผ่านฮับ แล้วรีบูต")
        problems.append("ไฟเลี้ยงไม่พอ")
    elif power and power.status == hw.PASS:
        d.findings.append(Finding("ok", "ไฟเลี้ยงปกติ"))
    else:
        d.unknown.append("ไฟเลี้ยง")

    if temp_c is None:
        d.unknown.append("อุณหภูมิ")
    elif temp_c >= HOT_C:
        d.findings.append(Finding("danger", f"อุณหภูมิ {temp_c:.0f}°C"))
        d.advice.append("ตรวจว่าพัดลมหมุน และไม่มีอะไรบังช่องระบายอากาศ")
        problems.append("เครื่องร้อนเกิน")
    else:
        d.findings.append(Finding("ok", f"อุณหภูมิ {temp_c:.0f}°C"))

    cooling = by_id.get("cooling")
    if cooling is None or cooling.status == hw.UNKNOWN:
        d.unknown.append("พัดลม")

    if avail_mb is None:
        d.unknown.append("RAM ว่าง")
    elif avail_mb < 1024:
        d.findings.append(Finding("warn", f"RAM ว่าง {avail_mb / 1024:.1f} GB"))
        d.advice.append("ปิดโปรแกรมหรือโมเดลที่ไม่ได้ใช้ เพื่อคืนหน่วยความจำ")
        problems.append("หน่วยความจำเหลือน้อย")
    else:
        d.findings.append(Finding("ok", f"RAM ว่าง {avail_mb / 1024:.1f} GB"))

    storage = by_id.get("storage")
    if storage and storage.status in (hw.FAIL, hw.WARN):
        level = "danger" if storage.status == hw.FAIL else "warn"
        d.findings.append(Finding(level, "พื้นที่เก็บข้อมูลใกล้เต็ม"))
        d.advice.append("ลบไฟล์ที่ไม่ใช้ หรือย้ายไปไดรฟ์อื่น (เกิน 90% ระบบจะหยุดงานเสริม)")
        problems.append("พื้นที่ใกล้เต็ม")
    elif storage and storage.status == hw.PASS:
        d.findings.append(Finding("ok", "พื้นที่เก็บข้อมูลพอ"))
    else:
        d.unknown.append("พื้นที่เก็บข้อมูล")

    if problems:
        d.headline = "พบปัญหา: " + " และ ".join(problems)
    elif len(d.unknown) >= 3:
        d.headline = "อ่านค่าสถานะของเครื่องนี้ไม่ได้เกือบทั้งหมด — น่าจะไม่ได้รันบน Raspberry Pi"
    else:
        d.headline = "ไม่พบปัญหาจากค่าที่อ่านได้"
    return d


def ask(root: Path = Path("/")) -> Diagnosis:
    """อ่านค่าจากเครื่องจริงแล้วตัดสิน."""
    return diagnose(hw.run_all(root), probe.cpu_temp_c(root), mem_available_mb(root))


# คำที่บอกว่าผู้ใช้ถามเรื่องเครื่อง (ใช้โดย router)
KEYWORDS = ("เครื่อง", "ช้า", "อืด", "ค้าง", "ร้อน", "อุณหภูมิ", "แรม", "ram", "พื้นที่", "ไฟตก", "พัดลม")
