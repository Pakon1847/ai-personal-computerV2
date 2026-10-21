"""การ์ด 0049 เกณฑ์ P1 P3: เวลาถึงคำแรก + AI เรียกสกิลของผู้ใช้ถูกไหม · ขับแอปตัวจริง ·
llama-server บน Pi 5 (ผ่าน SSH tunnel).

    python -m aipc.spikes.prompt_cache_eval --server http://127.0.0.1:18080
        --skills 9|30|0 --out ผล.json

ชุด tests/data/prompt_cache_eval.json (commit ก่อนเขียนโค้ด) ·
สกิลของผู้ใช้ 9 = tests/data/user_skills_knowledge · 30 = 9 + 21 ไฟล์แรกของ
docs/benchmarks/2026-10-01-retrieval/skills · ไม่มี Claude (ไม่มีอะไรออกนอกเครื่อง)
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tests" / "data"
LIBRARY = ROOT / "docs" / "benchmarks" / "2026-10-01-retrieval" / "skills"


def skills_dir(n: int) -> Path | None:
    if n == 0:
        return None
    d = Path(tempfile.mkdtemp(prefix="aipc-pc-skills-"))
    for f in sorted((DATA / "user_skills_knowledge").glob("*.md")):
        shutil.copy(f, d / f.name)
    if n == 30:
        for f in sorted(LIBRARY.glob("*.md"))[:21]:
            shutil.copy(f, d / f.name)
    return d


def main(argv: list[str] | None = None) -> int:
    from aipc.skills.userskills import UserSkills
    from aipc.spikes.app_driver import AppDriver

    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True)
    ap.add_argument("--skills", type=int, choices=(0, 9, 30), default=9)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    data = json.loads((DATA / "prompt_cache_eval.json").read_text(encoding="utf-8"))
    sd = skills_dir(a.skills)
    work = Path(tempfile.mkdtemp(prefix="aipc-pc-"))
    store = UserSkills(sd) if sd else None
    d = AppDriver(a.server, workdir=work, user_skills=store, model_name="gemma-4-E2B")
    state = {"first": None, "timings": []}
    d.chat._token.connect(lambda _t: state["first"] or state.update(first=time.monotonic()))
    d.chat._done.connect(lambda r: state["timings"].append(dict(getattr(r, "timings", {}) or {})))
    if not d.wait_ready(900):
        raise SystemExit("AI ในเครื่องไม่พร้อม")
    user = [s for s in d.skills._skills if d.skills._is_user(s.id)]
    names = {s.id: s.name for s in user}
    print(f"สกิลของผู้ใช้ {len(user)} ตัว", flush=True)

    def say(text: str) -> dict:
        state["first"], state["timings"] = None, []
        t0 = time.monotonic()
        t = d.say(text)
        ttft = round(state["first"] - t0, 2) if state["first"] else None
        return {"text": text, "route": t.route, "ttft": ttft, "seconds": t.seconds,
                "prompt_n": [x.get("prompt_n") for x in state["timings"]],
                "cache_n": [x.get("cache_n") for x in state["timings"]]}  # fmt: skip

    p1 = []
    for text in data["p1"]:
        r = say(text)
        p1.append(r)
        print(f"[p1] {text} → {r['route']} ttft={r['ttft']} prompt_n={r['prompt_n']}", flush=True)
    p3 = []
    for item in data["p3"]:
        r = say(item["text"])
        exp = item["expect"]
        r["expect"] = exp
        r["hit"] = r["route"] == f"skill:{exp}" or r["route"].endswith(":" + names.get(exp, "?"))
        p3.append(r)
        print(f"[p3] {item['text']} → {r['route']} hit={r['hit']}", flush=True)
    ttft = [r["ttft"] for r in p1 if r["ttft"] is not None]
    med = round(statistics.median(ttft), 2) if ttft else None
    summary = {"user_skills": len(user), "p1_ttft_median": med, "p1_n": len(p1),
               "p3_hit": sum(r["hit"] for r in p3), "p3_n": len(p3)}  # fmt: skip
    out = json.dumps({"summary": summary, "p1": p1, "p3": p3}, ensure_ascii=False, indent=1)
    a.out.write_text(out + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
