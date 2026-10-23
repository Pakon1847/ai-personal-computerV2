"""ตัวติดตั้งแอปจากรายการที่อนุญาต (การ์ด 0054) — รันด้วยสิทธิ์ root ผ่าน sudo เท่านั้น.

เซสชันของผู้ใช้เรียกได้ทางเดียว: `sudo -n /usr/local/sbin/aipc-apps` ไม่มีอาร์กิวเมนต์ (install-apps.sh)
คำขอ JSON ทาง stdin: {"app": "<คีย์ในรายการ>"}

หลัก H7 (ตัวนี้ตัดสินเองทุกข้อ ไม่เชื่อหน้าจอ):
- ติดตั้งได้เฉพาะคีย์ในรายการ (aipc.skills.app_catalog · ไฟล์ของผู้ดูแลหรือของแอปใน /opt ที่ root เป็นเจ้าของ)
  ชื่อแพ็กเกจมาจากรายการ ไม่ใช่จากคำขอ → "vlc; rm -rf /" หรือ "-o ..." ส่งมาก็ไม่มีทางถึง apt
- **ไม่ถามรหัส** (Pakon 2026-10-23: กด "ใช่" แล้ว ตกลง/ยกเลิก ก็พอ) · ผู้ใช้ทุกบัญชีบนเครื่องติดตั้งแอปในรายการได้ ·
  แอปที่ติดตั้งแล้วทุกบัญชีได้ใช้ · ความเสี่ยงที่ยอมรับ (การ์ด 0054 หัวข้อ 9): โปรแกรมในบัญชีผู้ใช้สั่งติดตั้งแอปในรายการได้
  ผลแย่สุด = มีแอปจากรายการเพิ่มและเปลืองดิสก์ · ไม่ได้สิทธิ์ root หรือแก้อย่างอื่น
- ดิสก์ว่างน้อยกว่า 2 GB = ไม่ติดตั้ง (H1) · apt-get install แพ็กเกจเดียว ไม่ remove ไม่ upgrade
บันทึกลง journal ว่าใครขอ แอปอะไร ผลเป็นยังไง
"""

from __future__ import annotations

import json
import os
import shutil
import sys

from aipc.accounts import helper
from aipc.skills import app_catalog

MIN_FREE = 2 * 1024**3
APT_TIMEOUT_S = 1800


class System(helper.System):
    """ของที่แตะเครื่องจริง (เพิ่มจากตัวช่วยบัญชี) · เทสต์ใส่ของปลอมแทน."""

    def free_bytes(self) -> int:
        return shutil.disk_usage("/").free

    def apt(self, args: list[str], on_status=None) -> tuple[int, str]:
        """รัน apt-get · on_status(ชนิด, เปอร์เซ็นต์) จากบรรทัด Status-Fd ของ apt เอง
        (dlstatus = ดาวน์โหลด · pmstatus = ติดตั้ง) · ตัวเลขจาก apt จริง ไม่ได้ประมาณเอง (H5)."""
        import subprocess
        import time as _time

        env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive", "LC_ALL": "C"}
        cmd = ["apt-get", "-o", "APT::Status-Fd=1", *args]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                env=env)  # fmt: skip
        tail, end = [], _time.monotonic() + APT_TIMEOUT_S
        for line in proc.stdout:
            status = parse_status(line)
            if status is not None:
                if on_status is not None:
                    on_status(*status)
            else:
                tail = (tail + [line])[-80:]
            if _time.monotonic() > end:
                proc.kill()
                proc.wait()
                return 124, "timeout"
        return proc.wait(), "".join(tail)[-4000:]

    def progress(self, msg: dict) -> None:
        """ส่งความคืบหน้าให้หน้าจอทันที (บรรทัดละ 1 JSON · บรรทัดสุดท้ายที่มี "ok" คือผล)."""
        print(json.dumps(msg, ensure_ascii=False), flush=True)

    def catalog(self) -> dict:
        return app_catalog.load()

    def lock(self):
        """ล็อกแยกจากตัวช่วยบัญชี: ติดตั้งนานหลายนาทีต้องไม่ทำให้หน้า Login สมัคร/กู้บัญชีค้าง."""
        import fcntl

        self.state.mkdir(mode=0o700, parents=True, exist_ok=True)
        f = open(self.state / "apps.lock", "w")  # noqa: SIM115 — ปล่อยเมื่อโปรเซสจบ
        fcntl.flock(f, fcntl.LOCK_EX)
        return f


