"""รวมค่าจาก Pi 5 (run_stage1.sh) เป็น speed.json ให้ summarize.py · 2026-10-30

    python scripts/bench/collect_pi.py > docs/benchmarks/2026-10-29-llm-compare/speed.json

ต่อ label: tg = tok/s ตอนตอบ (llama-bench median 5 รอบ) · ttft = เวลาเริ่มตอบ median 9 ข้อชุดพัฒนา ·
vmhwm_mb = RAM สูงสุดของ llama-server (VmHWM) · ค่าประกอบ: pp · ค่า min · อุณหภูมิ/throttled ก่อน-หลัง
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RAW = Path(__file__).resolve().parents[2] / "docs" / "benchmarks" / "2026-10-29-llm-compare" / "raw"


def main() -> int:
    out = {}
    for log in sorted(RAW.glob("*.log")):
        label = log.stem
        if label.endswith("-server"):
            continue
        bench = RAW / f"2026-10-30-pi5-llm-{label}-t3.json"
        ttft = RAW / f"{label}-ttft-dev.json"
        if not (bench.exists() and ttft.exists()):
            continue
        m = json.loads(bench.read_text(encoding="utf-8"))["summary_metrics"]
        t = json.loads(ttft.read_text(encoding="utf-8"))
        text = log.read_text(encoding="utf-8")
        hwm = re.search(r"server-VmHWM: (\d+) kB", text)
        states = re.findall(r"^(\S+) \S+ temp=([\d.]+) throttled=(0x[0-9a-f]+)", text, re.M)
        out[label] = {
            "tg": round(m["tg_tok_s"]["median"], 2),
            "tg_min": round(m["tg_tok_s"]["minimum"], 2),
            "pp": round(m["pp_tok_s"]["median"], 1),
            "ttft": t["summary"]["ttft_median"],
            "ttft_max": max(r["ttft"] or 0 for r in t["rows"]),
            "vmhwm_mb": round(int(hwm.group(1)) / 1024) if hwm else None,
            "bench_rss_mb": round(m["peak_rss_mb"]["median"]),
            "states": {s: f"{c}°C {th}" for s, c, th in states},
        }
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
