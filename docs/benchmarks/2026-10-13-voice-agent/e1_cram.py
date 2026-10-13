"""E1: -cram (แคชใน RAM) คืนแคชของ prompt เก่าให้เองไหม เมื่อมีคำขอ prefix อื่นคั่น (-np 1)."""
import http.client, json, sys, time
sys.path.insert(0, "src")
from aipc.browser import agent

def ask(msgs, max_tokens=1, **extra):
    body = {"messages": msgs, "stream": False, "cache_prompt": True, "max_tokens": max_tokens,
            "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}, **extra}
    c = http.client.HTTPConnection("127.0.0.1", 18080, timeout=900)
    t0 = time.monotonic()
    c.request("POST", "/v1/chat/completions", json.dumps(body), {"Content-Type": "application/json"})
    d = json.loads(c.getresponse().read())
    t = d.get("timings", {})
    return t.get("prompt_n"), round(t.get("prompt_ms", 0) / 1000, 1), round(time.monotonic() - t0, 1)

chat_sys = ("คุณคือผู้ช่วย AI ในเครื่องของผู้ใช้ชาวไทย ตอบสุภาพ กระชับ " * 1) + "\n".join(
    f"สกิลที่ {i}: ทำงานเกี่ยวกับเรื่องที่ {i} เช่น นัดหมาย เตือนความจำ เปิดเว็บ ปรับเสียง สรุปไฟล์ แปลภาษา" for i in range(40))
chat = [{"role": "system", "content": chat_sys}, {"role": "user", "content": "สวัสดีครับ"}]
web = agent.Turn("ย้อนกลับ").messages({"title": "YouTube", "url": "https://www.youtube.com/", "items": [], "text": ""})
print("chat cold      ", ask(chat))
print("chat again     ", ask(chat + [{"role": "assistant", "content": "สวัสดีครับ"}, {"role": "user", "content": "วันนี้วันอะไร"}]))
print("web (other)    ", ask(web))
print("chat after web ", ask(chat + [{"role": "assistant", "content": "สวัสดีครับ"}, {"role": "user", "content": "พรุ่งนี้วันอะไร"}]))
