"""วัดการ์ด 0018 (ส่งเฉพาะสกิลที่เกี่ยวข้อง) ตามเกณฑ์ข้อ 4.

    python -m aipc.spikes.retrieval_eval build --out docs/benchmarks/2026-10-01-retrieval
    python -m aipc.spikes.retrieval_eval eval --out docs/benchmarks/2026-10-01-retrieval

build: (1) Claude เขียนคำขอสร้างสกิล 45 ข้อ (ไม่เห็นตัวค้น) (2) Claude สร้างสกิลจริงทีละข้อผ่านประตู 0017 → คลังสกิล
(3) Claude เขียนประโยคเรียกใช้ 2 ประโยคต่อสกิล (เห็นแค่ชื่อ+คำอธิบายสกิล ไม่เห็นตัวค้น) · เก็บทุกอย่างเป็นไฟล์ก่อนวัด
eval: Recall@5 ของสกิลที่ถูก · ขนาด prompt (token โดยประมาณจากความยาว) · เวลาเลือก
เกณฑ์ (ประกาศก่อนสร้าง · การ์ด 0018 ข้อ 4): คลัง ≥ 40 · ประโยค ≥ 60 · Recall@5 ≥ 95% · เลือก ≤ 20 ms
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from aipc.cloud.ask import find_claude
from aipc.skills import forge, manifest, retrieval, userskills

ASK_REQUESTS = """ช่วยเขียนคำขอภาษาไทย 45 ข้อ ที่ผู้ใช้คอมพิวเตอร์ส่วนตัว (Raspberry Pi)
จะพิมพ์ขอให้ระบบ "สร้างสกิลใหม่" ไว้ใช้ซ้ำ
สกิลทำได้ 2 แบบ: (ก) สั่งเครื่องหลายขั้น: เปิดเว็บ YouTube Gmail Google Wikipedia Google Maps ·
เปิดแอปเบราว์เซอร์ ตัวจัดการไฟล์ · ปรับ/เพิ่ม/ลด/ปิด/เปิดเสียง · เปิดหน้าในแอป (ไฟล์ของฉัน ตั้งค่า สุขภาพเครื่อง Skill)
(ข) งานภาษาที่ AI ทำ (เขียน แต่ง อธิบาย ตรวจ คิดไอเดีย)
ห้ามซ้ำกับของที่มีแล้ว: แปลไทย-อังกฤษ สรุปข้อความ เขียนจดหมาย/อีเมล จดนัดเตือน ดูสถานะเครื่อง
หลากหลายผู้ใช้ (นักเรียน ผู้สูงอายุ แม่ค้า พนักงาน ครู) · แบบ (ก) ประมาณ 20 ข้อ แบบ (ข) ประมาณ 25 ข้อ · ห้ามซ้ำกันเอง
ตอบเป็น JSON อย่างเดียว: {"items": ["คำขอ 1", "คำขอ 2", ...]}"""

ASK_SENTENCES = """ด้านล่างคือสกิลในคอมพิวเตอร์ส่วนตัว (ชื่อ: คำอธิบาย)
ช่วยเขียนประโยคภาษาไทยที่ผู้ใช้จะพิมพ์เพื่อ "ใช้งาน" แต่ละสกิล
สกิลละ 2 ประโยค สำนวนต่างกัน ภาษาพูด เหมือนคนจริง · ห้ามลอกชื่อสกิลตรง ๆ ทั้งประโยค
ตอบเป็น JSON อย่างเดียว: {"items": [{"id": "id ของสกิล", "text": "ประโยค"}]}

