"""ตัวเฝ้าหน้าเจ้าของตอนจอล็อก (การ์ด 0055 ทาง ก) — โมดูล aipc-autounlock ของ gtklock เป็นคนเปิด.

ถาม visiond (คำขอ watch · เจ้าของบัญชีเท่านั้น · ได้แค่ จำนวนหน้า/ใช่เจ้าของไหม) ทุก 2 วิ ·
เห็นเจ้าของ = พิมพ์ "OWNER" แล้วจบทันที (ปิดการเชื่อมต่อ → visiond ปล่อยกล้องให้ PAM สแกนตรวจรูปปลอมต่อ) ·
ตัวนี้ไม่ได้ปลดล็อกเอง: แค่บอกโมดูลให้ "กด Enter" แล้ว PAM + visiond ตัดสินเหมือนคนกดเอง (H7)
exit 0 = เห็นเจ้าของ · 2 = ใช้ไม่ได้ (ไม่มีใบหน้าตอนสมัคร / visiond ไม่ตอบ) → โมดูลรอแล้วลองใหม่
"""

from __future__ import annotations

import getpass
import sys
import threading

OWNER, AGAIN, UNUSABLE = "owner", "again", "unusable"


def watch_once(user: str, watch) -> str:
    """คำขอ watch 1 รอบ (≤ 60 วิ) · เห็นเจ้าของ = หยุดทันที."""
    stop = threading.Event()
    seen = []

    def on_seen(msg: dict) -> None:
        if msg.get("owner"):
            seen.append(True)
            stop.set()

    r = watch(user, on_seen, stop)
    if seen:
        return OWNER
    return AGAIN if r.get("ok") else UNUSABLE


def run(user: str, watch, out=sys.stdout) -> int:
    while True:
        result = watch_once(user, watch)
        if result == OWNER:
            out.write("OWNER\n")
            out.flush()
            return 0
        if result == UNUSABLE:
            return 2


def main() -> int:
    from aipc.vision import client

    return run(getpass.getuser(), client.watch)


if __name__ == "__main__":
    sys.exit(main())
