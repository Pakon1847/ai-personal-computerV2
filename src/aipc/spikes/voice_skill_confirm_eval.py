"""การ์ด 0028 ข้อ ก2: ใช้ข้อความที่ตัวถอดได้ยินจริง (ค่าดิบของ voice_skill_asr) ถามว่าแอปจะทำอะไร.

ไม่อัดเสียงใหม่ · ใช้ SkillsController ตัวจริง (voiceSkill = ตรงเป๊ะ · voiceConfirm = การ์ด "หมายถึง … ใช่ไหม")
และ handsfree.route ตัวจริง · นับ: ตรงเป๊ะไปสกิลถูก · การ์ดยืนยันชี้สกิลถูก · **ชี้/ทำสกิลผิด** · ไม่มีอะไร

    python -m aipc.spikes.voice_skill_confirm_eval <asr.json> --skills <โฟลเดอร์สกิล> [--out ผล.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from aipc.skills import manifest, userskills
from aipc.ui.backend import SkillsController
from aipc.ui.handsfree import SKILL, UNKNOWN, route


def controller(folder: Path) -> SkillsController:
    """ติดตั้งสกิลผ่านประตูจริงลงโฟลเดอร์ชั่วคราว แล้วสร้างตัวคุมสกิลแบบเดียวกับแอป (ไม่มีตัวจับเวลา)."""
    tmp = Path(tempfile.mkdtemp(prefix="voice-confirm-"))
    store = userskills.UserSkills(tmp / "skills")
    for f in sorted(folder.glob("*.md")):
        try:
            store.install(f.read_text(encoding="utf-8"), manifest.load_builtin() + store.load(),
                          request="")  # fmt: skip
        except manifest.InvalidSkill:
            pass
    return SkillsController(reminders_path=tmp / "r.json", run_timer=False,
                            llm_ready=lambda: True, user_skills=store)  # fmt: skip


def judge(s: SkillsController, heard: str, want: str) -> tuple[str, str]:
    """(ผล, สกิลที่แอปเลือก) · ผล: exact · confirm_right · wrong · command · none."""
    way = route(heard, False, s.voiceSkill)
    if way == SKILL:
        got = s.voiceSkill(heard)
        return ("exact" if got == want else "wrong"), got
    if way != UNKNOWN:
        return "command", ""  # คำสั่งเว็บ/เครื่องเดิมรับไป (เช่น เปิดแผนที่)
    card = s.voiceConfirm(heard)
    if not card:
        return "none", ""
    got = s._pending[card["confirmToken"]][1].id
    return ("confirm_right" if got == want else "wrong"), got


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("asr", type=Path)
    ap.add_argument("--skills", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    QCoreApplication.instance() or QCoreApplication([])
    s = controller(a.skills)
    items = json.loads(a.asr.read_text(encoding="utf-8"))["items"]
    rows = []
    for it in items:
        verdict, got = judge(s, it["heard"], it["skill"])
        rows.append({"text": it["text"], "heard": it["heard"], "skill": it["skill"],
                     "verdict": verdict, "picked": got})  # fmt: skip
        print(f"{verdict:13} «{it['heard']}» ← {it['text']} ({it['skill']} → {got or '-'})")
    count = {k: sum(r["verdict"] == k for r in rows)
             for k in ("exact", "confirm_right", "wrong", "command", "none")}  # fmt: skip
    print(json.dumps(count, ensure_ascii=False))
    if a.out:
        a.out.write_text(json.dumps({"summary": count, "rows": rows}, ensure_ascii=False, indent=1),
                         encoding="utf-8")  # fmt: skip


if __name__ == "__main__":
    main()
