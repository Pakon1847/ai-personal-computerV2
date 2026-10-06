"""ตรวจฮาร์ดแวร์และ OS เทียบกับ BRIEF หัวข้อ 2 — อ่านอย่างเดียว.

ผลแต่ละข้อมี 4 แบบ:
- ผ่าน      อ่านค่าได้ และตรงตามที่ BRIEF ต้องการ
- เตือน     อ่านได้ แต่ไม่ตรง (มีวิธีแก้บอกไว้ — เครื่องมือนี้ไม่แก้ให้เอง)
- ไม่ผ่าน   อ่านได้ และขัดกับ BRIEF ชัดเจน
- ไม่รู้    อ่านค่าไม่ได้ **ไม่รู้ ≠ ผ่าน** จึงแยกออกมาให้เห็น

ทำไมต้องมี: ตอนนี้ STATUS.md รู้เรื่องฮาร์ดแวร์จากคำบอกเล่าเท่านั้น
คำบอกเล่าไม่ใช่หลักฐาน เช่น "มีอะแดปเตอร์ 27W" ไม่ได้แปลว่าบอร์ดรับรู้ว่าได้ไฟ 5A

**ข้อจำกัดที่ต้องรู้:** path ของไฟล์ในข้อไฟเลี้ยง (device tree `chosen/power`)
และข้อแบต RTC (`charging_voltage`) มาจากเอกสาร/ไดรเวอร์ของ Raspberry Pi
ยังไม่ได้ยืนยันกับเครื่องของเราเอง ถ้าเครื่องจริงไม่มีไฟล์นั้น ข้อนั้นจะออกมาเป็น "ไม่รู้"
ไม่ใช่ "ผ่าน" — รันครั้งแรกบน Pi 5 แล้วต้องตรวจผลข้อนี้ด้วยตาอีกครั้ง
"""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from aipc.bench import machine
from aipc.bench.machine import Runner, run_command

PASS, WARN, FAIL, UNKNOWN = "ผ่าน", "เตือน", "ไม่ผ่าน", "ไม่รู้"


@dataclass
class Check:
    id: str
    title: str
    status: str
    detail: str
    fix: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _p(root: Path, path: str) -> Path:
    return root / path.lstrip("/")


