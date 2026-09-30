"""วัดความเร็วพิมพ์คำตอบ: llama-server ปกติ เทียบ speculative decoding แบบ n-gram (ไม่ต้องมีโมเดลร่าง).

    python -m aipc.spikes.spec_bench --label none --server http://127.0.0.1:18080 --out
    docs/benchmarks/2026-10-01-spec-pi5/none.json

ชุดคำถาม (เลือกก่อนวัด): ชุดสอบจบ E01–E12 (งานภาษา: แปล สรุป เขียน) + A01–A05 (ความรู้)
· temperature 0 (greedy)
เพื่อเทียบความเร็วได้ตรง และคำตอบของ speculative ต้องเหมือนแบบปกติทุกตัวอักษร (Leviathan et al. 2023)
เกณฑ์รับไปใช้ (ประกาศก่อนวัด): token/วิ มัธยฐานเร็วขึ้น ≥ 1.2 เท่า และคำตอบเหมือนเดิม ≥ 16/17
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

from aipc.skills import catalog

REPO = Path(__file__).resolve().parents[3]
IDS = [f"E{i:02d}" for i in range(1, 13)] + [f"A{i:02d}" for i in range(1, 6)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--label", required=True)
    ap.add_argument("--server", required=True)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    items = {
        i["id"]: i
        for i in json.loads((REPO / "tests/data/exam_questions.json").read_text(encoding="utf-8"))[
            "items"
        ]
    }
    system = catalog.system_prompt(date(2026, 10, 1))
    rows = []
    for iid in IDS:
        q = items[iid]["q"]
        body = {
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": q}],
            "stream": False,
            "cache_prompt": True,
            "temperature": 0,
            "max_tokens": 200,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        req = urllib.request.Request(
            a.server.rstrip("/") + "/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        t0 = time.monotonic()
        data = json.loads(urllib.request.urlopen(req, timeout=900).read())
        tm = data.get("timings", {})
        text = data["choices"][0]["message"].get("content") or ""
        rows.append(
            {
                "id": iid,
                "q": q,
                "text": text,
                "seconds": round(time.monotonic() - t0, 2),
                "gen_n": tm.get("predicted_n"),
                "gen_tps": tm.get("predicted_per_second"),
                "draft_n": tm.get("draft_n"),
                "draft_accepted": tm.get("draft_n_accepted"),
            }
        )
        print(
            f"{iid} {tm.get('predicted_n')} tok {tm.get('predicted_per_second', 0):.2f} tok/s "
            f"draft {tm.get('draft_n')}/{tm.get('draft_n_accepted')}"
        )
    tps = [r["gen_tps"] for r in rows if r["gen_tps"] and (r["gen_n"] or 0) >= 20]
    summary = {
        "label": a.label,
        "gen_tps_median": round(statistics.median(tps), 2) if tps else None,
        "n": len(tps),
    }
    print(json.dumps(summary, ensure_ascii=False))
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(
            json.dumps({**summary, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
