"""ตรวจความพร้อมก่อนสาธิต (Pakon เลือก 2026-10-02) · กดครั้งเดียว ได้เขียว/เหลือง/แดง พร้อมวิธีแก้.

รวมเรื่องที่เจอจริงระหว่างทดสอบ: ปลั๊กหลุดจน Pi รีบูต (ไฟเลี้ยง) · เน็ตเปลี่ยนจน Pi หลุด · Pi ร้อน 87°C ·
หลังบูตนาฬิกาผิดจนเน็ตมา (ไม่มีแบต RTC) → นัดเตือนผิดเวลาได้
อ่านอย่างเดียว ไม่แก้อะไรบนเครื่อง · ค่าที่อ่านไม่ได้ = "ไม่รู้" ไม่ใช่ผ่าน
"""

from __future__ import annotations

import shutil
import socket
import subprocess
from collections.abc import Callable
from pathlib import Path

from aipc.doctor.hardware import FAIL, PASS, UNKNOWN, WARN, Check
from aipc.i18n import tr

Runner = Callable[[list[str]], str | None]


def _run(cmd: list[str]) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def check_ai(ready: bool) -> Check:
    if ready:
        return Check("ai", tr("AI ในเครื่อง"), PASS, tr("ตอบได้"))
    return Check(
        "ai",
        tr("AI ในเครื่อง"),
        FAIL,
        tr("ยังไม่พร้อม (กำลังโหลด หรือหยุดทำงาน)"),
        tr("รอ 1–2 นาทีหลังเข้าระบบ · ถ้ายังไม่พร้อม ออกจากระบบแล้วเข้าใหม่"),
    )


def check_network(connect=socket.create_connection) -> Check:
    try:
        connect(("api.open-meteo.com", 443), timeout=3).close()
        return Check("net", tr("อินเทอร์เน็ต"), PASS, tr("ต่อได้ (สกิลอากาศ · Claude ใช้ได้)"))
    except OSError:
        return Check(
            "net",
            tr("อินเทอร์เน็ต"),
            WARN,
            tr("ต่อไม่ได้ · AI ในเครื่องยังใช้ได้ แต่ถามข้อมูลสด/อากาศ/Claude ไม่ได้"),
            tr("ต่อ Wi-Fi หรือฮอตสปอต แล้วตรวจอีกครั้ง"),
        )


def check_clock(run: Runner = _run) -> Check:
    out = run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"])
    if out is None:
        return Check("clock", tr("นาฬิกาเครื่อง"), UNKNOWN, tr("อ่านสถานะการตั้งเวลาไม่ได้"))
    if out == "yes":
        return Check("clock", tr("นาฬิกาเครื่อง"), PASS, tr("ตั้งเวลาจากอินเทอร์เน็ตแล้ว · นัดเตือนตรงเวลา"))
    return Check(
        "clock",
        tr("นาฬิกาเครื่อง"),
        WARN,
        tr("ยังไม่ได้ตั้งเวลาจากอินเทอร์เน็ต · หลังบูตเวลาอาจผิด นัดอาจเตือนผิดเวลา"),
        tr("ต่อเน็ตแล้วรอ ~1 นาที · ถ้าไม่มีเน็ตวันสาธิต ให้ใส่แบต RTC (ดูการ์ดนาฬิกา RTC)"),
    )