def _read(root: Path, path: str) -> str | None:
    try:
        return _p(root, path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def _read_u32_be(root: Path, path: str) -> int | None:
    """ค่าตัวเลขใน device tree เก็บเป็น 4 ไบต์แบบ big-endian ไม่ใช่ข้อความ."""
    try:
        data = _p(root, path).read_bytes()
    except OSError:
        return None
    return int.from_bytes(data[:4], "big") if len(data) >= 4 else None


# ---------- แต่ละข้อ ----------


def check_board(root: Path) -> Check:
    model = machine.board_model(root)
    cls = machine.board_class(model)
    if cls == "pi5":
        return Check("board", "บอร์ด", PASS, f"{model} — เครื่องจริง")
    if cls == "pi4":
        return Check("board", "บอร์ด", WARN, f"{model} — เครื่องทดสอบ ใช้พิสูจน์ความถูกต้องเท่านั้น")
    return Check("board", "บอร์ด", UNKNOWN, "ไม่ใช่ Raspberry Pi (หรืออ่าน device tree ไม่ได้)")


def check_ram(root: Path) -> Check:
    mb = machine.ram_total_mb(root)
    if mb is None:
        return Check("ram", "RAM", UNKNOWN, "อ่าน /proc/meminfo ไม่ได้")
    # 8GB ที่ OS เห็นจริงจะน้อยกว่า 8192 MB เล็กน้อย เพราะบางส่วนถูกกันให้ GPU/firmware
    if mb >= 7500:
        return Check("ram", "RAM", PASS, f"{mb} MB")
    return Check("ram", "RAM", WARN, f"{mb} MB — น้อยกว่า 8GB ที่ BRIEF ออกแบบไว้")


def check_power(root: Path, run: Runner) -> Check:
    """ไฟเลี้ยง: ดูสองทาง คือบอร์ดรับรู้กระแสสูงสุดเท่าไร และเคยไฟตกไหมตั้งแต่บูต."""
    max_ma = _read_u32_be(root, "/proc/device-tree/chosen/power/max_current")
    throttled = machine.throttled_raw(run)
    parts = []
    if max_ma is not None:
        parts.append(f"บอร์ดรับรู้กระแสสูงสุด {max_ma} mA")
    if throttled is not None:
        problems = machine.decode_throttled(throttled)
        parts.append("ไม่เคยไฟตก/ร้อนเกินตั้งแต่บูต" if not problems else ", ".join(problems))
    detail = " · ".join(parts) or "อ่านค่าไม่ได้ทั้งสองทาง"
    fix = "ใช้อะแดปเตอร์ 27W ของแท้ ต่อสายตรง ไม่ผ่านฮับ แล้วรีบูตก่อนตรวจซ้ำ"

    if throttled is not None and throttled & 0x10001:  # บิตไฟตก ตอนนี้ หรือเคยเกิด
        return Check("power", "ไฟเลี้ยง", FAIL, detail, fix)
    if max_ma is not None and max_ma < 5000:
        return Check("power", "ไฟเลี้ยง", WARN, detail + " — ต่ำกว่า 5A", fix)
    if max_ma is None or throttled is None:
        return Check("power", "ไฟเลี้ยง", UNKNOWN, detail, fix)
    return Check("power", "ไฟเลี้ยง", PASS, detail)


# พัดลมหมุนแล้วยังร้อนเกินนี้ = ระบายความร้อนไม่พอ ·
# บนเครื่องเรา firmware ตั้งบิต soft temp limit ที่ 82.9 °C (soak 2026-10-01)
HOT_C = 80.0


def check_cooling(root: Path) -> Check:
    """หาพัดลมของ Pi 5 ผ่าน hwmon ชื่อ pwmfan.

    พัดลมหยุดหมุนตอนเครื่องเย็นเป็นเรื่องปกติ รอบ = 0 จึงเป็น "ไม่รู้" ไม่ใช่ "ไม่ผ่าน"
    ให้รันซ้ำตอนเครื่องทำงานหนัก (เช่น ระหว่างวัด LLM)
    """
    hwmon = _p(root, "/sys/class/hwmon")
    temp = machine.cpu_temp_c(root)
    temp_txt = f"อุณหภูมิ {temp:.1f} °C" if temp is not None else "อ่านอุณหภูมิไม่ได้"
    try:
        entries = sorted(hwmon.iterdir())
    except OSError:
        entries = []
    for entry in entries:
        if _read(entry, "name") == "pwmfan":
            rpm = _read(entry, "fan1_input")
            if rpm and rpm.isdigit() and int(rpm) > 0:
                if temp is not None and temp >= HOT_C:
                    # Pi 5 ของเรา 2026-10-05: พัดลม 9,711 rpm แต่ 84.8 °C
                    # และถูกลดความเร็ว (0xe0008) ขณะ AI ตอบ
                    return Check(
                        "cooling",
                        "ระบายความร้อน",
                        WARN,
                        f"พัดลม {rpm} rpm แต่ {temp_txt} (≥ {HOT_C:.0f} °C)",
                        "ตรวจแผ่นระบายความร้อนของ Active Cooler "
                        "(ลอกฟิล์มแล้วหรือยัง · กดแนบชิป) · ขาสปริงล็อกครบ · เคส/ช่องลม",
                    )
                return Check("cooling", "ระบายความร้อน", PASS, f"พัดลม {rpm} rpm · {temp_txt}")
            return Check(
                "cooling",
                "ระบายความร้อน",
                UNKNOWN,
                f"เจอตัวควบคุมพัดลม แต่รอบ = {rpm or '?'} · {temp_txt}",
                "รันซ้ำตอนเครื่องทำงานหนัก ถ้ายัง 0 rpm ให้ตรวจสายพัดลม",
            )
    return Check(
        "cooling",
        "ระบายความร้อน",
        UNKNOWN,
        f"ไม่เจอตัวควบคุมพัดลม · {temp_txt}",
        "ตรวจการต่อ Active Cooler",
    )


def check_rtc(root: Path) -> Check:
    if not _p(root, "/sys/class/rtc/rtc0").exists():
        return Check("rtc", "นาฬิกา RTC", UNKNOWN, "ไม่เจอ /sys/class/rtc/rtc0")
    volt = _read(root, "/sys/class/rtc/rtc0/charging_voltage")
    fix = (
        "BRIEF หัวข้อ 2 ให้เพิ่ม dtparam=rtc_bbat_vchg=3000000 ใน /boot/firmware/config.txt "
        "— เป็นไฟล์บูต ต้องสำรองไฟล์ก่อนแก้ และให้ Pakon ตัดสินใจเอง เครื่องมือนี้ไม่แก้ให้"
    )
    if volt is None:
        return Check("rtc", "นาฬิกา RTC", UNKNOWN, "มี RTC แต่อ่านสถานะการชาร์จแบตไม่ได้", fix)
    if volt.isdigit() and int(volt) > 0:
        return Check("rtc", "นาฬิกา RTC", PASS, f"ชาร์จแบตที่ {int(volt) / 1e6:.1f} V")
    return Check("rtc", "นาฬิกา RTC", WARN, "ไม่ได้ชาร์จแบต RTC (charging_voltage = 0)", fix)


def check_os(root: Path) -> Check:
    text = _read(root, "/etc/os-release") or ""
    info = dict(
        line.split("=", 1) for line in text.splitlines() if "=" in line and not line.startswith("#")
    )
    codename = info.get("VERSION_CODENAME", "").strip('"')
    arch = platform.machine()
    detail = f"{info.get('PRETTY_NAME', '?').strip(chr(34))} · {arch}"
    if not codename:
        return Check("os", "OS", UNKNOWN, "อ่าน /etc/os-release ไม่ได้")
    if codename == "trixie" and arch == "aarch64":
        return Check("os", "OS", PASS, detail)
    return Check(
        "os", "OS", FAIL, detail, "BRIEF หัวข้อ 2 ต้องการ Raspberry Pi OS 64-bit บน Debian 13 trixie"
    )


def check_glibc() -> Check:
    """PySide6 wheel สำหรับ aarch64 ตั้งแต่ 6.8.1 ต้องใช้ glibc ≥ 2.39 (BRIEF หัวข้อ 2)."""
    try:
        version = os.confstr("CS_GNU_LIBC_VERSION")  # เช่น "glibc 2.41"
    except (AttributeError, ValueError, OSError):
        version = None
    if not version:
        return Check("glibc", "glibc", UNKNOWN, "ไม่ใช่ระบบที่ใช้ glibc")
    num = version.split()[-1]
    major, minor = (int(x) for x in num.split(".")[:2])
    if (major, minor) >= (2, 39):
        return Check("glibc", "glibc", PASS, version)
    return Check("glibc", "glibc", FAIL, version, "ต่ำกว่า 2.39 — pip จะได้ PySide6 รุ่นเก่า")


def root_device(root: Path) -> str | None:
    text = _read(root, "/proc/mounts") or ""
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[1] == "/":
            return fields[0]
    return None


def check_storage(root: Path, usage_path: Path) -> Check:
    dev = root_device(root)
    kind = "ไม่รู้ชนิด"
    if dev:
        if "mmcblk" in dev:
            kind = "microSD"
        elif "nvme" in dev:
            kind = "NVMe SSD"
        elif dev.startswith("/dev/sd"):
            kind = "USB drive"
    try:
        du = shutil.disk_usage(usage_path)
    except OSError:
        return Check("storage", "ที่เก็บข้อมูล", UNKNOWN, f"{dev or '?'} ({kind})")
    used_pct = du.used / du.total * 100
    detail = (
        f"{dev or '?'} ({kind}) · ทั้งหมด {du.total / 1e9:.1f} GB · "
        f"ใช้แล้ว {used_pct:.0f}% · ว่าง {du.free / 1e9:.1f} GB"
    )
    # เกณฑ์เดียวกับ BRIEF 5.9 ข้อ 6: เตือนที่ 80%, ที่ 90% ต้องหยุดงานที่ไม่จำเป็น
    if used_pct >= 90:
        return Check("storage", "ที่เก็บข้อมูล", FAIL, detail, "พื้นที่เกิน 90% (BRIEF 5.9 ข้อ 6)")
    if used_pct >= 80:
        return Check("storage", "ที่เก็บข้อมูล", WARN, detail, "พื้นที่เกิน 80% (BRIEF 5.9 ข้อ 6)")
    return Check("storage", "ที่เก็บข้อมูล", PASS, detail)


def check_fscrypt_kernel(root: Path) -> Check:
    """เคอร์เนลรองรับการเข้ารหัสของ ext4 ไหม (เรื่องของ ADR-003).

    ตรวจแค่ฝั่งเคอร์เนล ไม่ได้ตรวจว่าพาร์ทิชันเปิดธง encrypt แล้วหรือยัง
    เพราะการตรวจนั้นต้องใช้สิทธิ์ root และการเปิดธงคือการแก้ระบบไฟล์ที่กำลังบูตอยู่ (เสี่ยง)
    """
    if _p(root, "/sys/fs/ext4/features/encryption").exists():
        return Check("fscrypt", "เคอร์เนลรองรับ fscrypt", PASS, "มี /sys/fs/ext4/features/encryption")
    return Check(
        "fscrypt", "เคอร์เนลรองรับ fscrypt", UNKNOWN, "ไม่เจอ /sys/fs/ext4/features/encryption"
    )


# /dev/video* ไม่ได้แปลว่ากล้อง · ชิปของ Pi สร้างโหนดวิดีโอของตัวเองไว้ถอดรหัสวิดีโอและแต่งภาพ (ISP)
# เสมอ แม้ไม่ได้ต่อกล้อง — Pi 4 ที่ไม่มีกล้องมี 14 ตัว (ตรวจจากเครื่องจริง 2026-09-24)
# ชื่ออยู่ใน /sys/class/video4linux/videoN/name · ตัวที่ขึ้นต้นด้วยชื่อเหล่านี้ไม่นับเป็นกล้อง
SOC_VIDEO_NODES = (
    "bcm2835-codec",  # Pi 4: ตัวถอด/เข้ารหัสวิดีโอ (ยืนยันแล้วบน Pi 4)
    "bcm2835-isp",  # Pi 4: ISP (ยืนยันแล้วบน Pi 4)
    "rpi-hevc-dec",  # Pi 4/5: ตัวถอด HEVC (ยืนยันแล้วบน Pi 4)
    "pispbe",  # Pi 5: ISP back end (ยืนยันแล้วบน Pi 5 2026-09-26: pispbe-input/-output0/-config ...)
)


def check_camera(root: Path) -> Check:
    try:
        videos = sorted(p.name for p in _p(root, "/dev").glob("video*"))
    except OSError:
        videos = []
    if not videos:
        return Check("camera", "กล้อง", UNKNOWN, "ไม่เจอ /dev/video*")

    cameras, unnamed = [], []
    for v in videos:
        name = _read(root, f"/sys/class/video4linux/{v}/name")
        if name is None:
            unnamed.append(v)
        elif not name.startswith(SOC_VIDEO_NODES):
            cameras.append(f"{v} ({name})")
    if cameras:
        return Check("camera", "กล้อง", PASS, f"เจอกล้อง: {', '.join(cameras[:4])}")
    if unnamed:
        # อ่านชื่อไม่ได้ = ไม่รู้ว่าเป็นกล้องหรือของชิป · ไม่เดาว่าเป็นกล้อง (H5)
        return Check("camera", "กล้อง", UNKNOWN, f"เจอ {', '.join(unnamed[:4])} แต่อ่านชื่ออุปกรณ์ไม่ได้")
    return Check(
        "camera",
        "กล้อง",
        WARN,
        f"ไม่พบกล้อง · โหนดวิดีโอ {len(videos)} ตัวเป็นของชิป (ถอดรหัสวิดีโอ/ISP) ไม่ใช่กล้อง",
        "ต่อกล้องแล้วตรวจด้วย `python -m aipc.vision.camera test` หรือ `v4l2-ctl --list-devices` · "
        "`rpicam-hello` เห็นเฉพาะกล้อง CSI (กล้อง USB จะขึ้นว่า No cameras available ทั้งที่ใช้ได้)",
    )


def check_audio(root: Path) -> Check:
    cards = _read(root, "/proc/asound/cards")
    if not cards or "no soundcards" in cards:
        return Check("audio", "เสียง", UNKNOWN, "ไม่เจอการ์ดเสียง")
    names = [line.split(":", 1)[1].strip() for line in cards.splitlines() if ":" in line]
    return Check("audio", "เสียง", PASS, " | ".join(names))


def check_memory_cgroup(root: Path) -> Check:
    """MemoryMax ของ aipc-llm.service มีผลเมื่อ cgroup v2 เปิด controller memory
    (audit 2026-09-30 hw-os-1)."""
    ctl = _read(root, "/sys/fs/cgroup/cgroup.controllers")
    if ctl is None:
        return Check(
            "memcg", "memory cgroup", UNKNOWN, "อ่าน /sys/fs/cgroup/cgroup.controllers ไม่ได้"
        )
    if "memory" in ctl.split():
        return Check("memcg", "memory cgroup", PASS, "เปิดอยู่ · MemoryMax ของ AI มีผล")
    cmd = _read(root, "/proc/cmdline") or ""
    why = " (cmdline มี cgroup_disable=memory)" if "cgroup_disable=memory" in cmd else ""
    return Check(
        "memcg",
        "memory cgroup",
        WARN,
        f"ปิดอยู่{why} · MemoryMax ของ aipc-llm.service ไม่มีผล",
        "สำรอง /boot/firmware/cmdline.txt แล้วเติม cgroup_enable=memory ท้ายบรรทัดเดียวกัน · รีบูต",
    )


def run_all(
    root: Path = Path("/"), run: Runner = run_command, usage_path: Path | None = None
) -> list[Check]:
    return [
        check_board(root),
        check_ram(root),
        check_power(root, run),
        check_cooling(root),
        check_rtc(root),
        check_os(root),
        check_glibc(),
        check_storage(root, usage_path or root),
        check_fscrypt_kernel(root),
        check_camera(root),
        check_audio(root),
        check_memory_cgroup(root),
    ]
