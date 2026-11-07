"""สกิลที่ Claude สร้างให้ผู้ใช้คนนี้ ติดตั้งอัตโนมัติ (การ์ด 0017) · เก็บใน home ของผู้ใช้ (0700) บัญชีอื่นไม่เห็น.

โครง: <โฟลเดอร์>/<id>.md = รุ่นที่ใช้ · .versions/<id>/<n>.md = ทุกรุ่น · index.json = ที่มา + นับใช้/ผิด + เปิด/ปิด
กันพลาด (การ์ด 0017 หัวข้อ 5):
  ชั้นที่ 1 gate(): ตัวตรวจไฟล์เดิม + id ไม่ซ้ำ + ไม่แย่งประโยคสกิลเดิม + นโยบายเฉพาะสกิลอัตโนมัติ (AUTO_POLICY)
  ชั้นที่ 3 wrong()/record(): ผิดหรือทำไม่สำเร็จ 2 ครั้งติดกัน = ปิดเอง
เขียนไฟล์ด้วยไฟล์ชั่วคราว + os.replace (ไฟดับกลางคัน = รุ่นเก่าหรือรุ่นใหม่ครบ) · index เสีย = ไม่ทำให้หน้าจอเปิดไม่ขึ้น
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from aipc.skills import manifest

MAX_STRIKES = 2  # ผิด/ทำไม่สำเร็จติดกันกี่ครั้งถึงปิด
# สกิลที่ติดตั้งโดยไม่มีคนดูก่อน ห้ามทำสิ่งเหล่านี้ (ถึงตัวตรวจทั่วไปจะยอม):
# เปิด URL ที่เขียนเอง (ลิงก์หลอกได้ · ใช้ได้เฉพาะเว็บในรายการของระบบ) · เปิดเทอร์มินัล (ช่องทางรันคำสั่ง)
AUTO_DENY_APPS = frozenset({"terminal"})
# ตัวทำงานที่ระบบมีให้สกิลของผู้ใช้ (การ์ด 0074): ขั้นตอน (code · code+llm) · งานภาษา (llm) · สกิลประจำเว็บ (code)
# แบบอื่น (กล้อง+ภาพ · เสียง+llm) มีแต่สกิลในตัวที่มีโค้ดรองรับ · S1 b19 = สกิล "ถ่ายภาพเงียบ ๆ" ผ่านด่านเดิมได้
USER_WORKERS = frozenset({"code", "code+llm", "llm"})


def default_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "aipc" / "skills"


def auto_policy(m: manifest.Manifest) -> list[str]:
    errors = []
    # สกิลของผู้ใช้ไม่มีโค้ดของตัวเอง (ADR-011 ข้อ 1) · ไม่มีทั้งขั้นตอนและคำสั่งให้ AI = ทำอะไรไม่ได้เลย
    # (ชุดสกิลเสีย b13 ผ่านตัวตรวจทั่วไปได้ เพราะสกิลในตัวแบบ worker code มีโค้ดรองรับ)
    # สกิลประจำเว็บ (การ์ด 0046) มี "## คำสั่ง" แทน
    if not m.steps and not m.prompt.strip() and not m.commands:
        errors.append("สกิลต้องมี “## ขั้นตอน” “## คำสั่งให้ AI” หรือ “## คำสั่ง” (สกิลประจำเว็บ) อย่างใดอย่างหนึ่ง")
    for s in m.steps:
        plan = s.plan
        if plan is None:
            continue
        if plan.action == "open_url" and "url" in plan.params:
            errors.append(f"สกิลอัตโนมัติเปิดได้เฉพาะเว็บในรายการของระบบ ไม่ใช่ลิงก์ {plan.params['url']}")
        if plan.action == "open_app" and plan.params.get("app") in AUTO_DENY_APPS:
            errors.append("สกิลอัตโนมัติเปิดเทอร์มินัลไม่ได้")
    if m.worker not in USER_WORKERS:
        errors.append(f"สกิลของผู้ใช้ใช้ worker “{m.worker}” ไม่ได้ (มีให้แค่ ขั้นตอน · งานภาษา · สกิลประจำเว็บ)")
    # ขอได้เฉพาะสิทธิ์ที่ขั้นตอนใช้จริง (การ์ด 0074 · S1 b07 b17: ขอสั่งเครื่องทั้งที่ไม่มีขั้นสั่งเครื่อง
    # = หน้าตรวจบอกสิทธิ์ไม่ตรงความจริง)
    used = set()
    if any(s.kind == "action" for s in m.steps):
        used.add("run_actions")
    if any(s.kind == "agenda" for s in m.steps):
        used.add("read_agenda")
    if m.commands:
        used.add("page_actions")
    if extra := [p for p in m.permissions if p not in used]:
        labels = ", ".join(manifest.PERMISSIONS[p] for p in extra)
        errors.append(f"ขอสิทธิ์ที่สกิลไม่ได้ใช้: {labels}")
    return errors


def check_md(skill_md: str) -> tuple[manifest.Manifest | None, list[str]]:
    """ตัวตรวจเดียวกับ forge (mdskill + manifest + ขนาด) + นโยบายสกิลอัตโนมัติ + เนื้อหา (การ์ด 0074)."""
    from aipc.skills import contentcheck, forge

    m, errors = forge._validate(skill_md)
    if m is None:
        return None, errors
    errors = auto_policy(m) + contentcheck.check(m, skill_md)
    return (None, errors) if errors else (m, [])


def gate(
    skill_md: str, existing: list[manifest.Manifest], replacing: str = ""
) -> tuple[manifest.Manifest | None, list[str]]:
    """ชั้นที่ 1: ผ่านทุกข้อ = คืน Manifest · ไม่ผ่าน = (None, เหตุผล).

    replacing = id ของสกิลที่กำลังแก้ (รุ่นใหม่ใช้ id เดิมได้ และไม่นับว่าแย่งประโยคของตัวเอง)
    """
    from aipc.skills import forge

    m, errors = check_md(skill_md)
    if m is None:
        return None, errors
    others = [s for s in existing if s.id != replacing]
    if m.id in {s.id for s in others}:
        return None, [f"id {m.id} ซ้ำกับสกิลที่มีอยู่"]
    if replacing and m.id != replacing:
        return None, [f"รุ่นแก้ต้องใช้ id เดิม ({replacing}) ไม่ใช่ {m.id}"]
    # ตัวอย่างของสกิลใหม่ต้องไม่ใช่งานของสกิลเดิม (ชุดสกิลเสีย b06 b15: เอาประโยคของสกิลแปล/สรุปมาเป็นตัวอย่าง
    # ตัวคัดสกิลแบบกฎยังส่งประโยคพวกนั้นไปสกิลเดิม trial จึงไม่เห็นว่าแย่ง แต่ AI
    # ในเครื่องเลือกจากคำอธิบาย+ตัวอย่าง อาจเลือกสกิลใหม่)
    # ดูเฉพาะส่วนคำสั่ง (ก่อน ":" · หลังจากนั้นคือข้อความที่ผู้ใช้วางมา เช่น "ทำให้เป็นทางการ:
    # ...มาช้า" ไม่ใช่งานเช็กเครื่องช้า) ·
    # คำสั่งตรงของระบบ (เปิดแผนที่) ทำก่อนถึง AI เสมอ จึงไม่นับว่าแย่ง (สกิลดีของ Claude 3/10
    # เคยถูกปฏิเสธผิดด้วยสองเหตุนี้)
    # สกิลประจำเว็บ (การ์ด 0046) ไม่เข้าตัวคัดสกิล จึงไม่แย่งงานใคร (ตัวอย่างของมันคือคำพูดในหน้าเว็บ)
    overlap = [
        (e, k)
        for e in m.examples
        if not m.site and (k := _pick(e.split(":")[0].split("：")[0], others))
    ]
    if overlap:
        return None, [f"ตัวอย่าง “{e}” เป็นงานของสกิลเดิม ({k})" for e, k in overlap]
    t = forge.trial(m, others, [], [])
    if t.stolen:
        return None, [f"แย่งประโยคของสกิลเดิม: {s} (เดิมคือ {k})" for s, k in t.stolen]
    return m, []


def _pick(text: str, skills: list[manifest.Manifest]) -> str:
    """สกิลที่ตัวคัดสกิลแบบกฎเลือกให้ประโยคนี้ ("" = ไม่มี) · ตัวเดียวกับที่ forge.trial ใช้."""
    from aipc.skills import router

    r = router.route(text, skills, {"llm"})
    if not (r.skill and r.kind == "skill"):
        return ""
    # ตัวคัดแบบกฎ (ทางสำรองตอนไม่มี AI) ส่งทุกประโยคที่บอกวัน/เวลาไปสกิลนัด และ "…แปลว่าอะไร" ไปสกิลแปล ·
    # S1 สกิลดีถูกปฏิเสธเพราะสองข้อนี้ ("พรุ่งนี้จะไปเที่ยว" "เงินเฟ้อแปลว่าอะไร") → นับว่าแย่งเฉพาะเมื่อชัดจริง:
    # นัด = มีคำสำคัญของสกิลนัด · แปล = มีคำต่างภาษา หรือคำสั่งแปลอื่นนอกจาก "แปลว่า" (การ์ด 0074 หัวข้อ 14 ข้อ 3)
    # ไม่ใช้ทางเลือกของแอป (route_ai_first) แทน เพราะชุดพัฒนา S1 สกิลแย่งงานหลุดเพิ่ม 4 ตัว
    if r.skill.id == "reminder" and not any(router.has_keyword(text, k) for k in r.skill.keywords):
        return ""
    if r.skill.id == "translate" and _meaning_question(text, r.skill):
        return ""
    return r.skill.id


def _meaning_question(text: str, translate: manifest.Manifest) -> bool:
    """ถามความหมายคำไทย ("เงินเฟ้อแปลว่าอะไร") ไม่ใช่ขอแปล.

    มีตัวอักษรละติน ("serendipity แปลว่าอะไร") = ขอแปล
    """
    import re

    from aipc.skills import router

    hits = [k for k in translate.keywords if router.has_keyword(text, k)]
    return hits == ["แปลว่า"] and not re.search(r"[A-Za-z]", text)


class UserSkills:
    def __init__(self, folder: Path | None = None):
        self.folder = folder or default_dir()
        self._index = self._read_index()

    # ---------- index ----------
    def _read_index(self) -> dict:
        try:
            data = json.loads((self.folder / "index.json").read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}  # ไม่มี / เสีย = ถือว่าทุกไฟล์เป็นรุ่น 1 เปิดอยู่

    def _write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def _save_index(self) -> None:
        self._write(
            self.folder / "index.json", json.dumps(self._index, ensure_ascii=False, indent=1)
        )

    def info(self, skill_id: str) -> dict:
        e = self._index.get(skill_id) or {}
        return {"version": 1, "enabled": True, "uses": 0, "strikes": 0, **e}

    # ---------- อ่าน ----------
    def load_all(self) -> list[manifest.Manifest]:
        """ทุกสกิลในโฟลเดอร์ที่โหลดผ่าน (ไฟล์เสีย = ข้าม ไม่ทำให้สกิลอื่นใช้ไม่ได้)."""
        out = []
        for p in sorted(self.folder.glob("*.md")) if self.folder.is_dir() else []:
            try:
                out.append(manifest.load(p))
            except manifest.InvalidSkill:
                continue
        return out

    def load(self) -> list[manifest.Manifest]:
        """เฉพาะสกิลที่เปิดอยู่ (ให้ AI เลือกได้)."""
        return [m for m in self.load_all() if self.info(m.id)["enabled"]]

    def entries(self) -> list[dict]:
        return [{"id": m.id, "name": m.name, **self.info(m.id)} for m in self.load_all()]

    # ---------- เขียน ----------
    def install(
        self,
        skill_md: str,
        existing: list[manifest.Manifest],
        *,
        request: str,
        model: str = "",
        cost_usd: float = 0.0,
        replacing: str = "",
    ) -> manifest.Manifest:
        """ผ่านชั้นที่ 1 แล้วติดตั้ง (หรือแทนรุ่นเดิมเมื่อ replacing) · ไม่ผ่าน = InvalidSkill ไม่เขียนอะไร."""
        m, errors = gate(skill_md, existing, replacing)
        if m is None:
            raise manifest.InvalidSkill(errors)
        old = self.info(m.id) if replacing else {}
        version = max([0, *self.versions(m.id)]) + 1 if replacing else 1
        self._write(self.folder / ".versions" / m.id / f"{version}.md", skill_md)
        self._write(self.folder / f"{m.id}.md", skill_md)
        self._index[m.id] = {
            "version": version,
            "enabled": True,
            "uses": old.get("uses", 0),
            "strikes": old.get("strikes", 0) if replacing else 0,
            "request": request,
            "model": model,
            "cost_usd": round(cost_usd, 4),
            "created": old.get("created") or datetime.now().isoformat(timespec="seconds"),
            "updated": datetime.now().isoformat(timespec="seconds"),
        }
        self._save_index()
        return m

    def remove(self, skill_id: str) -> bool:
        p = self.folder / f"{skill_id}.md"
        if not p.exists():
            return False
        p.unlink()
        shutil.rmtree(self.folder / ".versions" / skill_id, ignore_errors=True)
        self._index.pop(skill_id, None)
        self._save_index()
        return True

    def set_enabled(self, skill_id: str, on: bool) -> None:
        e = self.info(skill_id)
        e.update(enabled=on, strikes=0 if on else e["strikes"])
        self._index[skill_id] = e
        self._save_index()

    def record(self, skill_id: str, ok: bool) -> bool:
        """ผลการใช้ 1 ครั้ง · คืน True ถ้าสกิลถูกปิดเพราะครั้งนี้ (ชั้นที่ 3)."""
        e = self.info(skill_id)
        if ok:
            e.update(uses=e["uses"] + 1, strikes=0)
        else:
            e["strikes"] += 1
        disabled = e["strikes"] >= MAX_STRIKES and e["enabled"]
        if disabled:
            e["enabled"] = False
        self._index[skill_id] = e
        self._save_index()
        return disabled

    def wrong(self, skill_id: str) -> bool:
        """ผู้ใช้กด "ไม่ใช่แบบนี้" · คืน True ถ้าปิดสกิลแล้ว."""
        return self.record(skill_id, ok=False)

    def versions(self, skill_id: str) -> list[int]:
        d = self.folder / ".versions" / skill_id
        return sorted(int(p.stem) for p in d.glob("*.md") if p.stem.isdigit()) if d.is_dir() else []

    def revert(
        self, skill_id: str, version: int, existing: list[manifest.Manifest]
    ) -> manifest.Manifest:
        """กลับไปใช้รุ่นที่เก็บไว้ (หน้า Skill · การ์ด 0017 ชั้นที่ 3) · ผ่านประตูใหม่ก่อน (สกิลอื่นอาจเพิ่มมาหลังรุ่นนั้น)."""
        src = self.folder / ".versions" / skill_id / f"{version}.md"
        try:
            md = src.read_text(encoding="utf-8")
        except OSError as e:
            raise manifest.InvalidSkill([f"ไม่มีรุ่น {version}"]) from e
        m, errors = gate(md, existing, skill_id)
        if m is None:
            raise manifest.InvalidSkill(errors)
        self._write(self.folder / f"{skill_id}.md", md)
        e = self.info(skill_id)
        e.update(
            version=version,
            enabled=True,
            strikes=0,
            updated=datetime.now().isoformat(timespec="seconds"),
        )
        self._index[skill_id] = e
        self._save_index()
        return m

    def current_md(self, skill_id: str) -> str:
        try:
            return (self.folder / f"{skill_id}.md").read_text(encoding="utf-8")
        except OSError:
            return ""
