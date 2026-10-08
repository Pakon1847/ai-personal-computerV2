"""คู่มือเชื่อมต่อ Claude ในแอป (การ์ด 0021 · Pakon เลือก 2026-10-08).

ติดตั้งและเข้าสู่ระบบแยกต่อบัญชี (ตัวติดตั้งทางการวางไว้ที่ ~/.local/bin/claude = ที่ find_claude หา) ·
ทางที่ 1 (ทางสำรอง): ผู้ใช้ SSH จากคอมพิวเตอร์อีกเครื่อง · ทางที่ 2 อยู่ที่ aipc.cloud.connect · โมดูลนี้แค่สร้างข้อความ
ไม่ติดตั้ง ไม่เรียกเน็ต · อ่านแค่ที่อยู่ IP ของเครื่องจาก `hostname -I`
"""

from __future__ import annotations

import subprocess

INSTALL = "curl -fsSL https://claude.ai/install.sh | bash"
CLAUDE = "~/.local/bin/claude"


def addresses(run=subprocess.run) -> list[str]:
    """IPv4 ของเครื่องที่คอมพิวเตอร์เครื่องอื่นใช้ SSH เข้ามาได้ · อ่านไม่ได้ (วินโดวส์/ไม่มีเน็ต) = []."""
    try:
        r = run(["hostname", "-I"], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    return [a for a in r.stdout.split() if a.count(".") == 3 and not a.startswith("127.")]


def steps(user: str, addrs: list[str]) -> list[dict]:
    """ขั้นตอนสำหรับคนที่ไม่เคยใช้ Claude Code · {title, detail, command}.

    command ว่าง = ขั้นนั้นไม่มีคำสั่งให้พิมพ์
    """
    if addrs:
        ssh = {
            "title": "2. เข้าเครื่องนี้ด้วย SSH",
            "detail": "พิมพ์คำสั่งนี้ในเทอร์มินัลของคอมพิวเตอร์เครื่องนั้น · ครั้งแรกถ้าถาม yes/no ให้พิมพ์ yes · "
            "แล้วใส่รหัสผ่านของบัญชีนี้ (ตัวเดียวกับหน้า Login · ตอนพิมพ์จะไม่เห็นตัวอักษร)"
            + ("" if len(addrs) == 1 else " · ถ้าเข้าไม่ได้ ลองที่อยู่อื่น: " + ", ".join(addrs[1:])),
            "command": f"ssh {user}@{addrs[0]}",
        }
    else:
        ssh = {
            "title": "2. เข้าเครื่องนี้ด้วย SSH",
            "detail": "ตอนนี้เครื่องนี้ยังไม่ได้ต่อเน็ต จึงยังไม่มีที่อยู่ให้เข้า · "
            'ต่อเน็ตก่อน แล้วกด "วิธีเชื่อมต่อ Claude" ใหม่',
            "command": "",
        }
    return [
        {
            "title": "1. เตรียมของ",
            "detail": "คอมพิวเตอร์อีกเครื่อง (วินโดวส์เปิด PowerShell · Mac เปิด Terminal) "
            "ที่ต่อเน็ตวงเดียวกับเครื่องนี้ · และบัญชี Claude ที่ใช้ Claude Code ได้ · "
            "คำสั่งในกรอบให้พิมพ์บนเครื่องนั้นตามตัวอักษร",
            "command": "",
        },
        ssh,
        {
            "title": "3. ติดตั้ง Claude Code (ครั้งเดียวต่อบัญชี)",
            "detail": "พิมพ์ต่อในหน้าต่างเดิม แล้วรอจนเสร็จ",
            "command": INSTALL,
        },
        {
            "title": "4. เข้าสู่ระบบ Claude",
            "detail": "ถ้ามีคำถามอื่นขึ้นก่อน (เช่น เลือกสี) กด Enter ผ่านไปได้ · "
            "เลือกเข้าสู่ระบบด้วยบัญชี Claude → คัดลอกลิงก์ที่ขึ้นไปเปิดในเบราว์เซอร์ของคอมพิวเตอร์เครื่องนั้น → "
            "กดอนุญาต → เอารหัสที่ได้มาวาง → พิมพ์ /exit · ถ้าติดตั้งแล้วแต่ถาม Claude ไม่ได้ ให้ทำขั้นนี้ใหม่",
            "command": CLAUDE,
        },
        {
            "title": "5. กลับมาที่เครื่องนี้",
            "detail": 'ออกจากระบบแล้วเข้าใหม่ · หน้านี้จะมีสวิตช์ Claude ขึ้นมา · ลองถาม "ข่าวเด่นวันนี้มีอะไร"',
            "command": "",
        },
    ]
