"""การ์ด 0050 เกณฑ์ D1 D4: Claude ในเครื่อง (forge ของแอป · sonnet) สร้างสกิลประจำเว็บ
จากคำขอเดียวกับปุ่ม "ให้ Claude สร้าง".

    python -m aipc.spikes.site_create_eval --out ผล.json [--dir โฟลเดอร์เก็บไฟล์ที่ได้]

รันในบัญชีที่เข้าสู่ระบบ Claude แล้ว (Pi 5) · ไม่ติดตั้งลงที่เก็บสกิลของบัญชี (เก็บไฟล์ใน --dir เท่านั้น) ·
D1 = youtube spotify netflix news ผ่านตัวตรวจ + จำนวนคำสั่ง ·
D4 = gmail calendar drive docs ต้องไม่ได้สกิลสั่งในหน้าเว็บ · ไม่ใช้ Qt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

D1 = ("youtube", "spotify", "netflix", "news")
D4 = ("gmail", "calendar", "drive", "docs")


def request(site: str) -> str:
    """ข้อความเดียวกับ SkillsController._site_create_request (การ์ด 0050)."""
    from aipc.skills.actions import SITES

    return (
        f"สร้างสกิลประจำเว็บ (site: {site} · หัวข้อ ## คำสั่ง) สำหรับสั่ง {SITES[site][0]} ด้วยเสียง · "
        "อย่างน้อย 10 คำสั่งที่คนใช้บ่อยในเว็บนี้ · ใช้คีย์ลัดที่เว็บมีจริงก่อน · "
        "คลิกเฉพาะปุ่มที่ไม่มีคีย์ลัด · แต่ละคำสั่งมีคำพูดภาษาไทยที่คนพูดจริง 2–3 แบบ"
    )


def kind_of(m) -> str:
    if m is None:
        return ""
    return "site" if m.site else ("steps" if m.steps else "llm")


def main(argv: list[str] | None = None) -> int:
    from aipc.cloud import ask
    from aipc.skills import forge, manifest, userskills

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dir", type=Path, default=None)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    exe = ask.find_claude()
    if not exe:
        print("ไม่พบ claude ในบัญชีนี้")
        return 1
    version = forge.run_process([exe, "--version"], "", ".", 30)[1].strip()
    builtin = manifest.load_builtin()

    def check(md: str) -> list[str]:
        return userskills.gate(md, builtin)[1]

    rows = []
    for site in (*D1, *D4):
        p = forge.forge(request(site), skills=builtin, claude=exe, model="sonnet",
                        claude_version=version, check=check)  # fmt: skip
        m = userskills.check_md(p.skill_md)[0] if p.skill_md else None
        row = {"site": site, "ok": bool(m), "is_site_skill": bool(m and m.site),
               "commands": len(m.commands) if m else 0, "kind": kind_of(m),
               "errors": p.errors[:3], "attempts": p.attempts,
               "cost_usd": round(p.cost_usd, 4)}  # fmt: skip
        rows.append(row)
        if a.dir and p.skill_md:
            a.dir.mkdir(parents=True, exist_ok=True)
            (a.dir / f"{site}.md").write_text(p.skill_md, encoding="utf-8")
        print(json.dumps(row, ensure_ascii=False), flush=True)
    d1 = [r for r in rows if r["site"] in D1]
    d4 = [r for r in rows if r["site"] in D4]
    made = [r["commands"] for r in d1 if r["is_site_skill"]]
    summary = {"D1_site_skills_ok": len(made), "D1_n": len(d1),
               "D1_min_commands": min(made, default=0),
               "D4_site_skills_made": sum(r["is_site_skill"] for r in d4), "D4_n": len(d4),
               "cost_usd": round(sum(r["cost_usd"] for r in rows), 3), "claude": version}  # fmt: skip
    out = json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1)
    a.out.write_text(out + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
