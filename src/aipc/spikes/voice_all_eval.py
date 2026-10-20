"""วัดเกณฑ์ V1–V3 ของการ์ด 0042: คีย์ลัดเสียงใช้ได้กับทุกสกิล (ข้อความ · ไม่ผ่านตัวถอดเสียง).

    python -m aipc.spikes.voice_all_eval --set test --out <โฟลเดอร์ผล>/test.json
    python -m aipc.spikes.voice_all_eval --routes <ไฟล์ก่อนแก้>.json   # V3: เทียบเส้นทางชุดเดิมของ 0027

จำลองทางเดินเดียวกับ WorkspacePage.voiceCommand ด้วย backend จริง (คำสั่งเครื่อง = จำลอง ไม่ทำจริง ·
เบราว์เซอร์ = แค่แปลคำสั่ง ไม่เปิดเว็บ) · ตัดสินแบบกำหนดแน่นอน (กฎล้วน ไม่มี LLM) · ผลเหมือนกันทุกเครื่อง
ป้าย: browser:<kind>[:n|direction] · command · reminder · answer · llm:<id> · skill:<id> ·
near · create · none
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / "tests" / "data"
ACTS = ("browser:", "command")  # ทำอะไรกับเครื่อง/เบราว์เซอร์ทันที (V2 นับเฉพาะนี้)


def backend():
    tmp = tempfile.mkdtemp(prefix="aipc-voice-all-")
    for k in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR"):
        os.environ[k] = tmp
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["AIPC_CLOUD"] = "0"
    from aipc.skills import actions
    from aipc.ui import app as uiapp

    _, engine, _ = uiapp.build(uiapp.Options(screen="shell", software=True,
                                             settings_path=Path(tmp) / "ui.json"))  # fmt: skip
    skills = engine._backends["skills"]
    skills._exec = actions.Executor(dry_run=True)
    return engine, skills


def label(text: str, skills) -> str:
    """ทางเดียวกับ WorkspacePage.voiceCommand (ตอนเบราว์เซอร์ของผู้ช่วยเปิดอยู่)."""
    from aipc.skills import browse
    from aipc.ui import handsfree

    way = handsfree.route(text, True, skills.voiceSkill, skills.voiceIntent)
    if way == handsfree.BROWSER:
        c = browse.parse(text)[0]
        extra = (
            f":{c.n}"
            if c.kind == "open" and c.n
            else f":{c.direction}"
            if c.kind == "media"
            else ""
        )
        return f"browser:{c.kind}{extra}"
    if way == handsfree.COMMAND:
        card = skills.handle(text)
        return "reminder" if card.get("kind") == "reminder" else "command"
    if way == handsfree.SKILL:
        return "skill:" + skills.voiceSkill(text)
    if way == handsfree.REMINDER:
        return "reminder" if skills.voiceReminder(text).get("kind") == "reminder" else "reminder?"
    if way == handsfree.LLM_SKILL:
        return "llm:" + skills.voiceIntent(text)[4:]
    if way == handsfree.APP:
        return "app:" + handsfree.app_command(text)["kind"]
    if way == handsfree.UNKNOWN:
        if skills.voiceAnswer(text).get("kind") is not None:
            return "answer"
        near = skills.voiceConfirm(text)
        if near.get("confirmToken"):
            return "near:" + near["suggest"] if near.get("suggest") else "near"
        if skills.voiceCreate(text).get("kind") is not None:
            return "create"
        if skills.voiceAsk(text).get("confirmToken"):  # รอบ 3: ถามว่าส่งไปแชทไหม
            return "ask"
    return "none" if way == handsfree.UNKNOWN else way


def score(name: str, skills) -> dict:
    items = json.loads((DATA / f"voice_all_{name}.json").read_text(encoding="utf-8"))["items"]
    rows = [{**i, "got": label(i["text"], skills)} for i in items]
    cmd = [r for r in rows if r["expect"] not in ("none", "ask")]
    non = [r for r in rows if r["expect"] in ("none", "ask")]
    return {
        "set": name,
        "commands_correct": sum(r["got"] == r["expect"] for r in cmd),
        "commands_total": len(cmd),
        "noncommands_acted": sum(r["got"].startswith(ACTS) for r in non),
        "noncommands_total": len(non),
        "wrong": [r for r in rows if r["got"] != r["expect"]],
        "rows": rows,
    }


def routes(path: Path) -> dict:
    """V3: เส้นทางของชุด 0027 (routes.json) ตอนนี้ เทียบกับไฟล์ก่อนแก้."""
    from aipc.ui import handsfree

    _engine, skills = backend()  # ทางเดียวกับแอป: ส่ง voiceSkill + voiceIntent ด้วย
    old = json.loads(path.read_text(encoding="utf-8"))
    now = [{**r, "now": handsfree.route(r["text"], r["browser_running"], skills.voiceSkill,
                                        skills.voiceIntent)} for r in old]  # fmt: skip
    for r in now:  # ไปทางนัดแล้ว แต่โค้ดตอบเดิม (เลื่อน/ลบ/ถามนัด) ยังเป็นคนตอบ = ผลเหมือนเดิม
        r["same_card"] = r["now"] == handsfree.REMINDER and bool(skills.voiceAnswer(r["text"]))
    changed = [r for r in now if r["now"] != (r.get("before") or r.get("new"))]
    return {"total": len(now), "changed": changed}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=("dev", "test", "test2", "dev3", "test3"))
    ap.add_argument("--routes", type=Path, help="routes.json ของ 0027 หรือไฟล์ก่อนแก้ที่มีช่อง before")
    ap.add_argument("--snapshot", type=Path, help="เขียนเส้นทางตอนนี้ลงไฟล์ (ช่อง before) ไว้เทียบหลังแก้")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    if a.snapshot:
        from aipc.ui import handsfree

        src = (
            Path(__file__).resolve().parents[3]
            / "docs/benchmarks/2026-10-14-voice-command-mode/routes.json"
        )
        rows = json.loads(src.read_text(encoding="utf-8"))
        snap = [{"set": r["set"], "text": r["text"], "browser_running": r["browser_running"],
                 "before": handsfree.route(r["text"], r["browser_running"])}
                for r in rows]  # fmt: skip
        a.snapshot.write_text(
            json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        print(f"snapshot {len(snap)} rows → {a.snapshot}")
        return 0
    if a.routes:
        res = routes(a.routes)
        print(
            f"V3: {len(res['changed'])}/{res['total']} เปลี่ยนเส้นทาง · "
            f"ผลยังเหมือนเดิม (การ์ดที่โค้ดตอบ) {sum(r['same_card'] for r in res['changed'])}"
        )
        for r in res["changed"]:
            same = " (ผลเหมือนเดิม)" if r["same_card"] else ""
            was = r.get("before") or r.get("new")
            print(f"  {r['text']} (เปิดเบราว์เซอร์={r['browser_running']}): {was} → {r['now']}{same}")
        out = res
    else:
        _engine, skills = backend()
        out = score(a.set, skills)
        print(f"{a.set}: คำสั่งถูก {out['commands_correct']}/{out['commands_total']} · "
              f"ไม่ใช่คำสั่งแต่ทำ {out['noncommands_acted']}/{out['noncommands_total']}")  # fmt: skip
        for r in out["wrong"]:
            print(f"  ✗ {r['text']}: ต้องการ {r['expect']} ได้ {r['got']}")
    if a.out:
        a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
