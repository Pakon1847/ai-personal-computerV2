"""ทดลอง: RAM ที่ไม่ลดหลังใช้โมเดลในเธรดแยก เป็นเพราะยังมีคนถือโมเดล หรือ glibc ไม่คืนหน่วยความจำ."""
import ctypes, gc, threading, weakref
import numpy as np
from aipc.vision import camera, config

def rss():
    for l in open("/proc/self/status"):
        if l.startswith("VmRSS"):
            return int(l.split()[1]) // 1024

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
    t = threading.Thread(target=job); t.start(); t.join()
    gc.collect()
    print(f"round {i}: after thread+gc", rss(), "scanner alive?", ref["w"]() is not None)
    libc.malloc_trim(0)
    print(f"round {i}: after malloc_trim", rss())
