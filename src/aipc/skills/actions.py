"""รายการ Action ที่อนุญาต (allow-list) และตัวสั่งทำงาน (BRIEF 5.6).

กติกาที่ไฟล์นี้บังคับ:
1. ทำได้เฉพาะ Action ในตาราง ACTIONS · อะไรที่ไม่อยู่ในตาราง ทำไม่ได้ ไม่ว่าใครขอ
2. เรียกโปรแกรมแบบส่ง list ไม่ผ่าน shell (ไม่มี shell=True) ข้อความแปลก ๆ จึงกลายเป็นคำสั่งอื่นไม่ได้
3. เว็บที่เปิดได้เป็นรายการคงที่ ไม่รับ URL ที่ประกอบจากข้อความ (กันการพาข้อมูลออกทางพารามิเตอร์)
   · สกิล .md เปิด https://… ได้ เฉพาะที่เขียนตายตัวในไฟล์สกิลซึ่งผ่านการตรวจและอนุมัติแล้ว (mdskill.py)
4. ระดับความเสี่ยงอยู่ที่ Action ไม่ใช่ที่สกิล — สกิลหรือ AI ลดระดับเองไม่ได้

บนเครื่องที่ไม่ใช่ Linux (เช่นวินโดวส์ที่ใช้พัฒนา) ตัวสั่งทำงานเป็นแบบ "จำลอง": บอกว่าจะรันอะไร แต่ไม่รันจริง
ผลลัพธ์บอกเสมอว่าเป็นการจำลอง เพื่อไม่ให้หน้าจอแกล้งทำเป็นว่าทำสำเร็จ
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
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
    # แอปเว็บที่ใช้บ่อย (การ์ด 0031) · เปิดอย่างเดียว ผู้ใช้เข้าสู่ระบบในหน้าเว็บเอง · ระบบไม่เก็บรหัส
    "calendar": ("Google Calendar", "https://calendar.google.com"),
    "drive": ("Google Drive", "https://drive.google.com"),
    # แทน Facebook/Instagram (Pakon 2026-10-19): เอกสารออนไลน์ (บัญชี Google เดียวกับ Gmail/Drive) ·
    # ข่าวจากสื่อสาธารณะ (AI ในเครื่องไม่รู้ข่าววันนี้)
    "docs": ("Google Docs", "https://docs.google.com/document/"),
    "news": ("ข่าว Thai PBS", "https://www.thaipbs.or.th"),
    # ดูหนัง/ฟังเพลง (Pakon เลือก 2026-10-19 · มีบัญชีเอง) ·
    # ที่อยู่ตรวจ 2026-10-19 (hotstar.com/th → disneyplus.com)
    # ต้องใช้ Widevine · ปุ่มหน้าแรกเพิ่มเมื่อลองบน Pi แล้วเล่นได้จริง (การ์ด 0031 รอบ 2 เกณฑ์ R2)
    "netflix": ("Netflix", "https://www.netflix.com/th/"),
    "viu": ("Viu", "https://www.viu.com/ott/th"),
    "iqiyi": ("iQIYI", "https://www.iq.com"),
    "wetv": ("WeTV", "https://wetv.vip"),
    "disney": ("Disney+ Hotstar", "https://www.disneyplus.com/th-th"),
    "spotify": ("Spotify", "https://open.spotify.com"),
}
# เว็บที่ต้องเปิดด้วยเบราว์เซอร์ปกติแทนเบราว์เซอร์ของผู้ช่วย (การ์ด 0031 ข้อ 0: บริการที่ไม่ยอมให้เข้าสู่ระบบ
# ในเบราว์เซอร์ที่ถูกโปรแกรมควบคุม) · ยังไม่มีผลทดสอบ = ว่าง · ได้ผลแล้วใส่ชื่อเว็บที่โดนบล็อกที่นี่ที่เดียว
SYSTEM_BROWSER_SITES: frozenset[str] = frozenset()
FALLBACK_NOTE = (" · เปิดด้วยเบราว์เซอร์ปกติแทน"
                 " (เบราว์เซอร์ของผู้ช่วยไม่ว่างหรือใช้ไม่ได้ · ต้องเข้าสู่ระบบแยกกัน)")  # fmt: skip

# แอปบน Raspberry Pi OS: ชื่อไฟล์ .desktop ที่ gtk-launch ใช้ · ยังไม่ได้ตรวจกับ image จริงทุกตัว
# ถ้าเครื่องไม่มีแอปนั้น ผลจะบอกว่า "ไม่พบแอป" ไม่ใช่ทำเป็นว่าเปิดได้
APPS = {
    "browser": ("เบราว์เซอร์", "chromium.desktop"),
    "terminal": ("เทอร์มินัล", "lxterminal.desktop"),
    "filemanager": ("ตัวจัดการไฟล์", "pcmanfm.desktop"),
}

# แอปที่หาเจอจากไฟล์ .desktop ในเครื่อง (apps.py · งานข้อ ⑥) ใช้ id "desk:<ไฟล์>"
# แอปในตารางบนชนะถ้าเป็นไฟล์เดียวกัน


def app_table() -> dict[str, tuple[str, str]]:
    """id → (ชื่อที่แสดง, ไฟล์ .desktop) · ตารางคงที่ข้างบน + แอปที่ติดตั้งจริง (อ่านใหม่เมื่อโฟลเดอร์เปลี่ยน)."""
    from aipc.skills import apps

    static = {v[1] for v in APPS.values()}
    found = {f"desk:{a.desktop}": (a.name, a.desktop) for a in apps.REGISTRY.apps().values()
             if a.desktop not in static}  # fmt: skip
    return {**found, **APPS}


# หน้าในระบบของเรา (ไม่รันโปรแกรมใด แค่บอกหน้าจอให้เปลี่ยนหน้า)
PAGES = {
    "workspace": "ผู้ช่วย AI",
    "calendar": "ปฏิทิน",  # การ์ด 0038
    "files": "ไฟล์ของฉัน",
    "skills": "Skill",
    "privacy": "ตั้งค่า (ส่วนความเป็นส่วนตัว)",
    "health": "สุขภาพเครื่อง",
    "settings": "ตั้งค่า",
}
# หน้าความเป็นส่วนตัวตัดออกในขอบเขตรอบ 3 · ที่ลบข้อมูลใบหน้าอยู่ในหน้าตั้งค่า
# ผู้ใช้ยังพูดว่า "เปิดหน้าความเป็นส่วนตัว" ได้ แต่หน้าจอพาไปหน้าตั้งค่า
PAGE_SCREEN = {"privacy": "settings"}

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
    undo: tuple[Plan, ...] = ()  # ทำตามลำดับเพื่อคืนสภาพเดิม · () = ย้อนไม่ได้ หรืออ่านสภาพเดิมไม่ได้


Runner = Callable[[list[str]], int]
Reader = Callable[[list[str]], str | None]

# ย้อนกลับได้ (ข้อเสนอ 2026-10-03): ผลวัดเสียงพบว่าเสียงคนพูดแทรกทำให้ "เปิดวิกิ" กลายเป็น
# "เปิดเสียง…" แล้วทำเลยโดยไม่ถาม
# (docs/benchmarks/2026-10-01-voice-noise) · ห้ามพลาดไม่ได้ 100% จึงทำให้คืนได้ในกดเดียว
# อ่านสภาพก่อนทำทุกครั้ง · อ่านไม่ได้ = ไม่เสนอปุ่มย้อน (ไม่เดาว่าเดิมเป็นเท่าไหร่)
VOLUME_ACTIONS = ("set_volume", "change_volume", "mute", "unmute")


def read_output(args: list[str]) -> str | None:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def parse_volume(text: str | None) -> tuple[int, bool] | None:
    """ผลของ wpctl get-volume เช่น "Volume: 0.40 [MUTED]" → (40, True)."""
    m = re.match(r"\s*Volume:\s*(\d+(?:\.\d+)?)(\s*\[MUTED\])?", text or "")
    return (round(float(m[1]) * 100), bool(m[2])) if m else None


def undo_plans(before: tuple[int, bool]) -> tuple[Plan, ...]:
    percent, muted = before
    return (
        Plan("set_volume", {"percent": percent}, f"คืนระดับเสียงเป็น {percent}%"),
        Plan("mute" if muted else "unmute", {}, "ปิดเสียงเหมือนเดิม" if muted else "เปิดเสียงเหมือนเดิม"),
    )


# โปรแกรมที่เปิดแอปอื่น · แอปที่เปิดขึ้นมาทำงานต่อหลังคำสั่งจบ จึงห้ามรอ output ของมัน
LAUNCHERS = ("xdg-open", "gtk-launch", "gio")
LAUNCH_SETTLE_S = 1.5  # รอดูแค่ว่าตัวเปิดล้มทันทีไหม (เช่น ไม่พบแอป) · ยังทำงานอยู่ = กำลังเปิดแอป


def run_process(args: list[str]) -> int:
    """รันคำสั่งแบบ list (ไม่ผ่าน shell) · คืนรหัสจบ · 127 = รันไม่ได้หรือหมดเวลา."""
    quiet = dict.fromkeys(("stdin", "stdout", "stderr"), subprocess.DEVNULL)
    try:
        if args and args[0] in LAUNCHERS:
            return _launch(args, quiet)
        return subprocess.run(args, check=False, timeout=10, **quiet).returncode
    except (OSError, subprocess.TimeoutExpired):
        return 127


def _launch(args: list[str], quiet: dict) -> int:
    """เปิดแอปโดยไม่ผูก output และแยกกลุ่มโปรเซส.

    เดิมใช้ capture_output: แอปที่ถูกเปิดถือ pipe ไว้ → รอจนหมดเวลา 10 วิ (หน้าจอค้าง)
    แล้วรายงานว่าล้มเหลวทั้งที่แอปเปิดแล้ว (พบ 2026-09-28)
    """
    p = subprocess.Popen(args, start_new_session=True, **quiet)
    try:
        return p.wait(timeout=LAUNCH_SETTLE_S)
    except subprocess.TimeoutExpired:
        # ยังทำงานอยู่ = กำลังเปิดแอป (xdg-open บางแบบรันแอปค้างไว้เอง) · เก็บโปรเซสเมื่อจบ ไม่ให้เป็น zombie
        threading.Thread(target=p.wait, daemon=True).start()
        return 0


DESKTOP_DIRS = (
    "~/.local/share/applications",
    "/usr/local/share/applications",
    "/usr/share/applications",
)


def _app_command(desktop: str) -> list[str]:
    """gtk-launch ถ้ามี · ไม่มี = gio launch <ไฟล์ .desktop> (มากับ glib ทุกเครื่อง).

    พบบน Pi 5 (2026-10-01): Raspberry Pi OS ของเครื่องนี้ไม่มี gtk-launch
    → "เปิดเทอร์มินัล" และคำสั่งเปิดแอปทุกตัวเปิดไม่ขึ้น
    """
    import shutil
    from pathlib import Path

    if shutil.which("gtk-launch") is None and shutil.which("gio") is not None:
        for d in DESKTOP_DIRS:
            f = Path(d).expanduser() / desktop
            if f.is_file():
                return ["gio", "launch", str(f)]
    return ["gtk-launch", desktop]


def command_for(plan: Plan) -> list[str] | None:
    """แปลง Plan เป็นคำสั่งแบบ list · None = ไม่ต้องรันโปรแกรม (เช่น เปลี่ยนหน้าในระบบ)."""
    p = plan.params
    if plan.action == "open_url":
        return ["xdg-open", p["url"] if "url" in p else SITES[p["site"]][1]]
    if plan.action == "open_app":
        return _app_command(app_table()[p["app"]][1])  # KeyError = แอปถูกถอนไปแล้ว
    if plan.action == "set_volume":
        return ["wpctl", "set-volume", SINK, f"{int(p['percent'])}%"]
    if plan.action == "change_volume":
        step = int(p["step"])
        # -l 1.0: เพิ่มได้ไม่เกิน 100% (พบบน Pi 5 2026-10-12: 100% + "เพิ่มเสียง" = 110% เสียงแตกได้)
        return ["wpctl", "set-volume", "-l", "1.0", SINK, f"{abs(step)}%{'+' if step > 0 else '-'}"]
    if plan.action in ("mute", "unmute"):
        return ["wpctl", "set-mute", SINK, "1" if plan.action == "mute" else "0"]
    return None


class Executor:
    def __init__(
        self,
        runner: Runner = run_process,
        dry_run: bool | None = None,
        reader: Reader = read_output,
        browser=None,
    ):
        self._run = runner
        self._read = reader
        # การ์ด 0031: เปิดเว็บด้วยเบราว์เซอร์ของผู้ช่วยตัวเดียวกับคำสั่งเสียง (เข้าสู่ระบบครั้งเดียว) ·
        # browser(site, url) -> เริ่มเปิดได้ไหม · None / ไม่ว่าง = เปิดด้วยเบราว์เซอร์ปกติแล้วบอก (H2)
        self._browser = browser
        self.dry_run = (not sys.platform.startswith("linux")) if dry_run is None else dry_run

    def execute(self, plan: Plan) -> Outcome:
        if plan.action not in ACTIONS:  # ป้องกันซ้ำอีกชั้น แม้ Plan จะมาจากตัวแปลคำสั่งของเราเอง
            return Outcome(False, f"ไม่อนุญาต: {plan.action}")
        if plan.action == "open_page":
            key = plan.params["page"]
            return Outcome(True, f"เปิดหน้า{PAGES[key]}", page=PAGE_SCREEN.get(key, key))
        try:
            args = command_for(plan)
        except KeyError:
            return Outcome(False, "ไม่พบแอปนี้ในเครื่อง")
        if self.dry_run:
            return Outcome(True, f"จำลอง (ไม่ได้รันจริงบนเครื่องนี้): {' '.join(args)}", simulated=True)
        note = ""
        if plan.action == "open_url" and self._browser is not None:
            site = plan.params.get("site", "")
            url = plan.params.get("url") or SITES[site][1]
            if site not in SYSTEM_BROWSER_SITES:
                if self._browser(site, url):
                    return Outcome(True, f"{plan.summary or 'เปิดเว็บ'} ในเบราว์เซอร์ของผู้ช่วย")
                note = FALLBACK_NOTE
        before = None
        if plan.action in VOLUME_ACTIONS:
            before = parse_volume(self._read(["wpctl", "get-volume", SINK]))
        code = self._run(args)
        if code == 0:
            return Outcome(
                True, (plan.summary or "เรียบร้อย") + note, undo=undo_plans(before) if before else ()
            )
        if plan.action == "open_app":
            return Outcome(False, "ไม่พบแอปนี้ในเครื่อง")
        return Outcome(False, f"ทำไม่สำเร็จ (รหัส {code})")
