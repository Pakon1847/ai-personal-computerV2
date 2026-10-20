"""การ์ด 0046 ก่อน W5: "ไม่รู้จัก → ใช่ → Claude เพิ่มคำสั่ง → พูดซ้ำแล้วตรง" กับ Claude จริง ·
ไม่ใช้เสียง ไม่ใช้เบราว์เซอร์.

    python -m aipc.spikes.site_learn_eval --out ผล.json

ทางเดียวกับแอป: SkillsController.siteLearn → confirm(ใช่) → forge (claude -p · sonnet เหมือนแอป) →
ตัวตรวจ → ติดตั้ง
ในที่เก็บสกิลชั่วคราว → siteCommand(ประโยคเดิม) ต้องได้ "ทำเลย" · ครั้งแรกสร้างสกิลของผู้ใช้ · ครั้งต่อไปแก้รุ่นสกิลเดิม
(คำสั่งเก่าต้องยังอยู่) · W5 จริง = Pakon ลองสดด้วยเสียงในเบราว์เซอร์ (ไม่ใช่สคริปต์นี้)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

URL = "https://www.youtube.com/watch?v=x"
# ประกาศก่อนรัน (2026-10-21) · คำสั่งที่สกิล youtube-voice ในเครื่องยังไม่มี · ไม่ใช่คำถาม
PHRASES = ["ไปตอนท้ายคลิป", "กรอไปครึ่งคลิป", "ปิดเล่นอัตโนมัติ", "เปิดคำอธิบายคลิป", "ไปที่ช่องนี้"]


def main(argv: list[str] | None = None) -> int:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    from aipc.skills import actions, forge, userskills
    from aipc.ui.backend import SkillsController

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    exe = shutil.which("claude")
    if exe is None:
        print("ไม่พบคำสั่ง claude")
        return 1
    version = forge.run_process([exe, "--version"], "", ".", 30)[1].strip()

    def real_forge(request, **kw):
        return forge.forge(request, claude=exe, model="sonnet", claude_version=version, **kw)

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 · สัญญาณข้ามเธรดต้องมี event loop
    d = Path(tempfile.mkdtemp(prefix="aipc-site-learn-"))
    store = userskills.UserSkills(d / "skills")
    s = SkillsController(executor=actions.Executor(dry_run=True), run_timer=False,
                         reminders_path=d / "r.json", llm_ready=lambda: True, forge=real_forge,
                         user_skills=store)  # fmt: skip
    s._claude_on = lambda: True
    done = []
    s.forgeDone.connect(lambda card, text: done.append(card))
    rows = []
    for phrase in PHRASES:
        t0 = time.monotonic()
        ask = s.siteLearn(phrase, URL)
        if not ask.get("confirmToken"):
            rows.append({"phrase": phrase, "ok": False, "why": "ไม่ได้การ์ดถาม", "card": ask})
            continue
        n = len(done)
        s.confirm(ask["confirmToken"], True)
        while len(done) == n and time.monotonic() - t0 < 300:
            QCoreApplication.processEvents()
            time.sleep(0.05)
        card = done[-1] if len(done) > n else {}
        run = s.siteCommand(phrase, URL).get("siteRun")
        mine = [m for m in s._skills if m.site == "youtube" and s._is_user(m.id)]
        n_cmds = sum(len(m.commands) for m in mine)
        row = {"phrase": phrase, "ok": bool(run), "run": run, "card_title": card.get("title", ""),
               "card_lines": card.get("lines", []), "user_skills": [m.id for m in mine],
               "user_commands": n_cmds, "seconds": round(time.monotonic() - t0, 1)}  # fmt: skip
        rows.append(row)
        mark = "✓" if run else "✗"
        title = card.get("title", "")
        print(f"{mark} {phrase} → {run} · {title} · คำสั่งของผู้ใช้ {n_cmds}", flush=True)
    files = {p.name: p.read_text(encoding="utf-8") for p in (d / "skills").rglob("*.md")}
    summary = {"tries": len(rows), "ok": sum(r["ok"] for r in rows),
               "ledger": [e for e in getattr(store, "_index", {}).values()]}  # fmt: skip
    a.out.write_text(json.dumps({"summary": summary, "rows": rows, "files": files},
                                ensure_ascii=False, indent=1) + "\n", encoding="utf-8")  # fmt: skip
    print(json.dumps({"tries": summary["tries"], "ok": summary["ok"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
