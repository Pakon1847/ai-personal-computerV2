"""ตัวช่วยสร้างบัญชีและกู้คืนรหัสผ่าน (การ์ด 0012) — รันด้วยสิทธิ์ root ผ่าน sudo เท่านั้น.

หน้า Login (ผู้ใช้ `_greetd`) เรียกได้ทางเดียว: `sudo -n /usr/local/sbin/aipc-accounts` ไม่มีอาร์กิวเมนต์
คำขอส่งเป็น JSON ทาง stdin (รหัสผ่านจึงไม่อยู่ใน argv ที่ใครก็เห็นได้จาก ps) · ตอบเป็น JSON ทาง stdout

สมัครเสรี: ใครอยู่ที่หน้า Login ก็สร้างบัญชีได้ ไม่ต้องมีผู้ดูแลอนุมัติ (Pakon 2026-09-29 · การ์ด 0012 ข้อ 11)
บัญชีใหม่ไม่อยู่กลุ่ม sudo · ไม่มีขีดจำกัดจำนวนบัญชี

หลัก H7: หน้าจอไม่ตัดสินอะไร ตัวช่วยนี้ตรวจซ้ำเองทุกข้อ
- ชื่อ/รหัส/ชื่อที่แสดง → กฎชุดเดียวกับหน้าจอ (aipc.accounts.validation)
- PIN กู้คืน → เทียบ hash · ผิดหลายครั้งต้องรอ (สิ่งนี้คือตัวกันการเดา PIN จริง)

หลัก H1: สร้างบัญชีแบบ "ครบหรือไม่มีเลย" — จดงานค้างก่อน useradd แล้วลบเมื่อสำเร็จ
ไฟดับกลางคัน → เรียกครั้งถัดไปลบบัญชีครึ่ง ๆ ทิ้งก่อนทำงานใหม่ (ไม่มีบัญชีที่ไม่มีรหัสผ่านค้าง)
ทุกอย่างที่แตะ OS อยู่ในคลาส System → เทสต์ใส่ของปลอมแทนได้ รันบนวินโดวส์ได้
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from aipc.accounts import validation

CALLER = "_greetd"  # ผู้ใช้ของหน้า Login · คนอื่นเรียกไม่ได้ แม้ผ่าน sudo
VISION = "_aipcvision"  # visiond (การ์ด 0015) · เรียกได้เฉพาะ check-password
PAM_SERVICE = "aipc-accounts"  # /etc/pam.d/aipc-accounts (pam_unix · ติดตั้งโดย install-accounts.sh)
GROUPS = ("video", "render", "audio")  # จอ กล้อง เสียง · ใส่เฉพาะกลุ่มที่เครื่องมีจริง
STATE = Path("/var/lib/aipc")
REQUEST_MAX = 4096
FAIL_FREE = 5  # ผิดได้เท่านี้ก่อนต้องรอ
WAIT_BASE_S, WAIT_MAX_S = 60, 3600
SCRYPT = {"n": 2**14, "r": 8, "p": 1}  # ใช้หน่วยความจำราว 16 MB · 0.1–0.5 วิบน Pi (ค่าประมาณ)
RECOVER_FAIL = "ชื่อผู้ใช้หรือ PIN ไม่ถูกต้อง"  # ไม่บอกว่ามีบัญชีนี้หรือไม่


class System:
    """ทุกอย่างที่แตะเครื่องจริง · ตัวจริงใช้ได้บน Linux ด้วยสิทธิ์ root เท่านั้น."""

    state = STATE

    def caller(self) -> str:
        return os.environ.get("SUDO_USER", "")

    def is_root(self) -> bool:
        return hasattr(os, "geteuid") and os.geteuid() == 0

    def user_home(self, name: str) -> Path | None:
        import pwd

        try:
            return Path(pwd.getpwnam(name).pw_dir)
        except KeyError:
            return None

    def group_exists(self, group: str) -> bool:
        import grp

        try:
            grp.getgrnam(group)
            return True
        except KeyError:
            return False

    def run(self, argv: list[str], stdin: str | None = None) -> int:
        r = subprocess.run(argv, input=stdin.encode() if stdin is not None else None,
                           capture_output=True, timeout=120, check=False)  # fmt: skip
        return r.returncode

    def chmod(self, path: Path, mode: int) -> None:
        os.chmod(path, mode)

    def now(self) -> float:
        return time.time()

    def log(self, text: str) -> None:
        """บันทึกเหตุการณ์ลง journal ของระบบ · ห้ามมีรหัสผ่านหรือ PIN."""
        try:
            import syslog

            syslog.openlog("aipc-accounts")
            syslog.syslog(syslog.LOG_AUTH | syslog.LOG_NOTICE, text)
        except ImportError:  # วินโดวส์ไม่มี syslog
            pass

    def authenticate(self, user: str, password: str) -> bool:
        """PAM ของ OS ตรวจรหัสผ่าน · โค้ดเราไม่อ่าน /etc/shadow เอง."""
        from aipc.accounts import pam

        return pam.authenticate(PAM_SERVICE, user, password)

    def lock(self):
        """ทำทีละคำขอ (สองคำขอพร้อมกันอาจสร้างชื่อเดียวกันสองครั้ง)."""
        import fcntl

        self.state.mkdir(mode=0o700, parents=True, exist_ok=True)
        f = open(self.state / "lock", "w")  # noqa: SIM115 — ปล่อยเมื่อโปรเซสจบ
        fcntl.flock(f, fcntl.LOCK_EX)
        return f


# ---------- ไฟล์ของตัวช่วย (root 0600 ใน /var/lib/aipc) ----------


def _write_private(path: Path, data: dict) -> None:
    """เขียนแบบ atomic และสิทธิ์ 0600 ตั้งแต่สร้างไฟล์ (ไม่มีช่วงที่คนอื่นอ่านได้)."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _recovery_file(system: System, user: str) -> Path:
    return system.state / "recovery" / f"{user}.json"


