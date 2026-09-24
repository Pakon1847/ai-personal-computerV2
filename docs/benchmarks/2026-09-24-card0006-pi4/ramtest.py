"""ทดลอง: RAM ที่ไม่ลดหลังใช้โมเดลในเธรดแยก เป็นเพราะยังมีคนถือโมเดล หรือ glibc ไม่คืนหน่วยความจำ.

รันบน Pi: cd ~/aipc && ./.venv/bin/python <ไฟล์นี้>  (ไม่ใช้กล้อง · ป้อนภาพสุ่ม 20 เฟรม)
"""

import ctypes
import gc
import threading
import weakref

import numpy as np

from aipc.vision import camera, config


def rss():
    for line in open("/proc/self/status"):
        if line.startswith("VmRSS"):
            return int(line.split()[1]) // 1024


libc = ctypes.CDLL("libc.so.6")
print("start", rss())
ref = {}


def job():
    s = camera.build_scanner(config.load(None))
    rng = np.random.default_rng(0)
    for _ in range(20):
        s.process(rng.integers(0, 255, (720, 1280, 3), dtype=np.uint8))
    ref["w"] = weakref.ref(s)
    print("in thread, models loaded", rss())


for i in range(2):
    t = threading.Thread(target=job)
    t.start()
    t.join()
    gc.collect()
    print(f"round {i}: after thread+gc", rss(), "scanner alive?", ref["w"]() is not None)
    libc.malloc_trim(0)
    print(f"round {i}: after malloc_trim", rss())
