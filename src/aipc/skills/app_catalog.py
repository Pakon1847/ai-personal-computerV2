"""แอปที่ระบบรู้จักแม้ยังไม่ได้ติดตั้ง (การ์ด 0054).

สั่ง "เปิด X" แล้วเครื่องไม่มี X → ถามติดตั้ง (ถ้ามีแพ็กเกจ) → ไม่ติดตั้ง = ถามเปิดผ่านเว็บ (ถ้ามี) ·
ถามทุกครั้ง ไม่จำคำตอบ (Pakon 2026-10-22)
รายการมาจากไฟล์ของเราเอง (app_catalog.json) หรือของผู้ดูแล (/etc/aipc/apps-allowed.json แทนทั้งไฟล์) ·
ชื่อแพ็กเกจและลิงก์ไม่รับจากข้อความผู้ใช้ เว็บ หรือ AI (H7 H8) · ตัวติดตั้ง (root) อ่านไฟล์ชุดเดียวกันเองอีกรอบ
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

BUILTIN = Path(__file__).with_name("app_catalog.json")
ADMIN = Path("/etc/aipc/apps-allowed.json")
APT_NAME = re.compile(r"^[a-z0-9][a-z0-9+.-]{1,62}$")  # รูปชื่อแพ็กเกจของ Debian · ไม่มีช่องว่าง/ขีดนำหน้า
KEY = re.compile(r"^[a-z0-9-]{1,32}$")


@dataclass(frozen=True)
class Entry:
    key: str
    name: str
    aliases: tuple[str, ...]
    apt: str = ""  # "" = ติดตั้งจากที่นี่ไม่ได้
    web: str = ""  # "" = ไม่มีเว็บแทน


def load(admin: Path = ADMIN, builtin: Path = BUILTIN) -> dict[str, Entry]:
    """ไฟล์ของผู้ดูแลก่อน (อ่านไม่ได้/เสีย = ใช้ของเรา) · รายการที่รูปไม่ถูกถูกข้ามทีละรายการ."""
    for path in (admin, builtin):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            apps = data["apps"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        out = {}
        for key, a in apps.items() if isinstance(apps, dict) else []:
            entry = _entry(key, a)
            if entry is not None:
                out[key] = entry
        return out
    return {}


def _entry(key, a) -> Entry | None:
    if not (isinstance(key, str) and KEY.match(key) and isinstance(a, dict)):
        return None
    apt, web = a.get("apt", ""), a.get("web", "")
    if not isinstance(apt, str) or (apt and not APT_NAME.match(apt)):
        return None
    if not isinstance(web, str) or (web and not web.startswith("https://")):
        return None
    aliases = a.get("aliases")
    if not isinstance(aliases, list) or not all(isinstance(x, str) and x for x in aliases):
        return None
    words = tuple(re.sub(r"\s+", "", x.lower()) for x in aliases)
    return Entry(key, str(a.get("name") or key), words, apt, web)


def find(target: str, entries: dict[str, Entry]) -> Entry | None:
    """คำเรียกต้องตรงทั้งคำ (ไม่เดา) · "เปิดซูมภาพ" ไม่ใช่ Zoom."""
    return next((e for e in entries.values() if target in e.aliases), None)
