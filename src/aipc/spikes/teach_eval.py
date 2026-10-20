"""การ์ด 0047 เกณฑ์ K1–K8: Claude สอน AI ในเครื่อง · ขับแอปตัวจริง (app_driver) ·
AI ในเครื่อง = llama-server บน Pi 5 (ผ่าน SSH tunnel).

    python -m aipc.spikes.teach_eval --server http://127.0.0.1:18080 --work <โฟลเดอร์>
        --out <ผล.json> [--phase select teach answer volatile unrelated pairs]

ค่าเริ่มต้น = ทุกขั้นตามลำดับ · ผลกลางทางเก็บใน work/state.json (รันต่อจากที่ค้างได้)
ชุดข้อมูล tests/data/teach_eval.json + teach_pairs.json (commit ก่อนเขียนโค้ด · ห้ามแก้) ·
วิธีเลือกหัวข้อในการ์ดหัวข้อ 8
- select: คำถามต้นฉบับ 15 เรื่อง → Claude จริง (คำตอบอ้างอิง + ป้ายหัวข้อ) ·
  AI ในเครื่องที่ไม่มีความรู้ → ผู้ตรวจ · เลือกเรื่องที่ "ผิด/ไม่ครบ" ตามลำดับจนครบ 10
- teach (K1): ทางเดียวกับปุ่มในแอป skills.teach → ใช่ → forge จริง (sonnet เหมือนแอป)
- answer (K2 K3 K4 K7): คำถามแบบอื่น 30 ข้อ (held-out) · Claude "เปิด" แต่ตัดเน็ต
  (ตัวปลอมจดว่าแอปพยายามส่งออกไหม · ไม่ส่งจริง) · เทียบ AI ในเครื่องที่ไม่มีความรู้ (ชุดเดียวกัน)
- volatile (K5): โค้ดปฏิเสธไหม + Claude ตอบ volatile ไหม (แยกรายงาน)
- unrelated (K6): ประโยคไม่เกี่ยว 20 ข้อ เรียกสกิลความรู้ผิดกี่ข้อ
- pairs (K8): ชุด test ของคู่คำถาม (ป้ายหัวข้อจาก Claude จริง + ความคล้ายของตัวอักษร)
ผู้ตรวจ = claude -p (sonnet · ไม่มีเครื่องมือ) ด้วย JUDGE ข้างล่าง (commit ก่อนรัน · ห้ามแก้หลังเห็นผล) ·
ไม่ใช่คนตรวจ → Pakon ตรวจสุ่ม 10 ข้อของ K3 ภายหลัง
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
import time
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / "tests" / "data"
JUDGE = (
    "คุณเป็นผู้ตรวจคำตอบภาษาไทย · เทียบ “คำตอบที่ต้องตรวจ” กับ “คำตอบอ้างอิง” สำหรับคำถามนี้ · "
    'ตอบเป็น JSON object เดียว {"verdict": "ถูก" | "ไม่ครบ" | "ผิด", "why": "<เหตุผลสั้น ๆ>"} · '
    "ถูก = ใจความหลักที่คำถามต้องการตรงกับอ้างอิง และไม่มีข้อเท็จจริงที่ขัดกับอ้างอิง (ไม่ต้องครบทุกรายละเอียด) · "
    "ไม่ครบ = ไม่ขัดกับอ้างอิงแต่ขาดใจความหลักที่คำถามต้องการ · "
    "ผิด = มีข้อเท็จจริงขัดกับอ้างอิง หรือบอกว่าไม่รู้/ไม่ตอบคำถาม · "
    "ห้ามให้คะแนนตามความยาว สำนวน หรือความสุภาพ · คำตอบอ้างอิงอาจตอบกว้างกว่าคำถาม ให้ดูเฉพาะส่วนที่คำถามถาม"
)
TODAY = date.today().isoformat()


def judge(question: str, reference: str, answer: str) -> dict:
    from aipc.cloud import ask
    from aipc.skills import forge

    text = (
        f"คำถาม: {question}\n\nคำตอบอ้างอิง:\n{reference}\n\nคำตอบที่ต้องตรวจ:\n{answer or '(ไม่มีคำตอบ)'}"
    )
    r = ask.ask_plain(JUDGE, text, model="sonnet")
    data = forge.extract_json(r.text) if r.ok else None
    verdict = str((data or {}).get("verdict", "")).strip()
    return {"verdict": verdict if verdict in ("ถูก", "ไม่ครบ", "ผิด") else "ตรวจไม่ได้",
            "why": str((data or {}).get("why", r.error))[:300], "cost": r.cost_usd}  # fmt: skip


class Spy:
    """Claude ที่ "เปิด" แต่เน็ตหลุด: จดว่าแอปพยายามส่งอะไรออก (K4) · ไม่ส่งจริง."""

    def __init__(self):
        self.calls: list[str] = []

    def __call__(self, question, history):
        from aipc.cloud.ask import CloudReply

        self.calls.append(question)
        return CloudReply(False, error="ติดต่อ Claude ไม่ได้ (ตัววัดตัดเน็ต)")


def driver(server: str, work: Path, name: str, skills_dir: Path | None, cloud=None, forge=None):
    from aipc.skills.userskills import UserSkills
    from aipc.spikes.app_driver import AppDriver

    d = AppDriver(server, cloud=cloud, forge=forge, workdir=work / name,
                  user_skills=UserSkills(skills_dir) if skills_dir else None,
                  model_name="gemma-4-E2B")  # fmt: skip
    (work / name).mkdir(parents=True, exist_ok=True)
    d.first_token = None
    d.timings = []
    d.chat._token.connect(lambda _t: d.first_token or setattr(d, "first_token", time.monotonic()))
    d.chat._done.connect(lambda r: d.timings.append(dict(getattr(r, "timings", {}) or {})))
    if not d.wait_ready(600):
        raise SystemExit("AI ในเครื่องไม่พร้อม (เช็ก tunnel / llama-server)")
    return d


def say(d, text: str) -> dict:
    d.first_token, d.timings = None, []
    t0 = time.monotonic()
    t = d.say(text)
    ttft = round(d.first_token - t0, 2) if d.first_token else None
    return {"route": t.route, "text": t.text, "note": t.note, "seconds": t.seconds, "ttft": ttft,
            "prompt_ms": [x.get("prompt_ms") for x in d.timings],
            "skill_prompt": t.skill_prompt[:80]}  # fmt: skip


def knowledge_skills(d) -> dict[str, str]:
    from aipc.skills import knowledge

    return {s.id: s.name for s in d.skills._skills if s.extra.get("kind") == knowledge.KIND}


def phase_select(st, a, data):
    from aipc.cloud import ask

    d = driver(a.server, a.work, "base", None)
    for t in data["topics"]:
        if t["id"] in st["refs"]:
            continue
        ref = ask.ask(t["ask"])
        local = say(d, t["ask"])
        j = (
            judge(t["ask"], ref.text, local["text"])
            if ref.ok
            else {"verdict": "ตรวจไม่ได้", "why": ref.error}
        )
        st["refs"][t["id"]] = {"text": ref.text, "topic": ref.topic, "ok": ref.ok,
                               "cost": ref.cost_usd,
                               "seconds": ref.seconds, "local": local, "judge": j}  # fmt: skip
        print(f"[select] {t['id']} local={j['verdict']} · topic={ref.topic}", flush=True)
        save(st, a)
    poor = ("ไม่ครบ", "ผิด")
    refs = st["refs"]
    picked = [t["id"] for t in data["topics"] if refs[t["id"]]["ok"]
              and refs[t["id"]]["judge"]["verdict"] in poor][:10]  # fmt: skip
    st["selected"] = picked
    print("[select] เลือก", picked, flush=True)


def phase_teach(st, a, data):
    from aipc.ui.app import _skill_forge

    forge = _skill_forge(None, None)
    if forge is None:
        raise SystemExit("ไม่พบ claude หรือปิด AIPC_CLOUD/AIPC_FORGE")
    d = driver(a.server, a.work, "teach", a.work / "skills", forge=forge)
    topics = {t["id"]: t for t in data["topics"]}
    for tid in st["selected"]:
        if tid in st["taught"]:
            continue
        before = set(knowledge_skills(d))
        q, ref = topics[tid]["ask"], st["refs"][tid]["text"]
        card = d.skills.teach(q, ref)
        if not card.get("confirmToken"):
            st["taught"][tid] = {"ok": False, "why": card.get("title", "")}
            continue
        t = d.run_card(lambda c=card: d.skills.confirm(c["confirmToken"], True), q)
        new = sorted(set(knowledge_skills(d)) - before)
        st["taught"][tid] = {"ok": bool(new), "skill": new[0] if new else "",
                             "result": [c.get("title", "") for c in t.cards][-1:],
                             "seconds": t.seconds}  # fmt: skip
        print(f"[teach] {tid} → {new or 'ไม่สำเร็จ'}", flush=True)
        save(st, a)


def phase_answer(st, a, data):
    topics = {t["id"]: t for t in data["topics"]}
    spy = Spy()
    know = driver(a.server, a.work, "know", a.work / "skills", cloud=spy)
    base = driver(a.server, a.work, "base2", None, cloud=Spy())
    names = knowledge_skills(know)
    for tid in st["selected"]:
        skill = st["taught"].get(tid, {}).get("skill", "")
        for q in topics[tid]["held_out"]:
            key = f"{tid}|{q}"
            if key in st["answers"]:
                continue
            n0 = len(spy.calls)
            r = say(know, q)
            r["outbound"] = len(spy.calls) - n0
            r["right_skill"] = bool(skill) and (
                r["route"] == f"skill:{skill}" or r["route"].endswith(":" + names.get(skill, "?"))
            )
            r["judge"] = judge(q, st["refs"][tid]["text"], r["text"])
            b = say(base, q)
            b["judge"] = judge(q, st["refs"][tid]["text"], b["text"])
            st["answers"][key] = {"topic": tid, "q": q, "know": r, "base": b}
            print(f"[answer] {tid} {r['route']} right={r['right_skill']} {r['judge']['verdict']} "
                  f"(ไม่มีความรู้: {b['judge']['verdict']}) ttft={r['ttft']}", flush=True)  # fmt: skip
            save(st, a)


def phase_volatile(st, a, data):
    from aipc.cloud import ask
    from aipc.skills import forge, knowledge, manifest
    from aipc.ui.backend import SkillsController

    s = SkillsController(run_timer=False, llm_ready=lambda: True, claude_on=lambda: True)
    exe = shutil.which("claude")
    for q in data["volatile"]:
        if q in st["volatile"]:
            continue
        code_refused = not s.teach(q, "…").get("confirmToken")
        ref = ask.ask(q)
        pin = {"kind": knowledge.KIND, "worker": "llm", "needs": "llm", "permissions": "",
               "actions": "", "learned": TODAY}  # fmt: skip
        p = forge.forge(knowledge.request(q, ref.text, TODAY), skills=manifest.load_builtin(),
                        claude=exe, model="sonnet", pin=pin)  # fmt: skip
        st["volatile"][q] = {"code_refused": code_refused, "claude_volatile": p.volatile,
                             "made_skill": bool(p.skill_md),
                             "cost": ref.cost_usd + p.cost_usd}  # fmt: skip
        print(
            f"[volatile] {q} code={code_refused} claude={p.volatile} skill={bool(p.skill_md)}",
            flush=True,
        )
        save(st, a)


def phase_unrelated(st, a, data):
    know = driver(a.server, a.work, "know2", a.work / "skills", cloud=Spy())
    names = knowledge_skills(know)
    for q in data["unrelated"]:
        if q in st["unrelated"]:
            continue
        r = say(know, q)
        r["knowledge_hit"] = any(
            r["route"] == f"skill:{k}" or r["route"].endswith(":" + n) for k, n in names.items()
        )
        st["unrelated"][q] = r
        print(f"[unrelated] {q} → {r['route']} hit={r['knowledge_hit']}", flush=True)
        save(st, a)


def phase_pairs(st, a, data):
    from aipc.cloud import ask
    from aipc.skills import knowledge

    pairs = json.loads((DATA / "teach_pairs.json").read_text(encoding="utf-8"))["test"]
    by_q = {t["ask"]: st["refs"][t["id"]]["topic"] for t in data["topics"] if t["id"] in st["refs"]}
    for p in pairs:
        for q in (p["a"], p["b"]):
            if q not in by_q and q not in st["topics"]:
                st["topics"][q] = ask.ask(q).topic
                save(st, a)
    topic = {**by_q, **st["topics"]}
    rows = []
    for p in pairs:
        ta, tb = topic.get(p["a"], ""), topic.get(p["b"], "")
        lexical = knowledge.similarity(p["a"], p["b"]) >= knowledge.SIM_MIN
        tag = bool(ta and tb and knowledge.same_topic(ta, tb))
        hit = bool(knowledge.repeat_of(p["b"], tb, [(p["a"], ta)]))
        rows.append({**p, "topic_a": ta, "topic_b": tb, "lexical": lexical, "tag": tag, "hit": hit})
    st["pairs"] = rows


def save(st, a):
    (a.work / "state.json").write_text(
        json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def count(pairs: list[dict], key: str, same: bool) -> int:
    return sum(p[key] for p in pairs if p["same"] == same)


def summary(st) -> dict:
    ans = list(st["answers"].values())
    kn = [x["know"] for x in ans]
    ttft = [x["ttft"] for x in kn if x["right_skill"] and x["ttft"] is not None]
    vol = list(st["volatile"].values())
    pairs = st.get("pairs", [])
    return {
        "candidates": len(st["refs"]),
        "local_wrong_or_incomplete": sum(
            r["judge"]["verdict"] in ("ไม่ครบ", "ผิด") for r in st["refs"].values()
        ),
        "selected": len(st["selected"]),
        "K1_taught": sum(t.get("ok", False) for t in st["taught"].values()),
        "K2_right_skill": sum(x["right_skill"] for x in kn), "held_out": len(kn),
        "K3_correct_with_knowledge": sum(x["judge"]["verdict"] == "ถูก" for x in kn),
        "K3_correct_without": sum(x["base"]["judge"]["verdict"] == "ถูก" for x in ans),
        "K4_outbound": sum(x["outbound"] for x in kn),
        "K5_made_skill": sum(v["made_skill"] for v in vol),
        "K5_code_refused": sum(v["code_refused"] for v in vol),
        "K5_claude_volatile": sum(v["claude_volatile"] for v in vol), "volatile": len(vol),
        "K6_knowledge_hits": sum(r["knowledge_hit"] for r in st["unrelated"].values()),
        "unrelated": len(st["unrelated"]),
        "K7_ttft_median_s": round(statistics.median(ttft), 2) if ttft else None,
        "K8_same_hit": count(pairs, "hit", True), "K8_diff_hit": count(pairs, "hit", False),
        "K8_lexical_only": [count(pairs, "lexical", True), count(pairs, "lexical", False)],
        "K8_tag_only": [count(pairs, "tag", True), count(pairs, "tag", False)],
    }  # fmt: skip


PHASES = ("select", "teach", "answer", "volatile", "unrelated", "pairs")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--phase", nargs="*", choices=PHASES, default=list(PHASES))
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    a.work.mkdir(parents=True, exist_ok=True)
    path = a.work / "state.json"
    st = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for k in ("refs", "taught", "answers", "volatile", "unrelated", "topics"):
        st.setdefault(k, {})
    st.setdefault("selected", [])
    data = json.loads((DATA / "teach_eval.json").read_text(encoding="utf-8"))
    run = {"select": phase_select, "teach": phase_teach, "answer": phase_answer,
           "volatile": phase_volatile,
           "unrelated": phase_unrelated, "pairs": phase_pairs}  # fmt: skip
    for name in PHASES:
        if name in a.phase:
            run[name](st, a, data)
            save(st, a)
    out = {"summary": summary(st), "state": st}
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
