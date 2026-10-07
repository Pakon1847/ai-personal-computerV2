"""วัดเกณฑ์ ข ข้อ 1 (docs/benchmarks/2026-10-07-privacy-panel) และ ค ข้อ 1–2 (2026-10-07-energy-meter-pi5).

รันบน Pi 5 เป็น aipc2030 ทาง SSH · PYTHONPATH=~/aipc/src (commit 63d5e9a) · เกณฑ์ commit ก่อน (7a177f9)
"""

import http.client
import json
import os
import statistics
import subprocess
import time

from aipc.bench import energy
from aipc.chat import client
from aipc.spikes.energy_bench import QUESTIONS, Sampler
from aipc.ui import privacy

SOCK = os.path.join(os.environ["XDG_RUNTIME_DIR"], "aipc", "llm.sock")
T = client.Target(sock=SOCK)
OUT: dict = {"start": time.strftime("%F %T")}


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True)


def env() -> str:
    return sh("vcgencmd", "measure_temp").stdout.strip() + " " + sh("vcgencmd", "get_throttled").stdout.strip()


def wait_ready(timeout=240) -> float:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if client.health(T) == "ready":
            return round(time.monotonic() - t0, 1)
        time.sleep(0.5)
    raise SystemExit("llama-server ไม่พร้อม")


def main_pid(unit: str) -> int:
    return int(sh("systemctl", "--user", "show", unit, "-p", "MainPID", "--value").stdout.strip() or 0)


def ask_short(q: str) -> float:
    """คำขอเดียวกันทุกรอบ (128 token · temperature 0) ผ่าน Unix socket · คืน token/วิ."""
    body = {"messages": [{"role": "user", "content": q}], "max_tokens": 128, "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False}, "cache_prompt": False}  # fmt: skip
    conn = client._UnixConnection(SOCK, 600)
    conn.request("POST", "/v1/chat/completions", body=json.dumps(body), headers={"Content-Type": "application/json"})
    d = json.loads(conn.getresponse().read())
    conn.close()
    return float(d["timings"]["predicted_per_second"])


print("== เริ่ม", OUT["start"], "·", env(), flush=True)
sh("systemctl", "--user", "daemon-reload")
sh("systemctl", "--user", "start", "aipc-llm")
OUT["ready_s"] = wait_ready()

# ---------- ข ข้อ 1 (unit จริง) ----------
pid = privacy.llm_pid()
OUT["b1_locked"] = {"pid": pid, "state": privacy.sandbox_state(pid)}
print("ข1 unit จริง:", OUT["b1_locked"], flush=True)

# ---------- ค ข้อ 1: มิเตอร์ (1 ครั้ง/วิ) เทียบตัวอ้างอิง (4 ครั้ง/วิ) พร้อมกัน · เส้นทางเดียวกับแอป (client.Stream) ----------
OUT["c1"] = []
for q in QUESTIONS:
    with Sampler(0.25) as ref:
        time.sleep(1.0)  # ให้ตัวอ้างอิงมีค่าก่อนเริ่ม
        m = energy.Meter(period=1.0)
        t0 = time.monotonic()
        m.start()
        reply = client.Stream(T, [{"role": "user", "content": q}]).run(lambda tok: None)
        app = m.stop()
        t1 = time.monotonic()
        time.sleep(0.5)
    r = ref.window(t0, t1)
    diff = abs(app["joules"] - r["joules"]) / r["joules"] * 100 if app and r["joules"] else None
    row = {"q": q, "tokens": reply.timings.get("predicted_n"), "app": app, "ref": r,
           "diff_pct": round(diff, 2) if diff is not None else None}  # fmt: skip
    OUT["c1"].append(row)
    print("ค1", q[:24], "| app", app and app["joules"], "J", app and app["seconds"], "วิ | ref",
          r["joules"], "J", r["samples"], "ค่า | ต่าง", row["diff_pct"], "% |", env(), flush=True)

# ---------- ค ข้อ 2: token/วิ มี/ไม่มีมิเตอร์ (สลับกัน 3 คู่) ----------
Q2 = "อธิบายภาวะโลกร้อนแบบเข้าใจง่าย"
ask_short(Q2)  # อุ่น
OUT["c2"] = {"without": [], "with": []}
for _ in range(3):
    OUT["c2"]["without"].append(ask_short(Q2))
    m = energy.Meter(period=1.0)
    m.start()
    OUT["c2"]["with"].append(ask_short(Q2))
    m.stop()
OUT["c2"]["median_without"] = statistics.median(OUT["c2"]["without"])
OUT["c2"]["median_with"] = statistics.median(OUT["c2"]["with"])
print("ค2", OUT["c2"], "|", env(), flush=True)

# ---------- ข ข้อ 1 (unit ชั่วคราวไม่จำกัด · สคริปต์เดียวกัน) ----------
sh("systemctl", "--user", "stop", "aipc-llm")
time.sleep(3)
sh("systemd-run", "--user", "--quiet", "--unit", "aipc-llm-cmp", "/opt/aipc-v2/scripts/pi/session/aipc-llm-start")
wait_ready()
cpid = main_pid("aipc-llm-cmp")
OUT["b1_open"] = {"pid": cpid, "state": privacy.sandbox_state(cpid)}
print("ข1 ไม่จำกัด:", OUT["b1_open"], flush=True)
sh("systemctl", "--user", "stop", "aipc-llm-cmp")

OUT["end"] = time.strftime("%F %T")
OUT["env_end"] = env()
with open("/tmp/measure_bc.json", "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)
print("== จบ", OUT["end"], "·", OUT["env_end"], flush=True)