def _why_apt_failed(out: str) -> str:
    """ข้อความของ apt → เหตุที่ผู้ใช้เข้าใจ (H2) · ไม่รู้ = บอกว่าไม่สำเร็จพร้อมบรรทัดท้ายจริง."""
    if "Could not get lock" in out or "dpkg was interrupted" in out:
        return "มีการติดตั้งอื่นค้างอยู่ในเครื่อง · รอสักครู่แล้วลองใหม่"
    net = ("Temporary failure resolving", "Could not resolve", "Failed to fetch")
    if any(w in out for w in net):
        return "ดาวน์โหลดไม่ได้ · ตรวจอินเทอร์เน็ตแล้วลองใหม่"
    if "Unable to locate package" in out:
        return "ไม่พบแพ็กเกจนี้ในคลังของระบบ"
    if "No space left" in out:
        return "พื้นที่ดิสก์ไม่พอ"
    if out == "timeout":
        return "ติดตั้งนานเกินไป (เกิน 30 นาที) · ยกเลิกแล้ว"
    last = [ln for ln in out.splitlines() if ln.strip()][-1:] or ["ไม่มีข้อความ"]
    return "ติดตั้งไม่สำเร็จ: " + last[0][:200]


def parse_status(line: str) -> tuple[str, float] | None:
    """บรรทัด Status-Fd ของ apt → (ชนิด, เปอร์เซ็นต์) · อย่างอื่น = None.

    "dlstatus:1:42.5:Retrieving file 3 of 9" → ("download", 42.5) ·
    "pmstatus:gimp:60:Unpacking" → ("install", 60)
    """
    parts = line.strip().split(":", 3)
    if len(parts) < 3 or parts[0] not in ("dlstatus", "pmstatus"):
        return None
    try:
        pct = max(0.0, min(100.0, float(parts[2])))
    except ValueError:
        return None
    return ("download" if parts[0] == "dlstatus" else "install"), pct


# เปอร์เซ็นต์รวมบนจอ: เตรียม (apt update) 0–5 · ดาวน์โหลด 5–50 · ติดตั้ง 50–100 · ไม่ถอยหลัง
STAGES = {"download": (5.0, 45.0), "install": (50.0, 50.0)}
STAGE_TEXT = {"prepare": "กำลังเตรียม", "download": "กำลังดาวน์โหลด", "install": "กำลังติดตั้ง"}


def install(request: dict, system: System) -> dict:
    key = request.get("app")
    if not isinstance(key, str):
        return helper._fail("คำขอไม่ครบ")
    entry = system.catalog().get(key)
    if entry is None or not entry.apt:
        return helper._fail("แอปนี้ไม่อยู่ในรายการที่ติดตั้งได้")
    caller = system.caller()
    if system.free_bytes() < MIN_FREE:
        return helper._fail("พื้นที่ดิสก์เหลือน้อยกว่า 2 GB · ไม่ติดตั้ง")
    system.log(f"ติดตั้ง {entry.apt} ({key}) · ผู้ขอ {caller}")
    shown = [0.0]

    def report(stage: str, pct: float) -> None:
        start, span = STAGES.get(stage, (0.0, 5.0))
        total = max(shown[0], round(start + span * pct / 100, 1))
        if total > shown[0] or stage == "prepare":
            shown[0] = total
            system.progress({"state": "progress", "stage": STAGE_TEXT[stage], "percent": total})

    report("prepare", 0)
    code, out = system.apt(["update"])
    if code != 0:
        return helper._fail(_why_apt_failed(out))
    code, out = system.apt(["install", "-y", "--no-install-recommends", entry.apt], report)
    system.log(f"ติดตั้ง {entry.apt}: {'สำเร็จ' if code == 0 else f'ไม่สำเร็จ ({code})'}")
    if code != 0:
        return helper._fail(_why_apt_failed(out))
    return {"ok": True, "message": f"ติดตั้ง {entry.name} แล้ว"}


def handle(raw: bytes, system: System) -> dict:
    caller = system.caller()
    if not caller or caller in ("root", helper.CALLER):
        return helper._fail("เรียกได้จากเซสชันของผู้ใช้เท่านั้น")
    if len(raw) > helper.REQUEST_MAX:
        return helper._fail("คำขอใหญ่เกินไป")
    try:
        request = json.loads(raw)
    except ValueError:
        return helper._fail("คำขออ่านไม่ได้")
    if not isinstance(request, dict):
        return helper._fail("คำขออ่านไม่ได้")
    return install(request, system)


def main() -> int:
    system = System()
    if not system.is_root():
        print(json.dumps(helper._fail("ต้องรันด้วยสิทธิ์ root ผ่าน sudo"), ensure_ascii=False))
        return 1
    lock = system.lock()  # ทีละคำขอ (apt/dpkg ติดตั้งพร้อมกันไม่ได้อยู่แล้ว)
    try:
        result = handle(sys.stdin.buffer.read(helper.REQUEST_MAX + 1), system)
    finally:
        lock.close()
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
