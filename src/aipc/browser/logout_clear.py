"""ออกจากบัญชีเว็บทุกครั้งที่ออกจากระบบ (การ์ด 0031 รอบ 3) · สคริปต์เซสชันเรียกหลัง labwc จบ ก่อน greetd ปิดเซสชัน.

ทุกทางของการออกจากระบบจบที่ labwc (กดออก · ไม่ใช้เครื่องนาน · กล้องไม่เห็นเจ้าของ · หน้าจอล่มซ้ำ) จึงล้างที่จุดเดียว ·
ผู้ใช้ไม่ได้เปิดสวิตช์ = ไม่แตะอะไร · ลบจนเสร็จที่นี่ (ไม่ทิ้งไว้เธรดเบื้องหลัง เพราะเซสชันจบแล้วโปรเซสถูกปิดหมด) ·
ทำอะไรไม่สำเร็จ = เขียนลง log แล้วจบปกติ ไม่ขวางการออกจากระบบ (H2) · ไม่แตะเบราว์เซอร์ธรรมดาและไฟล์ดาวน์โหลด

    python -m aipc.browser.logout_clear
"""

from __future__ import annotations

import os
import shutil
import signal
import sys
import time
from pathlib import Path

from aipc.browser import control

FAILED = "web-clear-failed"  # ไฟล์บอกว่าล้างครั้งก่อนไม่สำเร็จ (หน้าจอบอกผู้ใช้ตอนเข้าครั้งหน้า)


def state_dir() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "aipc"


def browser_pids(profile: Path, proc: Path = Path("/proc")) -> list[int]:
    """โปรเซส Chromium ที่ใช้โปรไฟล์นี้ (ดูจาก --user-data-dir ในบรรทัดคำสั่ง) · ไม่มี /proc = []."""
    want = f"--user-data-dir={profile}".encode()
    out = []
    for d in proc.glob("[0-9]*"):
        try:
            if want in (d / "cmdline").read_bytes():
                out.append(int(d.name))
        except (OSError, ValueError):
            continue
    return out


def close_browser(profile: Path, wait_s: float = 3.0, kill=os.kill, pids=browser_pids) -> None:
    """ปิดเบราว์เซอร์ของผู้ช่วยที่ยังค้าง (TERM แล้วรอ · ยังอยู่ = KILL) ก่อนลบ ไม่ให้เขียนไฟล์ระหว่างลบ."""
    for pid in pids(profile):
        try:
            kill(pid, signal.SIGTERM)
        except OSError:
            pass
    end = time.monotonic() + wait_s
    while pids(profile) and time.monotonic() < end:
        time.sleep(0.1)
    for pid in pids(profile):
        try:
            kill(pid, signal.SIGKILL)
        except OSError:
            pass


def clear(profile: Path, enabled: bool, state_dir: Path, close=close_browser) -> str:
    """คืนสิ่งที่ทำ: "off" · "none" (ไม่มีโปรไฟล์) · "cleared" · "failed: …"."""
    flag = state_dir / FAILED
    if not enabled:
        return "off"
    try:
        close(profile)
        if profile.exists():
            gone = profile.with_name(f"{profile.name}{control.REMOVING}{time.time_ns()}")
            profile.rename(gone)  # ออกจากบัญชีทันทีแม้ไฟดับระหว่างลบ
        left = sorted(profile.parent.glob(profile.name + control.REMOVING + "*"))
        for p in left:
            shutil.rmtree(p)
        flag.unlink(missing_ok=True)
        return "cleared" if left else "none"
    except OSError as e:
        try:
            state_dir.mkdir(parents=True, exist_ok=True)
            flag.write_text(str(e), encoding="utf-8")
        except OSError:
            pass
        return f"failed: {e}"


def main() -> int:
    from aipc.ui import settings

    prefs = settings.load()
    from aipc.skills.actions import account_profile

    on = prefs.clear_web_on_logout
    for profile in (control.default_profile(), account_profile()):  # ผู้ช่วย + หน้าต่างบัญชี Google
        result = clear(profile, on, state_dir())
        print(f"aipc-logout-clear {profile.name}: {result}", file=sys.stderr)
    return 0  # ไม่ขวางการออกจากระบบไม่ว่าผลเป็นอะไร


if __name__ == "__main__":
    sys.exit(main())
