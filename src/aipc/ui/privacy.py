"""แผงความเป็นส่วนตัวแบบสด (Pakon เลือกข้อ ข 2026-10-07 · docs/benchmarks/2026-10-07-privacy-panel).

อ่านค่าจริงจาก OS และบันทึกส่งออก ไม่เดา (H5):
- AI ในเครื่องถูกล็อกเน็ตไหม: llama-server ของผู้ใช้ (aipc-llm.service) มี `Seccomp: 2` และอยู่คนละ
  network namespace กับหน้าจอ (docs/benchmarks/2026-10-07-llm-netsandbox-pi5) · อ่านไม่ได้ = "unknown"
- ส่งข้อมูลออกวันนี้กี่ครั้ง: นับจาก ~/.local/share/aipc/outbound.json (aipc.cloud.ledger)
"""

from __future__ import annotations

import os
import subprocess
from datetime import date, datetime
from pathlib import Path


def llm_pid(run=subprocess.run) -> int | None:
    """PID ของ llama-server ของผู้ใช้คนนี้ · ไม่มี systemd / service ไม่ได้รัน = None."""
    try:
        r = run(["systemctl", "--user", "show", "aipc-llm", "-p", "MainPID", "--value"],
                capture_output=True, text=True, timeout=5)  # fmt: skip
    except (OSError, subprocess.TimeoutExpired):
        return None
    try:
        pid = int(str(r.stdout).strip())
    except ValueError:
        return None
    return pid if r.returncode == 0 and pid > 0 else None


def sandbox_state(pid: int | None, proc: Path = Path("/proc"), readlink=os.readlink) -> str:
    """สถานะล็อกเน็ตของ llama-server จาก OS.

    locked = seccomp เปิด และ network namespace แยกจากหน้าจอ · open = ไม่ครบ · unknown = อ่านไม่ได้
    """
    if pid is None:
        return "unknown"
    try:
        status = (proc / str(pid) / "status").read_text(encoding="utf-8", errors="replace")
        ns_llm = readlink(str(proc / str(pid) / "ns" / "net"))
        ns_me = readlink(str(proc / "self" / "ns" / "net"))
    except OSError:
        return "unknown"
    seccomp = False
    for line in status.splitlines():
        if line.startswith("Seccomp:"):
            seccomp = line.split(":", 1)[1].strip() == "2"
    return "locked" if seccomp and ns_llm != ns_me else "open"


def today_counts(entries: list[dict], today: date) -> dict[str, int]:
    """จำนวนรายการที่ส่งออกวันนี้ แยกตามชนิด (ask · skill · weather)."""
    out: dict[str, int] = {}
    for e in entries:
        try:
            when = datetime.fromisoformat(str(e.get("time", ""))).date()
        except ValueError:
            continue
        if when == today:
            kind = str(e.get("kind", ""))
            out[kind] = out.get(kind, 0) + 1
    return out


def panel_text(llm: str, sent_today: int, all_off: bool) -> str:
    parts = []
    if llm == "locked":
        parts.append("AI ในเครื่อง: ต่อเน็ตไม่ได้")
    elif llm == "open":
        parts.append("AI ในเครื่อง: ไม่ได้ล็อกเน็ต")
    # all_off = ปิดทางที่ส่งออกเอง (Claude · อากาศ) · ค้นเว็บด้วยเสียงไม่มีสวิตช์และส่งเมื่อผู้ใช้สั่ง →
    # ห้ามเขียน "ปิดทั้งหมด" และนับครั้งที่ส่งจริงเสมอ (ตรวจทั้งระบบ 2026-10-18 ข้อ 2.6 · H5)
    if all_off:
        parts.append("Claude/อากาศ: ปิด")
    parts.append(f"ส่งออกวันนี้ {sent_today} ครั้ง")
    return " · ".join(parts)


def panel_kind(llm: str, all_off: bool, flash: bool) -> str:
    """สีของป้าย: มีข้อมูลเพิ่งออก = accent · AI ไม่ได้ล็อก = warn · ล็อก/ปิดทั้งหมด = ok."""
    if flash:
        return "accent"
    if llm == "open":
        return "warn"
    return "ok" if llm == "locked" or all_off else "neutral"