def _hash(pin: str, salt: bytes) -> str:
    norm = validation.normalize_pin(pin).encode()
    return hashlib.scrypt(norm, salt=salt, maxmem=64 * 1024 * 1024, **SCRYPT).hex()


def _set_pin(system: System, user: str, pin: str) -> None:
    salt = os.urandom(16)
    _write_private(_recovery_file(system, user),
                   {"kind": "pin", "salt": salt.hex(), "hash": _hash(pin, salt), "scrypt": SCRYPT,
                    "issued": int(system.now()), "failed": 0, "wait_until": 0})  # fmt: skip


def _cleanup_pending(system: System) -> None:
    """งานสมัครที่ค้างจากไฟดับ = บัญชีครึ่ง ๆ → ลบทิ้งก่อนทำงานใหม่ (การ์ด 0012 ข้อ 4)."""
    pending = system.state / "pending"
    if not pending.is_dir():
        return
    for marker in pending.iterdir():
        name = marker.name
        if validation.check_username(name).ok and system.user_home(name) is not None:
            system.run(["userdel", "-r", name])
        _recovery_file(system, name).unlink(missing_ok=True)
        marker.unlink(missing_ok=True)
        system.log(f"ลบบัญชีที่สมัครค้างไว้: {name}")


# ---------- คำขอ ----------


def _fail(message: str) -> dict:
    return {"ok": False, "message": message}


def _strings(request: dict, *keys: str) -> list[str] | None:
    vals = [request.get(k) for k in keys]
    return vals if all(isinstance(v, str) for v in vals) else None


def create(request: dict, system: System) -> dict:
    vals = _strings(request, "username", "display_name", "password", "pin")
    if vals is None:
        return _fail("คำขอไม่ครบ")
    user, display, password, pin = vals
    display = display.strip()
    for check in (validation.check_username(user), validation.check_display_name(display),
                  validation.check_password(password, password),
                  validation.check_pin(pin, pin)):  # fmt: skip
        if not check.ok:
            return _fail(check.message)
    if system.user_home(user) is not None:
        return _fail("ชื่อผู้ใช้นี้มีคนใช้แล้ว")

    marker = system.state / "pending" / user
    _write_private(marker, {"since": int(system.now())})
    groups = [g for g in GROUPS if system.group_exists(g)]
    argv = ["useradd", "--create-home", "--shell", "/bin/bash", "--comment", display]
    if groups:
        argv += ["--groups", ",".join(groups)]
    if system.run([*argv, user]) != 0:
        marker.unlink(missing_ok=True)
        return _fail("สร้างบัญชีไม่สำเร็จ (พื้นที่อาจเต็ม) · ไม่มีอะไรค้างในเครื่อง")
    if system.run(["chpasswd"], stdin=f"{user}:{password}\n") != 0:
        system.run(["userdel", "-r", user])
        marker.unlink(missing_ok=True)
        return _fail("ตั้งรหัสผ่านไม่สำเร็จ · ยกเลิกบัญชีนี้แล้ว")
    home = system.user_home(user)
    if home is not None:
        system.chmod(home, 0o700)  # ผู้ใช้อื่นเปิดโฟลเดอร์นี้ไม่ได้ (ข้ออ้างที่ 2 ของเล่ม)
    _set_pin(system, user, pin)
    marker.unlink(missing_ok=True)
    system.log(f"สร้างบัญชี {user} (สมัครเองที่หน้า Login)")
    return {"ok": True, "message": f"สร้างบัญชี {user} แล้ว"}