"""


def claude_json(prompt: str, exe: str) -> dict:
    r = forge.ask_claude(prompt, claude=exe, model="sonnet", runner=forge.run_process)
    data = forge.extract_json(r.text) if r.ok else None
    if data is None:
        raise SystemExit(f"Claude ตอบไม่เป็น JSON: {r.error or r.text[:300]}")
    return {**data, "_cost": r.cost_usd}


def build(out: Path) -> int:
    exe = find_claude()
    if exe is None:
        raise SystemExit("ไม่มี claude")
    out.mkdir(parents=True, exist_ok=True)
    reqs_file = out / "requests.json"
    if not reqs_file.exists():
        d = claude_json(ASK_REQUESTS, exe)
        reqs_file.write_text(
            json.dumps({"prompt": ASK_REQUESTS, **d}, ensure_ascii=False, indent=1), "utf-8"
        )
    reqs = json.loads(reqs_file.read_text("utf-8"))["items"]
    builtin = manifest.load_builtin()
    store = userskills.UserSkills(out / "skills")
    log_file = out / "build-log.json"
    log = json.loads(log_file.read_text("utf-8")) if log_file.exists() else []
    done = {x["request"] for x in log}
    version = forge.run_process([exe, "--version"], "", ".", 30)[1].strip()
    for req in reqs:
        if req in done:
            continue
        skills = builtin + store.load()
        t0 = time.monotonic()
        p = forge.forge(
            req,
            skills=skills,
            claude=exe,
            model="sonnet",
            claude_version=version,
            check=lambda md, s=skills: userskills.gate(md, s)[1],
        )
        row = {"request": req, "cost": round(p.cost_usd, 4), "s": round(time.monotonic() - t0, 1)}
        try:
            m = store.install(p.skill_md, skills, request=req, model=p.model, cost_usd=p.cost_usd)
            row.update(ok=True, id=m.id)
        except manifest.InvalidSkill as e:
            row.update(ok=False, errors=(p.errors or e.errors)[:2])
        log.append(row)
        log_file.write_text(json.dumps(log, ensure_ascii=False, indent=1), "utf-8")
        print(
            f"{'✓' if row['ok'] else '✗'} {row.get('id', '')} {row['s']}s "
            f"${row['cost']} · {req[:50]}",
            flush=True,
        )
    sent_file = out / "sentences.json"
    if not sent_file.exists():
        pool = store.load()
        listing = "\n".join(f"- {s.id}: {s.name} · {s.description}" for s in pool)
        d = claude_json(ASK_SENTENCES + listing, exe)
        sent_file.write_text(
            json.dumps({"prompt": ASK_SENTENCES + listing, **d}, ensure_ascii=False, indent=1),
            "utf-8",
        )
    print(
        "คลัง", len(store.load()), "· ประโยค", len(json.loads(sent_file.read_text("utf-8"))["items"])
    )
    return 0


def evaluate(out: Path) -> int:
    pool = userskills.UserSkills(out / "skills").load()
    ids = {s.id for s in pool}
    sents = [
        x
        for x in json.loads((out / "sentences.json").read_text("utf-8"))["items"]
        if x.get("id") in ids
    ]
    rows, secs = [], []
    for x in sents:
        t0 = time.perf_counter()
        got = [s.id for s in retrieval.pick(pool, x["text"])]
        secs.append((time.perf_counter() - t0) * 1000)
        rows.append(
            {
                **x,
                "top5": got,
                "hit": x["id"] in got,
                "rank": got.index(x["id"]) + 1 if x["id"] in got else None,
            }
        )
    hit = sum(r["hit"] for r in rows)
    tool_chars_all = sum(len(json.dumps(t, ensure_ascii=False)) for t in _tools(pool))
    tool_chars_k = statistics.median(
        sum(len(json.dumps(t, ensure_ascii=False)) for t in _tools(retrieval.pick(pool, x["text"])))
        for x in sents
    )
    summary = {
        "pool": len(pool),
        "sentences": len(rows),
        "recall_at_5": [hit, len(rows)],
        "pick_ms_median": round(statistics.median(secs), 2),
        "pick_ms_max": round(max(secs), 2),
        "user_tool_chars_all": tool_chars_all,
        "user_tool_chars_top5_median": tool_chars_k,
    }
    ok = (
        len(pool) >= 40
        and len(rows) >= 60
        and hit / len(rows) >= 0.95
        and summary["pick_ms_max"] <= 20
    )
    print(json.dumps(summary, ensure_ascii=False), "→", "ผ่าน" if ok else "ไม่ผ่าน")
    for r in rows:
        if not r["hit"]:
            print("  พลาด:", r["id"], "·", r["text"], "→", r["top5"])
    (out / "eval.json").write_text(
        json.dumps({"summary": summary, "passed": ok, "rows": rows}, ensure_ascii=False, indent=1),
        "utf-8",
    )
    return 0


def _tools(skills):
    from aipc.skills import catalog

    return catalog.tools(skills, {"llm"})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("step", choices=["build", "eval"])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    return build(a.out) if a.step == "build" else evaluate(a.out)


if __name__ == "__main__":
    sys.exit(main())
