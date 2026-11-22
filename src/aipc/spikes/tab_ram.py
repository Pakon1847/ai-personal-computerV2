"""การ์ด 0065 หัวข้อ 7: RAM ของเบราว์เซอร์ของผู้ช่วยตอนเปิด 1 แท็บ กับ 3 แท็บ (ใช้ตั้งเพดาน MAX_TABS).

    WAYLAND_DISPLAY=… python -m aipc.spikes.tab_ram --rounds 3 --out ผล.json

วิธี (ประกาศในการ์ดก่อนรัน 2026-10-27): ตัวคุมเบราว์เซอร์ตัวจริง (BrowserControl) · โปรไฟล์ชั่วคราว ไม่เข้าสู่ระบบ ·
1 แท็บ = "เปิดยูทูบ" · 3 แท็บ = + "เปิดวิกิพีเดีย" + "เปิดข่าวไทยพีบีเอส" (เปิดเป็นแท็บใหม่ตามการ์ด 0065) ·
รอหน้านิ่ง SETTLE_S วิ แล้วรวม PSS ของโปรเซส Chromium ทุกตัวที่สคริปต์นี้เปิด (/proc/<pid>/smaps_rollup) ·
จด MemAvailable ของเครื่องก่อน/หลังด้วย · ไม่ใช่เกณฑ์ผ่าน/ไม่ผ่าน
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

from aipc.browser.control import BrowserControl
from aipc.skills.browse import BrowseCommand

SETTLE_S = 15
PROC = Path("/proc")


def children_map() -> dict[int, list[int]]:
    kids: dict[int, list[int]] = {}
    for d in PROC.iterdir():
        if not d.name.isdigit():
            continue
        try:
            ppid = int((d / "stat").read_text().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        kids.setdefault(ppid, []).append(int(d.name))
    return kids


def tree(root: int) -> list[int]:
    kids, out, todo = children_map(), [], [root]
    while todo:
        pid = todo.pop()
        out.append(pid)
        todo.extend(kids.get(pid, []))
    return out


def pss_mb(root: int) -> float:
    total = 0
    for pid in tree(root):
        try:
            for line in (PROC / str(pid) / "smaps_rollup").read_text().splitlines():
                if line.startswith("Pss:"):
                    total += int(line.split()[1])
        except OSError:
            continue
    return round(total / 1024, 1)


def mem_available_mb() -> float:
    for line in (PROC / "meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return round(int(line.split()[1]) / 1024, 1)
    return 0.0


def one_round() -> dict:
    with tempfile.TemporaryDirectory(prefix="aipc-tabram-") as tmp:
        before = mem_available_mb()
        ctl = BrowserControl(profile=Path(tmp) / "profile")
        r1 = ctl.run(BrowseCommand("site", site="youtube"))
        time.sleep(SETTLE_S)
        root = ctl._proc.pid
        one = {"pss_mb": pss_mb(root), "tabs": len(ctl._pages()), "say": r1.say}
        says = [ctl.run(BrowseCommand("site", site=s)).say for s in ("wikipedia", "news")]
        time.sleep(SETTLE_S)
        three = {"pss_mb": pss_mb(root), "tabs": len(ctl._pages()), "say": says,
                 "urls": [p.get("url", "") for p in ctl._pages()]}  # fmt: skip
        after = mem_available_mb()
        ctl.close()
    return {"mem_available_before_mb": before, "mem_available_3tabs_mb": after,
            "one_tab": one, "three_tabs": three}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    rows = []
    for i in range(a.rounds):
        rows.append(one_round())
        print(json.dumps({"round": i + 1, **rows[-1]}, ensure_ascii=False), flush=True)
        time.sleep(5)
    one = [r["one_tab"]["pss_mb"] for r in rows]
    three = [r["three_tabs"]["pss_mb"] for r in rows]
    m1, m3 = statistics.median(one), statistics.median(three)
    summary = {"rounds": len(rows), "one_tab_median_mb": m1, "three_tabs_median_mb": m3,
               "per_extra_tab_mb": round((m3 - m1) / 2, 1), "settle_s": SETTLE_S}  # fmt: skip
    a.out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1)
                     + "\n", encoding="utf-8")  # fmt: skip
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
