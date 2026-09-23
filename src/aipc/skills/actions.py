"""รายการ Action ที่อนุญาต (allow-list) และตัวสั่งทำงาน (BRIEF 5.6).

กติกาที่ไฟล์นี้บังคับ:
1. ทำได้เฉพาะ Action ในตาราง ACTIONS · อะไรที่ไม่อยู่ในตาราง ทำไม่ได้ ไม่ว่าใครขอ
2. เรียกโปรแกรมแบบส่ง list ไม่ผ่าน shell (ไม่มี shell=True) ข้อความแปลก ๆ จึงกลายเป็นคำสั่งอื่นไม่ได้
3. เว็บที่เปิดได้เป็นรายการคงที่ ไม่รับ URL ที่ประกอบจากข้อความ (กันการพาข้อมูลออกทางพารามิเตอร์)
4. ระดับความเสี่ยงอยู่ที่ Action ไม่ใช่ที่สกิล — สกิลหรือ AI ลดระดับเองไม่ได้

บนเครื่องที่ไม่ใช่ Linux (เช่นวินโดวส์ที่ใช้พัฒนา) ตัวสั่งทำงานเป็นแบบ "จำลอง": บอกว่าจะรันอะไร แต่ไม่รันจริง
ผลลัพธ์บอกเสมอว่าเป็นการจำลอง เพื่อไม่ให้หน้าจอแกล้งทำเป็นว่าทำสำเร็จ
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ActionSpec:
    id: str
    risk: str  # low | medium | high
    label: str
    needs_network: bool = False


ACTIONS: dict[str, ActionSpec] = {
    a.id: a
    for a in [
        ActionSpec("open_url", "low", "เปิดเว็บจากรายการที่กำหนด", needs_network=True),
        ActionSpec("open_app", "low", "เปิดแอป"),
        ActionSpec("open_page", "low", "เปิดหน้าในระบบ"),
        ActionSpec("set_volume", "medium", "ปรับเสียง"),
        ActionSpec("change_volume", "medium", "เพิ่ม/ลดเสียง"),
        ActionSpec("mute", "low", "ปิดเสียง"),
        ActionSpec("unmute", "low", "เปิดเสียง"),
    ]
}

# เว็บที่เปิดได้ — ต้องเพิ่มที่นี่เท่านั้น (ห้ามรับ URL จากข้อความ)
SITES = {
    "youtube": ("YouTube", "https://www.youtube.com"),
    "gmail": ("Gmail", "https://mail.google.com"),
    "google": ("Google", "https://www.google.com"),
    "wikipedia": ("วิกิพีเดีย", "https://th.wikipedia.org"),
    "maps": ("Google Maps", "https://maps.google.com"),
}

# แอปบน Raspberry Pi OS: ชื่อไฟล์ .desktop ที่ gtk-launch ใช้ · ยังไม่ได้ตรวจกับ image จริงทุกตัว
# ถ้าเครื่องไม่มีแอปนั้น ผลจะบอกว่า "ไม่พบแอป" ไม่ใช่ทำเป็นว่าเปิดได้
APPS = {
    "browser": ("เบราว์เซอร์", "chromium.desktop"),
    "terminal": ("เทอร์มินัล", "lxterminal.desktop"),
    "filemanager": ("ตัวจัดการไฟล์", "pcmanfm.desktop"),
}

# หน้าในระบบของเรา (ไม่รันโปรแกรมใด แค่บอกหน้าจอให้เปลี่ยนหน้า)
PAGES = {
    "workspace": "ผู้ช่วย AI",
    "files": "ไฟล์ของฉัน",
    "skills": "Skill",
    "privacy": "ความเป็นส่วนตัว",
    "health": "สุขภาพเครื่อง",
    "settings": "ตั้งค่า",
}

SINK = "@DEFAULT_AUDIO_SINK@"  # ลำโพงหลักของ PipeWire (ระบบเสียงของ Raspberry Pi OS)


@dataclass(frozen=True)
class Plan:
    """สิ่งที่จะทำ 1 อย่าง · summary คือประโยคที่ผู้ใช้เห็นก่อน/หลังทำ."""

    action: str
    params: dict = field(default_factory=dict)
    summary: str = ""

    @property
    def spec(self) -> ActionSpec:
        return ACTIONS[self.action]


@dataclass(frozen=True)
class Outcome:
    ok: bool
    message: str
    simulated: bool = False
    page: str = ""  # สำหรับ open_page: หน้าที่หน้าจอต้องเปลี่ยนไป


Runner = Callable[[list[str]], int]


def run_process(args: list[str]) -> int:
    try:
        return subprocess.run(args, check=False, capture_output=True, timeout=10).returncode
    except (OSError, subprocess.TimeoutExpired):
        return 127


def command_for(plan: Plan) -> list[str] | None:
    """แปลง Plan เป็นคำสั่งแบบ list · None = ไม่ต้องรันโปรแกรม (เช่น เปลี่ยนหน้าในระบบ)."""
    p = plan.params
    if plan.action == "open_url":
        return ["xdg-open", SITES[p["site"]][1]]
    if plan.action == "open_app":
        return ["gtk-launch", APPS[p["app"]][1]]
    if plan.action == "set_volume":
        return ["wpctl", "set-volume", SINK, f"{int(p['percent'])}%"]
    if plan.action == "change_volume":
        step = int(p["step"])
        return ["wpctl", "set-volume", SINK, f"{abs(step)}%{'+' if step > 0 else '-'}"]
    if plan.action in ("mute", "unmute"):
        return ["wpctl", "set-mute", SINK, "1" if plan.action == "mute" else "0"]
    return None


class Executor:
    def __init__(self, runner: Runner = run_process, dry_run: bool | None = None):
        self._run = runner
        self.dry_run = (not sys.platform.startswith("linux")) if dry_run is None else dry_run

    def execute(self, plan: Plan) -> Outcome:
        if plan.action not in ACTIONS:  # ป้องกันซ้ำอีกชั้น แม้ Plan จะมาจากตัวแปลคำสั่งของเราเอง
            return Outcome(False, f"ไม่อนุญาต: {plan.action}")
        if plan.action == "open_page":
            return Outcome(True, f"เปิดหน้า{PAGES[plan.params['page']]}", page=plan.params["page"])
        args = command_for(plan)
        if self.dry_run:
            return Outcome(True, f"จำลอง (ไม่ได้รันจริงบนเครื่องนี้): {' '.join(args)}", simulated=True)
        code = self._run(args)
        if code == 0:
            return Outcome(True, plan.summary or "เรียบร้อย")
        if plan.action == "open_app":
            return Outcome(False, "ไม่พบแอปนี้ในเครื่อง")
        return Outcome(False, f"ทำไม่สำเร็จ (รหัส {code})")
