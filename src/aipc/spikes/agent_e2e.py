"""งานจริงบน Pi (การ์ด 0025 เกณฑ์ข้อ 3 และ 4): ผู้ช่วยเว็บ + Chromium จริง + Gemma จริง · ตรวจผลจากหน้าเว็บ.

    WAYLAND_DISPLAY=wayland-0 PYTHONPATH=src python -m aipc.spikes.agent_e2e --out e2e.json

10 งานต่อกัน (เหมือนคนใช้จริง) · พักระหว่างงาน --pause วิ (คนดูหน้าเว็บ = ผู้ช่วยอ่านหน้าไว้ก่อน) ·
ตรวจจากของจริง: ที่อยู่เว็บ · ค่าในช่อง · ตัวเลือกที่ติ๊ก · ตัวเลขในคำตอบเทียบกับหน้า · สถานะหน้าต่าง
"""

from __future__ import annotations

import argparse
import json
import re
import time
from urllib.parse import unquote, urlsplit

from aipc.browser.agent import Agent, Llm
from aipc.browser.control import BrowserControl
from aipc.chat.client import Target

ENGINES = ("google.", "duckduckgo.com", "bing.com")


def host(url: str) -> str:
    return (urlsplit(url).hostname or "").removeprefix("www.")


def not_engine(url: str) -> bool:
    return bool(host(url)) and not any(e in host(url) for e in ENGINES)


def js(bc: BrowserControl, expr: str):
    with bc._lock:
        return bc._eval(expr)


def window_state(bc: BrowserControl) -> str:
    with bc._lock:
        win = bc._cdp.call("Browser.getWindowForTarget", {"targetId": bc._target})
        return bc._cdp.call("Browser.getWindowBounds", {"windowId": win["windowId"]})["bounds"].get(
            "windowState", ""
        )


def price_on_page(bc: BrowserControl) -> str:
    t = js(bc, "document.body.innerText") or ""
    m = re.search(r"ทองคำแท่ง[^0-9]{0,40}?รับซื้อ\s*([\d,]+\.\d\d)\s*ขายออก\s*([\d,]+\.\d\d)", t)
    return m[2] if m else ""


# (คำสั่ง, ชนิด, ตัวตรวจ(bc, out, memo) -> (ผ่านไหม, หลักฐาน))
TASKS = [
    ("ค้นหาราคาทองวันนี้แล้วเข้าลิงก์แรก", "plan",
     lambda bc, o, m: (not_engine(u := bc._url()), m.__setitem__("first", u) or u)),
    ("ย้อนกลับ", "plan",
     lambda bc, o, m: (any(e in host(u := bc._url()) for e in ENGINES), u)),
    ("เข้าลิงก์ที่สอง", "plan",
     lambda bc, o, m: (not_engine(u := bc._url()) and u != m.get("first"), u)),
    ("เปิดยูทูบแล้วหาเพลงคาราบาว", "plan",
     lambda bc, o, m: ("youtube.com/results" in (u := unquote(bc._url())) and "คาราบาว" in u, u)),
    ("เปิดคลิปแรก", "plan",
     lambda bc, o, m: ("youtube.com/watch" in (u := bc._url()), u)),
    ("เปิดเว็บ httpbin.org/forms/post แล้วใส่ชื่อว่าสมชาย", "plan+look",
     lambda bc, o, m: ("สมชาย" in (v := js(bc, "document.querySelector('[name=custname]').value")
                                   or ""), v)),
    ("เลือกพิซซ่าไซส์ใหญ่", "look",
     lambda bc, o, m: ((v := js(bc, "(document.querySelector('[name=size]:checked')||{}).value"))
                       == "large", v)),
    ("ใส่เบอร์โทร 0812345678", "look",
     lambda bc, o, m: ((v := js(bc, "document.querySelector('[name=custtel]').value")) ==
                       "0812345678", v)),
    ("เปิดเว็บสมาคมค้าทองคำแล้วบอกราคาทองแท่งขายออก", "plan+look",
     lambda bc, o, m: (bool(p := price_on_page(bc)) and p.replace(",", "")[:5]
                       in o.say.replace(",", ""), f"หน้า {p} · ตอบ {o.say}")),
    ("กลับไปแอป", "plan",
     lambda bc, o, m: ((s := window_state(bc)) == "minimized", s)),
]  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:18080")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--pause", type=float, default=20.0)
    ap.add_argument("--out", default="agent-e2e.json")
    a = ap.parse_args()
    rows = []
    for rnd in range(1, a.rounds + 1):
        bc = BrowserControl(load_timeout=15)
        agent = Agent(bc, Llm(Target(url=a.url), timeout=600))
        memo: dict = {}
        for i, (cmd, kind, check) in enumerate(TASKS, 1):
            pre = dict(done=agent.pre.done_chars) if agent.pre else {}
            t0 = time.monotonic()
            out = agent.run(cmd)
            secs = round(time.monotonic() - t0, 2)
            try:
                ok, evidence = check(bc, out, memo)
            except Exception as e:  # noqa: BLE001 · ตรวจไม่ได้ = ไม่ผ่าน
                ok, evidence = False, f"ตรวจไม่ได้: {e}"
            looks = [t for t in out.trace if t.get("stage") == "look"]
            row = {"round": rnd, "n": i, "command": cmd, "kind": kind, "ok": bool(ok),
                   "evidence": str(evidence)[:200], "say": out.say, "seconds": secs,
                   "plan": out.plan, "steps": out.steps, "cloud": out.cloud,
                   "preread_used": [t.get("preread") for t in looks],
                   "trace": out.trace, "preread_before": pre}  # fmt: skip
            rows.append(row)
            print(f"{'✓' if ok else '✗'} r{rnd} {i:2} {cmd[:40]:40} {secs:6}s → {out.plan} · "
                  f"{' ; '.join(out.steps)[:60]} · {str(evidence)[:60]}", flush=True)  # fmt: skip
            time.sleep(a.pause)
        bc.close()
    ok = sum(r["ok"] for r in rows)
    print(f"รวม {ok}/{len(rows)}", flush=True)
    json.dump({"pause_s": a.pause, "rows": rows}, open(a.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)  # fmt: skip


if __name__ == "__main__":
    main()