def recover(request: dict, system: System) -> dict:
    vals = _strings(request, "username", "pin", "new_password")
    if vals is None:
        return _fail("คำขอไม่ครบ")
    user, pin, password = vals
    if not validation.check_username(user).ok:
        return _fail(RECOVER_FAIL)
    path = _recovery_file(system, user)
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _fail(RECOVER_FAIL)  # ไม่มี PIN (เช่น บัญชีแรกที่มาจากตอนลง OS) = ข้อความเดียวกัน
    now = system.now()
    if rec.get("wait_until", 0) > now:
        minutes = int((rec["wait_until"] - now) // 60) + 1
        return _fail(f"ลองผิดหลายครั้ง · ลองใหม่ได้ในอีก {minutes} นาที")
    if not hmac.compare_digest(_hash(pin, bytes.fromhex(rec["salt"])), rec["hash"]):
        rec["failed"] = rec.get("failed", 0) + 1
        extra = rec["failed"] - FAIL_FREE
        if extra >= 0:
            rec["wait_until"] = now + min(WAIT_BASE_S * 2**extra, WAIT_MAX_S)
        _write_private(path, rec)
        system.log(f"กู้คืน {user} ไม่สำเร็จ (ครั้งที่ {rec['failed']})")
        return _fail(RECOVER_FAIL)
    check = validation.check_password(password, password)
    if not check.ok:
        return _fail(check.message)  # PIN ถูก ลองตั้งรหัสใหม่อีกครั้งได้
    if system.run(["chpasswd"], stdin=f"{user}:{password}\n") != 0:
        return _fail("ตั้งรหัสผ่านใหม่ไม่สำเร็จ · ลองใหม่ได้")
    rec["failed"], rec["wait_until"] = 0, 0  # PIN เดิมใช้ต่อได้ (ผู้ใช้จำเอง ไม่ต้องจดชุดใหม่)
    _write_private(path, rec)
    system.log(f"กู้คืน {user} สำเร็จ")
    return {"ok": True, "message": "ตั้งรหัสผ่านใหม่แล้ว"}


def _check_file(system: System, user: str) -> Path:
    return system.state / "password-checks" / f"{user}.json"


def check_password(request: dict, system: System) -> dict:
    """visiond ถามก่อนเปิด/ปิดเข้าเครื่องด้วยใบหน้า (การ์ด 0015) · ผิดหลายครั้งต้องรอ (กันใช้เป็นที่เดารหัส)."""
    vals = _strings(request, "username", "password")
    if vals is None or not validation.check_username(vals[0]).ok:
        return _fail("รหัสผ่านไม่ถูกต้อง")
    user, password = vals
    path = _check_file(system, user)
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rec = {"failed": 0, "wait_until": 0}
    now = system.now()
    if rec.get("wait_until", 0) > now:
        return _fail("ลองผิดหลายครั้ง · รอสักครู่แล้วลองใหม่")
    if system.user_home(user) is None or not system.authenticate(user, password):
        rec["failed"] = rec.get("failed", 0) + 1
        extra = rec["failed"] - FAIL_FREE
        if extra >= 0:
            rec["wait_until"] = now + min(WAIT_BASE_S * 2**extra, WAIT_MAX_S)
        _write_private(path, rec)
        system.log(f"ตรวจรหัสผ่าน {user} (ใบหน้า) ไม่ผ่าน ครั้งที่ {rec['failed']}")
        return _fail("รหัสผ่านไม่ถูกต้อง")
    path.unlink(missing_ok=True)
    return {"ok": True, "message": "รหัสผ่านถูกต้อง"}


def handle(raw: bytes, system: System) -> dict:
    caller = system.caller()
    if caller not in (CALLER, VISION):
        return _fail("เรียกได้จากหน้า Login เท่านั้น")
    if len(raw) > REQUEST_MAX:
        return _fail("คำขอใหญ่เกินไป")
    try:
        request = json.loads(raw)
    except ValueError:
        return _fail("คำขออ่านไม่ได้")
    if not isinstance(request, dict):
        return _fail("คำขออ่านไม่ได้")
    ops = (
        {"create": create, "recover": recover}
        if caller == CALLER
        else {"check-password": check_password}
    )
    op = ops.get(request.get("op"))
    if op is None:
        return _fail("ไม่รู้จักคำขอนี้")
    _cleanup_pending(system)
    return op(request, system)


def main() -> int:
    system = System()
    if not system.is_root():
        print(json.dumps(_fail("ต้องรันด้วยสิทธิ์ root ผ่าน sudo"), ensure_ascii=False))
        return 1
    lock = system.lock()
    try:
        result = handle(sys.stdin.buffer.read(REQUEST_MAX + 1), system)
    finally:
        lock.close()
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
