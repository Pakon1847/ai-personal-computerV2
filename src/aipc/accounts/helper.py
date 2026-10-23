"""ตัวช่วยสร้างบัญชีและกู้คืนรหัสผ่าน (การ์ด 0012) — รันด้วยสิทธิ์ root ผ่าน sudo เท่านั้น.

หน้า Login (ผู้ใช้ `_greetd`) เรียกได้ทางเดียว: `sudo -n /usr/local/sbin/aipc-accounts` ไม่มีอาร์กิวเมนต์
คำขอส่งเป็น JSON ทาง stdin (รหัสผ่านจึงไม่อยู่ใน argv ที่ใครก็เห็นได้จาก ps) · ตอบเป็น JSON ทาง stdout

สมัครเสรี: ใครอยู่ที่หน้า Login ก็สร้างบัญชีได้ ไม่ต้องมีผู้ดูแลอนุมัติ (Pakon 2026-09-29 · การ์ด 0012 ข้อ 11)
บัญชีใหม่ไม่อยู่กลุ่ม sudo · ไม่มีขีดจำกัดจำนวนบัญชี

หลัก H7: หน้าจอไม่ตัดสินอะไร ตัวช่วยนี้ตรวจซ้ำเองทุกข้อ
- ชื่อ/รหัส/ชื่อที่แสดง → กฎชุดเดียวกับหน้าจอ (aipc.accounts.validation)
- PIN กู้คืน → เทียบ hash · ผิดหลายครั้งต้องรอ (สิ่งนี้คือตัวกันการเดา PIN จริง)

ลบบัญชี (ข้อเสนอ 2026-10-03 · สิทธิ์ขอให้ลบตาม PDPA): ทำที่หน้า Login ด้วยรหัสผ่าน + พิมพ์ชื่อผู้ใช้ยืนยัน ·
ลบทุกที่ที่ระบบเก็บข้อมูลของบัญชี แล้ว **ตรวจซ้ำทีละที่** ส่งผลกลับเป็นใบยืนยัน · ห้ามลบผู้ดูแล (กลุ่ม sudo)

หลัก H1: สร้างบัญชีแบบ "ครบหรือไม่มีเลย" — จดงานค้างก่อน useradd แล้วลบเมื่อสำเร็จ
ไฟดับกลางคัน → เรียกครั้งถัดไปลบบัญชีครึ่ง ๆ ทิ้งก่อนทำงานใหม่ (ไม่มีบัญชีที่ไม่มีรหัสผ่านค้าง)
ทุกอย่างที่แตะ OS อยู่ในคลาส System → เทสต์ใส่ของปลอมแทนได้ รันบนวินโดวส์ได้
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from aipc.accounts import validation

CALLER = "_greetd"  # ผู้ใช้ของหน้า Login · คนอื่นเรียกไม่ได้ แม้ผ่าน sudo
VISION = "_aipcvision"  # visiond (การ์ด 0015) · เรียกได้เฉพาะ check-password
PAM_SERVICE = "aipc-face-check"  # /etc/pam.d/aipc-face-check · ติดตั้งโดย install-visiond.sh
GROUPS = ("video", "render", "audio", "netdev")  # จอ กล้อง เสียง · เลือก Wi-Fi (การ์ด 0063 ทาง ก)
# ใส่เฉพาะกลุ่มที่เครื่องมีจริง · netdev = เปลี่ยน Wi-Fi ของเครื่องได้ (กฎของ Raspberry Pi OS)
# ไม่ใช่สิทธิ์ผู้ดูแล
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

    # ---------- ใช้ตอนลบบัญชี ----------
    vision_dir = Path("/var/lib/aipc-vision/face-login")  # แม่แบบใบหน้าสำหรับเข้าเครื่อง (visiond)
    leftover_roots = (Path("/tmp"), Path("/var/tmp"), Path("/dev/shm"))

    def uid_of(self, name: str) -> int | None:
        import pwd

        try:
            return pwd.getpwnam(name).pw_uid
        except KeyError:
            return None

    def in_group(self, name: str, group: str) -> bool:
        import grp

        try:
            return name in grp.getgrnam(group).gr_mem
        except KeyError:
            return False

    def has_processes(self, uid: int) -> bool:
        """ยังเข้าใช้อยู่ (มีโปรเซสของบัญชีนี้) = ห้ามลบ."""
        return self.run(["pgrep", "-u", str(uid)]) == 0

    def system_files(self, name: str) -> list[Path]:
        """ไฟล์ของบัญชีนอก home ที่ userdel -r ไม่ได้ลบให้ทุกเครื่อง."""
        return [Path("/var/spool/cron/crontabs") / name, Path("/var/mail") / name,
                Path("/var/spool/mail") / name, Path("/var/lib/systemd/linger") / name]  # fmt: skip

    def owned_by(self, uid: int) -> list[Path]:
        """ไฟล์ค้างที่ยังเป็นของเลขผู้ใช้นี้ · ต้องลบ ไม่งั้นบัญชีใหม่ที่ได้เลขเดิมจะเปิดอ่านได้."""
        found = []
        for top in self.leftover_roots:
            for d, dirs, files in os.walk(top, followlinks=False):
                for n in dirs + files:
                    p = Path(d) / n
                    try:
                        if p.lstat().st_uid == uid:
                            found.append(p)
                    except OSError:
                        pass
        return found

    def remove(self, path: Path) -> None:
        """ลบโดยไม่ตามลิงก์ (ลิงก์ที่ชี้ไปไฟล์ของคนอื่นต้องไม่ทำให้ไฟล์นั้นหาย)."""
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        except FileNotFoundError:
            pass

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
    _reset_keyring(system, user)
    system.log(f"กู้คืน {user} สำเร็จ")
    return {"ok": True, "message": "ตั้งรหัสผ่านใหม่แล้ว"}


def _reset_keyring(system: System, user: str) -> None:
    """ที่เก็บรหัส "login" ของ gnome-keyring เข้ารหัสด้วยรหัสผ่านเก่า → หลังกู้คืนจะถามรหัสเก่าที่ผู้ใช้ลืมไปแล้วทุกครั้ง.

    ลบให้ระบบสร้างใหม่ด้วยรหัสใหม่ตอน login ครั้งถัดไป (Pakon 2026-10-06) ·
    ข้อมูลในนั้นเปิดไม่ได้อยู่แล้วเมื่อไม่มีรหัสเก่า ·
    ลบ**ในนามผู้ใช้** (runuser) → ถ้าใน home มี symlink ก็พาไปลบไฟล์นอกสิทธิ์ของผู้ใช้ไม่ได้ ·
    ลบไม่ได้ = จดไว้ ไม่ทำให้กู้คืนล้ม
    """
    home = system.user_home(user)
    if home is None:
        return
    kr = home / ".local" / "share" / "keyrings"
    code = system.run(
        [
            "runuser",
            "-u",
            user,
            "--",
            "rm",
            "-f",
            str(kr / "login.keyring"),
            str(kr / "user.keystore"),
        ]
    )
    if code != 0:
        system.log(f"ล้าง keyring ของ {user} ไม่สำเร็จ (รหัส {code})")


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


# ---------- ลบบัญชี ----------

PROTECTED_GROUPS = ("sudo", "adm")  # ผู้ดูแลเครื่อง ลบจากหน้า Login ไม่ได้
LIMITS = [
    "ลบไฟล์บน microSD ไม่รับประกันว่าข้อมูลเก่าหายจากชิปจริง (ต้องเข้ารหัส home ตาม ADR-003 · ยังไม่มีในรุ่นนี้)",
    "ข้อความที่เคยส่งให้ Claude หรือ Open-Meteo ลบจากเครื่องนี้แล้ว แต่ลบจากฝั่งผู้ให้บริการไม่ได้",
    "สำเนาสำรองบนไดรฟ์ USB (ถ้าเคยทำ) อยู่นอกเครื่อง ต้องลบเอง",
]


def _deleting_file(system: System, user: str) -> Path:
    return system.state / "deleting" / user


def _faces(system: System, user: str) -> list[Path]:
    return sorted(system.vision_dir.glob(f"{user}.json*"))  # หลัก สำรอง ชั่วคราว


def _wipe(system: System, user: str, uid: int | None, home: Path | None) -> list[dict]:
    """ลบทุกที่ที่เก็บข้อมูลของบัญชี แล้วตรวจซ้ำทีละที่ · คืนรายการสำหรับใบยืนยัน."""
    if system.user_home(user) is not None:
        system.run(["userdel", "-r", user])
    if home is not None and home.exists():
        system.remove(home)  # userdel ลบ home ไม่ครบ (เช่น มีไฟล์ของคนอื่นอยู่ข้างใน)
    for p in [_recovery_file(system, user), _check_file(system, user), *_faces(system, user),
              *system.system_files(user)]:  # fmt: skip
        system.remove(p)
    if uid is not None:  # ลึกสุดก่อน: ลบไฟล์ข้างในก่อนโฟลเดอร์
        for p in sorted(system.owned_by(uid), key=lambda p: len(p.parts), reverse=True):
            system.remove(p)
    left = system.owned_by(uid) if uid is not None else []
    others = not any(p.exists() for p in system.system_files(user))
    return [
        {"what": "บัญชีผู้ใช้ในระบบ", "gone": system.user_home(user) is None},
        {"what": "โฟลเดอร์ส่วนตัว (แชท นัด ไฟล์ การตั้งค่า สกิล ประวัติส่งออก แม่แบบใบหน้าในโฟลเดอร์)",
         "gone": home is None or not home.exists()},
        {"what": "PIN กู้คืน", "gone": not _recovery_file(system, user).exists()},
        {"what": "ตัวนับรหัสผ่านผิด", "gone": not _check_file(system, user).exists()},
        {"what": "แม่แบบใบหน้าสำหรับเข้าเครื่อง", "gone": not _faces(system, user)},
        {"what": "งานตั้งเวลา · กล่องจดหมาย · บริการค้าง", "gone": others},
        {"what": "ไฟล์ค้างที่ยังผูกกับเลขผู้ใช้เดิม (/tmp /var/tmp /dev/shm)", "gone": not left},
    ]  # fmt: skip


def delete(request: dict, system: System) -> dict:
    vals = _strings(request, "username", "password", "confirm")
    if vals is None:
        return _fail("คำขอไม่ครบ")
    user, password, confirm = vals
    if confirm.strip() != user:
        return _fail("พิมพ์ชื่อผู้ใช้ยืนยันไม่ตรง · ยังไม่ได้ลบอะไร")
    uid = system.uid_of(user) if validation.check_username(user).ok else None
    if uid is None or system.user_home(user) is None:
        return _fail("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")  # ไม่บอกว่ามีบัญชีนี้หรือไม่
    # ผิดหลายครั้งต้องรอ (ตัวนับเดียวกับ check-password · ใช้ลบเป็นทางเดารหัสไม่ได้)
    if not check_password({"username": user, "password": password}, system)["ok"]:
        return _fail("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    if uid < 1000 or any(system.in_group(user, g) for g in PROTECTED_GROUPS):
        return _fail("บัญชีผู้ดูแลเครื่องลบจากหน้า Login ไม่ได้")
    if system.has_processes(uid):
        return _fail("บัญชีนี้ยังเปิดใช้อยู่ · ออกจากระบบบัญชีนี้ก่อน แล้วลองใหม่")
    home = system.user_home(user)
    marker = _deleting_file(system, user)
    _write_private(marker, {"uid": uid, "home": str(home), "since": int(system.now())})
    checks = _wipe(system, user, uid, home)
    ok = all(c["gone"] for c in checks)
    if ok:
        marker.unlink(missing_ok=True)
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(system.now()))
    system.log(f"ลบบัญชี {user} ({'ครบ' if ok else 'ไม่ครบ'})")
    return {"ok": ok, "user": user, "at": when, "checks": checks, "limits": LIMITS,
            "message": f"ลบบัญชี {user} แล้ว" if ok else "ลบไม่ครบ · ดูรายการที่ยังเหลือ"}  # fmt: skip


def _resume_deleting(system: System) -> None:
    """ไฟดับกลางการลบ → ลบต่อให้จบก่อนทำงานใหม่ (ไม่ทิ้งบัญชีครึ่ง ๆ)."""
    folder = system.state / "deleting"
    if not folder.is_dir():
        return
    for marker in folder.iterdir():
        try:
            info = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            info = {}
        name = marker.name
        if not validation.check_username(name).ok:
            marker.unlink(missing_ok=True)
            continue
        home = Path(info["home"]) if info.get("home") else None
        if all(c["gone"] for c in _wipe(system, name, info.get("uid"), home)):
            marker.unlink(missing_ok=True)
        system.log(f"ลบบัญชีที่ค้างจากไฟดับต่อ: {name}")


THEMES = ("dark", "light")  # ชุดเดียวกับ aipc.ui.settings.THEMES (ตัวช่วยไม่ import ส่วนหน้าจอ)
THEME_FILE_MAX = 65536


def _greeter_user_file(system: System) -> Path:
    return system.state / "greeter-user.json"


def greeter_theme(request: dict, system: System) -> dict:
    """ธีมของหน้า Login = ธีมของผู้ใช้ที่เข้าล่าสุด (การ์ด 0051 · Pakon 2026-10-22).

    หน้า Login (`_greetd`) อ่าน home ของผู้ใช้ไม่ได้ (ตั้งใจ) → ตัวช่วยอ่านให้ แต่คืนแค่ "dark"/"light"
    มี "user" = เพิ่งเข้าสำเร็จ → จำชื่อไว้ (root 0600) · ไม่มี = หน้า Login เพิ่งเปิด → อ่านธีมปัจจุบันของคนที่จำไว้
    (จึงได้ธีมที่ผู้ใช้เปลี่ยนระหว่างใช้งานด้วย) · อ่านไม่ได้ทุกกรณี = ธีมดำ (ค่าเริ่มต้นการ์ด 0041)
    """
    user = request.get("user")
    if user is not None:
        if not isinstance(user, str) or not validation.USERNAME_RE.match(user):
            return _fail("ชื่อผู้ใช้ไม่ถูกต้อง")
        if system.user_home(user) is not None:
            _write_private(_greeter_user_file(system), {"user": user})
    return {"ok": True, "theme": _theme_of_last_user(system)}


def _theme_of_last_user(system: System) -> str:
    try:
        user = json.loads(_greeter_user_file(system).read_text(encoding="utf-8")).get("user")
        home = system.user_home(user) if isinstance(user, str) else None
        if home is None:
            return "dark"
        # ไฟล์อยู่ในพื้นที่ของผู้ใช้ (ผู้ใช้แก้/ทำลิงก์ได้) → ต้องอยู่ใน home จริง · จำกัดขนาด ·
        # คืนได้แค่ค่าในรายการ จึงไม่มีข้อมูลอื่นรั่วออกไปหน้า Login
        path = (home / ".config" / "aipc" / "ui.json").resolve()
        if not path.is_relative_to(home.resolve()) or path.stat().st_size > THEME_FILE_MAX:
            return "dark"
        theme = json.loads(path.read_text(encoding="utf-8")).get("theme")
    except (OSError, ValueError, AttributeError):
        return "dark"
    return theme if theme in THEMES else "dark"


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
        {"create": create, "recover": recover, "delete": delete, "greeter-theme": greeter_theme}
        if caller == CALLER
        else {"check-password": check_password}
    )
    op = ops.get(request.get("op"))
    if op is None:
        return _fail("ไม่รู้จักคำขอนี้")
    _cleanup_pending(system)
    _resume_deleting(system)
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
