"""ให้ Claude เขียนสกิลในเครื่องใหม่ (การ์ด 0043 · เราสร้างเครื่องมือ · Claude สร้างสกิล).

    python -m aipc.skills.rebuild translate reminder … [--out โฟลเดอร์] [--apply]

ใช้ทางเดียวกับ forge (claude -p · โฟลเดอร์ว่าง · ปิดเครื่องมือ · ตัวตรวจ · ทดลองเส้นทาง) ต่างกันแค่:
- คำขอ = คำอธิบายงาน/เครื่องมือโค้ดของสกิลนั้น (BRIEFS) · **ไม่ส่งไฟล์เดิมให้ Claude ดู** (Claude เขียนเอง ไม่ลอก)
- ส่วนหัวเรื่องสิทธิ์ (id worker needs permissions actions) = ค่าเดิมของระบบเสมอ (forge.pin_header · H7)
- --apply = เขียนทับไฟล์ใน builtin/ เมื่อผ่านตัวตรวจและไม่แย่งประโยคของสกิลอื่น · ไฟล์เดิมอยู่ใน git (ย้อนได้)
- สกิลประจำเว็บ (การ์ด 0046 · youtube-voice spotify-voice) สร้างใหม่ได้ด้วยคำสั่งเดียวกัน (ยังไม่มีไฟล์เดิม)
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from aipc.skills import forge, manifest

# งานภาษา: Claude เขียน prompt เอง · เครื่องมือโค้ด: Claude เขียนชื่อ คำอธิบาย คำสำคัญ ตัวอย่าง (โค้ดทำงานเอง)
_TOOL = " · ".join([
    "ไฟล์นี้เป็นสกิลที่เรียกเครื่องมือโค้ดของระบบ (worker: code)",
    "ไม่ต้องมี ## ขั้นตอน และไม่ต้องมี ## คำสั่งให้ AI",
    "เขียน name description keywords examples (อย่างน้อย 3) และคำอธิบายสั้น ๆ ให้คนอ่าน",
    "ส่วนหัว id worker needs permissions actions ระบบกำหนดเอง",
])  # fmt: skip
_LLM = " · ".join([
    "สกิลงานภาษา (worker: llm · needs: llm) · เขียน ## คำสั่งให้ AI เอง",
    "AI ในเครื่องเป็นโมเดลเล็ก (ราว 4B) จึงต้องสั้นและชัด",
    "ส่วนหัว id worker needs ระบบกำหนดเอง",
])  # fmt: skip
# สกิลประจำเว็บ (การ์ด 0046): Claude เขียนคำพูด + คีย์ลัด/ตัวเลือกปุ่มเอง · ระบบกำหนด id สิทธิ์ และเว็บ
_SITE = " · ".join([
    "เป็นสกิลประจำเว็บ (หัวข้อ ## คำสั่ง ตามแบบในคำแนะนำ) · ไม่มี ## ขั้นตอน และไม่มี ## คำสั่งให้ AI",
    "อย่างน้อย 12 คำสั่งที่ใช้บ่อย · ใช้คีย์ลัดที่เว็บมีจริงก่อน · คลิกเฉพาะปุ่มที่ไม่มีคีย์ลัด",
    "แต่ละคำสั่งใส่คำพูดภาษาไทยที่คนพูดจริง 2–3 แบบ",
    "ส่วนหัว id permissions site ระบบกำหนดเอง",
])  # fmt: skip
SITE_SKILLS = {"youtube-voice": "youtube", "spotify-voice": "spotify"}
BRIEFS = {
    "translate": " · ".join([
        "สร้างสกิลแปลข้อความระหว่างภาษาไทยกับภาษาอังกฤษ (ทั้งสองทาง) ที่ผู้ใช้พิมพ์หรือพูด",
        "คำเดียว ประโยค หรือย่อหน้า · ตอบเฉพาะคำแปล ไม่แต่งเพิ่ม", _LLM,
    ]),
    "summarize-text": " · ".join([
        "สร้างสกิลสรุปข้อความยาวที่ผู้ใช้วางมา (ข่าว ประกาศ อีเมล บทความ)",
        "ให้เหลือใจความสำคัญเป็นข้อ ๆ ภาษาไทย",
        "ไม่ใช้เมื่อไม่มีข้อความให้สรุป หรือเมื่ออยากแปล", _LLM,
    ]),
    "letter-writer": " · ".join([
        "สร้างสกิลร่างจดหมาย/อีเมลภาษาไทยแบบสุภาพ",
        "เช่น ลาป่วย ลากิจ ขอเลื่อนส่งงาน ขอบคุณ ถึงอาจารย์/หัวหน้า/ลูกค้า",
        "มีหัวเรื่อง คำขึ้นต้น เนื้อความ คำลงท้าย · ไม่ส่งอีเมลให้ · ไม่ใช่งานนัดหมาย",
        "ห้ามเดาชื่อหรือวันที่ ให้เว้นช่องไว้", _LLM,
    ]),
    "reminder": " · ".join([
        "สร้างสกิลนัดหมายและเตือนความจำ",
        "เครื่องมือโค้ด 'reminder' ของระบบ: อ่านประโยคภาษาไทย หาวันเวลาเอง",
        "(พรุ่งนี้ บ่ายสอง สองทุ่ม วันศุกร์ วันที่ 5 อีก 10 นาที)",
        "บันทึกนัดหลังผู้ใช้ยืนยัน แล้วเตือนเมื่อถึงเวลา",
        "ผู้ใช้มักขึ้นต้นด้วย เตือน / นัด / อย่าลืม / ปลุก", _TOOL,
    ]),
    "system-command": " · ".join([
        "สร้างสกิลสั่งงานเครื่อง",
        "เครื่องมือโค้ดของระบบ: เปิดเว็บในรายการ เปิดแอปในรายการ เปิดหน้าในระบบ",
        "ปรับเสียงเป็นเปอร์เซ็นต์ เพิ่ม/ลดเสียง ปิด/เปิดเสียง (ตัวแปลคำสั่งของระบบแปลประโยคเอง)", _TOOL,
    ]),
    "machine-status": " · ".join([
        "สร้างสกิลถามเครื่องว่าเป็นอะไร",
        "เครื่องมือโค้ดของระบบอ่านค่าจริง (อุณหภูมิ แรม พื้นที่เก็บข้อมูล ไฟเลี้ยง/ไฟตก พัดลม เครือข่าย)",
        "แล้วอธิบายเป็นภาษาคนพร้อมวิธีแก้",
        "ใช้เมื่อผู้ใช้บอกอาการ (ช้า ค้าง ร้อน) หรือถามค่าของเครื่อง", _TOOL,
    ]),
    "youtube-voice": " · ".join([
        "สร้างสกิลสั่ง YouTube ด้วยเสียงขณะดูวิดีโอในเบราว์เซอร์ (site: youtube)",
        "เช่น หยุด/เล่น ถอย/ข้ามสิบวิ ปิดเสียง เต็มจอ คำบรรยาย ความเร็ว วิดีโอถัดไป โหมดโรงภาพยนตร์ กดไลก์", _SITE,
    ]),
    "spotify-voice": " · ".join([
        "สร้างสกิลสั่ง Spotify ด้วยเสียงในเว็บเพลเยอร์ open.spotify.com (site: spotify)",
        "เช่น หยุด/เล่น เพลงถัดไป/ก่อนหน้า สุ่มเพลง เล่นซ้ำ ปิดเสียง ถูกใจเพลงนี้ ดูคิว ดูเนื้อเพลง", _SITE,
    ]),
}  # fmt: skip


def site_header(skill_id: str) -> dict[str, str]:
    """ส่วนหัวที่ระบบกำหนดของสกิลประจำเว็บในเครื่อง (ไม่ขึ้นกับไฟล์เดิม · มีหรือยังไม่มีก็ได้)."""
    return {"id": skill_id, "worker": "", "needs": "", "permissions": "page_actions", "actions": "",
            "site": SITE_SKILLS[skill_id]}  # fmt: skip


def fixed_header(path: Path) -> dict[str, str]:
    """ค่าส่วนหัวเรื่องสิทธิ์ของไฟล์เดิม (ค่า "" = ไฟล์เดิมไม่มีบรรทัดนี้)."""
    lines = path.read_text(encoding="utf-8").split("\n")
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    out = dict.fromkeys(forge.PINNED_KEYS, "")
    for x in lines[1:end]:
        key = x.split(":", 1)[0].strip()
        if key in out:
            out[key] = x.split(":", 1)[1].strip()
    return out


def rebuild(skill_id: str, *, claude: str, version: str, model: str | None = None,
            runner: forge.Runner = forge.run_process) -> forge.Proposal:  # fmt: skip
    path = manifest.BUILTIN_DIR / f"{skill_id}.md"
    others = [s for s in manifest.load_builtin() if s.id != skill_id]
    pin = site_header(skill_id) if skill_id in SITE_SKILLS else fixed_header(path)
    return forge.forge(BRIEFS[skill_id], skills=others, claude=claude, model=model,
                       claude_version=version, runner=runner, pin=pin)  # fmt: skip


def apply(p: forge.Proposal) -> Path:
    """เขียนทับไฟล์สกิลในเครื่อง · เฉพาะที่ผ่านตัวตรวจ + ไม่แย่งประโยค (p.ok)."""
    if not p.ok:
        raise manifest.InvalidSkill([f"{p.skill_id or '?'}: ยังไม่ผ่าน · ไม่เขียนทับ"])
    target = manifest.BUILTIN_DIR / f"{p.skill_id}.md"
    tmp = target.with_suffix(".md.tmp")
    tmp.write_text(p.skill_md, encoding="utf-8", newline="\n")
    os.replace(tmp, target)
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m aipc.skills.rebuild", description=__doc__.splitlines()[0]
    )
    ap.add_argument("ids", nargs="+", choices=sorted(BRIEFS))
    ap.add_argument("--model", default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--apply", action="store_true", help="เขียนทับไฟล์ใน builtin/ เมื่อผ่าน")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    claude = shutil.which("claude")
    if claude is None:
        print("ไม่พบคำสั่ง claude (ติดตั้ง Claude Code และเข้าสู่ระบบก่อน)")
        return 1
    version = forge.run_process([claude, "--version"], "", ".", 30)[1].strip()
    bad = 0
    for skill_id in a.ids:
        p = rebuild(skill_id, claude=claude, version=version, model=a.model)
        path = forge.save(p, a.out or forge.default_out())
        print(f"===== {skill_id} =====")
        print(forge.report(p, path))
        print(f"ส่วนหัวเรื่องสิทธิ์ที่ Claude ใส่ต่างไป (ระบบแทนแล้ว): {', '.join(p.pinned_changed) or 'ไม่มี'}")
        if a.apply and p.ok:
            print(f"เขียนทับแล้ว: {apply(p)}")
        bad += not p.ok
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
