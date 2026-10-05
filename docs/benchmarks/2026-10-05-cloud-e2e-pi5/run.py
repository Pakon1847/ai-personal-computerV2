"""ไฮบริดทั้งสายบน Pi 5 (2026-10-05) · รันในนามบัญชีที่เข้าสู่ระบบ Claude Code แล้ว · ใช้โค้ดของแอป (app._cloud_client / _skill_forge).

    python run.py <โฟลเดอร์ผล>

ไม่แตะข้อมูลจริงของบัญชี: งบ/บันทึกส่งออกอยู่ในโฟลเดอร์ผล · สกิลที่สร้างไม่ติดตั้ง (เก็บแค่ไฟล์ .md)
ไม่อ่านไฟล์การเข้าสู่ระบบของ Claude · เกณฑ์อยู่ใน README.md (commit ก่อนรัน)
"""

import json
import sys
import time
from pathlib import Path

from aipc.cloud import ask
from aipc.cloud.budget import Budget
from aipc.cloud.ledger import Ledger
from aipc.skills import manifest
from aipc.ui import app

CANARY = "CANARY-7Q4X"
QUESTION = "วันนี้ในประเทศไทยมีข่าวอะไรเด่นบ้าง ตอบสั้น ๆ 3 ข้อ พร้อมแหล่งข่าว"
HISTORY = [
    {"role": "user", "content": "สวัสดีครับ"},
    {"role": "assistant", "content": "สวัสดีครับ มีอะไรให้ช่วยไหม"},
    {"role": "user", "content": f"[ใบเสร็จค่าซ่อมแอร์.txt] รหัสลูกค้า {CANARY} ยอด 3,500 บาท\nคำถาม: จ่ายไปเท่าไร",
     "shown": "จ่ายไปเท่าไร", "file": "ใบเสร็จค่าซ่อมแอร์.txt"},
    {"role": "assistant", "content": f"จ่ายไป 3,500 บาท (รหัสลูกค้า {CANARY})"},
]
REQUEST = "ทำโหมดประชุมให้หน่อย: ปิดเสียงเครื่องแล้วเปิด Google Calendar"


def main(out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    budget, ledger = Budget(out / "usage.json"), Ledger(out / "outbound.json")
    res = {"claude": ask.find_claude()}
    run = app._cloud_client(budget, ledger)
    if run is None:
        res["error"] = "ไม่มี claude ในบัญชีนี้"
    else:
        t0 = time.monotonic()
        r = run(QUESTION, HISTORY)
        res["ask"] = {"ok": r.ok, "seconds": round(time.monotonic() - t0, 1), "cost_usd": r.cost_usd,
                      "error": r.error, "answer": r.text}
    forge_run = app._skill_forge(budget, ledger)
    if forge_run is not None:
        t0 = time.monotonic()
        p = forge_run(REQUEST, skills=manifest.load_builtin())
        res["forge"] = {"ok": p.ok, "seconds": round(time.monotonic() - t0, 1), "cost_usd": p.cost_usd,
                        "attempts": p.attempts, "errors": p.errors, "claude_version": p.claude_version}
        if p.ok:
            (out / "forged-skill.md").write_text(p.skill_md, encoding="utf-8")
    sent = [e["sent"] for e in ledger.entries()]
    res["ledger_kinds"] = [e["kind"] for e in ledger.entries()]
    res["ask_sent_matches_build_input"] = ask.build_input(QUESTION, HISTORY) in sent
    res["canary_in_ledger"] = any(CANARY in s for s in sent)
    (out / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "ask"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
