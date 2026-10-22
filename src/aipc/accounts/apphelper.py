"""ตัวติดตั้งแอปจากรายการที่อนุญาต (การ์ด 0054) — รันด้วยสิทธิ์ root ผ่าน sudo เท่านั้น.

เซสชันของผู้ใช้เรียกได้ทางเดียว: `sudo -n /usr/local/sbin/aipc-apps` ไม่มีอาร์กิวเมนต์ (install-apps.sh)
คำขอ JSON ทาง stdin: {"app": "<คีย์ในรายการ>", "admin": "<ชื่อผู้ดูแล>", "password": "<รหัสผู้ดูแล>"}

หลัก H7 (ตัวนี้ตัดสินเองทุกข้อ ไม่เชื่อหน้าจอ):
- ติดตั้งได้เฉพาะคีย์ในรายการ (aipc.skills.app_catalog · ไฟล์ของผู้ดูแลหรือของแอปใน /opt ที่ root เป็นเจ้าของ)
  ชื่อแพ็กเกจมาจากรายการ ไม่ใช่จากคำขอ → "vlc; rm -rf /" หรือ "-o ..." ส่งมาก็ไม่มีทางถึง apt
- ต้องมีรหัสผ่านของบัญชีในกลุ่ม sudo (ผู้ดูแล) · PAM ของ OS ตรวจ · แอปที่ติดตั้งแล้วทุกบัญชีได้ใช้
- ดิสก์ว่างน้อยกว่า 2 GB = ไม่ติดตั้ง (H1) · apt-get install แพ็กเกจเดียว ไม่ remove ไม่ upgrade
บันทึกลง journal ว่าใครขอ แอปอะไร ผลเป็นยังไง · ไม่บันทึกรหัสผ่าน
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time

from aipc.accounts import helper, validation
from aipc.skills import app_catalog

PAM_SERVICE = "aipc-apps"  # /etc/pam.d/aipc-apps · ติดตั้งโดย install-apps.sh
ADMIN_GROUP = "sudo"
MIN_FREE = 2 * 1024**3
APT_TIMEOUT_S = 1800
FAIL_WAIT_S = 3  # รหัสผิด = รอก่อนตอบ (ชะลอการเดารหัสผ่านตัวนี้)
DENIED = "ชื่อหรือรหัสผ่านของผู้ดูแลไม่ถูกต้อง"  # ไม่บอกว่าผิดที่ชื่อหรือรหัส


class System(helper.System):
    """ของที่แตะเครื่องจริง (เพิ่มจากตัวช่วยบัญชี) · เทสต์ใส่ของปลอมแทน."""

    def free_bytes(self) -> int:
        return shutil.disk_usage("/").free

    def apt(self, args: list[str]) -> tuple[int, str]:
        env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive", "LC_ALL": "C"}
        import subprocess

        try:
            r = subprocess.run(["apt-get", *args], capture_output=True, text=True, env=env,
                               timeout=APT_TIMEOUT_S, check=False)  # fmt: skip
        except subprocess.TimeoutExpired:
            return 124, "timeout"
        return r.returncode, (r.stdout + r.stderr)[-4000:]

    def authenticate(self, user: str, password: str) -> bool:
        from aipc.accounts import pam

        return pam.authenticate(PAM_SERVICE, user, password)

    def sleep(self, s: float) -> None:
        time.sleep(s)

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


def install(request: dict, system: System) -> dict:
    key, admin, password = (request.get(k) for k in ("app", "admin", "password"))
    if not all(isinstance(v, str) for v in (key, admin, password)):
        return helper._fail("คำขอไม่ครบ")
    entry = system.catalog().get(key)
    if entry is None or not entry.apt:
        return helper._fail("แอปนี้ไม่อยู่ในรายการที่ติดตั้งได้")
    caller = system.caller()
    if not validation.USERNAME_RE.match(admin) or not system.in_group(admin, ADMIN_GROUP) or \
            not system.authenticate(admin, password):  # fmt: skip
        system.log(f"ติดตั้ง {key}: รหัสผู้ดูแลไม่ผ่าน (ผู้ขอ {caller})")
        system.sleep(FAIL_WAIT_S)
        return helper._fail(DENIED)
    if system.free_bytes() < MIN_FREE:
        return helper._fail("พื้นที่ดิสก์เหลือน้อยกว่า 2 GB · ไม่ติดตั้ง")
    system.log(f"ติดตั้ง {entry.apt} ({key}) · ผู้ขอ {caller} · ผู้ดูแลยืนยัน {admin}")
    code, out = system.apt(["update"])
    if code != 0:
        return helper._fail(_why_apt_failed(out))
    code, out = system.apt(["install", "-y", "--no-install-recommends", entry.apt])
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
