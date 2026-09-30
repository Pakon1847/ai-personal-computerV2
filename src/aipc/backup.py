"""สำรอง/กู้ข้อมูลของผู้ใช้ลงไดรฟ์ USB (ฟีเจอร์ข้อ 7 · ADR-012 "คัดลอก home ลงไดรฟ์ USB" → ปุ่มในหน้าตั้งค่า).

สำรอง: ข้อมูลแอป (~/.local/share/aipc = แชท นัด สกิล
· ~/.config/aipc = ตั้งค่า) + ไฟล์ของฉัน (ไฟล์ไม่ซ่อนใน home)
  → <ไดรฟ์>/AIPC-backup/<ชื่อผู้ใช้>/<วันเวลา>/ เป็นไฟล์ธรรมดา (เปิดดูในคอมอื่นได้) + manifest.json (sha256 ทุกไฟล์)
  เขียนลงโฟลเดอร์ .partial ก่อน ครบแล้วค่อยเปลี่ยนชื่อ = ถอดไดรฟ์กลางคัน ไม่มีชุดที่ดูเหมือนครบแต่ไม่ครบ
กู้: ตรวจ sha256 ทุกไฟล์ก่อน · ของเดิมย้ายไป ~/.local/share/aipc-before-restore-<วันเวลา> (ไม่ลบ) แล้วคัดลอกกลับ
ไม่รวม: แม่แบบใบหน้า (อยู่ใน /var/lib ของระบบ · สมัครใหม่ได้) · แคช · ไฟล์ซ่อนอื่น ๆ
· ไม่เข้ารหัส (ADR-003) → บอกผู้ใช้
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

APP_DIRS = (".local/share/aipc", ".config/aipc")
ROOT_NAME = "AIPC-backup"
SKIP_TOP = {".cache", ".local", ".config", ".claude", ".ssh", ".gnupg", ".mozilla", ".var"}


class BackupError(Exception):
    pass


def drives(mounts: str | None = None, user: str | None = None) -> list[Path]:
    """ไดรฟ์ที่เสียบอยู่และเขียนได้ (/media/<ผู้ใช้>/... หรือ /media/...) · อ่านจาก /proc/mounts."""
    if mounts is None:
        try:
            mounts = Path("/proc/mounts").read_text(encoding="utf-8")
        except OSError:
            return []
    out = []
    for line in mounts.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        mp = parts[1].replace("\\040", " ")
        if mp.startswith(("/media/", "/run/media/")):
            p = Path(mp)
            if os.access(p, os.W_OK):
                out.append(p)
    return out


def mount_usb(run=None) -> list[str]:
    """ต่อไดรฟ์ USB ที่เสียบแต่ยังไม่ได้ต่อ (เซสชันของเราไม่มีตัวต่ออัตโนมัติ) · คืนข้อความผิดพลาด (ว่าง = ปกติ).

    ใช้ udisksctl (ผู้ใช้ที่นั่งหน้าเครื่องทำได้ตาม polkit ไม่ต้องเป็น root) · เฉพาะอุปกรณ์ถอดได้ที่ต่อผ่าน USB
    """
    import subprocess

    run = run or subprocess.run
    try:
        r = run(["lsblk", "-J", "-o", "PATH,RM,TRAN,FSTYPE,MOUNTPOINTS,TYPE"], capture_output=True,
                text=True, timeout=10)  # fmt: skip
        tree = json.loads(r.stdout or "{}").get("blockdevices", [])
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return ["อ่านรายการไดรฟ์ไม่ได้"]
    errors = []

    def walk(devs, usb=False):
        for d in devs:
            is_usb = usb or (d.get("tran") == "usb" and d.get("rm") in (True, "1", 1))
            mounted = [m for m in (d.get("mountpoints") or []) if m]
            if is_usb and d.get("fstype") and not mounted and d.get("type") in ("part", "disk"):
                try:
                    m = run(["udisksctl", "mount", "-b", d["path"], "--no-user-interaction"],
                            capture_output=True, text=True, timeout=20)  # fmt: skip
                    if m.returncode != 0:
                        errors.append(f"ต่อ {d['path']} ไม่ได้: {(m.stderr or '').strip()[:120]}")
                except (OSError, subprocess.TimeoutExpired) as e:
                    errors.append(f"ต่อ {d['path']} ไม่ได้: {e}")
            walk(d.get("children") or [], is_usb)

    walk(tree)
    return errors


def files_to_copy(home: Path) -> list[Path]:
    """path สัมพัทธ์จาก home ของทุกไฟล์ที่จะสำรอง (ไม่ตาม symlink)."""
    out: list[Path] = []
    for d in APP_DIRS:
        base = home / d
        if base.is_dir():
            out += [
                p.relative_to(home) for p in base.rglob("*") if p.is_file() and not p.is_symlink()
            ]
    for top in sorted(home.iterdir()) if home.is_dir() else []:
        if top.name.startswith(".") or top.name in SKIP_TOP or top.is_symlink():
            continue
        if top.is_file():
            out.append(top.relative_to(home))
        elif top.is_dir():
            out += [
                p.relative_to(home)
                for p in top.rglob("*")
                if p.is_file()
                and not p.is_symlink()
                and not any(x.startswith(".") for x in p.parts)
            ]
    return out


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


@dataclass
class Result:
    ok: bool
    message: str
    path: str = ""
    files: int = 0
    bytes: int = 0
    skipped: list[str] = field(default_factory=list)


def backup(home: Path, drive: Path, user: str, now: datetime | None = None) -> Result:
    rels = files_to_copy(home)
    size = sum((home / r).stat().st_size for r in rels)
    free = shutil.disk_usage(drive).free
    if size > free:
        return Result(
            False, f"ไดรฟ์เหลือที่ไม่พอ (ต้องใช้ {size / 1e6:.0f} MB · เหลือ {free / 1e6:.0f} MB)"
        )
    stamp = (now or datetime.now()).strftime("%Y-%m-%d_%H%M")
    final = drive / ROOT_NAME / user / stamp
    tmp = final.with_name(stamp + ".partial")
    shutil.rmtree(tmp, ignore_errors=True)
    manifest, skipped = {}, []
    try:
        for r in rels:
            src, dst = home / r, tmp / "home" / r
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                manifest[r.as_posix()] = _sha(dst)
            except OSError as e:  # ไฟล์เปิดไม่ได้ (สิทธิ์/กำลังเขียน) = ข้ามแล้วบอก ไม่ล้มทั้งชุด
                skipped.append(f"{r.as_posix()} ({e.strerror or e})")
        info = {"user": user, "created": stamp, "files": manifest, "skipped": skipped,
                "note": "ไม่รวมแม่แบบใบหน้า · ไม่เข้ารหัส"}  # fmt: skip
        (tmp / "manifest.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), "utf-8")
        os.replace(tmp, final)
    except OSError as e:
        shutil.rmtree(tmp, ignore_errors=True)
        return Result(False, f"สำรองไม่สำเร็จ: {e.strerror or e} (ไดรฟ์ถูกถอด?) · ไม่มีชุดที่ครึ่ง ๆ ค้าง")
    return Result(
        True,
        f"สำรองแล้ว {len(manifest)} ไฟล์ ({size / 1e6:.1f} MB)",
        str(final),
        len(manifest),
        size,
        skipped,
    )


def backups(drive: Path, user: str) -> list[Path]:
    """ชุดสำรองที่ครบ (มี manifest.json) ใหม่สุดก่อน."""
    base = drive / ROOT_NAME / user
    if not base.is_dir():
        return []
    ok = [
        p
        for p in base.iterdir()
        if p.is_dir() and not p.name.endswith(".partial") and (p / "manifest.json").is_file()
    ]
    return sorted(ok, key=lambda p: p.name, reverse=True)


def verify(folder: Path) -> list[str]:
    """ไฟล์ที่หายหรือไม่ตรง sha256 (ว่าง = ครบ)."""
    try:
        info = json.loads((folder / "manifest.json").read_text("utf-8"))
    except (OSError, ValueError):
        return ["manifest.json อ่านไม่ได้"]
    bad = []
    for rel, sha in info.get("files", {}).items():
        p = folder / "home" / rel
        if not p.is_file() or _sha(p) != sha:
            bad.append(rel)
    return bad


def restore(folder: Path, home: Path, now: datetime | None = None) -> Result:
    """กู้ข้อมูลแอป + ไฟล์ของฉันจากชุดสำรอง · ตรวจครบก่อน · ข้อมูลแอปเดิมย้ายเก็บไว้ (ไม่ลบ) · ไฟล์ที่มีอยู่แล้วไม่ทับ."""
    bad = verify(folder)
    if bad:
        return Result(False, f"ชุดสำรองเสีย {len(bad)} ไฟล์ (เช่น {bad[0]}) · ไม่ได้กู้อะไร")
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    info = json.loads((folder / "manifest.json").read_text("utf-8"))
    for d in APP_DIRS:
        cur = home / d
        if cur.exists():
            cur.rename(cur.with_name(cur.name + f"-before-restore-{stamp}"))
    n, kept = 0, []
    for rel in info["files"]:
        src, dst = folder / "home" / rel, home / rel
        app = any(rel.startswith(d + "/") for d in APP_DIRS)
        if dst.exists() and not app:
            kept.append(rel)  # ไฟล์ของฉันที่มีอยู่แล้ว = ไม่ทับ
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    msg = f"กู้แล้ว {n} ไฟล์ · ออกจากระบบแล้วเข้าใหม่เพื่อใช้ข้อมูลที่กู้"
    if kept:
        msg += f" · ไฟล์ของฉันที่มีอยู่แล้ว {len(kept)} ไฟล์ไม่ถูกทับ"
    return Result(True, msg, str(folder), n)
