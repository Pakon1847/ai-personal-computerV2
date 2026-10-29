"""เทียบ LLM ขั้น 1 ส่วนความแม่น (โน้ตบุ๊ก) · 2026-10-29 · docs/benchmarks/2026-10-29-llm-compare/README.md

    python scripts/bench/run_accuracy.py --server-bin D:/tools/llama-b11249/llama-server.exe \
        --models D:/bench-models [label ...]

ต่อโมเดล: เปิด llama-server ค่าเดียวกับแอป (ยกเว้น thread = ความเร็วอย่างเดียว) → ชุดทดสอบอิสระ 100 ข้อ
(รันครั้งเดียว · มีไฟล์ผลครบแล้ว = ข้าม ไม่รันซ้ำ) → ปิด · ความเร็ว/RAM ไม่วัดที่นี่ (วัดบน Pi 5)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BENCH = REPO / "docs" / "benchmarks" / "2026-10-29-llm-compare"
DATASET = REPO / "tests" / "data" / "llm_compare_heldout.json"
PORT = 18080


def healthy() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2) as r:
            return r.status == 200
    except OSError:
        return False


def run(label: str, model: Path, server_bin: str, threads: int, out: Path) -> str:
    dest = out / f"{label}-heldout.json"
    if dest.exists() and json.loads(dest.read_text(encoding="utf-8")).get("done"):
        return "have"
    log = (out / f"{label}-server.log").open("w", encoding="utf-8")
    cmd = [server_bin, "-m", str(model), "--host", "127.0.0.1", "--port", str(PORT),
           "-c", "4096", "-np", "1", "-t", str(threads), "-fa", "off", "-cram", "512",
           "--no-webui", "--no-slots", "--swa-full"]  # fmt: skip
    srv = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(300):
            if healthy() or srv.poll() is not None:
                break
            time.sleep(1)
        if not healthy():
            return "server-fail"
        r = subprocess.run([sys.executable, "-m", "aipc.spikes.exam", "--label", label,
                            "--server", f"http://127.0.0.1:{PORT}", "--dataset", str(DATASET),
                            "--out", str(dest)], cwd=REPO,
                           env={**__import__("os").environ, "PYTHONPATH": str(REPO / "src"),
                                "PYTHONIOENCODING": "utf-8", "AIPC_CLOUD": "0"},
                           stdout=(out / f"{label}-heldout.log").open("w", encoding="utf-8"),
                           stderr=subprocess.STDOUT)  # fmt: skip
        if r.returncode != 0:
            return "exam-fail"
        res = json.loads(dest.read_text(encoding="utf-8"))
        res["done"] = True
        res["machine"] = "laptop · llama.cpp b11249 (6d78fb0) · win-cpu-x64"
        text = json.dumps(res, ensure_ascii=False, indent=1)
        dest.write_text(text, encoding="utf-8", newline="\n")
        return "ok"
    finally:
        srv.terminate()
        srv.wait(timeout=30)
        log.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server-bin", required=True)
    ap.add_argument("--models", type=Path, required=True)
    ap.add_argument("--threads", type=int, default=10)
    ap.add_argument("labels", nargs="*")
    a = ap.parse_args()
    rows = json.loads((BENCH / "models.json").read_text(encoding="utf-8"))
    out = BENCH / "raw-laptop"
    out.mkdir(parents=True, exist_ok=True)
    for r in rows:
        if a.labels and r["label"] not in a.labels:
            continue
        model = a.models / r["file"]
        if not model.exists():
            print("SKIP", r["label"], "ไม่มีไฟล์", flush=True)
            continue
        t0 = time.monotonic()
        status = run(r["label"], model, a.server_bin, a.threads, out)
        print(f"{status.upper()} {r['label']} {time.monotonic() - t0:.0f} วิ", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
