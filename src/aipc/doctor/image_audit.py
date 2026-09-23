"""ตรวจช่องโหว่ของ image ตั้งต้น ตาม BRIEF 5.2 ข้อ 2 และเกณฑ์ผ่าน "ตรวจ image หลัง OOBE".

อ่านอย่างเดียวทั้งหมด — ไม่ลบ sudo ไม่ปิดบริการ ไม่แก้สิทธิ์ไฟล์
ผลนี้ใช้สองจังหวะ:
1. เฟส 0: ดูว่า image ที่ใช้จริงมีช่องโหว่อะไรบ้าง (คาดว่าจะเจอหลายข้อ เป็นเรื่องปกติ)
2. หลัง OOBE (เฟส 1): ต้องผ่านทุกข้อ นี่คือหลักฐานของเกณฑ์ผ่านใน 5.2

บางไฟล์ (เช่น /etc/sudoers) อ่านได้เฉพาะ root ถ้ารันเป็นผู้ใช้ธรรมดา ข้อนั้นจะเป็น "ไม่รู้"
รันด้วย sudo ได้ถ้าต้องการผลครบ — เครื่องมือยังอ่านอย่างเดียวเหมือนเดิม
"""

from __future__ import annotations

import stat
from pathlib import Path

from aipc.bench.machine import Runner, run_command
from aipc.doctor.hardware import FAIL, PASS, UNKNOWN, WARN, Check, _p, _read

# บริการเข้าถึงระยะไกลที่ BRIEF 5.2 ข้อ 2 ให้ปิดถ้าไม่ใช้
# ชื่อ unit ของ VNC และ Raspberry Pi Connect ต่างกันได้ตามรุ่น image — ยืนยันกับ image จริงอีกครั้ง
REMOTE_UNITS = [
    "ssh.service",
    "wayvnc.service",
    "vncserver-x11-serviced.service",
    "rpi-connect.service",
]
# Raspberry Pi Connect (แชร์หน้าจอ/เชลล์ระยะไกล) ไม่ใช่บริการของระบบ แต่เป็นบริการ "รายผู้ใช้"
# ที่ Raspberry Pi Imager เปิดให้บัญชีแรก · `systemctl is-enabled` ของระบบจึงตอบ not-found
# ยืนยันกับ Pi 4 trixie 2026-09-24: ลิงก์อยู่ที่ ~/.config/systemd/user/default.target.wants/
USER_REMOTE_UNITS = ["rpi-connect.service", "rpi-connect-wayvnc.service", "wayvnc.service"]
LOOPBACK6 = "00000000000000000000000001000000"


def parse_sudoers_nopasswd(text: str, source: str) -> list[str]:
    """หาบรรทัดที่ให้ sudo โดยไม่ต้องใส่รหัส (ข้ามคอมเมนต์)."""
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        body = line.split("#", 1)[0].strip()
        if "NOPASSWD" in body:
            hits.append(f"{source}:{n} `{body}`")
    return hits


def check_sudo_nopasswd(root: Path) -> Check:
    files = [_p(root, "/etc/sudoers")]
    try:
        files += sorted(_p(root, "/etc/sudoers.d").iterdir())
    except OSError:
        pass
    hits, unreadable = [], []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            unreadable.append(f.name)
            continue
        hits += parse_sudoers_nopasswd(text, "/" + f.relative_to(root).as_posix())
    title = "sudo แบบไม่ใส่รหัส"
    if hits:
        return Check(
            "sudo",
            title,
            FAIL,
            "; ".join(hits),
            "ลบหลัง OOBE (BRIEF 5.2 ข้อ 2) — ห้ามลบก่อนมีผู้ดูแลที่ใส่รหัสได้",
        )
    if unreadable:
        return Check("sudo", title, UNKNOWN, f"อ่านไม่ได้: {', '.join(unreadable)}", "รันด้วย sudo")
    return Check("sudo", title, PASS, "ไม่พบ NOPASSWD")


def human_users(root: Path) -> dict[str, int]:
    """บัญชีคน (uid 1000–59999) จาก /etc/passwd."""
    users = {}
    for line in (_read(root, "/etc/passwd") or "").splitlines():
        f = line.split(":")
        if len(f) >= 3 and f[2].isdigit() and 1000 <= int(f[2]) < 60000:
            users[f[0]] = int(f[2])
    return users


def group_members(root: Path) -> dict[str, list[str]]:
    groups = {}
    for line in (_read(root, "/etc/group") or "").splitlines():
        f = line.split(":")
        if len(f) >= 4:
            groups[f[0]] = [m for m in f[3].split(",") if m]
    return groups


