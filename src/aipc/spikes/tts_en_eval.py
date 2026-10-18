"""วัดเกณฑ์ B2 ของการ์ด 0039 บน Pi 5: อ่านออกเสียงภาษาอังกฤษ (ตัวสังเคราะห์จริงในกล่องไม่มีเน็ตแบบเดียวกับแอป).

ชุดวัด tests/data/tts_en/set.json (20 ข้อความ · ผู้ช่วยที่ไม่เห็นโค้ดเขียน · commit ก่อนรัน · H9) ·
ทำตามทางของแอป: tts.language → to_speech_en → sentences → piper_worker (tts.sandboxed) ·
อุ่นเครื่องด้วยข้อความไทย 1 ครั้ง (= สภาพตอนแอปเปิดตัวอ่านแล้ว) → วัด RAM → อ่านอังกฤษครั้งแรก (โหลดเสียง) → วัด RAM ·
แล้ววัดทุกข้อ: เวลาจากส่งงานถึงท่อนแรกพร้อมเล่น (เสียงอังกฤษโหลดแล้ว)

ผ่านเมื่อ: สำเร็จ 20/20 · มัธยฐานเวลาท่อนแรก ≤ 1.5 วิ · RAM เพิ่มจากโหลดเสียงอังกฤษ ≤ 200 MB ·
ตัวสังเคราะห์ไม่มีช่องทางเน็ต (network namespace ของมันมีแค่ lo)

ไฟล์เสียงของ 10 ข้อแรกเก็บไว้ที่ --keep ให้ Pakon ฟัง (เกณฑ์ B4) ·
ไม่ใส่ใน git (เสียงสังเคราะห์ ไม่ใช่เสียงคน แต่ไฟล์ใหญ่)

    python -m aipc.spikes.tts_en_eval --out ผล.json --keep ~/tts-en-b4
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import wave
from pathlib import Path

SET = Path("tests/data/tts_en/set.json")


def rss_mb(pid: int) -> float:
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) / 1024
    return 0.0


def worker_pid(timeout: float = 20) -> int:
    """pid ของ piper_worker ที่ systemd-run เปิด (Popen ได้ pid ของ systemd-run ไม่ใช่ตัวสังเคราะห์)."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        r = subprocess.run(["pgrep", "-n", "-f", "piper_worker.py"], capture_output=True, text=True)
        if r.stdout.strip():
            return int(r.stdout.split()[0])
        time.sleep(0.2)
    raise RuntimeError("หา piper_worker ไม่เจอ")


def net_ifaces(pid: int) -> list[str]:
    rows = Path(f"/proc/{pid}/net/dev").read_text().splitlines()[2:]
    return [r.split(":")[0].strip() for r in rows]


class Worker:
    def __init__(self, workdir: Path):
        from aipc.voice import tts

        env = {**os.environ, "OMP_NUM_THREADS": "2", "PYTHONIOENCODING": "utf-8"}
        cmd = [str(tts.VOICE_DIR / "venv/bin/python"), str(tts.WORKER),
               str(tts.VOICE_DIR / tts.MODEL), str(tts.VOICE_DIR / tts.EN_MODEL)]  # fmt: skip
        self.proc = subprocess.Popen(tts.sandboxed(cmd, env), stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, text=True, encoding="utf-8",
                                     env=env)  # fmt: skip
        assert json.loads(self.proc.stdout.readline()).get("ready")
        self.dir, self.n = workdir, 0

    def say(self, text: str) -> dict:
        """ส่งงานแบบเดียวกับ Speaker.say · คืนเวลาท่อนแรก · เวลาทั้งหมด · ไฟล์ทุกท่อน · ข้อผิดพลาด."""
        from aipc.voice import tts
        from aipc.voice.speech_text import sentences, to_speech, to_speech_en

        voice = tts.language(text)
        chunks = sentences(to_speech_en(text) if voice == "en" else to_speech(text))
        self.n += 1
        t0 = time.monotonic()
        msg = {"cmd": "say", "id": self.n, "chunks": chunks, "dir": str(self.dir),
               "voice": voice}  # fmt: skip
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        first, paths = None, []
        while True:
            r = json.loads(self.proc.stdout.readline())
            if r.get("error"):
                return {"voice": voice, "chunks": len(chunks), "error": r["error"]}
            first = first if first is not None else time.monotonic() - t0
            paths.append(r["path"])
            if r.get("last"):
                break
        total = round(time.monotonic() - t0, 3)
        return {"voice": voice, "chunks": len(chunks), "first_s": round(first, 3),
                "total_s": total, "paths": paths, "error": ""}  # fmt: skip

    def close(self) -> None:
        self.proc.stdin.close()
        self.proc.wait(timeout=10)


def join_wavs(paths: list[str], out: Path) -> None:
    with wave.open(str(out), "wb") as w:
        for i, p in enumerate(paths):
            with wave.open(p, "rb") as r:
                if i == 0:
                    w.setparams(r.getparams())
                w.writeframes(r.readframes(r.getnframes()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=Path, default=SET)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--keep", type=Path, required=True)
    a = ap.parse_args(argv)
    items = json.loads(a.set.read_text(encoding="utf-8"))["items"]
    work = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "aipc-tts-eval"
    work.mkdir(mode=0o700, exist_ok=True)
    a.keep.mkdir(parents=True, exist_ok=True)
    w = Worker(work)
    pid = worker_pid()
    warm = w.say("สวัสดีครับ วันนี้อากาศดี")  # สภาพเดียวกับแอปที่เคยอ่านไทยแล้ว
    rss_th = rss_mb(pid)
    load = w.say("Hello. This loads the English voice.")
    rss_en = rss_mb(pid)
    ifaces = net_ifaces(pid)
    rows = []
    for i, it in enumerate(items):
        r = w.say(it["text"])
        if not r["error"] and i < 10:
            join_wavs(r["paths"], a.keep / f"{it['id']}.wav")
        for p in r.pop("paths", []):
            Path(p).unlink(missing_ok=True)
        rows.append({"id": it["id"], **r})
        mark = "✓" if not r["error"] else "✗ " + r["error"]
        print(f"{mark} {it['id']} {r['voice']} first {r.get('first_s', '-')} s · "
              f"total {r.get('total_s', '-')} s · {r['chunks']} ท่อน")  # fmt: skip
    rss_end = rss_mb(pid)
    w.close()
    for p in warm.get("paths", []) + load.get("paths", []):
        Path(p).unlink(missing_ok=True)
    ok = [r for r in rows if not r["error"] and r["voice"] == "en"]
    med = statistics.median(r["first_s"] for r in ok) if ok else None
    added = round(rss_en - rss_th, 1)
    summary = {
        "items": len(rows), "ok": len(ok), "median_first_s": med,
        "max_first_s": max((r["first_s"] for r in ok), default=None),
        "rss_after_thai_mb": round(rss_th, 1), "rss_after_english_mb": round(rss_en, 1),
        "rss_end_mb": round(rss_end, 1), "rss_added_mb": added,
        "english_first_load_s": load.get("total_s"), "net_ifaces": ifaces,
    }  # fmt: skip
    summary["passed"] = (len(ok) == len(rows) == 20 and med is not None and med <= 1.5
                         and added <= 200 and ifaces == ["lo"])  # fmt: skip
    print(json.dumps(summary, ensure_ascii=False))
    print("ผ่าน" if summary["passed"] else "ไม่ผ่าน")
    a.out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
                     encoding="utf-8")  # fmt: skip
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
