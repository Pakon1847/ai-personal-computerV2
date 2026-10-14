"""วัดเกณฑ์ข้อ 2–3 ของการ์ด 0027: คำพูดจากคีย์ลัดไปทางไหน เทียบแอปเดิมทีละประโยค (ข้อความ · ไม่ผ่านเสียง).

    python -m aipc.spikes.voice_route_eval --out <โฟลเดอร์ผล>/routes.json
    (ผลการ์ด 0027: docs/benchmarks/2026-10-14-voice-command-mode/)

แอปเดิม (ก่อน 0027 · WorkspacePage.qml voiceCommand): BrowserController.handle ได้ = "browser" ·
ไม่ได้ = sendText → คำสั่งเครื่อง (command.parse) = "command" · ที่เหลือ = "chat" (แชท/สกิลอื่น/AI ในเครื่อง)
แอปใหม่: aipc.ui.handsfree.route (ตัวเดียวกับแอป) · รันทั้งตอนเบราว์เซอร์ของผู้ช่วยปิดและเปิด
ตัดสินแบบกำหนดแน่นอน (กฎล้วน ไม่มี LLM) · ผลเหมือนกันทุกเครื่อง · ไม่มีตัวเลขเวลา
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aipc.browser.control import NEEDS_PAGE
from aipc.skills import browse, command
from aipc.ui.handsfree import route

DATA = Path(__file__).resolve().parents[3] / "tests" / "data"
SETS = ("browse_v1.json", "browse_heard_dev.json")  # ชุดพัฒนาของ 0024 · ไม่ใช้ V2/V4/H (ชุดทดสอบ)
# ตารางทดสอบสด 20 ข้อ (docs/runbooks/0026-pi-trial-2000.md · เขียนก่อนทดสอบ)
# + ข้อ 21–22 ของการ์ด 0027 หัวข้อ 8
LIVE = (
    "ค้นหาราคาทองวันนี้", "เข้าลิงก์แรก", "ย้อนกลับ", "เปิดผลลัพธ์ที่สาม", "เลื่อนลง", "เลื่อนขึ้นหน่อย",
    "โหลดหน้านี้ใหม่", "ไปข้างหน้า", "ช่วยหาร้านกาแฟแถวนี้ให้หน่อย", "เปิดยูทูบ", "ปิดแท็บนี้",
    "กลับไปหน้าผู้ช่วย", "ขอดูอันที่สองหน่อย", "เข้ากูเกิลหน่อย", "สภาพอากาศเชียงใหม่ ค้นให้หน่อย",
    "ตอนนี้กี่โมงแล้ว", "เตือนกินยาพรุ่งนี้แปดโมง", "หาแว่นไม่เจอ วางไว้ไหนนะ", "ปิดเสียงหน่อย",
    "ย้อนกลับไปเรื่องเมื่อกี้ที่คุยกัน", "เปิดเบราว์เซอร์", "เลื่อนลง",
)  # fmt: skip
EXECUTES = {"browser", "open_browser", "command"}  # ทางที่ทำอะไรกับเครื่อง/เบราว์เซอร์


def old_route(text: str, running: bool) -> str:
    cmds = browse.parse(text)
    if cmds and (running or not all(c.kind in NEEDS_PAGE for c in cmds)):
        return "browser"
    return "command" if command.parse(text) else "chat"


def judge(old: str, new: str) -> str:
    """same · intended (ตั้งใจเปลี่ยนตามการ์ด) · new_action (เดิมไม่ทำ ตอนนี้ทำ = อันตราย) ·
    lost (เดิมทำ ตอนนี้ไม่ทำ) · changed (อื่น ๆ)."""
    if old == new:
        return "same"
    if old == "chat" and new in ("unknown", "needs_browser"):
        return "intended"
    if old == "command" and new == "open_browser":
        return "intended"
    if new in EXECUTES and old not in EXECUTES:
        return "new_action"
    if old in EXECUTES and new not in EXECUTES:
        return "lost"
    return "changed"


def sentences() -> list[tuple[str, str]]:
    rows = []
    for name in SETS:
        for item in json.loads((DATA / name).read_text(encoding="utf-8"))["items"]:
            rows.append((name, item["text"]))
    rows += [("live-22", t) for t in LIVE]
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True, help="ไฟล์ค่าดิบ JSON")
    args = ap.parse_args()
    out = []
    for src, text in sentences():
        for running in (False, True):
            old, new = old_route(text, running), route(text, running)
            out.append({"set": src, "text": text, "browser_running": running,
                        "old": old, "new": new, "judge": judge(old, new)})  # fmt: skip
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    to_ai = sum(r["new"] == "chat" for r in out)
    counts = {k: sum(r["judge"] == k for r in out) for k in
              ("same", "intended", "new_action", "lost", "changed")}  # fmt: skip
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"ประโยค {len(out) // 2} × เบราว์เซอร์ปิด/เปิด = {len(out)} กรณี")
    print(f"เกณฑ์ 2 · ไปทาง AI ในเครื่อง (แชท): {to_ai}")
    print("เกณฑ์ 3 · เทียบแอปเดิม: " + " · ".join(f"{k} {v}" for k, v in counts.items()))
    for r in out:
        if r["judge"] != "same":
            on = "เปิด" if r["browser_running"] else "ปิด"
            where = f"{r['set']} · เบราว์เซอร์{on}"
            print(f"  [{r['judge']}] ({where}) {r['text']}: {r['old']} → {r['new']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
