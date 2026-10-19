"""การ์ด 0041 เกณฑ์ U6: RAM สูงสุด (peak RSS) และเวลาเปิดหน้าแรกของโปรเซสหน้าจอ · รุ่นเดิม vs รุ่นใหม่.

ใช้ Python ตัวเดียวกันทั้งสองรุ่น ต่างกันแค่ซอร์ส (PYTHONPATH) · สลับรุ่นทีละรอบ (ลดผลจากความร้อน) ·
วิธี: python -m aipc.ui --dev --screen shell --page workspace --software --screenshot (เปิด → วาด → ถ่าย → ปิด) ·
RAM = ru_maxrss ของโปรเซสลูก (KB) · เวลา = นาฬิกาจริงตั้งแต่เริ่มจนโปรเซสจบ (รวมหน่วงถ่ายภาพคงที่ 600 ms ทั้งสองรุ่น)
ใช้: python bench_ui.py <ซอร์สรุ่นเดิม> <ซอร์สรุ่นใหม่> <จำนวนรอบ> > raw.csv
"""

import os
import resource
import subprocess
import sys
import tempfile
import time


def run_once(src: str) -> tuple[int, float]:
    with tempfile.TemporaryDirectory() as home:
        env = dict(os.environ, PYTHONPATH=src, QT_QPA_PLATFORM="offscreen", AIPC_CLOUD="0",
                   HOME=home, XDG_CONFIG_HOME=home, XDG_DATA_HOME=home, XDG_STATE_HOME=home,
                   XDG_RUNTIME_DIR=home)  # fmt: skip
        cmd = [sys.executable, "-m", "aipc.ui", "--dev", "--screen", "shell", "--page", "workspace",
               "--software", "--screenshot", os.path.join(home, "x.png")]  # fmt: skip
        t0 = time.monotonic()
        # แต่ละรอบเป็นโปรเซสหลานแยก (ตัวกลาง) เพื่อให้ ru_maxrss ของลูกเป็นของรอบนี้รอบเดียว
        probe = ("import resource,subprocess,sys;subprocess.run(sys.argv[1:],check=True,timeout=120);"
                 "print(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)")  # fmt: skip
        out = subprocess.run([sys.executable, "-c", probe, *cmd], env=env, check=True,
                             capture_output=True, text=True).stdout.split()[-1]  # fmt: skip
        return int(out), time.monotonic() - t0


def temp() -> str:
    try:
        return subprocess.run(["vcgencmd", "measure_temp"], capture_output=True, text=True).stdout.strip()
    except OSError:
        return "-"


if __name__ == "__main__":
    old, new, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
    print("round,version,peak_rss_kb,seconds,temp_before")
    for i in range(n):
        for name, src in (("old", old), ("new", new)) if i % 2 == 0 else (("new", new), ("old", old)):
            t = temp()
            rss, sec = run_once(src)
            print(f"{i + 1},{name},{rss},{sec:.2f},{t}", flush=True)
    _ = resource  # ใช้ในโปรเซสตัวกลาง
