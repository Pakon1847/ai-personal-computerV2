import json, os, sys, tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from aipc.cloud.ask import CloudReply
from aipc.spikes.app_driver import AppDriver
H = json.load(open("/tmp/hist13.json", encoding="utf-8"))
asked = []
def cloud(q, h):
    asked.append(q); return CloudReply(True, text="[Claude ปลอม]", cost_usd=0.0)
d = AppDriver("http://127.0.0.1:18080", cloud=cloud, workdir=Path(tempfile.mkdtemp()))
print("ready", d.wait_ready(300), flush=True)
cases = [
    ("real6", H[:6]),       # ข่าว · ขอบคุณ · กีฬา (ตามที่ Pakon ทำ)
    ("none", []),
    ("first2", H[:4]),      # ข่าว + ขอบคุณ
]
qs = ["ญัตติไม่ไว้วางใจคืออะไร", "ญัญติไม่ไว้ใจคืออะไร", "ญัตติไม่ไว้วางใจคืออะไร อธิบายง่าย ๆ"]
for name, hist in cases:
    for q in qs:
        for rep in range(2):
            n = len(asked); t = d.say(q, history=hist)
            print(f"{name:7} {rep} {q:35} → {t.route:6} tool={t.local_tool or '-':10} fwd={t.forwarded[:30]!r} local={t.local_text[:80]!r}", flush=True)
d.close()
