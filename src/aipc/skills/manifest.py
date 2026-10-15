"""รูปแบบไฟล์สกิล และตัวตรวจว่าไฟล์ถูกต้องและไม่ขอเกินที่ระบบอนุญาต.

ไฟล์สกิลเป็น .md (mdskill.py · ตั้งแต่ 2026-09-29) หรือ .json แบบเดิม · ทั้งสองแบบกลายเป็นข้อมูลรูปเดียวกัน
แล้วผ่านตัวตรวจตัวเดียวกันนี้

ตัวตรวจนี้ใช้กับทุกสกิล ทั้งที่มากับเครื่อง ที่ AI ช่วยสร้าง และที่นำเข้าจากเครื่องอื่น
สกิลที่ไม่ผ่านตัวตรวจ ติดตั้งไม่ได้เลย (BRIEF 5.8 ข้อ 4: ผลตรวจอัตโนมัติ schema ขนาด รูปแบบต้องห้าม)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from aipc.skills.actions import ACTIONS

ID_RE = re.compile(r"^[a-z][a-z0-9-]{2,40}$")
WORKERS = {"code", "llm", "code+llm", "stt+llm", "camera+vlm"}
# สิทธิ์ที่สกิลขอได้ · เพิ่มได้เฉพาะโดยแก้โค้ดของระบบ ไม่ใช่จากไฟล์สกิล
PERMISSIONS = {
    "read_machine_status": "อ่านสถานะเครื่อง",
    "run_actions": "สั่งงานเครื่องตาม Action ที่อนุญาต",
    "write_notes": "เขียนไฟล์ในโฟลเดอร์ ~/โน้ต",
    "write_reminders": "เขียนไฟล์นัดหมาย",
    "camera_capture": "ใช้กล้องเมื่อคุณกดถ่าย",
    # ขั้น "บอกนัด…" ในสกิล (การ์ด 0034) · โค้ดอ่านนัดในเครื่องเอง · Claude ที่สร้างสกิลไม่เห็นนัด
    "read_agenda": "อ่านนัดและปฏิทินของคุณ (ในเครื่อง)",
}
# สิ่งที่สกิลต้องมีจากระบบก่อนใช้งานได้
NEEDS = {"llm", "stt", "vlm", "camera"}
# คำอ้างขอบเขตกว้างเกิน: กันไม่ให้สกิลเดียวยึดทุกบทสนทนา (BRIEF 5.8 ข้อ 3)
TOO_BROAD = ("ทุกคำขอ", "ทุกเรื่อง", "ทุกข้อความ", "ใช้เสมอ", "every request", "always use", "any request")
MAX_DESCRIPTION = 200
MAX_PROMPT = 1200


@dataclass(frozen=True)
class Manifest:
    id: str
    name: str
    description: str
    examples: tuple[str, ...]
    worker: str
    version: str = "1.0"
    actions: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    needs: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    prompt: str = ""
    author: str = "ระบบ"
    steps: tuple = ()  # ขั้นตอนของสกิล .md (mdskill.Step) · โค้ดทำตามทีละข้อ
    extra: dict = field(default_factory=dict, compare=False)

    def permission_labels(self) -> list[str]:
        return [PERMISSIONS[p] for p in self.permissions]


class InvalidSkill(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def validate(data: dict) -> list[str]:
    """คืนรายการปัญหาเป็นภาษาคน · รายการว่าง = ผ่าน."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["ไฟล์สกิลต้องเป็น JSON object"]

    def text(key, required=True):
        v = data.get(key)
        if v is None:
            if required:
                errors.append(f"ไม่มี {key}")
            return ""
        if not isinstance(v, str):
            errors.append(f"{key} ต้องเป็นข้อความ")
            return ""
        return v

    sid = text("id")
    if sid and not ID_RE.match(sid):
        errors.append("id ใช้ a–z 0–9 และ - ยาว 3–41 ตัว")
    text("name")
    desc = text("description")
    if len(desc) > MAX_DESCRIPTION:
        errors.append(f"description ยาวเกิน {MAX_DESCRIPTION} ตัวอักษร")
    if any(b in desc.lower() for b in TOO_BROAD):
        errors.append("description อ้างว่าใช้ได้กับทุกคำขอ — กว้างเกินไป")

    worker = text("worker")
    if worker and worker not in WORKERS:
        errors.append(f"worker ต้องเป็นหนึ่งใน {sorted(WORKERS)}")

    examples = data.get("examples", [])
    if (
        not isinstance(examples, list)
        or len(examples) < 3
        or not all(isinstance(e, str) for e in examples)
    ):
        errors.append("ต้องมีตัวอย่างคำขอ (examples) อย่างน้อย 3 ข้อ")

    for key, allowed, label in (
        ("actions", ACTIONS, "Action"),
        ("permissions", PERMISSIONS, "สิทธิ์"),
        ("needs", NEEDS, "สิ่งที่ต้องมี"),
    ):
        values = data.get(key, [])
        if not isinstance(values, list):
            errors.append(f"{key} ต้องเป็นรายการ")
            continue
        for v in values:
            if v not in allowed:
                errors.append(f"{label} ที่ไม่รู้จัก: {v}")

    if data.get("actions") and "run_actions" not in data.get("permissions", []):
        errors.append("ใช้ Action ต้องขอสิทธิ์ run_actions")

    prompt = text("prompt", required=False)
    if "llm" in (worker or "") and not prompt:
        errors.append("สกิลที่ใช้ LLM ต้องมี prompt")
    if len(prompt) > MAX_PROMPT:
        errors.append(f"prompt ยาวเกิน {MAX_PROMPT} ตัวอักษร (prompt ยาว = รอนานก่อนคำแรก)")
    return errors


def from_dict(data: dict) -> Manifest:
    errors = validate(data)
    if errors:
        raise InvalidSkill(errors)
    known = {f for f in Manifest.__dataclass_fields__ if f != "extra"}
    kwargs = {k: (tuple(v) if isinstance(v, list) else v) for k, v in data.items() if k in known}
    return Manifest(**kwargs, extra={k: v for k, v in data.items() if k not in known})


def load(path: Path) -> Manifest:
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".md":
            from aipc.skills import mdskill

            data, errors = mdskill.parse(text)
            if errors:
                raise InvalidSkill([f"{path.name}: {e}" for e in errors])
        else:
            data = json.loads(text)
    except (OSError, ValueError) as e:
        if isinstance(e, InvalidSkill):
            raise
        raise InvalidSkill([f"อ่านไฟล์ไม่ได้: {e}"]) from e
    return from_dict(data)


BUILTIN_DIR = Path(__file__).parent / "builtin"


def load_dir(folder: Path) -> list[Manifest]:
    """สกิลทุกไฟล์ในโฟลเดอร์ (.md และ .json) · id ซ้ำ = ผิด (สองสกิลแย่งกันไม่ได้)."""
    skills = [load(p) for p in sorted([*folder.glob("*.md"), *folder.glob("*.json")])]
    seen: set[str] = set()
    for s in skills:
        if s.id in seen:
            raise InvalidSkill([f"id ซ้ำ: {s.id}"])
        seen.add(s.id)
    return skills


def load_builtin() -> list[Manifest]:
    return load_dir(BUILTIN_DIR)
