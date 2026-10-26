"""การ์ด 0024 เกณฑ์ข้อ 2 และ 5: เสียงจนจบ (Piper พูด → whisper.cpp ถอด → ตัวแปลคำสั่งเว็บ) บน Pi.

เสียงสังเคราะห์ ไม่ใช่เสียงคน (จุดอ่อน · เกณฑ์ข้อ 7 ให้ Pakon พูดเอง) ·
ใช้ตัวถอดและค่าเดียวกับแอป (aipc.voice.stt)

python -m aipc.spikes.voice_loop_eval tests/data/browse_v2.json ผล.json
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from aipc.skills import browse
from aipc.spikes.browse_eval import as_recorded
from aipc.voice import stt, tts

SYNTH = r"""
import sys, wave, json
from piper import PiperVoice
v = PiperVoice.load(sys.argv[1])
for i, text in enumerate(json.load(open(sys.argv[2], encoding="utf-8"))):
    with wave.open(f"{sys.argv[3]}/{i:02d}.wav", "wb") as w:
        v.synthesize_wav(text, w)
"""


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    items = json.loads(Path(argv[0]).read_text(encoding="utf-8"))["items"]
    work = Path(tempfile.mkdtemp(prefix="v3-"))
    (work / "texts.json").write_text(json.dumps([it["text"] for it in items], ensure_ascii=False),
                                     encoding="utf-8")  # fmt: skip
    py = stt.VOICE_DIR / "venv" / "bin" / "python"
    t0 = time.monotonic()
    subprocess.run([str(py), "-c", SYNTH, str(stt.VOICE_DIR / tts.MODEL), str(work / "texts.json"),
                    str(work)], check=True)  # fmt: skip
    print(f"สังเคราะห์ {len(items)} ประโยคใน {time.monotonic() - t0:.0f} วิ", flush=True)
    # ค่าเดียวกับ stt.Listener
    whisper = [str(stt.VOICE_DIR / stt.WHISPER), "-m", str(stt.VOICE_DIR / stt.MODEL), "-l", "th",
               "-t", "4", "-nt", "-ac", "512", "-f"]  # fmt: skip
    rows = []
    for i, it in enumerate(items):
        src, wav = work / f"{i:02d}.wav", work / f"{i:02d}-16k.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-ar", "16000",
                        "-ac", "1", str(wav)], check=True)  # fmt: skip
        t1 = time.monotonic()
        r = subprocess.run([*whisper, str(wav)], capture_output=True, text=True)
        secs = round(time.monotonic() - t1, 2)
        heard = stt.clean(r.stdout)
        got = as_recorded([c.as_dict() for c in browse.parse(heard)])
        ok = got == it["expect"]
        rows.append({"text": it["text"], "heard": heard, "expect": it["expect"], "got": got,
                     "ok": ok, "stt_seconds": secs})  # fmt: skip
        print(f"{'✓' if ok else '✗'} {secs:4.1f}s {it['text']} → «{heard}» → {got}", flush=True)
    cmd = [r for r in rows if r["expect"]]
    neg = [r for r in rows if not r["expect"]]
    res = {
        "commands": f"{sum(r['ok'] for r in cmd)}/{len(cmd)}",
        "commands_pct": round(100 * sum(r["ok"] for r in cmd) / max(1, len(cmd)), 1),
        "non_commands_caught": sum(bool(r["got"]) for r in neg),
        "non_commands": len(neg),
        "stt_median_s": statistics.median(r["stt_seconds"] for r in rows),
        "stt_max_s": max(r["stt_seconds"] for r in rows),
        "rows": rows,
    }
    print(f"คำสั่งเว็บถูก {res['commands']} ({res['commands_pct']}%) · ประโยคอื่นถูกจับ "
          f"{res['non_commands_caught']}/{res['non_commands']} · "
          f"ถอดเสียงมัธยฐาน {res['stt_median_s']} วิ (สูงสุด {res['stt_max_s']})")  # fmt: skip
    if len(argv) > 1:
        Path(argv[1]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
