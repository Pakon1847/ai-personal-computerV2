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
import re
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
    ap.add_argument("--skill-hotwords", action="store_true", help="ทาง ข: ประโยคสกิลเข้า hotwords")
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    installed, _ = install_skills(a.skills)
    voice = [m for m in installed if m.steps and m.worker == "code"]

    def skill(text: str) -> str:
        m = router.repeat_of(text, voice)
        return m.id if m else ""

    # Piper ไทยไม่อ่านคำอังกฤษ (ได้ไฟล์ว่าง · พบใน 0026) → ประโยคที่ไม่มีตัวอักษรไทยข้ามและนับแยก
    phrases = [(m.id, t) for m in voice for t in m.examples]
    skipped = [t for _, t in phrases if not re.search("[฀-๿]", t)]
    items = [{"skill": sid, "text": t,
              "reaches_skill": {route(t, r, skill) for r in (False, True)} == {SKILL}}
             for sid, t in phrases if t not in skipped]  # fmt: skip
    print(f"ประโยค {len(items)} · ข้าม (ไม่มีตัวอักษรไทย) {len(skipped)}: {skipped}", flush=True)
    texts = json.dumps([i["text"] for i in items], ensure_ascii=False)
    old = work / "texts.json"
    # Piper สุ่มทุกครั้ง (พบ 2026-10-15: โค้ดเดิม ไม่มี hotwords ได้ 4/15 แล้ว 7/15) → สังเคราะห์ครั้งเดียว
    # แล้วใช้ไฟล์เสียงชุดเดียวกันเทียบ มี/ไม่มี hotwords
    if not (old.exists() and old.read_text(encoding="utf-8") == texts
            and (work / f"{len(items) - 1:03d}-16k.wav").exists()):  # fmt: skip
        old.write_text(texts, encoding="utf-8")
        py = tts.VOICE_DIR / "venv" / "bin" / "python"
        subprocess.run([str(py), "-c", SYNTH, str(tts.VOICE_DIR / tts.MODEL), str(old), str(work)],
                       check=True)  # fmt: skip
        for i in range(len(items)):
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(work / f"{i:03d}.wav"),
                            "-ar", "16000", "-ac", "1", str(work / f"{i:03d}-16k.wav")],
                           check=True)  # fmt: skip
        print(f"สังเคราะห์ใหม่ {len(items)} ไฟล์ · {temp()}", flush=True)
    else:
        print(f"ใช้ไฟล์เสียงเดิม {len(items)} ไฟล์ · {temp()}", flush=True)
    extra = [t for m in voice for t in m.examples] if a.skill_hotwords else []
    z = Transcriber(base=Path(a.zip_base), extra_hotwords=lambda: extra)
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
    summary = {"phrases": len(items), "skipped_non_thai": skipped, "exact": exact,
               "skill_hotwords": a.skill_hotwords, "hotwords": len(z.hotwords()),
               "picked_right": right, "picked_wrong": wrong,
               "reaches_skill_phrases": len(reach),
               "reaches_skill_right": sum(i["picked"] == i["skill"] for i in reach),
               "temp": temp()}  # fmt: skip
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    a.out.write_text(json.dumps({"summary": summary, "items": items}, ensure_ascii=False, indent=1,
                                default=list), encoding="utf-8")  # fmt: skip


if __name__ == "__main__":
    main()
