"""การ์ด 0057 Y1/Y2: "เปิด/ดู/เล่น X" ค้นถูกเว็บ + คำค้นถูกไหม · ไม่ใช่คำสั่งถูกค้นไหม (กฎล้วน · ไม่ต้องมีเบราว์เซอร์).

    python -m aipc.spikes.youtube_open_eval tests/data/youtube_open_dev.json [--out ผล.json]

แต่ละข้อ: {"text", "on": เว็บที่เปิดอยู่ ("" = ไม่มี), "expect": {"site", "query"} หรือ null (ไม่ใช่คำสั่งค้น)} ·
ลำดับเหมือนแอป: กฎคำสั่งเว็บ (browse.parse) ก่อน → ไม่มี = ค้นในเว็บที่เปิดอยู่ (browse.on_site_search) ·
ไม่รวมคำสั่งของสกิลประจำเว็บ (มาก่อนในแอป เช่น "เปิดซับ") → ข้อที่ชนสกิลให้เฉลยตามสกิล
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aipc.skills import browse


def searched(text: str, on: str) -> dict | None:
    cmds = browse.parse(text)
    if not cmds and on:
        one = browse.on_site_search(text, on)
        cmds = [one] if one else []
    for c in cmds:
        if c.kind in ("site_search", "search"):
            return {"site": c.site or "google", "query": c.query}
    return None


def same(a: str, b: str) -> bool:
    return a.replace(" ", "").lower() == b.replace(" ", "").lower()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    items = json.loads(a.dataset.read_text(encoding="utf-8"))["items"]
    rows = []
    for it in items:
        got, want = searched(it["text"], it.get("on", "")), it["expect"]
        if want is None:
            ok = got is None
        else:
            ok = bool(got) and got["site"] == want["site"] and same(got["query"], want["query"])
        rows.append({**it, "got": got, "ok": ok})
        print(f"{'✓' if ok else '✗'} [{it.get('on') or '-'}] {it['text']} → {got}")
    cmd = [r for r in rows if r["expect"] is not None]
    non = [r for r in rows if r["expect"] is None]
    summary = {"commands": len(cmd), "commands_ok": sum(r["ok"] for r in cmd),
               "non_commands": len(non),
               "non_command_searched": sum(not r["ok"] for r in non)}  # fmt: skip
    print(json.dumps(summary, ensure_ascii=False))
    if a.out:
        doc = json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1)
        a.out.write_text(doc, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
