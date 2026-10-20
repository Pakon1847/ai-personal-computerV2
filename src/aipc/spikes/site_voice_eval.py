"""การ์ด 0046 (ชุดพัฒนา): ตัวถอดเสียงของคีย์ลัดจับคำพูดของสกิลประจำเว็บได้แค่ไหน · มี/ไม่มีคำใบ้ของสกิล · บน Pi 5.

    python -m aipc.spikes.site_voice_eval --out ผล.json

Piper พูดคำพูดทุกข้อในสกิลประจำเว็บในเครื่อง → Zipformer ของแอปถอด 2 แบบ (คำใบ้เดิม 118 / + คำพูดของสกิล) →
sitecmd.match ในเว็บของสกิล: ตรงคำสั่งเดิม = ทำได้ทันที · ใกล้ = ได้การ์ดถามก่อน · อื่น = พลาด ·
ชุดพัฒนา (คำพูดของสกิลเอง) ใช้เลือกแบบ ไม่ใช่ชุดทดสอบ · เสียงสังเคราะห์ ไม่ใช่เสียงคน
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from aipc.skills import manifest, sitecmd
from aipc.spikes.voice_cmd_eval import SYNTH
from aipc.voice import stt, tts, zipformer

URLS = {"youtube": "https://www.youtube.com/watch?v=x", "spotify": "https://open.spotify.com/"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    skills = [s for s in manifest.load_builtin() if s.site]
    items = [(s, c, p) for s in skills for c in s.commands for p in c.phrases]
    phrases = [p for _, _, p in items]
    work = Path(tempfile.mkdtemp(prefix="vsite-"))
    (work / "texts.json").write_text(json.dumps(phrases, ensure_ascii=False), encoding="utf-8")
    py = stt.VOICE_DIR / "venv" / "bin" / "python"
    subprocess.run([str(py), "-c", SYNTH, str(stt.VOICE_DIR / tts.MODEL), str(work / "texts.json"),
                    str(work)], check=True)  # fmt: skip
    for i in range(len(phrases)):
        src, wav = work / f"{i:03d}.wav", work / f"{i:03d}-16k.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-ar", "16000",
                        "-ac", "1", str(wav)], check=True)  # fmt: skip
    out = {}
    for name, extra in (("base", None), ("site", lambda: phrases)):
        fast = zipformer.Transcriber(extra_hotwords=extra)
        rows = []
        for i, (s, c, p) in enumerate(items):
            heard, _err = fast.transcribe(work / f"{i:03d}-16k.wav")
            got_s, got_c, exact = sitecmd.match(heard, skills, URLS[s.site])
            same = got_c is not None and got_c == c
            verdict = (
                "exact" if same and exact else "confirm" if same else "wrong" if got_c else "miss"
            )
            rows.append({"phrase": p, "heard": heard, "verdict": verdict})
        fast.close()
        n = len(rows)
        out[name] = {"hotwords": len(fast.hotwords()), "n": n,
                     "exact": sum(r["verdict"] == "exact" for r in rows),
                     "confirm": sum(r["verdict"] == "confirm" for r in rows),
                     "wrong": sum(r["verdict"] == "wrong" for r in rows), "rows": rows}  # fmt: skip
        print(name, {k: v for k, v in out[name].items() if k != "rows"}, flush=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
