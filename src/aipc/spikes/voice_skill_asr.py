"""การ์ด 0028 ข้อ 3 (คัดกรอง · รายงานเท่านั้น): ตัวถอดเสียงของคีย์ลัดได้ยินประโยคของสกิลตรงเป๊ะกี่ประโยค.

เสียง Piper ตัวเดียวกับชุด H ของ 0026 → 16 kHz → aipc.voice.zipformer.Transcriber
(กล่องตัดเน็ต · hotwords ชุดเดิม) · ประโยค = ตัวอย่างของสกิลโค้ดล้วนที่ผ่านประตูตรวจ
(สกิลที่ Claude เขียนใน docs/benchmarks/2026-09-30-skill-author/claude)

    python -m aipc.spikes.voice_skill_asr <งาน> --skills <สกิล> --zip-base <ฐาน> --out ผล.json
"""

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
from pathlib import Path

from aipc.skills import command, router
from aipc.spikes.voice_h_eval import SYNTH, temp
from aipc.spikes.voice_route_eval import install_skills
from aipc.ui.handsfree import SKILL, route
from aipc.voice import tts
from aipc.voice.zipformer import Transcriber


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--skills", required=True, type=Path)
    ap.add_argument("--zip-base", required=True)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    installed, _ = install_skills(a.skills)
    voice = [m for m in installed if m.steps and m.worker == "code"]

    def skill(text: str) -> str:
        m = router.repeat_of(text, voice)
        return m.id if m else ""

    items = [{"skill": m.id, "text": t,
              "reaches_skill": {route(t, r, skill) for r in (False, True)} == {SKILL}}
             for m in voice for t in m.examples]  # fmt: skip
    (work / "texts.json").write_text(json.dumps([i["text"] for i in items], ensure_ascii=False),
                                     encoding="utf-8")  # fmt: skip
    py = tts.VOICE_DIR / "venv" / "bin" / "python"
    subprocess.run([str(py), "-c", SYNTH, str(tts.VOICE_DIR / tts.MODEL), str(work / "texts.json"),
                    str(work)], check=True)  # fmt: skip
    for i in range(len(items)):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(work / f"{i:03d}.wav"),
                        "-ar", "16000", "-ac", "1", str(work / f"{i:03d}-16k.wav")],
                       check=True)  # fmt: skip
    print(f"เสียงพร้อม {len(items)} ไฟล์ · {temp()}", flush=True)
    z = Transcriber(base=Path(a.zip_base))
    assert z.available, "ไม่มี venv/ หรือ model/ ใต้ --zip-base"
    z.transcribe(work / "000-16k.wav")  # อุ่นก่อน = เหมือนกดคีย์ลัดแล้วพูด
    for i, it in enumerate(items):
        heard, err = z.transcribe(work / f"{i:03d}-16k.wav")
        key, want = command.normalize(heard), command.normalize(it["text"])
        it.update(heard=heard, err=err, exact=key == want, picked=skill(heard),
                  near=round(difflib.SequenceMatcher(None, key, want).ratio(), 2))  # fmt: skip
        print(f"{'ตรง' if it['exact'] else 'ไม่ตรง':6} {it['near']:.2f} «{heard}» ← {it['text']}",
              flush=True)  # fmt: skip
    z.close()
    exact = sum(i["exact"] for i in items)
    right = sum(i["picked"] == i["skill"] for i in items)
    wrong = sum(bool(i["picked"]) and i["picked"] != i["skill"] for i in items)
    reach = [i for i in items if i["reaches_skill"]]
    summary = {"phrases": len(items), "exact": exact, "picked_right": right, "picked_wrong": wrong,
               "reaches_skill_phrases": len(reach),
               "reaches_skill_right": sum(i["picked"] == i["skill"] for i in reach),
               "temp": temp()}  # fmt: skip
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    a.out.write_text(json.dumps({"summary": summary, "items": items}, ensure_ascii=False, indent=1,
                                default=list), encoding="utf-8")  # fmt: skip


if __name__ == "__main__":
    main()
