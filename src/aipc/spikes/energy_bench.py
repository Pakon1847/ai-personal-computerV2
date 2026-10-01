"""พลังงานต่อคำตอบบน Pi 5 (แนวคิดข้อ 2 · 2026-10-01) · รันบน Pi.

    python -m aipc.spikes.energy_bench --server http://127.0.0.1:8080 --out /tmp/energy.json

อ่านวัตต์บนบอร์ดทุก 0.25 วิ (aipc.bench.energy) ในเธรดแยก:
1) เครื่องว่าง 20 วิ  2) AI ในเครื่องตอบคำถาม 5 ข้อ (ไม่ stream)  3) อ่านออกเสียง 1 ประโยค (ถ้าติดตั้งตัวอ่าน)
พลังงาน = ผลรวม วัตต์ × ช่วงเวลา (จูล) · ส่วนเพิ่มจากตอนว่าง = พลังงานที่งานนั้นใช้จริง
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from aipc.bench import energy

QUESTIONS = ["ทำไมท้องฟ้าถึงเป็นสีฟ้า", "แนะนำวิธีนอนให้หลับง่ายขึ้นหน่อย", "สรุปประโยชน์ของการออกกำลังกาย 3 ข้อ",
             "อธิบายภาวะโลกร้อนแบบเข้าใจง่าย", "ช่วยคิดชื่อร้านกาแฟเก๋ ๆ ให้สามชื่อ"]  # fmt: skip


class Sampler:
    def __init__(self, period: float = 0.25):
        self.period = period
        self.samples: list[tuple[float, float]] = []
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            w = energy.read()
            if w is not None:
                self.samples.append((time.monotonic(), w))
            self._stop.wait(self.period)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._t.join()

    def window(self, t0: float, t1: float) -> dict:
        pts = [(t, w) for t, w in self.samples if t0 <= t <= t1]
        if len(pts) < 2:
            return {
                "seconds": round(t1 - t0, 2),
                "samples": len(pts),
                "mean_w": None,
                "joules": None,
            }
        joules = sum((b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(pts, pts[1:], strict=False))
        mean = sum(w for _, w in pts) / len(pts)
        return {"seconds": round(t1 - t0, 2), "samples": len(pts), "mean_w": round(mean, 3),
                "joules": round(joules, 2)}  # fmt: skip


def ask(server: str, q: str) -> dict:
    body = {"messages": [{"role": "user", "content": q}], "max_tokens": 256, "temperature": 0.6,
            "chat_template_kwargs": {"enable_thinking": False}}  # fmt: skip
    url = server.rstrip("/") + "/v1/chat/completions"
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})  # fmt: skip
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
    return {"tokens": (d.get("usage") or {}).get("completion_tokens"),
            "chars": len(d["choices"][0]["message"].get("content") or "")}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.spikes.energy_bench")
    ap.add_argument("--server", default="http://127.0.0.1:8080")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--voice-dir", type=Path, default=Path("/opt/aipc-voice"))
    a = ap.parse_args(argv)
    if energy.read() is None:
        print("หยุด: อ่าน vcgencmd pmic_read_adc ไม่ได้ (ไม่ใช่ Pi 5?)", file=sys.stderr)
        return 2
    out: dict = {"note": "วัตต์บนบอร์ดจาก PMIC · ไม่รวมอะแดปเตอร์/USB · ไม่ใช้สูตรแก้", "answers": []}
    with Sampler() as s:
        t0 = time.monotonic()
        time.sleep(20)
        out["idle"] = s.window(t0, time.monotonic())
        for q in QUESTIONS:
            t0 = time.monotonic()
            r = ask(a.server, q)
            w = s.window(t0, time.monotonic())
            idle_j = (out["idle"]["mean_w"] or 0) * w["seconds"]
            extra = round(w["joules"] - idle_j, 2) if w["joules"] is not None else None
            out["answers"].append({"q": q, **r, **w, "extra_joules": extra})
            print(
                f"{q[:20]} · {w['seconds']} วิ · {w['mean_w']} W · เพิ่มจากตอนว่าง {extra} J",
                flush=True,
            )
        py = a.voice_dir / "venv" / "bin" / "python"
        if py.exists():
            t0 = time.monotonic()
            model = str(a.voice_dir / "th_TH-tsync2-medium.onnx")
            subprocess.run([str(py), "-m", "piper", "-m", model,
                            "-f", "/tmp/energy-tts.wav"], input="สวัสดีครับ วันนี้มีนัดสองรายการ".encode(),
                           capture_output=True, check=False)  # fmt: skip
            out["tts_cold"] = s.window(t0, time.monotonic())
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in out if k != "answers"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
