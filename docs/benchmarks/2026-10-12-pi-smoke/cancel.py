import os, tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from aipc.spikes.app_driver import AppDriver
d = AppDriver("http://127.0.0.1:18080", workdir=Path(tempfile.mkdtemp()))
print("ready", d.wait_ready(120))
for q in ["พรุ่งนี้เช้า 9 โมงมีประชุม", "เตือนกินยาทุกวันตอน 8 โมงเช้า", "อยากดูไฟล์ของฉัน"]:
    t = d.say(q)
    c = t.cards[-1]
    print(q, "→", t.route, c.get("title"), c.get("lines"))
    if c.get("confirmToken") and c.get("kind") == "reminder":
        print("   confirm:", d.skills.confirm(c["confirmToken"], True)["title"])
for q in ["วันนี้ต้องทำอะไรบ้าง", "ยกเลิกนัดกินยา"]:
    t = d.say(q); c = t.cards[-1]; print(q, "→", t.route, c.get("title"), c.get("lines"))
print("   confirm:", d.skills.confirm(c["confirmToken"], True)["title"])
print("left:", [r.what for r in d.skills._store.items])
d.close()
