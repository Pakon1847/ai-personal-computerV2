"""E3: อ่านหน้าไว้ก่อน [sys][page] → คำสั่งสั้น [sys][cmd] คั่น → [sys][page][task] ต้องอ่านใหม่กี่ token.
แบบ same = system เดียวกันทั้งสองขั้น · แบบ diff = system คนละข้อความ · และลอง max_tokens 0."""
import http.client, json, sys, time
sys.path.insert(0, "src")
from aipc.browser import agent

def ask(msgs, max_tokens=1):
    body = {"messages": msgs, "stream": False, "cache_prompt": True, "max_tokens": max_tokens,
            "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}}
    c = http.client.HTTPConnection("127.0.0.1", 18080, timeout=900)
    t0 = time.monotonic()
    c.request("POST", "/v1/chat/completions", json.dumps(body), {"Content-Type": "application/json"})
    r = c.getresponse(); d = json.loads(r.read())
    t = d.get("timings", {})
    return r.status, t.get("prompt_n"), round(t.get("prompt_ms", 0) / 1000, 1), round(time.monotonic() - t0, 1)

obs = json.load(open(sys.argv[1], encoding="utf-8"))
page = agent.page_text(obs["goldtraders"])
SYS_B = "You read a web page for a Thai user and pick what to do. " * 6
SYS_A_same = SYS_B
SYS_A_diff = "You plan browser actions for a Thai user from a short command. " * 6
for name, sys_a in (("same", SYS_A_same), ("diff", SYS_A_diff)):
    tag = f" ({name} {time.time():.0f})"  # ทำให้ prompt ใหม่ทุกแบบ ไม่ติดแคชของแบบก่อน
    sb = SYS_B + tag
    sa = (sys_a + tag) if name == "diff" else sb
    print(name, "preread  ", ask([{"role": "system", "content": sb}, {"role": "user", "content": page}]))
    print(name, "cmd A    ", ask([{"role": "system", "content": sa}, {"role": "user", "content": "หน้าเว็บ: Homepage · goldtraders\nคำสั่ง: ย้อนกลับ"}]))
    print(name, "task B   ", ask([{"role": "system", "content": sb}, {"role": "user", "content": page + "\nงาน: ราคาทองแท่งขายออกเท่าไหร่"}]))
print("max_tokens0", ask([{"role": "system", "content": "x" + SYS_B}, {"role": "user", "content": "สวัสดี"}], max_tokens=0))
