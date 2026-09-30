"""แชท 1 ครั้งผ่าน AI ของผู้ใช้ (socket) ด้วย prompt + รายการสกิลของแอป · พิมพ์ ok/fail + เวลา (T11 soak)."""

import json
import os
import random
import time
from datetime import date

from aipc.chat import client
from aipc.skills import catalog, manifest

QUESTIONS = ["ทำไมท้องฟ้าถึงเป็นสีฟ้า", "แนะนำวิธีนอนหลับให้ดีขึ้น", "สรุปข้อดีของการออกกำลังกายสั้น ๆ",
             "อธิบาย AI แบบเด็กเข้าใจ", "1 ปีมีกี่วัน", "เล่าเรื่องสั้นเกี่ยวกับแมว 3 ประโยค"]  # fmt: skip
t = client.Target(sock=f"/run/user/{os.getuid()}/aipc/llm.sock")
system = catalog.system_prompt(date.today(), model="gemma-4-E2B-it-Q4_K_M") + catalog.TOOLS_HINT
tools = catalog.tools(manifest.load_builtin(), {"llm"})
client.warm(t, system, tools)
msgs = [{"role": "system", "content": system}, {"role": "user", "content": random.choice(QUESTIONS)}]
tokens: list[str] = []
t0 = time.monotonic()
r = client.Stream(t, msgs, tools=tools).run(tokens.append)
ok = not r.reason and (r.text or r.tool_call)
print(json.dumps({"ok": bool(ok), "s": round(time.monotonic() - t0, 1), "reason": r.reason,
                  "chars": len(r.text), "tool": r.tool_call}, ensure_ascii=False))  # fmt: skip
