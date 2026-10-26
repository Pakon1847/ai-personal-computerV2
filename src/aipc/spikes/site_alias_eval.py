"""การ์ด 0066: "ไม่รู้จัก → ใช่ → Claude เพิ่มคำสั่ง → พูดซ้ำแล้วทำได้" เมื่อคำนั้นหมายถึงคำสั่งของระบบ (คำพ้อง).

    python -m aipc.spikes.site_alias_eval tests/data/site_alias_dev.json --precheck
    python -m aipc.spikes.site_alias_eval tests/data/site_alias_test.json --out ผล.json

--precheck (ไม่เรียก Claude): ประโยคต้องไปถึงการ์ด "ให้ Claude เพิ่มคำสั่งไหม"
ตามลำดับเดียวกับหน้าจอ (WorkspacePage.voiceCommand) · ไม่มี --precheck = เรียก Claude จริง (เสียเงิน):
ทางเสียง (handsfree.route) = ไม่รู้จัก → ไม่ใช่คำถามที่โค้ดตอบเอง → ไม่ใกล้คำสั่งของเว็บ → ไม่ใช่ "ค้นในเว็บ" (0057) →
ไม่ใกล้สกิล → ไม่ใช่ขอโหมดใหม่ → ได้การ์ดถาม · ประโยคที่ไม่ถึงต้องเปลี่ยนก่อนวัด (ไม่ใช่ตัดทิ้งเงียบ ๆ)

วัดจริง: ทางเดียวกับแอป (siteLearn → ใช่ → forge · claude -p sonnet → ตัวตรวจ → ติดตั้ง ในที่เก็บสกิลชั่วคราว) →
siteCommand(ประโยคเดิม) · ผ่าน = ได้คำสั่งที่ตรงกับ expect (คำพ้องที่แปลแล้วได้คำสั่งของระบบนั้น
หรือคีย์ลัดที่ยอมรับใน keys) · expect = null (ทำไม่ได้จริง) ผ่าน = ไม่ติดตั้งคำสั่งนั้น
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

URLS = {
    "youtube": "https://www.youtube.com/watch?v=x",
    "spotify": "https://open.spotify.com/",
    "wikipedia": "https://th.wikipedia.org/wiki/x",
}


def path_of(text: str, site: str, skills) -> str:
    """ทางที่หน้าจอจะพาไป · "learn" = ถึงการ์ดให้ Claude เพิ่มคำสั่ง (ต้องเป็นแบบนี้ทุกข้อในชุดวัด)."""
    from aipc.skills import browse
    from aipc.ui import handsfree

    url = URLS[site]
    way = handsfree.route(text, True, skills.voiceSkill, skills.voiceIntent)
    if way != handsfree.UNKNOWN:
        return f"route:{way}"
    if skills.siteCommand(text, url):
        return "site-command"
    if skills.voiceAnswer(text).get("kind") is not None:
        return "answer"
    if skills.siteNear(text, url).get("confirmToken"):
        return "site-near"
    if browse.on_site_search(text, site):
        return "site-search"
    if skills.voiceConfirm(text).get("confirmToken"):
        return "skill-near"
    if skills.voiceCreate(text).get("kind") is not None:
        return "create"
    return "learn" if skills.siteLearn(text, url).get("confirmToken") else "not-learn"


def matches(run: dict | None, item: dict) -> bool:
    """คำสั่งที่ติดตั้งได้ ตรงกับที่ชุดวัดคาดไหม."""
    from aipc.skills import browse

    want = item["expect"]
    if want is None:
        return run is None
    if not run:
        return False
    if run["kind"] == "key":
        return run["arg"] in item.get("keys", [])
    if run["kind"] != "system":
        return False
    got = [c.as_dict() for c in browse.parse(run["arg"])]
    return bool(got) and all(got[0].get(k) == v for k, v in want.items())


def controller(forge_fn):
    from aipc.skills import actions, userskills
    from aipc.ui.backend import SkillsController

    d = Path(tempfile.mkdtemp(prefix="aipc-site-alias-"))
    store = userskills.UserSkills(d / "skills")
    s = SkillsController(executor=actions.Executor(dry_run=True), run_timer=False,
                         reminders_path=d / "r.json", llm_ready=lambda: True, forge=forge_fn,
                         user_skills=store)  # fmt: skip
    s._claude_on = lambda: True
    return s, d


def main(argv: list[str] | None = None) -> int:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    from aipc.skills import forge

    ap = argparse.ArgumentParser()
    ap.add_argument("set", type=Path)
    ap.add_argument("--precheck", action="store_true", help="ตรวจทางของประโยคเท่านั้น ไม่เรียก Claude")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    items = json.loads(a.set.read_text(encoding="utf-8"))["items"]
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 · สัญญาณข้ามเธรดต้องมี event loop

    if a.precheck:
        s, _ = controller(lambda request, **kw: None)
        bad = 0
        for it in items:
            p = path_of(it["text"], it["site"], s)
            bad += p != "learn"
            print(("✓" if p == "learn" else "✗"), it["site"], it["text"], "→", p)
        print(json.dumps({"items": len(items), "not_learn": bad}, ensure_ascii=False))
        return 0 if bad == 0 else 2

    if a.out is None:
        ap.error("วัดจริงต้องมี --out")
    exe = shutil.which("claude")
    if exe is None:
        print("ไม่พบคำสั่ง claude")
        return 1
    version = forge.run_process([exe, "--version"], "", ".", 30)[1].strip()

    def real_forge(request, **kw):
        return forge.forge(request, claude=exe, model="sonnet", claude_version=version, **kw)

    s, d = controller(real_forge)
    done: list[dict] = []
    s.forgeDone.connect(lambda card, text: done.append(card))
    rows = []
    for it in items:
        t0 = time.monotonic()
        text, site = it["text"], it["site"]
        url = URLS[site]
        path = path_of(text, site, s)
        row = {"text": text, "site": site, "expect": it["expect"], "path": path}
        if path != "learn":
            rows.append({**row, "ok": False, "why": "ไม่ถึงการ์ดให้ Claude เพิ่ม"})
            print("✗", text, "→", path, flush=True)
            continue
        ask = s.siteLearn(text, url)
        n = len(done)
        s.confirm(ask["confirmToken"], True)
        while len(done) == n and time.monotonic() - t0 < 300:
            QCoreApplication.processEvents()
            time.sleep(0.05)
        card = done[-1] if len(done) > n else {}
        run = s.siteCommand(text, url).get("siteRun") or None
        ok = matches(run, it)
        rows.append({**row, "ok": ok, "run": run, "card_title": card.get("title", ""),
                     "card_lines": card.get("lines", []),
                     "seconds": round(time.monotonic() - t0, 1)})  # fmt: skip
        print(("✓" if ok else "✗"), text, "→", run, "·", card.get("title", ""), flush=True)
    files = {p.name: p.read_text(encoding="utf-8") for p in (d / "skills").rglob("*.md")}
    can = [r for r in rows if r["expect"] is not None]
    cannot = [r for r in rows if r["expect"] is None]
    summary = {"items": len(rows), "can_ok": sum(r["ok"] for r in can), "can_total": len(can),
               "cannot_ok": sum(r["ok"] for r in cannot), "cannot_total": len(cannot),
               "not_learn": sum(r["path"] != "learn" for r in rows),
               "claude_version": version}  # fmt: skip
    a.out.write_text(json.dumps({"summary": summary, "rows": rows, "files": files},
                                ensure_ascii=False, indent=1) + "\n", encoding="utf-8")  # fmt: skip
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
