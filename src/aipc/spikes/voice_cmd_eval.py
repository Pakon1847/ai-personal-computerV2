"""การ์ด 0045: ถอดเสียงคำสั่งแม่นแค่ไหน (Piper พูด → Zipformer ของแอปถอด → ป้ายเดียวกับตอนพิมพ์ไหม) · บน Pi 5.

    python -m aipc.spikes.voice_cmd_eval tests/data/voice_cmd_test.json --out ผล.json
    (--app-hotwords = คำใบ้แบบแอปจริง: + คำพูดของสกิล · การ์ด 0046)

ป้าย = aipc.spikes.voice_all_eval.label (ทางเดียวกับคีย์ลัดในแอป) ของข้อความที่ถอดได้ เทียบกับของประโยคต้นฉบับ ·
ถูกตรง = ป้ายเท่ากัน · ถูกผ่านการยืนยัน = ได้การ์ด "หมายถึง … ใช่ไหม" ที่ชี้คำสั่งถูก
(near:<ประโยค> แล้วป้ายของประโยคนั้นเท่ากัน) ·
ไม่ใช่คำสั่ง (ป้ายต้นฉบับ ask/none) ที่ถอดแล้วกลายเป็นคำสั่งทันที (browser:/command/app) = ทำผิด ·
เสียงสังเคราะห์ ไม่ใช่เสียงคน (ตัวเลขนี้ใช้เทียบก่อน/หลังแก้ ไม่ใช่ความแม่นที่ผู้ใช้จะได้)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from aipc.spikes import voice_all_eval as ev
from aipc.voice import stt, tts, zipformer

SYNTH = r"""
import sys, wave, json
from piper import PiperVoice
v = PiperVoice.load(sys.argv[1])
for i, text in enumerate(json.load(open(sys.argv[2], encoding="utf-8"))):
    with wave.open(f"{sys.argv[3]}/{i:03d}.wav", "wb") as w:
        v.synthesize_wav(text, w)
"""
ACTS = ("browser:", "command", "app:")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    # การ์ด 0046 W6: คำใบ้แบบแอปจริงของบัญชีใหม่ = รายการเดิม + คำพูดของสกิล (SkillsController.voicePhrases)
    ap.add_argument("--app-hotwords", action="store_true")
    a = ap.parse_args(argv)
    items = json.loads(a.dataset.read_text(encoding="utf-8"))["items"]
    work = Path(tempfile.mkdtemp(prefix="vcmd-"))
    (work / "texts.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    py = stt.VOICE_DIR / "venv" / "bin" / "python"
    subprocess.run([str(py), "-c", SYNTH, str(stt.VOICE_DIR / tts.MODEL), str(work / "texts.json"),
                    str(work)], check=True)  # fmt: skip
    _engine, skills = ev.backend()
    fast = zipformer.Transcriber(extra_hotwords=skills.voicePhrases if a.app_hotwords else None)
    rows = []
    for i, text in enumerate(items):
        src, wav = work / f"{i:03d}.wav", work / f"{i:03d}-16k.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-ar", "16000",
                        "-ac", "1", str(wav)], check=True)  # fmt: skip
        t = time.monotonic()
        heard, err = fast.transcribe(wav)
        secs = round(time.monotonic() - t, 3)
        want, got = ev.label(text, skills), ev.label(heard, skills)
        near = ""
        if got.startswith("near:"):
            near = got[5:]
        verdict = "exact" if got == want else "wrong"
        if verdict == "wrong" and near and ev.label(near, skills) == want:
            verdict = "confirm"
        non = want in ("ask", "none") or want.startswith(("near", "create"))
        acted = non and got.startswith(ACTS)
        rows.append({"said": text, "heard": heard, "want": want, "got": got, "verdict": verdict,
                     "non_command": non, "acted": acted, "seconds": secs})  # fmt: skip
        mark = {"exact": "✓", "confirm": "?", "wrong": "✗"}[verdict]
        print(f"{mark} {text} → «{heard}» {want} / {got}", flush=True)
    fast.close()
    cmd = [r for r in rows if not r["non_command"]]
    summary = {
        "commands": len(cmd),
        "exact": sum(r["verdict"] == "exact" for r in cmd),
        "via_confirm": sum(r["verdict"] == "confirm" for r in cmd),
        "non_commands": len(rows) - len(cmd),
        "non_command_acted": sum(r["acted"] for r in rows),
        "hotwords": len(fast.hotwords()),
    }
    a.out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
                     encoding="utf-8")  # fmt: skip
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
