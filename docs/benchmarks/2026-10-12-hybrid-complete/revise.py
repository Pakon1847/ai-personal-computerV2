"""ข้อ 11 (pi5-hybrid-check): สกิลที่ Claude สร้าง → ใช้ซ้ำ → กด "ไม่ใช่แบบนี้" → พิมพ์คำติ.
หน้าจอเต็มแบบไม่มีจอ · AI ในเครื่องจริง (AIPC_LLM_URL) · Claude ปลอม (คืนสกิลตายตัว + จดคำขอ)."""
import os, sys, tempfile, time
from pathlib import Path
tmp = Path(tempfile.mkdtemp(prefix="rev-"))
home = tmp / "home"; home.mkdir()
os.environ.update(QT_QPA_PLATFORM="offscreen", XDG_DATA_HOME=str(tmp / "data"), HOME=str(home), AIPC_CLOUD="0")
from PySide6.QtCore import QEventLoop, QObject, QTimer
from aipc.skills import forge as forge_mod
from aipc.skills.userskills import UserSkills
from aipc.ui import app as uiapp
from aipc.spikes.app_driver import RecExecutor

MD = """---
id: music-mode
name: โหมดฟังเพลง
description: เปิดยูทูบแล้วปรับเสียงเป็น 60 ไว้ฟังเพลง
keywords: โหมดฟังเพลง, สกิลโหมดฟังเพลง
examples:
  - อยากได้สกิลโหมดฟังเพลง เปิดยูทูบแล้วปรับเสียงเป็น 60
  - เปิดโหมดฟังเพลง
  - ขอโหมดฟังเพลงหน่อย
permissions: run_actions
worker: code
version: 1.0
author: Claude (ปลอม)
created: 2026-10-13
request: {req}
---
# โหมดฟังเพลง

## ขั้นตอน
1. เปิดเว็บ youtube
2. ปรับเสียง 60
{extra}3. บอก: เปิดโหมดฟังเพลงแล้ว
"""
calls = []
def forge(request, skills=None, revise=None, check=None, **kw):
    calls.append((request, revise[1] if revise else None))
    extra = "2.5 เปิดเว็บ gmail\n" if revise else ""
    md = MD.format(req=request, extra=extra).replace("2.5 เปิดเว็บ gmail\n3.", "3. เปิดเว็บ gmail\n4.")
    errs = check(md) if check else []
    return forge_mod.Proposal(not errs, request, skill_md=md, skill_id="music-mode", errors=list(errs or []))

def items_of(page):
    v = page.property("items"); return v.toVariant() if hasattr(v, "toVariant") else v
def settle(ms=200):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()

opts = uiapp.Options(screen="shell", page="workspace", software=True, settings_path=tmp / "ui.json")
app, engine, warnings = uiapp.build(opts)
win = engine.rootObjects()[0]; win.resize(1280, 800)
ctx = engine.rootContext()
chat, skills = ctx.contextProperty("chat"), ctx.contextProperty("skills")
skills._exec = rec = RecExecutor()
skills._forge = forge
if skills._user is None: skills._user = UserSkills()
skills._claude_on = lambda: True
chat._claude_on = lambda: True
page = [o for o in win.findChildren(QObject) if o.objectName() == "workspace"][0]
t0 = time.time()
while not chat.ready and time.time() - t0 < 300: settle(500)
print("ready", chat.ready, "canForge", skills.canForge, flush=True)
out = Path(sys.argv[1]); out.mkdir(exist_ok=True)

def wait():
    t1 = time.time(); settle(300)
    while (chat.busy or skills._forging) and time.time() - t1 < 300: settle(300)
    settle(400)
def show(n, label):
    items = items_of(page)
    for it in items[-3:]:
        c = it.get("card") or {}
        print(f"   {'U' if it.get('user') else 'A'}: {(it.get('text') or c.get('title') or '')[:90]!r}"
              f" kind={c.get('kind')} badge={ {k: v for k, v in (c.get('badge') or {}).items() if k in ('name','forgedId')} } tok={bool(c.get('confirmToken'))}")
    rows = [r for r in win.findChildren(QObject) if r.objectName() == "forgedRow" and r.property("visible")]
    print(f"{n:02d} {label} · ปุ่ม 'ไม่ใช่แบบนี้' ที่เห็น={len(rows)} · forge={calls} · plans={rec.plans}", flush=True)
    win.grabWindow().save(str(out / f"{n:02d}.png"))
def yes():
    items = items_of(page)
    tok = next((it["card"]["confirmToken"] for it in reversed(items) if it.get("card") and it["card"].get("confirmToken")), "")
    print("   กดใช่", bool(tok)); page.answer(tok, True) if tok else None

REQ = "อยากได้สกิลโหมดฟังเพลง เปิดยูทูบแล้วปรับเสียงเป็น 60"
page.sendText(REQ); wait(); show(1, "ข้อ 9 ขอสร้าง")
yes(); wait(); show(2, "ข้อ 9 กดใช่")
page.sendText(REQ); wait(); show(3, "ข้อ 10 พิมพ์ซ้ำ")
items = items_of(page)
c = next((it["card"] for it in reversed(items) if it.get("card") and (it["card"].get("badge") or {}).get("forgedId")), None)
print("   การ์ดที่มี forgedId:", c and c.get("title"))
if c and c.get("confirmToken"):
    yes(); wait(); show(4, "ข้อ 10 กดใช่")
    items = items_of(page)
    c = next((it["card"] for it in reversed(items) if it.get("card") and (it["card"].get("badge") or {}).get("forgedId")), c)
if c:
    page.setProperty("feedbackFor", {"id": c["badge"]["forgedId"], "name": c["badge"]["name"]})  # = onWrongSkill
    print("   placeholder:", [o.property("placeholderText") for o in win.findChildren(QObject) if o.objectName() == "chatInput"])
page.sendText("ขอเปิด Gmail ด้วย"); wait(); show(5, "ข้อ 11 คำติ")
print("plans", rec.plans)
