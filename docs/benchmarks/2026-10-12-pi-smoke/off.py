import os, tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from aipc.cloud.ask import CloudReply
from aipc.skills import forge as forge_mod
from aipc.spikes.app_driver import AppDriver
asked = []
def cloud(q, h):
    asked.append(q); return CloudReply(True, text="[Claude ปลอม]", cost_usd=0.0)
def forge(req, **kw):
    asked.append("FORGE " + req); return forge_mod.Proposal(False, req, errors=["ปลอม"])
d = AppDriver("http://127.0.0.1:18080", cloud=cloud, forge=forge, workdir=Path(tempfile.mkdtemp()))
off = lambda: False
d.chat._claude_on = off; d.skills._claude_on = off
print("ready", d.wait_ready(120))
for q in ["ข่าววันนี้มีอะไรบ้าง", "ราคาทองวันนี้เท่าไหร่", "อยากได้สกิลโหมดฟังเพลง เปิดยูทูบแล้วปรับเสียงเป็น 60", "ตั้งโหมดอ่านหนังสือให้หน่อย", "สวัสดี"]:
    n = len(asked); t = d.say(q); c = t.cards[-1]
    print(q, "→", t.route, "|", (t.text or c.get("title") or "")[:160].replace("\n", " "), "| ส่งออก:", asked[n:])
d.close()
