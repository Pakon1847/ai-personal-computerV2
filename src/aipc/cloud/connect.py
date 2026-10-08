"""เชื่อมต่อ Claude ที่เครื่องนี้ (การ์ด 0021 หัวข้อ 10 · Pakon เลือก 2026-10-08).

รันในหน้าต่างคำสั่งที่แอปเปิดให้ (`lxterminal --command="python -m aipc.cloud.connect"`) ·
คำสั่งตายตัว ไม่ใช่ shell ทั่วไป:
ไม่มี claude → ตัวติดตั้งทางการ → รัน claude ให้ผู้ใช้เข้าสู่ระบบ (หน้าเข้าสู่ระบบเปิดใน Chromium ของเครื่องนี้) →
ผู้ใช้พิมพ์ /exit → บอกผล แล้วรอ Enter ก่อนปิดหน้าต่าง · การเข้าสู่ระบบเก็บใน home ของบัญชีนี้เท่านั้น
"""

from __future__ import annotations

import subprocess
import sys

from aipc.cloud.ask import find_claude
from aipc.cloud.setup_guide import INSTALL


def _wait(ask) -> None:
    try:
        ask("\nกด Enter เพื่อปิดหน้าต่างนี้ ")
    except EOFError:
        pass


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
    out("  - ถ้ามีคำถามอื่นขึ้นก่อน (เช่น เลือกสี) กด Enter ผ่านไปได้")
    out("  - เลือกเข้าสู่ระบบด้วยบัญชี Claude → หน้าเข้าสู่ระบบจะเปิดใน Chromium → กดอนุญาต")
    out("  - ถ้า Chromium ให้รหัสมา ให้คัดลอกมาวางในหน้าต่างนี้")
    out("  - เสร็จแล้วพิมพ์ /exit แล้วกด Enter\n")
    run([exe])
    if find() is None:
        out("\nไม่พบ Claude Code · ลองกดปุ่มเชื่อมต่อใหม่")
        _wait(ask)
        return 1
    out("\nเสร็จแล้ว · ออกจากระบบแล้วเข้าใหม่ หน้าผู้ช่วยจะใช้ Claude ได้")
    out("ถ้าถาม Claude แล้วยังไม่ได้ = ยังไม่ได้เข้าสู่ระบบ · กดปุ่มเชื่อมต่อใหม่แล้วทำขั้น 2 อีกครั้ง")
    _wait(ask)
    return 0


if __name__ == "__main__":
    sys.exit(main())
