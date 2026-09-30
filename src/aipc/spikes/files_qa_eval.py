"""วัดถาม AI ในเครื่องเกี่ยวกับไฟล์ (ฟีเจอร์ข้อ 4) บน Pi 5 · ข้อความ/prompt ชุดเดียวกับแอป.

    python -m aipc.spikes.files_qa_eval --server http://127.0.0.1:18080 \
        --out docs/benchmarks/2026-10-01-files-qa/gemma4-e2b.json

ชุด tests/data/files_qa.json (Claude เขียน · commit ก่อนวัด) · ตัดสินอัตโนมัติตามที่ชุดประกาศไว้
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import date
from pathlib import Path

from aipc import files_qa
from aipc.chat import client
from aipc.cloud.ask import local_gave_up
from aipc.skills import catalog

REPO = Path(__file__).resolve().parents[3]
DATASET = REPO / "tests" / "data" / "files_qa.json"
NOT_IN_FILE = (
    "ไม่มีข้อมูล",
    "ไม่ได้ระบุ",
    "ไม่พบ",
    "ไม่ได้กล่าวถึง",
    "ไม่มีในเอกสาร",
    "ไม่มีการระบุ",
    "ไม่ได้บอก",
    "ไม่ปรากฏ",
    "ไม่ได้ให้ข้อมูล",
    "ไม่มีรายละเอียด",
)


def judge(q: dict, text: str) -> bool:
    t = text.replace(" ", "").lower()
    if q["expect"] == "not_in_file":
        return any(w in text for w in NOT_IN_FILE) or local_gave_up(text)
    return any(m.replace(" ", "").lower() in t for m in q.get("must_any", []))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--server", required=True)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    target = client.Target(url=a.server)
    system = catalog.system_prompt(date.today(), model="gemma-4-E2B-it-Q4_K_M")
    rows = []
    for doc in data["docs"]:
        for q in doc["questions"]:
            content = files_qa.build_message(doc["name"], doc["text"], q["q"])
            msgs = [{"role": "system", "content": system}, {"role": "user", "content": content}]
            first: list[float] = []
            t0 = time.monotonic()

            def on_token(tok, t0=t0, first=first):
                if not first:
                    first.append(time.monotonic() - t0)

            r = client.Stream(target, msgs).run(on_token)
            ok = judge(q, r.text)
            rows.append(
                {
                    "doc": doc["id"],
                    **q,
                    "reply": r.text,
                    "ok": ok,
                    "reason": r.reason,
                    "ttft": round(first[0], 1) if first else None,
                    "seconds": round(time.monotonic() - t0, 1),
                    "chars_sent": len(content),
                }
            )
            mark = "✓" if ok else "✗"
            print(f"{mark} {doc['id']} {q['expect']:11} ttft {rows[-1]['ttft']} · {q['q'][:40]}")
            print("     ", " ".join(r.text.split())[:150])
    by = {e: [r for r in rows if r["expect"] == e] for e in ("answer", "summary", "not_in_file")}
    ttfts = [r["ttft"] for r in rows if r["ttft"] is not None]
    summary = {k: [sum(r["ok"] for r in v), len(v)] for k, v in by.items()}
    summary["ttft_median"] = statistics.median(ttfts) if ttfts else None
    c = data["criteria"]
    ok = (
        summary["answer"][0] / summary["answer"][1] >= c["answer_min"]
        and summary["not_in_file"][0] >= c["not_in_file_min"]
        and (summary["ttft_median"] or 1e9) <= c["ttft_median_max_s"]
    )
    print(json.dumps(summary, ensure_ascii=False), "→", "ผ่าน" if ok else "ไม่ผ่าน")
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(
            json.dumps(
                {"summary": summary, "passed": ok, "rows": rows}, ensure_ascii=False, indent=1
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
