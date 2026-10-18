"""การ์ด 0040 ระยะ D1 (spike บน Pi 5): ตัวถอดเสียงภาษาอังกฤษตัวไหนเร็วพอและแม่นพอสำหรับคำสั่ง.

เสียงทดสอบ = เสียงสังเคราะห์ ljspeech (ระยะ B) อ่านประโยคชุด C1 รอบ 1
(tests/data/english_cmd/set.json · กลายเป็นชุดพัฒนาแล้ว) ·
เสียงสังเคราะห์ชัดกว่าคนจริง → ตัวเลขนี้คือ "เพดาน" ใช้เลือกโมเดล ไม่ใช่ความแม่นที่ผู้ใช้จะได้ (นั่นคือ D2 · เสียง Pakon)

ต่อโมเดล: เวลาถอดต่อประโยค (whisper-cli ทั้งโปรเซส · ธงเดียวกับตัวถอดไทยของแอป: -t 4 -nt -ac 512) ·
RAM สูงสุด (VmHWM) ·
คำสั่งที่ช่องข้อมูลหลังถอด = ตอนพิมพ์ประโยคเดียวกัน · ประโยคไม่ใช่คำสั่งที่กลายเป็นคำสั่ง

    python -m aipc.spikes.stt_en_spike --models ~/voice-bench/en-stt --out ผล.json
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from aipc.spikes.english_cmd_eval import slots

SET = Path("tests/data/english_cmd/set.json")
VOICE = Path("/opt/aipc-voice")
WHISPER = VOICE / "whisper/bin/whisper-cli"
MODELS = ["ggml-tiny.en.bin", "ggml-base.en.bin", "ggml-small.en-q5_1.bin"]
TAGS = re.compile(r"\[[^\]]*\]|\([^)]*\)")
SYNTH = r"""
import json, sys, wave
from piper import PiperVoice
v = PiperVoice.load(sys.argv[1])
for it in json.load(open(sys.argv[2], encoding="utf-8")):
    with wave.open(it["path"], "wb") as w:
        v.synthesize_wav(it["text"], w)
"""


def synth(items: list[dict], work: Path) -> None:
    jobs = [{"text": it["text"], "path": str(work / f"{it['id']}-22k.wav")} for it in items]
    (work / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    voice = str(VOICE / "en_US-ljspeech-medium.onnx")
    subprocess.run([str(VOICE / "venv/bin/python"), "-c", SYNTH, voice, str(work / "jobs.json")],
                   check=True)  # fmt: skip
    for it in items:
        src, dst = work / f"{it['id']}-22k.wav", work / f"{it['id']}.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-ar", "16000",
                        "-ac", "1", str(dst)], check=True)  # fmt: skip


def transcribe(model: Path, wav: Path) -> tuple[str, float, float]:
    """(ข้อความ, วินาที, RAM สูงสุด MB)."""
    t0 = time.monotonic()
    cmd = [str(WHISPER), "-m", str(model), "-l", "en", "-t", "4", "-nt", "-ac", "512",
           "-f", str(wav)]  # fmt: skip
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    hwm = 0.0
    while p.poll() is None:
        try:
            for line in Path(f"/proc/{p.pid}/status").read_text().splitlines():
                if line.startswith("VmHWM:"):
                    hwm = max(hwm, int(line.split()[1]) / 1024)
        except OSError:
            pass
        time.sleep(0.05)
    out = p.stdout.read()
    secs = time.monotonic() - t0
    return re.sub(r"\s+", " ", TAGS.sub(" ", out)).strip(), secs, hwm


def same(a: dict, b: dict) -> bool:
    drop = {"thai"}
    a = {k: v for k, v in a.items() if k not in drop}
    b = {k: v for k, v in b.items() if k not in drop}
    if a.get("kind") == b.get("kind") and "what" in a:  # ตัวพิมพ์ใหญ่เล็กของชื่อนัดไม่นับ
        a["what"], b["what"] = (a["what"] or "").lower(), (b["what"] or "").lower()
    return a == b


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--set", type=Path, default=SET)
    a = ap.parse_args(argv)
    items = json.loads(a.set.read_text(encoding="utf-8"))["items"]
    result = {"set": str(a.set), "models": {}}
    with tempfile.TemporaryDirectory(prefix="stt-en-") as tmp:
        work = Path(tmp)
        synth(items, work)
        for name in MODELS:
            rows = []
            for it in items:
                text, secs, hwm = transcribe(a.models / name, work / f"{it['id']}.wav")
                ref, got = slots(it["text"]), slots(text)
                rows.append({"id": it["id"], "ref_text": it["text"], "heard": text,
                             "secs": round(secs, 2), "hwm_mb": round(hwm, 1),
                             "command": it["kind"] != "none", "ref_kind": ref["kind"],
                             "same": same(ref, got), "got": got})  # fmt: skip
            cmds = [r for r in rows if r["command"] and r["ref_kind"] != "none"]
            negs = [r for r in rows if not r["command"]]
            s = {
                "median_s": round(statistics.median(r["secs"] for r in rows), 2),
                "p90_s": round(sorted(r["secs"] for r in rows)[int(len(rows) * 0.9) - 1], 2),
                "max_hwm_mb": max(r["hwm_mb"] for r in rows),
                "commands_same": f"{sum(r['same'] for r in cmds)}/{len(cmds)}",
                "negatives_converted": sum(r["got"]["kind"] != "none" for r in negs),
            }  # fmt: skip
            print(name, json.dumps(s, ensure_ascii=False), flush=True)
            result["models"][name] = {"summary": s, "rows": rows}
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
