"""การ์ด 0026 (spike · วัดก่อนออกแบบ): ให้ whisper ให้คะแนน "ต้นคำสั่ง" แทนถอดอิสระอย่างเดียว · บน Pi.

    python -m aipc.spikes.voice_score_eval <โฟลเดอร์เสียง> <ไฟล์ชุด.json ...> --out ผล.json

ต่อเสียงหนึ่งประโยค (ตัวช่วย tools/whisper-score ฟังครั้งเดียว):
1. ถอดอิสระ (greedy · หน้าต่างเสียงพอดีความยาว) → ข้อความ + คะแนน free
2. บังคับขึ้นต้นด้วย "ต้นคำสั่ง" แต่ละตัว (ค้นหา · เข้าลิงก์ · ย้อนกลับ …) แล้วให้ whisper ถอดต่อเอง → ข้อความ + คะแนน
3. แปลข้อความแต่ละแบบด้วยกฎเดิม (aipc.skills.browse) · เลือกแบบที่เป็นคำสั่งเว็บและคะแนนสูงสุด
4. คะแนนห่างจากถอดอิสระไม่เกิน T = เชื่อว่าเป็นคำสั่ง · เกิน = ไม่ใช่คำสั่ง (ไปแชท)
รายงานหลายค่า T · เทียบกับ "ถอดอิสระ + กฎ" บนเสียงชุดเดียวกัน · เสียงสังเคราะห์ = บอกแนวโน้มเท่านั้น
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from aipc.skills import browse
from aipc.voice import stt

HELPER = Path.home() / "voice-bench/score/aipc-whisper-score"

# ต้นคำสั่ง: whisper ถอดต่อเองหลังต้นคำ (คำค้น · ลำดับลิงก์ · คำลงท้าย) แล้วกฎเดิมแปลความหมาย
STEMS = [
    "ค้นหา",
    "หา",
    "ช่วยค้นหา",
    "ช่วยหา",
    "เสิร์ช",
    "ค้น",
    "กูเกิล",
    "เข้าลิงก์",
    "เปิดลิงก์",
    "กดลิงก์",
    "คลิกลิงก์",
    "เข้าเว็บ",
    "กดเว็บ",
    "ย้อนกลับ",
    "กลับไปหน้า",
    "ถอยกลับ",
    "ไปข้างหน้า",
    "เดินหน้า",
    "โหลดใหม่",
    "รีเฟรช",
    "โหลดหน้า",
    "เลื่อนลง",
    "เลื่อนขึ้น",
    "เลื่อนหน้า",
    "ปิดแท็บ",
    "ปิดหน้า",
    "กลับไปแอป",
    "ไปที่แอป",
    "เปิดกูเกิล",
    "เปิดยูทูบ",
    "เปิดเว็บ",
]


class Helper:
    def __init__(self, model: Path, threads: int = 4):
        self.p = subprocess.Popen(
            [str(HELPER), str(model), str(threads)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.ready = json.loads(self.p.stdout.readline())

    def ask(self, wav: Path, pre: list[str]) -> dict:
        lines = [f"WAV {wav}", *(f"PRE {s}" for s in pre), "GO"]
        self.p.stdin.write("\n".join(lines) + "\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())


def meaning(text: str) -> list[dict]:
    return [c.as_dict() for c in browse.parse(stt.clean(text))]


def decide(res: dict, stems: list[str], t: float) -> tuple[list[dict], dict]:
    """คำสั่งที่เลือก ([] = ไม่ใช่คำสั่ง) + รายละเอียด."""
    free_lp = res["free"]
    best = None
    for stem, c in zip(stems, res["cands"], strict=False):
        if c["lp"] is None:
            continue
        m = meaning(c["text"])
        if m and (best is None or c["lp"] > best["lp"]):
            best = {"stem": stem, "text": c["text"], "lp": c["lp"], "meaning": m}
    free_m = meaning(res["text"])
    info = {"free_text": res["text"], "free_lp": free_lp, "free_meaning": free_m, "best": best}
    if best is None:
        return [], info
    info["gap"] = round(free_lp - best["lp"], 2)
    return (best["meaning"] if free_lp - best["lp"] <= t else []), info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio_dir")
    ap.add_argument("sets", nargs="+")
    ap.add_argument("--model", default=str(stt.VOICE_DIR / stt.MODEL))
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    h = Helper(Path(a.model))
    rows = []
    for set_path in a.sets:
        name = Path(set_path).stem
        items = json.loads(Path(set_path).read_text(encoding="utf-8"))["items"]
        for i, it in enumerate(items):
            wav = Path(a.audio_dir) / name / f"{i:02d}-16k.wav"
            t0 = time.monotonic()
            res = h.ask(wav, STEMS)
            secs = round(time.monotonic() - t0, 2)
            rows.append(
                {
                    "set": name,
                    "i": i,
                    "text": it["text"],
                    "expect": it["expect"],
                    "res": res,
                    "seconds": secs,
                }
            )
            print(
                f"{name} {i:02d} {secs:5.2f}s full {res.get('full_ms')}ms "
                f"score {res.get('score_ms')}ms «{res.get('text')}» ← {it['text']}",
                flush=True,
            )
    summary = {}
    for t in (5, 10, 15, 20, 25, 30):
        ok_cmd = n_cmd = caught = n_neg = 0
        for r in rows:
            got, info = decide(r["res"], STEMS, t)
            r.setdefault("decide", {})[str(t)] = {"got": got, **info}
            if r["expect"]:
                n_cmd += 1
                ok_cmd += got == r["expect"]
            else:
                n_neg += 1
                caught += bool(got)
        summary[f"T{t}"] = {
            "commands": f"{ok_cmd}/{n_cmd}",
            "non_commands_caught": f"{caught}/{n_neg}",
        }
    ok_free = sum(meaning(r["res"]["text"]) == r["expect"] for r in rows if r["expect"])
    caught_free = sum(bool(meaning(r["res"]["text"])) for r in rows if not r["expect"])
    summary["free+rules"] = {
        "commands": f"{ok_free}/{sum(1 for r in rows if r['expect'])}",
        "non_commands_caught": f"{caught_free}/{sum(1 for r in rows if not r['expect'])}",
    }
    full = sorted(r["res"].get("full_ms", 0) for r in rows)
    score = sorted(r["res"].get("score_ms", 0) for r in rows)
    summary["full_ms_median"] = full[len(full) // 2]
    summary["score_ms_median"] = score[len(score) // 2]
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if a.out:
        Path(a.out).write_text(
            json.dumps(
                {"summary": summary, "stems": STEMS, "rows": rows}, ensure_ascii=False, indent=1
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
