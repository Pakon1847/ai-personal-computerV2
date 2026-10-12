"""การ์ด 0024 เกณฑ์ข้อ 3–4: 12 ขั้นกับ Chromium จริง + เว็บจริง · ตรวจจาก URL / scrollY / สถานะหน้าต่างจริง.

รันบน Pi ในเซสชัน Wayland (หรือ labwc แบบไม่มีจอ): python -m aipc.spikes.browser_e2e [รอบ] [ผล.json]
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

from aipc.browser.control import BrowserControl
from aipc.skills.browse import parse


def host(url: str) -> str:
    return (urlsplit(url).hostname or "").removeprefix("www.")


def listening_ports() -> str:
    out = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True).stdout
    return "\n".join(line for line in out.splitlines() if "chrom" in line)


def one_round(b: BrowserControl) -> list[dict]:
    rows, state = [], {}

    def step(name, text, check):
        t0 = time.monotonic()
        cmds = parse(text)
        res = [b.run(c) for c in cmds]
        took = round(time.monotonic() - t0, 2)
        r = res[-1] if res else None
        try:
            ok, detail = check(r)
        except Exception as e:  # noqa: BLE001 · ตัวตรวจล้ม = ข้อนี้ไม่ผ่าน
            ok, detail = False, f"ตรวจไม่ได้: {e}"
        rows.append({"step": name, "text": text, "cmds": [c.as_dict() for c in cmds],
                     "say": r.say if r else "", "url": r.url if r else "", "ok": ok,
                     "detail": detail, "seconds": took})  # fmt: skip
        print(
            f"{'✓' if ok else '✗'} {name:10} {took:5.1f}s · {r.say if r else '-'} · {detail}",
            flush=True,
        )

    def searched(r):
        state["search"] = b._url()
        links = b.links()
        state["links"] = [x["href"] for x in links]
        is_search = (
            host(state["search"]) in ("google.com", "bing.com") and "/search" in state["search"]
        )
        return is_search and len(links) >= 3, f"{host(state['search'])} · ลิงก์ {len(links)}"

    def opened(i):
        def check(r):
            # ลิงก์ของ Bing ผ่านตัวพาไป (bing.com/ck/a) · ตรวจว่าออกจากหน้าค้นหาไปเว็บอื่นจริง
            # และลิงก์ที่ 2 ไม่ใช่หน้าเดียวกับลิงก์ที่ 1
            url = b._url()
            state[f"open{i}"] = url
            left = host(url) not in ("google.com", "bing.com", "duckduckgo.com")
            new = i == 1 or url != state.get("open1")
            return left and new, f"{host(url)} · {url[:60]}"

        return check

    def at(key):
        return lambda r: (b._url() == state[key], b._url()[:70])

    def scrolled(direction):
        def check(r):
            y = b._eval("scrollY")
            prev = state.get("y", 0)
            state["y"] = y
            return (y > prev) if direction == "down" else (y < prev), f"scrollY {prev}→{y}"

        return check

    def closed(r):
        return not b.running, f"running={b.running}"

    def minimized(r):
        win = b._cdp.call("Browser.getWindowForTarget", {"targetId": b._target})
        st = b._cdp.call("Browser.getWindowBounds", {"windowId": win["windowId"]})["bounds"]
        return st.get("windowState") == "minimized", st.get("windowState")

    step("ค้นหา", "ค้นหาราคาทองหน่อย", searched)
    step("ลิงก์1", "เข้าลิงก์แรก", opened(1))
    step("ย้อน", "ย้อนกลับ", at("search"))
    step("ลิงก์2", "เข้าลิงก์ที่สอง", opened(2))
    step("ย้อน", "ย้อนกลับ", at("search"))
    step("หน้า", "ไปข้างหน้า", at("open2"))
    step("โหลดใหม่", "โหลดใหม่", at("open2"))
    state["y"] = b._eval("scrollY") or 0
    step("เลื่อนลง", "เลื่อนลง", scrolled("down"))
    step("เลื่อนขึ้น", "เลื่อนขึ้น", scrolled("up"))
    step("ปิดแท็บ", "ปิดแท็บ", closed)
    step("ค้นใหม่", "ค้นหาวิธีทำไข่เจียว", searched)
    ports = listening_ports()
    rows.append({"step": "พอร์ต", "ok": ports == "", "detail": ports or "ไม่มีพอร์ตที่ Chromium ฟัง"})
    print(f"{'✓' if ports == '' else '✗'} พอร์ต TCP ของ Chromium: {ports or 'ไม่มี'}", flush=True)
    step("กลับแอป", "กลับไปแอป", minimized)
    return rows


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    rounds = int(argv[0]) if argv else 3
    out = {"rounds": []}
    for i in range(rounds):
        print(f"--- รอบ {i + 1}", flush=True)
        b = BrowserControl(profile=Path(tempfile.mkdtemp(prefix="aipc-browser-")))
        try:
            rows = one_round(b)
        finally:
            b.close()
        out["rounds"].append(rows)
        print(f"รอบ {i + 1}: ผ่าน {sum(r['ok'] for r in rows)}/{len(rows)}", flush=True)
    if len(argv) > 1:
        Path(argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
