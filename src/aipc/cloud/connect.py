"""เชื่อมต่อ Claude ที่เครื่องนี้ (การ์ด 0021 หัวข้อ 10 · Pakon เลือก 2026-10-08).

รันในหน้าต่างคำสั่งที่แอปเปิดให้ (`lxterminal --command="python -m aipc.cloud.connect"`) ·
คำสั่งตายตัว ไม่ใช่ shell ทั่วไป:
ไม่มี claude → ตัวติดตั้งทางการ → `claude auth login` (หน้าเข้าสู่ระบบเปิดใน Chromium ของเครื่องนี้ ·
ไม่ต้องพิมพ์ /exit · Pakon 2026-10-28: "ทำให้เข้าผ่านเทอร์มินัลในเครื่องได้เลย จะได้ง่าย") →
ตรวจด้วย `claude auth status` → บอกผลตามจริง
แล้วรอ Enter ก่อนปิดหน้าต่าง · การเข้าสู่ระบบเก็บใน home ของบัญชีนี้เท่านั้น
"""

from __future__ import annotations

import json
import subprocess
import sys

from aipc.cloud.ask import find_claude
from aipc.cloud.setup_guide import INSTALL


def _wait(ask) -> None:
    try:
        ask("\nกด Enter เพื่อปิดหน้าต่างนี้ ")
    except EOFError:
        pass


def logged_in(exe: str, run=subprocess.run) -> bool:
    """`claude auth status` บอก loggedIn: true · อ่านไม่ได้ = ถือว่ายังไม่เข้า (H5)."""
    try:
        r = run([exe, "auth", "status"], capture_output=True, text=True, timeout=20)
        return bool(json.loads(r.stdout or "{}").get("loggedIn"))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def main(find=find_claude, run=subprocess.run, out=print, ask=input) -> int:
    out("เชื่อมต่อ Claude สำหรับบัญชีนี้ · ทำครั้งเดียว · การเข้าสู่ระบบเป็นของบัญชีนี้คนเดียว\n")
    exe = find()
    if exe is None:
        out("ขั้น 1/2 · ติดตั้ง Claude Code (ต้องต่อเน็ต · รอสักครู่)\n")
        # pipefail: curl ล้ม (ไม่มีเน็ต) ต้องไม่กลายเป็น "สำเร็จ" เพราะ bash ฝั่งขวาได้ข้อความว่าง
        r = run(["bash", "-c", "set -o pipefail; " + INSTALL])
        exe = find()
        if r.returncode != 0 or exe is None:
            out('\nติดตั้งไม่สำเร็จ · ตรวจว่าเครื่องต่อเน็ตอยู่ แล้วกดปุ่ม "เชื่อมต่อที่เครื่องนี้" ใหม่')
            _wait(ask)
            return 1
    else:
        out("ขั้น 1/2 · มี Claude Code ในบัญชีนี้แล้ว ข้ามการติดตั้ง\n")
    out("ขั้น 2/2 · เข้าสู่ระบบ Claude")
    out("  - หน้าเข้าสู่ระบบ Claude จะเปิดใน Chromium → เข้าสู่ระบบ → กด Authorize (อนุญาต)")
    out("  - ถ้าหน้านั้นให้รหัสมา: กด Copy Code → กลับมาหน้าต่างนี้")
    out("    → กด Ctrl+Shift+V (หรือคลิกขวา → Paste) → กด Enter")
    out("  - ถ้า Chromium ไม่เปิดเอง: กด Enter ตามที่หน้าต่างนี้บอก หรือคัดลอกลิงก์ที่ขึ้นไปเปิดใน Chromium\n")
    run([exe, "auth", "login"])
    if not logged_in(exe, run):
        out('\nยังไม่ได้เข้าสู่ระบบ Claude · ปิดหน้าต่างนี้แล้วกดปุ่ม "เชื่อมต่อที่เครื่องนี้" ใหม่')
        _wait(ask)
        return 1
    out("\nเข้าสู่ระบบ Claude แล้ว · ออกจากระบบแล้วเข้าใหม่ หน้าผู้ช่วยจะใช้ Claude ได้")
    _wait(ask)
    return 0


if __name__ == "__main__":
    sys.exit(main())