def check_privileged_groups(root: Path) -> Check:
    users = human_users(root)
    if not users:
        return Check("groups", "ผู้ใช้ในกลุ่มสิทธิ์สูง", UNKNOWN, "อ่าน /etc/passwd ไม่ได้")
    groups = group_members(root)
    found = {g: [u for u in groups.get(g, []) if u in users] for g in ("sudo", "adm", "video")}
    found = {g: us for g, us in found.items() if us}
    if not found:
        return Check(
            "groups", "ผู้ใช้ในกลุ่มสิทธิ์สูง", PASS, f"ผู้ใช้ {len(users)} คน ไม่มีใครอยู่ใน sudo/adm/video"
        )
    detail = " · ".join(f"{g}: {', '.join(us)}" for g, us in found.items())
    return Check(
        "groups",
        "ผู้ใช้ในกลุ่มสิทธิ์สูง",
        WARN,
        detail,
        "ก่อน OOBE เป็นเรื่องปกติ (บัญชีที่ใช้ติดตั้ง) · หลัง OOBE บัญชีผู้ใช้ทั่วไปต้องไม่อยู่ในกลุ่มเหล่านี้",
    )


def user_remote_units(root: Path) -> list[str]:
    """บริการระยะไกลที่เปิดรายผู้ใช้ · อ่านลิงก์ใน *.wants/ (ไม่ต้องเรียก systemctl --user ของแต่ละคน).

    home ของคนอื่นเป็น 0700 → ถ้ารันโดยไม่ใช้ sudo จะเห็นแค่ของตัวเอง
    """
    dirs = [_p(root, "/etc/systemd/user")]
    try:
        dirs += [h / ".config/systemd/user" for h in sorted(_p(root, "/home").iterdir())]
    except OSError:
        pass
    found = []
    for d in dirs:
        for unit in USER_REMOTE_UNITS:
            try:
                hits = list(d.glob(f"*.wants/{unit}"))
            except OSError:
                continue
            if hits:
                owner = "ทุกผู้ใช้" if d.parts[-3:-1] == ("etc", "systemd") else d.parts[-4]
                found.append(f"{unit} (ผู้ใช้: {owner})")
    return found


def check_remote_services(run: Runner, root: Path = Path("/")) -> Check:
    enabled = []
    for unit in REMOTE_UNITS:
        state = run(["systemctl", "is-enabled", unit])
        if state in ("enabled", "enabled-runtime", "static", "alias"):
            enabled.append(f"{unit} ({state})")
    enabled += user_remote_units(root)
    if run(["systemctl", "--version"]) is None:
        return Check("remote", "บริการเข้าถึงระยะไกล", UNKNOWN, "เรียก systemctl ไม่ได้")
    if enabled:
        return Check(
            "remote",
            "บริการเข้าถึงระยะไกล",
            WARN,
            ", ".join(enabled),
            "ปิดถ้าไม่ใช้ (BRIEF 5.2 ข้อ 2) — ระวัง: ถ้าใช้ SSH เข้าเครื่องอยู่ ปิดแล้วจะเข้าไม่ได้",
        )
    return Check("remote", "บริการเข้าถึงระยะไกล", PASS, "ไม่มีบริการในรายการที่เปิดใช้")


def listening_ports(root: Path) -> list[str]:
    """พอร์ต TCP ที่รอรับการเชื่อมต่อจากนอกเครื่อง อ่านจาก /proc/net/tcp และ tcp6.

    ในไฟล์นี้ ที่อยู่เป็นเลขฐาน 16 · สถานะ 0A = LISTEN
    IPv4 127.x.x.x และ IPv6 ::1 คือรับเฉพาะในเครื่อง จึงไม่นับ
    """
    ports = set()
    for name in ("tcp", "tcp6"):
        text = _read(root, f"/proc/net/{name}") or ""
        for line in text.splitlines()[1:]:
            f = line.split()
            if len(f) < 4 or f[3] != "0A":
                continue
            addr, port_hex = f[1].rsplit(":", 1)
            if name == "tcp" and addr.endswith("7F"):  # little-endian: 127 อยู่ท้ายสุด
                continue
            if name == "tcp6" and addr == LOOPBACK6:
                continue
            ports.add(f"{int(port_hex, 16)}/{name}")
    return sorted(ports, key=lambda p: int(p.split("/")[0]))


def check_listening(root: Path) -> Check:
    if not _p(root, "/proc/net/tcp").exists():
        return Check("ports", "พอร์ตที่เปิดรับจากนอกเครื่อง", UNKNOWN, "อ่าน /proc/net/tcp ไม่ได้")
    ports = listening_ports(root)
    if ports:
        return Check(
            "ports",
            "พอร์ตที่เปิดรับจากนอกเครื่อง",
            WARN,
            ", ".join(ports),
            "ทุกพอร์ตต้องอธิบายได้ว่าเป็นของบริการไหน (BRIEF หัวข้อ 7 ข้อ 3–4)",
        )
    return Check("ports", "พอร์ตที่เปิดรับจากนอกเครื่อง", PASS, "ไม่มี")


