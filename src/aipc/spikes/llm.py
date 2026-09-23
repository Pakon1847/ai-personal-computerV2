"""Spike 0.7: วัด LLM บน Pi 5 ด้วย llama-bench เพื่อตัดสิน ADR-007 (โมเดลค่าเริ่มต้น).

llama-bench คือโปรแกรมวัดความเร็วที่มากับ llama.cpp วัดสองช่วงแยกกัน:
- pp (prompt processing หรือ prefill) = ช่วงที่โมเดล "อ่าน" prompt ก่อนตอบคำแรก
- tg (text generation) = ช่วงที่โมเดล "พิมพ์" คำตอบทีละ token

BRIEF 5.4 เน้นว่าคอขวดจริงคือ pp ไม่ใช่ tg เพราะผู้ใช้รอเงียบ ๆ จนกว่า pp จะเสร็จ
เลยต้องรายงานสองค่านี้แยกกันเสมอ

สองโหมด:
1. วัดซ้ำ (ค่าเริ่มต้น): รัน llama-bench ทีละ 1 รอบ ผ่าน aipc.bench.runner
   → ได้ median/p95 และกติกาเดียวกับการวัดอื่นทั้งหมด
2. soak (--soak-minutes 10): รันต่อเนื่องตามเวลาที่ตั้ง บันทึก tok/s กับอุณหภูมิทุกรอบ
   → เห็นว่าพอเครื่องร้อนแล้วช้าลงไหม (BRIEF 5.4 "หลังตอบต่อเนื่อง 10 นาที")

**ต้องตรวจกับของจริงก่อนเชื่อผล:** ชื่อฟิลด์ใน JSON ของ llama-bench (`n_prompt`, `n_gen`,
`avg_ts`) มาจากความรู้ของผู้เขียน ยังไม่ได้เทียบกับ llama.cpp รุ่นที่ติดตั้งบน Pi
ถ้าไม่ตรง ตัวแปลงจะหยุดพร้อมบอกว่าเจอฟิลด์อะไรบ้าง — ไม่เดาค่าให้
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import date
from pathlib import Path

from aipc.bench import machine, runner
from aipc.bench.__main__ import parse_meta

REPO = Path(__file__).resolve().parents[3]

# เกณฑ์ผ่านของ BRIEF 5.4: เวลาถึงคำแรกสำหรับ prompt 200 token (ค่าเสนอ ยืนยันหลัง spike)
TTFT_TARGET_S = {"1b": 5.0, "3-4b": 10.0}


def peak_child_rss_mb() -> float | None:
    """หน่วยความจำสูงสุดที่โปรเซสลูก (llama-bench) เคยใช้ อ่านจากเคอร์เนล.

    ค่านี้สะสม — เป็นค่าสูงสุดของทุกโปรเซสลูกตั้งแต่เริ่ม จึงไม่ลดลงระหว่างรอบ
    ใช้ได้เพราะเราวัดทีละโมเดลต่อหนึ่งคำสั่ง · บนวินโดวส์ไม่มีโมดูล resource → None
    """
    try:
        import resource
    except ImportError:
        return None
    return resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024  # Linux ให้หน่วย kB


def parse_llama_bench_json(text: str) -> dict[str, float]:
    """แปลงผล `llama-bench -o json` เป็น {pp_tok_s, tg_tok_s, prefill_s, ...}.

    ในผลมีหลายแถว แถว pp คือแถวที่ n_prompt > 0 และ n_gen = 0 ส่วนแถว tg กลับกัน
    """
    try:
        rows = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"ผลของ llama-bench ไม่ใช่ JSON: {e}") from e
    if isinstance(rows, dict):
        rows = [rows]
    out: dict[str, float] = {}
    for row in rows:
        missing = {"n_prompt", "n_gen", "avg_ts"} - row.keys()
        if missing:
            raise ValueError(
                f"ไม่เจอฟิลด์ {sorted(missing)} ในผลของ llama-bench — ฟิลด์ที่มี: {sorted(row)}"
            )
        n_prompt, n_gen, ts = int(row["n_prompt"]), int(row["n_gen"]), float(row["avg_ts"])
        if n_prompt > 0 and n_gen == 0:
            out["pp_tok_s"] = ts
            # เวลา prefill ≈ จำนวน token ÷ ความเร็ว · เป็นค่าประมาณของ "เวลาถึงคำแรก"
            # (ไม่รวมเวลาตัดคำและเวลาสร้าง token แรก) ค่าจริงแบบ end-to-end วัดผ่าน llama-server ในเฟส 1
            out["prefill_s"] = n_prompt / ts
        elif n_gen > 0 and n_prompt == 0:
            out["tg_tok_s"] = ts
    if not out:
        raise ValueError("ผลของ llama-bench ไม่มีแถว pp หรือ tg เลย")
    rss = peak_child_rss_mb()
    if rss is not None:
        out["peak_rss_mb"] = rss
    return out


def bench_args(bench: str, model: str, threads: int, prompt: int, gen: int) -> list[str]:
    """คำสั่ง llama-bench หนึ่งรอบ · -r 1 = ให้ llama-bench วัดแค่รอบเดียว
    เพราะการวัดซ้ำและสถิติเป็นหน้าที่ของ aipc.bench ซึ่งเก็บค่าดิบทุกรอบไว้
    """
    return [bench, "-m", model, "-t", str(threads), "-p", str(prompt), "-n", str(gen),
            "-r", "1", "-o", "json"]  # fmt: skip


def soak(
    args: list[str],
    minutes: float,
    out_csv: Path,
    run=runner.command_task,
    clock=time.monotonic,
    temp=machine.cpu_temp_c,
    throttled=machine.throttled_raw,
) -> list[dict]:
    """รัน tg ต่อเนื่องจนครบเวลา แล้วบันทึกทุกรอบ.

    ใช้ time.monotonic ไม่ใช่นาฬิกาปกติ เพราะนาฬิกาปกติเปลี่ยนได้ (เช่น NTP ปรับเวลา)
    แต่ monotonic เดินหน้าอย่างเดียว เหมาะกับการนับเวลาที่ผ่านไป
    """
    if out_csv.exists():
        raise FileExistsError(f"{out_csv} มีอยู่แล้ว — ห้ามเขียนทับ")
    task = run(args, parse_llama_bench_json)
    start = clock()
    rows = []
    while clock() - start < minutes * 60:
        metrics = task() or {}
        rows.append(
            {
                "elapsed_s": round(clock() - start, 1),
                "tg_tok_s": metrics.get("tg_tok_s"),
                "temp_c": temp(),
                "throttled": throttled(),
            }
        )
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["elapsed_s", "tg_tok_s", "temp_c", "throttled"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def soak_summary(rows: list[dict]) -> str:
    speeds = [r["tg_tok_s"] for r in rows if r["tg_tok_s"] is not None]
    temps = [r["temp_c"] for r in rows if r["temp_c"] is not None]
    throttled_rows = [r["elapsed_s"] for r in rows if r["throttled"] and r["throttled"] & 0xF]
    lines = [f"รอบทั้งหมด {len(rows)}"]
    if speeds:
        drop = (speeds[0] - speeds[-1]) / speeds[0] * 100 if speeds[0] else 0
        lines.append(
            f"tg tok/s รอบแรก {speeds[0]:.2f} → รอบสุดท้าย {speeds[-1]:.2f} (ลดลง {drop:.1f}%)"
        )
    if temps:
        lines.append(f"อุณหภูมิสูงสุด {max(temps):.1f} °C")
    lines.append(
        f"throttle ระหว่าง soak ที่วินาที {throttled_rows}" if throttled_rows else "ไม่ throttle"
    )
    return "\n".join(f"- {line}" for line in lines)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="python -m aipc.spikes.llm")
    p.add_argument("--bench", required=True, help="path ของ llama-bench")
    p.add_argument("--model", required=True, help="ไฟล์ .gguf")
    p.add_argument("--label", required=True, help="ชื่อสั้นของโมเดล เช่น gemma3-1b-q4km")
    p.add_argument("--size", choices=sorted(TTFT_TARGET_S), required=True, help="ชั้นโมเดล")
    p.add_argument("--threads", type=int, default=4)
    p.add_argument(
        "--prompt", type=int, default=200, help="จำนวน token ของ prompt (BRIEF 5.4: 200)"
    )
    p.add_argument("--gen", type=int, default=64)
    p.add_argument("--runs", type=int, default=runner.MIN_RUNS)
    p.add_argument("--soak-minutes", type=float, default=0, help="> 0 = โหมด soak")
    p.add_argument("--meta", action="append", default=[], help="key=value เช่น llama_cpp=<commit>")
    p.add_argument("--out", type=Path, default=REPO / "docs" / "benchmarks")
    a = p.parse_args(argv)

    info = machine.collect(repo=REPO)
    name = f"{date.today().isoformat()}-{info.board_class}-llm-{a.label}-t{a.threads}"

    if a.soak_minutes > 0:
        args = bench_args(a.bench, a.model, a.threads, 0, 128)  # tg อย่างเดียว
        rows = soak(args, a.soak_minutes, a.out / f"{name}-soak.csv")
        print(soak_summary(rows))
        return 0

    args = bench_args(a.bench, a.model, a.threads, a.prompt, a.gen)
    records = runner.measure(
        runner.command_task(args, parse_llama_bench_json), warmup=runner.MIN_WARMUP, runs=a.runs
    )
    meta = {"threads": str(a.threads), "prompt_tokens": str(a.prompt), "gen_tokens": str(a.gen),
            "size_class": a.size, "ttft_target_s": str(TTFT_TARGET_S[a.size]),
            **parse_meta(a.meta)}  # fmt: skip
    files = {a.model: runner.sha256_file(Path(a.model))}
    paths = runner.write_report(a.out, name, info, records, info.throttled, meta, files, args)

    prefill = [r.metrics["prefill_s"] for r in records if r.phase == "measured"]
    worst = max(prefill)
    target = TTFT_TARGET_S[a.size]
    print(paths["md"].read_text(encoding="utf-8"))
    print(
        f"เกณฑ์ BRIEF 5.4 (prefill {a.prompt} token ≤ {target} วิ, ใช้รอบที่แย่สุด): "
        f"{worst:.2f} วิ → {'ผ่าน' if worst <= target else 'ไม่ผ่าน'}"
        + ("" if info.board_class == "pi5" else " (ไม่ใช่ Pi 5 — ใช้ตัดสิน ADR-007 ไม่ได้)")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
