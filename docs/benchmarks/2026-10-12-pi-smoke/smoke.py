"""สำรวจหาบั๊ก (ไม่ใช่ชุดวัดผล) · โค้ดแอปจริง + AI ในเครื่องจริงบน Pi · Claude ปลอม (จดว่าถูกส่ง)."""
import json, os, sys, tempfile, time
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from aipc.cloud.ask import CloudReply
from aipc.spikes.app_driver import AppDriver
from aipc.ui import app as uiapp

work = Path(tempfile.mkdtemp(prefix="smoke-"))
home = work / "home"; (home / "Documents").mkdir(parents=True)
(home / "Documents" / "รายงานประจำสัปดาห์.txt").write_text("รายงานความคืบหน้าโปรเจกต์ AI PC สัปดาห์ที่ 3", encoding="utf-8")
(home / "Documents" / "thesis-ch1.md").write_text("# บทที่ 1 บทนำ\nความเป็นมาของปัญหา", encoding="utf-8")
asked = []
def cloud(q, h):
    asked.append(q)
    return CloudReply(True, text="[Claude ปลอม] คำตอบจาก Claude", cost_usd=0.0)
d = AppDriver("http://127.0.0.1:18080", cloud=cloud, workdir=work)
d.skills._home = home
d.skills._weather = uiapp._weather()
print("ready", d.wait_ready(300), flush=True)
cases = [l.rstrip("\n") for l in open(sys.argv[1], encoding="utf-8") if l.strip() and not l.startswith("#")]
out = []
for q in cases:
    q = q.replace("\n", "\n")
    n = len(asked)
    try:
        t = d.say(q, timeout=300)
        r = {"q": q, "route": t.route, "text": t.text, "note": t.note, "local": t.local_text, "tool": t.local_tool,
             "fwd": t.forwarded, "plans": t.plans, "s": t.seconds,
             "cards": [{k: c.get(k) for k in ("kind", "title", "lines", "chips") if c.get(k)} for c in t.cards]}
    except Exception as e:
        import traceback; r = {"q": q, "route": "CRASH", "text": traceback.format_exc()}
    r["cloud_q"] = asked[n:]
    out.append(r)
    print(json.dumps(r, ensure_ascii=False)[:600], flush=True)
json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
d.close()
