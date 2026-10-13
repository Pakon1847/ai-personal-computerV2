"""วัดก่อนสร้าง (การ์ด 0025): Gemma บน Pi 5 อ่านหน้าเว็บจริงแล้วเลือกการกระทำได้เร็วแค่ไหน.

ขั้น 1 (--capture out.json): เปิดหน้าเว็บจริงด้วย BrowserControl แล้วเก็บสิ่งที่ AI จะเห็น (OBSERVE_JS)
ขั้น 2 (--ask obs.json --url http://127.0.0.1:18080): ส่งคำสั่งตัวอย่าง × หน้าเว็บ ให้ AI
· บันทึก token/เวลา/คำตอบ
"""

from __future__ import annotations

import argparse
import http.client
import json
import time
from urllib.parse import quote_plus, urlparse

from aipc.browser import agent

DDG = "https://duckduckgo.com/?kl=th-th&q="
PAGES = [
    ("ddg-gold", DDG + quote_plus("ราคาทองวันนี้")),
    ("ddg-egg", DDG + quote_plus("วิธีทำไข่เจียว")),
    ("ddg-weather", DDG + quote_plus("พยากรณ์อากาศเชียงใหม่")),
    ("wiki-th", "https://th.wikipedia.org/wiki/กรุงเทพมหานคร"),
    ("wiki-th-mid", "https://th.wikipedia.org/wiki/กรุงเทพมหานคร#scroll"),
    ("youtube", "https://www.youtube.com/"),
    ("youtube-results", "https://www.youtube.com/results?search_query=" + quote_plus("เพลงลูกทุ่ง")),
    ("goldtraders", "https://www.goldtraders.or.th/"),
    ("news", "https://www.thairath.co.th/news/local"),
    ("form", "https://httpbin.org/forms/post"),
    ("pantip", "https://pantip.com/"),
]

COMMANDS = {
    "blank": ["ค้นหาราคาทองหน่อย", "เปิดยูทูบ", "พรุ่งนี้มีนัดอะไรบ้าง"],
    "ddg-gold": ["เข้าลิงก์แรก", "ราคาทองวันนี้เท่าไหร่", "ย้อนกลับ", "เลื่อนลง"],
    "ddg-egg": ["เข้าลิงก์ที่สอง", "ค้นหาวิธีทำต้มยำแทน"],
    "wiki-th": ["กรุงเทพมีประชากรเท่าไหร่", "เลื่อนลงอีก"],
    "youtube": ["ค้นหาเพลงลูกทุ่งในยูทูบ", "กลับไปแอป"],
}


def capture(out: str) -> None:
    from aipc.browser.control import BrowserControl

    bc = BrowserControl(load_timeout=15)
    bc._start("about:blank")
    obs = {"blank": {}}
    for name, url in PAGES:
        t0 = time.monotonic()
        bc._go(url.replace("#scroll", ""))
        time.sleep(1.5)
        if url.endswith("#scroll"):
            bc._eval("window.scrollBy(0, innerHeight * 2.4)")
            time.sleep(0.8)
        o = bc._eval(agent.OBSERVE_JS)
        if o is None:
            print(name, "OBSERVE_JS ล้ม", flush=True)
            continue
        o["_load_s"] = round(time.monotonic() - t0, 2)
        obs[name] = o
        print(name, o["url"][:80], len(o["items"]), "items", len(o["text"]), "chars", flush=True)
    bc.close()
    json.dump(obs, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def ask(url: str, messages: list[dict], max_tokens: int = 120) -> dict:
    u = urlparse(url)
    body = {
        "messages": messages,
        "stream": False,
        "cache_prompt": True,
        "max_tokens": max_tokens,
        "temperature": 0,
        "chat_template_kwargs": {"enable_thinking": False},
        "json_schema": agent.ACTION_SCHEMA,
    }
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=600)
    t0 = time.monotonic()
    conn.request("POST", "/v1/chat/completions", body=json.dumps(body),
                 headers={"Content-Type": "application/json"})  # fmt: skip
    data = json.loads(conn.getresponse().read())
    conn.close()
    return {
        "wall_s": round(time.monotonic() - t0, 2),
        "content": data["choices"][0]["message"].get("content", ""),
        "timings": data.get("timings", {}),
    }


def run_ask(obs_path: str, url: str, out: str) -> None:
    obs = json.load(open(obs_path, encoding="utf-8"))
    rows = []
    for page, cmds in COMMANDS.items():
        for cmd in cmds:
            msgs = agent.Turn(cmd).messages(obs.get(page) or {})
            r = ask(url, msgs)
            t = r["timings"]
            rows.append({"page": page, "command": cmd, **r})
            print(
                f"{page:10} {cmd:28} prompt {t.get('prompt_n')} tok"
                f" {t.get('prompt_ms', 0) / 1000:.1f}s"
                f" · gen {t.get('predicted_n')} tok {t.get('predicted_ms', 0) / 1000:.1f}s"
                f" · wall {r['wall_s']}s → {r['content']}",
                flush=True,
            )
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture")
    ap.add_argument("--ask")
    ap.add_argument("--url", default="http://127.0.0.1:18080")
    ap.add_argument("--out", default="agent-speed.json")
    a = ap.parse_args()
    if a.capture:
        capture(a.capture)
    if a.ask:
        run_ask(a.ask, a.url, a.out)