def check_camera_nodes(root: Path) -> Check:
    try:
        nodes = sorted(_p(root, "/dev").glob("video*"))
    except OSError:
        nodes = []
    if not nodes:
        return Check("camnode", "สิทธิ์โหนดกล้อง", UNKNOWN, "ไม่เจอ /dev/video*")
    open_to_all = [n.name for n in nodes if n.stat().st_mode & (stat.S_IROTH | stat.S_IWOTH)]
    detail = f"{len(nodes)} โหนด"
    fix = (
        "BRIEF 5.2 ข้อ 2: udev rule ตัด uaccess เฉพาะโหนดกล้อง ให้กล้องเป็นของ visiond · "
        "ตรวจ ACL ด้วย `getfacl /dev/videoN` ด้วย เพราะ uaccess ให้สิทธิ์ผ่าน ACL ซึ่งเครื่องมือนี้ยังไม่ได้อ่าน"
    )
    if open_to_all:
        return Check("camnode", "สิทธิ์โหนดกล้อง", FAIL, f"ทุกคนเปิดได้: {', '.join(open_to_all)}", fix)
    return Check(
        "camnode", "สิทธิ์โหนดกล้อง", UNKNOWN, detail + " · สิทธิ์ปกติไม่เปิดให้ทุกคน แต่ยังไม่ได้ตรวจ ACL", fix
    )


def check_home_permissions(root: Path) -> Check:
    try:
        homes = sorted(p for p in _p(root, "/home").iterdir() if p.is_dir())
    except OSError:
        return Check("homes", "สิทธิ์ home", UNKNOWN, "อ่าน /home ไม่ได้")
    loose = [
        f"{h.name} ({stat.S_IMODE(h.stat().st_mode):o})" for h in homes if h.stat().st_mode & 0o077
    ]
    if loose:
        return Check(
            "homes", "สิทธิ์ home", FAIL, ", ".join(loose), "BRIEF 5.2 ข้อ 1: home ต้องเป็น 0700"
        )
    return Check("homes", "สิทธิ์ home", PASS, f"{len(homes)} โฟลเดอร์ เป็น 0700 ทั้งหมด")


def logind_setting(root: Path, key: str) -> str | None:
    """ค่าใน logind.conf · ไฟล์ใน logind.conf.d/ มาทีหลังจึงชนะ (เรียงตามชื่อ)."""
    files = [_p(root, "/etc/systemd/logind.conf")]
    try:
        files += sorted(_p(root, "/etc/systemd/logind.conf.d").glob("*.conf"))
    except OSError:
        pass
    value = None
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if line.startswith(key + "="):
                value = line.split("=", 1)[1].strip()
    return value


def check_logout_cleanup(root: Path) -> Check:
    if not _p(root, "/etc/systemd").is_dir():
        return Check("logout", "Logout ปิดโปรเซสของผู้ใช้", UNKNOWN, "ไม่ใช่ระบบที่ใช้ systemd")
    kill = logind_setting(root, "KillUserProcesses")
    try:
        linger = sorted(p.name for p in _p(root, "/var/lib/systemd/linger").iterdir())
    except OSError:
        linger = []
    problems = []
    if (kill or "no").lower() not in ("yes", "true", "1"):
        problems.append(f"KillUserProcesses={kill or 'no (ค่าเริ่มต้น)'}")
    if linger:
        problems.append(f"เปิด linger: {', '.join(linger)}")
    if problems:
        return Check(
            "logout",
            "Logout ปิดโปรเซสของผู้ใช้",
            WARN,
            " · ".join(problems),
            "BRIEF 5.2 ข้อ 6: KillUserProcesses=yes และไม่เปิด linger — ทำตอนเฟส 1 พร้อมเทสต์",
        )
    return Check("logout", "Logout ปิดโปรเซสของผู้ใช้", PASS, "KillUserProcesses=yes · ไม่มี linger")


def check_swap(root: Path) -> Check:
    text = _read(root, "/proc/swaps")
    if text is None:
        return Check("swap", "swap", UNKNOWN, "อ่าน /proc/swaps ไม่ได้")
    devices = [line.split()[0] for line in text.splitlines()[1:] if line.strip()]
    on_disk = [d for d in devices if "zram" not in d]
    if on_disk:
        return Check(
            "swap",
            "swap",
            WARN,
            f"swap บนดิสก์: {', '.join(on_disk)}",
            "BRIEF 5.8 ข้อ 4: ใช้ zram แทน swap บน microSD (หน่วยความจำที่มีความลับอาจถูกเขียนลงการ์ด)",
        )
    return Check(
        "swap", "swap", PASS, f"zram เท่านั้น ({len(devices)} อุปกรณ์)" if devices else "ไม่มี swap"
    )


def run_all(root: Path = Path("/"), run: Runner = run_command) -> list[Check]:
    return [
        check_sudo_nopasswd(root),
        check_privileged_groups(root),
        check_remote_services(run, root),
        check_listening(root),
        check_camera_nodes(root),
        check_home_permissions(root),
        check_logout_cleanup(root),
        check_swap(root),
    ]
