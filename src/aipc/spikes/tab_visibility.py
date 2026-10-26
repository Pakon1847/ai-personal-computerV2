"""T0 ของการ์ด 0065: Chromium บน Pi บอกได้ไหมว่าแท็บไหนอยู่หน้าสุด (document.visibilityState).

รันบน Pi 5 ในเซสชันที่มีจอ (ต้องมี WAYLAND_DISPLAY) · โปรไฟล์ชั่วคราว ไม่แตะโปรไฟล์ของผู้ใช้ ·
เปิด 2 แท็บ → สลับด้วย Target.activateTarget 5 ครั้ง → ถามทุกแท็บว่ามองเห็นไหม · ถูก = แท็บที่สลับไปตอบ visible
และแท็บอื่นตอบ hidden · เกณฑ์ (ประกาศในการ์ดก่อนรัน): ถูก 5/5 = ใช้วิธีนี้
"""

import json
import tempfile
import time
from pathlib import Path

from aipc.browser.control import BrowserControl


def visibility(ctl: BrowserControl, target: str) -> str:
    session = ctl._cdp.call("Target.attachToTarget", {"targetId": target, "flatten": True})[
        "sessionId"
    ]
    r = ctl._cdp.call(
        "Runtime.evaluate",
        {"expression": "document.visibilityState", "returnByValue": True},
        session=session,
    )
    return r.get("result", {}).get("value", "")


def main(rounds: int = 5) -> dict:
    with tempfile.TemporaryDirectory(prefix="aipc-t0-") as tmp:
        ctl = BrowserControl(profile=Path(tmp) / "profile")
        ctl._start("data:text/html,<title>A</title>A")
        first = ctl._cdp.call("Target.getTargets")["targetInfos"]
        a = next(t["targetId"] for t in first if t["type"] == "page")
        b = ctl._cdp.call("Target.createTarget", {"url": "data:text/html,<title>B</title>B"})[
            "targetId"
        ]
        time.sleep(1.0)
        rows = []
        for i in range(rounds):
            front, back = (a, b) if i % 2 == 0 else (b, a)
            ctl._cdp.call("Target.activateTarget", {"targetId": front})
            time.sleep(0.8)
            seen = {"front": visibility(ctl, front), "back": visibility(ctl, back)}
            rows.append({**seen, "ok": seen == {"front": "visible", "back": "hidden"}})
        ctl.close()
    return {"correct": sum(r["ok"] for r in rows), "total": rounds, "rows": rows}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
