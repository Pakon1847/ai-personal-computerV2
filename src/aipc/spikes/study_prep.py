"""เตรียมบัญชีสำหรับทดสอบกับผู้ใช้ (docs/eval/user-study/README.md) · รันเช้าวันทดสอบ.

    # ดูก่อน (ไม่เปลี่ยนอะไร) แล้วจึงสร้าง + ใส่ข้อมูล (--apply)
    sudo /opt/aipc-v2/.venv/bin/python -m aipc.spikes.study_prep p1 p2 p3 p4 p5
    sudo /opt/aipc-v2/.venv/bin/python -m aipc.spikes.study_prep p1 p2 p3 p4 p5 --apply

ต่อบัญชี: สร้างผ่านตัวช่วยเดียวกับหน้าสมัคร (sudo -u _greetd sudo -n /usr/local/sbin/aipc-accounts) ·
ใส่ไฟล์ใบเสร็จสำหรับโจทย์ T5 · ใส่นัดของวันนี้ 1 นัด (โจทย์ T3 "วันนี้ต้องทำอะไรบ้าง" ต้องมีคำตอบ) ·
ไม่บันทึกเสียง/ภาพ · หลังทดสอบลบบัญชีที่หน้า Login › ลบบัญชี (ได้ทดสอบฟีเจอร์ลบบัญชีกับของจริงไปด้วย)
รหัสผ่าน/PIN ถามทางคีย์บอร์ด ไม่รับทาง argument (ไม่ค้างใน history)
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
from datetime import datetime, time
from pathlib import Path

from aipc.skills.reminders import Reminder, ReminderStore

RECEIPT_NAME = "ใบเสร็จค่าซ่อมแอร์.txt"
RECEIPT = """ร้านแอร์เย็นฉ่ำ เซอร์วิส
ใบเสร็จรับเงิน เลขที่ 2026/0917
วันที่ 17 กันยายน 2569

รายการ
- ล้างแอร์ติดผนัง 12,000 BTU 1 เครื่อง   600 บาท
- เปลี่ยนคาปาซิเตอร์คอมเพรสเซอร์          850 บาท
- ค่าเดินทาง                               150 บาท

รวมทั้งสิ้น 1,600 บาท (หนึ่งพันหกร้อยบาทถ้วน)
ชำระเงินสด · ขอบคุณที่ใช้บริการ
"""
TASK_T5_ANSWER = "1,600 บาท"
TODAY_REMINDER = ("รับยาที่โรงพยาบาล", time(18, 0))
HELPER = ["sudo", "-u", "_greetd", "sudo", "-n", "/usr/local/sbin/aipc-accounts"]


def seed(home: Path, now: datetime) -> list[Path]:
    """ใส่ข้อมูลโจทย์ลง home (ยังไม่ chown) · คืนไฟล์ที่เขียน."""
    docs = home / "Documents"
    docs.mkdir(parents=True, exist_ok=True)
    receipt = docs / RECEIPT_NAME
    receipt.write_text(RECEIPT, encoding="utf-8")
    path = home / ".local" / "share" / "aipc" / "reminders.json"
    store = ReminderStore(path)
    what, at = TODAY_REMINDER
    when = datetime.combine(now.date(), at).astimezone()
    store.add(Reminder(what=what, when=when), now=now)
    return [receipt, path]


def chown_tree(paths: list[Path], home: Path, uid: int, gid: int) -> None:
    for p in paths:
        cur = p
        while True:
            os.chown(cur, uid, gid)
            if cur.parent == home or cur == home:
                break
            cur = cur.parent


def create(user: str, display: str, password: str, pin: str, run=subprocess.run) -> dict:
    req = json.dumps({"op": "create", "username": user, "display_name": display,
                      "password": password, "pin": pin})  # fmt: skip
    r = run(HELPER, input=req, capture_output=True, text=True, check=False)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"ok": False, "message": (r.stderr or r.stdout)[:300]}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m aipc.spikes.study_prep")
    p.add_argument("users", nargs="+")
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    now = datetime.now().astimezone()
    print(
        f"วันนี้ {now:%Y-%m-%d} · นัด T3: {TODAY_REMINDER[0]} {TODAY_REMINDER[1]:%H:%M} · "
        f"ไฟล์ T5: ~/Documents/{RECEIPT_NAME}"
        f" (คำตอบที่ถูก {TASK_T5_ANSWER})"
    )
    if not a.apply:
        for u in a.users:
            print(f"[จะทำ] สร้างบัญชี {u} (ชื่อที่แสดง: ผู้ร่วมทดสอบ {u.upper()}) → ใส่ไฟล์ใบเสร็จ + นัดวันนี้")
        print("ถ้าถูกต้อง: เติม --apply")
        return 0
    if os.geteuid() != 0:
        print("ต้องรันด้วย sudo", file=sys.stderr)
        return 2
    password = getpass.getpass("รหัสผ่านของบัญชีทดสอบ (ใช้ร่วมกันทุกบัญชี · บอกผู้ร่วมทดสอบตอนโจทย์ T1): ")
    pin = getpass.getpass("PIN กู้คืน (ตัวเลข): ")
    import pwd  # มีเฉพาะ Linux

    bad = 0
    for u in a.users:
        res = create(u, f"ผู้ร่วมทดสอบ {u.upper()}", password, pin)
        if not res.get("ok"):
            print(f"✕ {u}: {res.get('message')}")
            bad += 1
            continue
        pw = pwd.getpwnam(u)
        home = Path(pw.pw_dir)
        written = seed(home, now)
        chown_tree(written, home, pw.pw_uid, pw.pw_gid)
        print(f"✓ {u}: สร้างแล้ว · {', '.join(str(x.relative_to(home)) for x in written)}")
    print(
        "ต่อไป: เข้าบัญชีละครั้งที่หน้าจอ รอ 1 นาทีให้ AI อุ่นแคช แล้วออก (ข้อความแรกของผู้ร่วมทดสอบจะไม่ต้องรอ ~40 วิ)"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
