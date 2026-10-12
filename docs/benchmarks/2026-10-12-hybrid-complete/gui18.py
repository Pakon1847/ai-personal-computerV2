"""ลองแอปทั้งหน้าจอแบบไม่มีจอ (สำรวจหาบั๊ก): พิมพ์ → Enter → รอ → กด "ใช่" (ถ้ามี) → ถ่ายภาพ.
AI ในเครื่องจริง (AIPC_LLM_URL) · คำสั่งเครื่องจด ไม่ทำจริง · home/ข้อมูลชั่วคราว."""
import json, os, sys, tempfile, time
from pathlib import Path
tmp = Path(tempfile.mkdtemp(prefix="gui-"))
home = tmp / "home"; (home / "Documents").mkdir(parents=True)
(home / "Documents" / "ใบเสร็จค่าซ่อมแอร์.txt").write_text("ใบเสร็จร้านแอร์เย็นฉ่ำ\nค่าล้างแอร์ 600 บาท\nค่าเติมน้ำยา 1,000 บาท\nรวม 1,600 บาท", encoding="utf-8")
os.environ.update(QT_QPA_PLATFORM="offscreen", XDG_DATA_HOME=str(tmp / "data"))
if os.environ.get("GUI_REAL_CLOUD") != "1": os.environ.update(HOME=str(home), AIPC_CLOUD="0")
from PySide6.QtCore import QEventLoop, QObject, QTimer, qInstallMessageHandler
msgs = []
qInstallMessageHandler(lambda mode, ctx, m: msgs.append(m))
from aipc.ui import app as uiapp
from aipc.spikes.app_driver import RecExecutor
def items_of(page):
    v = page.property("items")
    return v.toVariant() if hasattr(v, "toVariant") else v
def settle(ms=200):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()
opts = uiapp.Options(screen="shell", page="workspace", software=True, settings_path=tmp / "ui.json")
app, engine, warnings = uiapp.build(opts)
win = engine.rootObjects()[0]; win.resize(1280, 800)
ctx = engine.rootContext()
chat, skills = ctx.contextProperty("chat"), ctx.contextProperty("skills")
skills._exec = rec = RecExecutor()
skills._home = home
page = [o for o in win.findChildren(QObject) if o.objectName() == "workspace"][0]
t0 = time.time()
while not chat.ready and time.time() - t0 < 300: settle(500)
print("ready", chat.ready, flush=True)
out = Path(sys.argv[2]); out.mkdir(exist_ok=True)
steps = [l.rstrip("\n") for l in open(sys.argv[1], encoding="utf-8") if l.strip() and not l.startswith("#")]
for n, step in enumerate(steps, 1):
    msgs.clear()
    if step.startswith("!yes") or step.startswith("!no"):
        items = items_of(page)
        tok = next((it["card"]["confirmToken"] for it in reversed(items) if it.get("card") and it["card"].get("confirmToken")), "")
        page.answer(tok, step.startswith("!yes")) if tok else print("  ไม่มีปุ่มให้กด")
    elif step.startswith("!attach "):
        f = step[8:]
        print("  attach:", repr(chat.attachFile(f if f.startswith("/") else str(home / f))))
    elif step.startswith("!undo"):
        items = items_of(page)
        tok = next((it["card"]["undoToken"] for it in reversed(items) if it.get("card") and it["card"].get("undoToken")), "")
        page.showCard(skills.undo(tok)) if tok else print("  ไม่มีปุ่มย้อน")
    elif step.startswith("!claude "):
        ctx.contextProperty("uiSettings").setUseClaude(step.endswith("on")) if hasattr(ctx.contextProperty("uiSettings"), "setUseClaude") else print("  no setUseClaude")
    elif step.startswith("!wait "):
        due = []
        skills.reminderDue.connect(lambda r: due.append(dict(r)))
        t2 = time.time()
        while not due and time.time() - t2 < float(step[6:]): settle(500)
        print("  due:", due, f"{time.time()-t2:.0f}s")
    elif step.startswith("!open "):
        h = chat.history
        h = h.toVariant() if hasattr(h, "toVariant") else h
        print("  history:", [(x.get("title"), x.get("id")) for x in h][:5])
        idx = int(step[6:])
        page.loadChat(chat.openChat(h[idx]["id"]))
    elif step.startswith("!new"):
        chat.newChat(False); page.setProperty("items", [])
    else:
        page.sendText(step)
    t1 = time.time(); settle(300)
    while (chat.busy or getattr(skills, "_forging", False)) and time.time() - t1 < 300: settle(300)
    settle(400)
    items = items_of(page)
    last = items[-1] if items else {}
    show = last.get("text") or (last.get("card") or {}).get("title")
    lst = [o for o in win.findChildren(QObject) if o.objectName() == "chatList"]; lst = lst[0] if lst else None; print("   atYEnd", lst and lst.property("atYEnd"), lst and round(lst.property("contentY")), lst and round(lst.property("contentHeight")))
    print(f"{n:02d} {step[:40]!r} → {time.time()-t1:.1f}s · {str(show)[:150]!r}", flush=True)
    for m in msgs: print("   QT:", m[:200])
    win.grabWindow().save(str(out / f"{n:02d}.png"))
    if os.environ.get("GUI_REAL_CLOUD") == "1": print("   trace:", {k: v for k, v in chat._trace.items() if k != "t0"})
print("plans", rec.plans)
