"""วัดตัวค้นไฟล์ด้วยเนื้อหา (tests/data/file_search_*.json) · Recall@1 / Recall@3 · เวลา.

python -m aipc.spikes.file_search_eval tests/data/file_search_dev.json [--method index|words]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path


def words_rank(docs: list[dict], query: str) -> list[str]:
    """แบบง่ายสำหรับเทียบ: นับ n-gram ตัวอักษร 3 ตัวที่ตรง (ไม่ถ่วงน้ำหนัก)."""
    q = re.sub(r"\s+", "", query)
    qg = {q[i : i + 3] for i in range(len(q) - 2)}
    scored = []
    for d in docs:
        t = re.sub(r"\s+", "", d["name"] + d["text"])
        tg = {t[i : i + 3] for i in range(len(t) - 2)}
        scored.append((-len(qg & tg), d["name"]))
    return [n for _, n in sorted(scored)]


def evaluate(data: dict, method: str) -> dict:
    from aipc.files_search import Index

    docs = data["docs"]
    t0 = time.monotonic()
    index = Index([(d["name"], d["text"]) for d in docs]) if method != "words" else None
    build_s = time.monotonic() - t0
    rows, times = [], []
    for q in data["queries"]:
        t0 = time.monotonic()
        ranked = (
            [h.name for h in index.search(q["text"], 30)] if index else words_rank(docs, q["text"])
        )
        times.append(time.monotonic() - t0)
        rank = ranked.index(q["doc"]) + 1 if q["doc"] in ranked else None
        rows.append({**q, "rank": rank, "top3": ranked[:3]})
    n = len(rows)
    r1 = sum(r["rank"] == 1 for r in rows)
    r3 = sum(r["rank"] is not None and r["rank"] <= 3 for r in rows)
    return {"method": method, "n": n, "recall_at_1": r1, "recall_at_3": r3,
            "build_s": round(build_s, 4), "query_ms_max": round(max(times) * 1000, 2),
            "rows": rows}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.spikes.file_search_eval")
    ap.add_argument("dataset", type=Path)
    ap.add_argument("--method", default="index", choices=("index", "words"))
    ap.add_argument("--show", action="store_true", help="แสดงข้อที่พลาด (ห้ามใช้กับชุดอิสระก่อนวัด)")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    res = evaluate(json.loads(a.dataset.read_text(encoding="utf-8")), a.method)
    n = res["n"]
    r1, r3 = res["recall_at_1"], res["recall_at_3"]
    print(f"{a.dataset.name} [{a.method}]: R@1 {r1}/{n} · R@3 {r3}/{n}"
          f" · สร้างดัชนี {res['build_s']} วิ · ค้นช้าสุด {res['query_ms_max']} ms")  # fmt: skip
    if a.show:
        for r in res["rows"]:
            if r["rank"] != 1:
                print(f"  #{r['rank']} {r['doc']:22} | {r['text']} | {r['top3']}")
    if a.out:
        a.out.write_text(
            json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
