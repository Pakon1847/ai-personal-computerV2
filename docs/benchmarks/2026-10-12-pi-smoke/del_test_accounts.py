"""ลบบัญชีทดสอบที่ค้าง (Pakon สั่ง 2026-10-13) · ใช้ _wipe ตัวเดียวกับปุ่มลบบัญชีในหน้า Login.

รัน: sudo /opt/aipc-v2/.venv/bin/python -I /tmp/del_test_accounts.py
"""

import pwd
import sys

sys.path.insert(0, "/opt/aipc-v2/src")
from aipc.accounts import helper  # noqa: E402

USERS = ["t12a", "t12b", "pakon2"]
system = helper.System()
if not system.is_root():
    sys.exit("ต้องรันด้วย sudo")
for name in USERS:
    try:
        info = pwd.getpwnam(name)
    except KeyError:
        print(f"{name}: ไม่มีแล้ว")
        continue
    if info.pw_uid < 1000 or any(system.in_group(name, g) for g in helper.PROTECTED_GROUPS):
        print(f"{name}: เป็นบัญชีผู้ดูแล · ข้าม")
        continue
    if system.has_processes(info.pw_uid):
        print(f"{name}: ยังเปิดใช้อยู่ · ข้าม")
        continue
    checks = helper._wipe(system, name, info.pw_uid, helper.Path(info.pw_dir))
    ok = all(c["gone"] for c in checks)
    system.log(f"ลบบัญชี {name} ({'ครบ' if ok else 'ไม่ครบ'}) · ลบบัญชีทดสอบค้างตามที่ Pakon สั่ง")
    print(f"{name} (uid {info.pw_uid}): {'ลบครบ' if ok else 'ไม่ครบ'}")
    for c in checks:
        print(f"   {'✓' if c['gone'] else '✗'} {c['what']}")
