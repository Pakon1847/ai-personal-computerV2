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
from aipc.ui.handsfree import UNKNOWN, route

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


def install_store(folder: Path):
    """ติดตั้งสกิล .md ทุกไฟล์ผ่านประตูตรวจจริงลงโฟลเดอร์ชั่วคราว → (UserSkills, รายการที่ไม่ผ่าน)."""
    import tempfile

    from aipc.skills import manifest, userskills

    store = userskills.UserSkills(Path(tempfile.mkdtemp(prefix="voice-skills-")))
    builtin, rejected = manifest.load_builtin(), []
    for f in sorted(folder.glob("*.md")):
        try:
            store.install(f.read_text(encoding="utf-8"), builtin + store.load(), request="")
        except manifest.InvalidSkill as e:
            rejected.append(f"{f.name}: {e.errors[0] if e.errors else e}")
    return store, rejected


def app_answers(store, create: bool = False):
    """การ์ด 0029: ตัวคุมสกิลตัวจริง (ตัวสั่งเครื่องจำลอง · home ว่าง).

    คืน (ฟังก์ชันจัดประเภททาง unknown, รายการคำสั่งที่ถูกสั่ง, ตัวคุม)
    """
    import tempfile

    from PySide6.QtCore import QCoreApplication

    from aipc.skills import actions
    from aipc.ui.backend import SkillsController

    QCoreApplication.instance() or QCoreApplication([])
    calls: list = []
    tmp = Path(tempfile.mkdtemp(prefix="voice-answers-"))
    s = SkillsController(executor=actions.Executor(runner=lambda a: calls.append(a) or 0,
                                                   dry_run=False),
                         reminders_path=tmp / "r.json", run_timer=False, llm_ready=lambda: True,
                         user_skills=store)  # fmt: skip
    (tmp / "home").mkdir()
    s._home = tmp / "home"
    if create:  # การ์ด 0030: Claude ปลอมที่จดทุกครั้งที่ถูกเรียก (ต้องไม่ถูกเรียกเลย เพราะไม่มีใครตอบ "ใช่")
        s._forge = lambda request, **kw: calls.append(("claude", request))
        s._claude_on = lambda: True

    def classify(text: str) -> str:
        if card := s.voiceAnswer(text):
            gate = ":confirm" if card.get("confirmToken") else ""
            return f"answer:{card.get('kind', '')}{gate}"
        if card := s.voiceConfirm(text):
            return "confirm_skill:" + s._pending[card["confirmToken"]][1].id
        if create and (card := s.voiceCreate(text)):
            info = f"create_info:{card.get('kind', '')}"
            return "create_ask" if card.get("confirmToken") else info
        return UNKNOWN

    return classify, calls, s


def install_skills(folder: Path) -> tuple[list, list[str]]:
    """การ์ด 0028: สกิลที่ติดตั้งผ่านประตูตรวจจริง (ไม่ผ่านประตู = ไม่ใช้ เหมือนในแอป)."""
    store, rejected = install_store(folder)
    return store.load(), rejected


def main() -> int:
    from aipc.skills import router

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True, help="ไฟล์ค่าดิบ JSON")
    ap.add_argument("--skills", type=Path, help="การ์ด 0028: โฟลเดอร์สกิล .md ที่ติดตั้งก่อนตัดสินทาง")
    ap.add_argument("--baseline", type=Path, help="การ์ด 0028: ผล 0027 (routes.json) ไว้เทียบ")
    ap.add_argument("--create", action="store_true", help="การ์ด 0030: ทางขอสร้างสกิล (คู่ --answers)")
    ap.add_argument("--answers", action="store_true",
                    help="การ์ด 0029: ตอบด้วยโค้ด + การ์ดยืนยันสกิล (คู่กับ --skills)")  # fmt: skip
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    skill, extra, classify, calls = None, {}, None, []
    if args.skills:
        store, rejected = install_store(args.skills)
        installed = store.load()
        if args.answers:
            classify, calls, _ = app_answers(store, create=args.create)
        voice = [m for m in installed if m.steps and m.worker == "code"]  # เหมือน SkillsController

        def skill(text: str) -> str:
            m = router.repeat_of(text, voice)
            return m.id if m else ""

        # ประโยคของสกิลเอง: โค้ดล้วนต้องเป็น "skill" ทุกประโยค · สกิลที่ใช้ AI ต้องไม่เป็น
        own = [{"skill": m.id, "worker": m.worker, "text": t, "way": route(t, False, skill)}
               for m in installed for t in m.examples]  # fmt: skip
        extra = {"installed": [f"{m.id} ({m.worker})" for m in installed], "rejected": rejected,
                 "own_phrases": own}  # fmt: skip
        n = f"ติดตั้งผ่านประตู {len(installed)} ตัว (สั่งด้วยเสียงได้ {len(voice)})"
        print(f"{n} · ไม่ผ่าน {len(rejected)}")
        for r in rejected:
            print("  ไม่ผ่านประตู:", r)
        ok = sum((o["way"] == "skill") == (o["worker"] == "code") for o in own)
        print(f"ประโยคของสกิลเอง: ไปทางถูก {ok}/{len(own)} (โค้ดล้วน = skill · ใช้ AI = ไม่ใช่ skill)")
    out = []
    for src, text in sentences():
        for running in (False, True):
            old, new = old_route(text, running), route(text, running, skill)
            if classify is not None and new == UNKNOWN:
                new = classify(text)
            out.append({"set": src, "text": text, "browser_running": running,
                        "old": old, "new": new, "judge": judge(old, new)})  # fmt: skip
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"cases": out, **extra} if extra else out, ensure_ascii=False,
                                   indent=1), encoding="utf-8")  # fmt: skip
    if args.baseline:
        base = json.loads(args.baseline.read_text(encoding="utf-8"))
        base = base["cases"] if isinstance(base, dict) else base
        key = {(b["set"], b["text"], b["browser_running"]): b["new"] for b in base}
        diff = [r for r in out if key.get((r["set"], r["text"], r["browser_running"])) != r["new"]]
        print(f"ต่างจากผลเทียบ ({args.baseline}): {len(diff)} กรณี")
        for r in diff:
            was = key.get((r["set"], r["text"], r["browser_running"]))
            print(f"  ต่าง: {r['text']} ({r['browser_running']}): {was} → {r['new']}")
    if args.answers:
        print(f"การ์ด 0029: คำสั่งเครื่องที่ถูกสั่งโดยไม่ได้ยืนยัน {len(calls)} ครั้ง"
              + (" (รวมการเรียก Claude ของการ์ด 0030)" if args.create else ""))  # fmt: skip
    to_ai = sum(r["new"] == "chat" for r in out)
    counts = {k: sum(r["judge"] == k for r in out) for k in
              ("same", "intended", "new_action", "lost", "changed")}  # fmt: skip
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
