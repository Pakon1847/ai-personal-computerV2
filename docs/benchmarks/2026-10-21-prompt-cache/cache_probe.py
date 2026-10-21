import json, http.client, os, sys
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtGui import QGuiApplication
app = QGuiApplication([])
from aipc.ui.backend import ChatController, SkillsController
from aipc.skills.userskills import UserSkills
from aipc.chat import client
skills_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
s = SkillsController(run_timer=False, llm_ready=lambda: True, user_skills=UserSkills(skills_dir) if skills_dir else None)
c = ChatController(active=False, target=client.Target(url="http://127.0.0.1:18080"), tools=lambda text="": s.tool_catalog(text))
texts = ["สวัสดีครับ", "ทำไมท้องฟ้าเป็นสีฟ้า", "ปั๊มหัวใจต้องกดลึกเท่าไหร่", "สวัสดีครับ", "เลือดกรุ๊ปโอให้ใครได้"]
for t in texts:
    tools = c._all_tools(t)
    body = {"messages": [{"role": "system", "content": c._system(tools, t)}, {"role": "user", "content": t}],
            "tools": tools, "tool_choice": "auto", "stream": False, "max_tokens": 1, "cache_prompt": True}
    conn = http.client.HTTPConnection("127.0.0.1", 18080, timeout=600)
    conn.request("POST", "/v1/chat/completions", body=json.dumps(body), headers={"Content-Type": "application/json"})
    tm = json.loads(conn.getresponse().read()).get("timings", {})
    names = [x["function"]["name"] for x in tools]
    print(t, "| tools", len(names), names[-5:], "| prompt_n", tm.get("prompt_n"), "cache_n", tm.get("cache_n"), "ms", round(tm.get("prompt_ms", 0)))