def check_power_and_heat(run: Runner = _run) -> list[Check]:
    out = []
    t = run(["vcgencmd", "measure_temp"])
    try:
        temp = float(t.split("=")[1].split("'")[0]) if t else None
    except (IndexError, ValueError):
        temp = None
    if temp is None:
        out.append(Check("heat", tr("ความร้อน"), UNKNOWN, tr("อ่านอุณหภูมิไม่ได้")))
    elif temp < 75:
        out.append(Check("heat", tr("ความร้อน"), PASS, f"{temp:.0f}°C"))
    else:
        out.append(
            Check(
                "heat",
                tr("ความร้อน"),
                WARN if temp < 85 else FAIL,
                tr("{t}°C · ร้อนแล้วเครื่องจะช้าลงเอง", t=f"{temp:.0f}"),
                tr("เช็กว่าพัดลมหมุนและช่องลมของเคสไม่ถูกบัง · พักเครื่องสักครู่"),
            )
        )
    th = run(["vcgencmd", "get_throttled"])
    try:
        bits = int(th.split("=")[1], 16) if th else None
    except (IndexError, ValueError):
        bits = None
    if bits is None:
        out.append(Check("power", tr("ไฟเลี้ยง"), UNKNOWN, tr("อ่านสถานะไฟไม่ได้")))
    elif bits & 0x1:
        out.append(
            Check(
                "power",
                tr("ไฟเลี้ยง"),
                FAIL,
                tr("ไฟตกอยู่ตอนนี้"),
                tr("ใช้อะแดปเตอร์ Pi 5 ของแท้ (5V 5A) · เสียบปลั๊กให้แน่น"),
            )
        )
    elif bits & 0x10000:
        out.append(
            Check(
                "power",
                tr("ไฟเลี้ยง"),
                WARN,
                tr("ไฟเคยตกตั้งแต่เปิดเครื่อง"),
                tr("เช็กอะแดปเตอร์และสาย · เสียบปลั๊กให้แน่น (เคยหลุดจนเครื่องรีบูต)"),
            )
        )
    else:
        out.append(Check("power", tr("ไฟเลี้ยง"), PASS, tr("ไม่เคยตกตั้งแต่เปิดเครื่อง")))
    return out


def check_disk(home: Path) -> Check:
    try:
        free = shutil.disk_usage(home).free / 1e9
    except OSError:
        return Check("disk", tr("พื้นที่ว่าง"), UNKNOWN, tr("อ่านพื้นที่ไม่ได้"))
    if free >= 2:
        return Check("disk", tr("พื้นที่ว่าง"), PASS, tr("ว่าง {gb} GB", gb=f"{free:.0f}"))
    return Check(
        "disk", tr("พื้นที่ว่าง"), WARN, tr("ว่างแค่ {gb} GB", gb=f"{free:.1f}"), tr("ลบไฟล์ที่ไม่ใช้")
    )


def check_devices(
    root: Path, voice_available: bool, mic_available: bool, claude: str | None
) -> list[Check]:
    # ใช้ตัวตรวจเดียวกับการ์ดฮาร์ดแวร์ · พบบน Pi 5 2026-10-12: ถอดกล้องแล้วยังขึ้น "พบกล้อง"
    # เพราะนับ /dev/video* ทุกตัว (ชิปของ Pi มีโหนดวิดีโอของตัวเอง 17 ตัว)
    from aipc.doctor.hardware import check_camera

    cams = check_camera(root).status == PASS
    return [
        Check(
            "camera",
            tr("กล้อง"),
            PASS if cams else WARN,
            tr("พบกล้อง") if cams else tr("ไม่พบกล้อง (เข้าเครื่องด้วยใบหน้าไม่ได้)"),
            "" if cams else tr("เสียบกล้อง USB แล้วตรวจอีกครั้ง"),
        ),
        Check(
            "speak",
            tr("อ่านออกเสียง"),
            PASS if voice_available else WARN,
            tr("พร้อม") if voice_available else tr("ยังไม่ได้ติดตั้ง หรือไม่มีตัวเล่นเสียง"),
            "" if voice_available else "sudo ./scripts/pi/install-voice.sh --apply",
        ),
        Check(
            "mic",
            tr("สั่งด้วยเสียง"),
            PASS if mic_available else WARN,
            tr("พร้อม (ไมค์ใกล้ปากแม่นกว่าไมค์ในกล้อง)") if mic_available else tr("ยังไม่ได้ติดตั้งตัวถอดเสียง"),
            "" if mic_available else "install-voice.sh --apply --stt-model …",
        ),
        Check(
            "claude",
            tr("Claude (ถามข้อมูลสด · สร้างสกิล)"),
            PASS if claude else WARN,
            tr("ติดตั้งในบัญชีนี้แล้ว") if claude else tr("บัญชีนี้ยังไม่มี Claude Code · ใช้ได้แค่ AI ในเครื่อง"),
            "" if claude else tr("ติดตั้ง Claude Code ในบัญชีนี้แล้วเข้าสู่ระบบ"),
        ),
    ]


def run_all(
    ai_ready: bool,
    home: Path,
    voice_available: bool,
    mic_available: bool,
    claude: str | None,
    root: Path = Path("/"),
    run: Runner = _run,
    connect=socket.create_connection,
) -> list[Check]:
    return [
        check_ai(ai_ready),
        check_network(connect),
        check_clock(run),
        *check_power_and_heat(run),
        check_disk(home),
        *check_devices(root, voice_available, mic_available, claude),
    ]
