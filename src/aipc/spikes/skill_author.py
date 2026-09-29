"""วัดว่าใครเขียนสกิล .md ได้: Claude (`claude -p` · พี่ใหญ่) เทียบ AI ในเครื่อง (llama-server บน Pi 5).

ผู้ใช้ถาม 2026-09-30: AI ในเครื่องฉลาดพอจะเขียนสกิลเองไหม หรือต้องให้ Claude เขียน ·
ชุดคำขอ tests/data/skill_authoring.json เขียนและ commit ก่อนวัด (H9)

    # 1) เขียนสกิล · ผู้เขียนทุกตัวใช้ forge.forge ตัวเดียวกัน (แม่แบบคำขอ ตัวตรวจ แก้ได้ 2 รอบ) ต่างกันแค่ใครตอบ
    python -m aipc.spikes.skill_author author --label claude --claude claude --out <โฟลเดอร์>
    python -m aipc.spikes.skill_author author --label typhoon25-4b \
        --server http://127.0.0.1:8080 --out <โฟลเดอร์>
    # 2) ตัดสินด้วยตัวเลือกสกิลของแอปจริง (router.route_ai_first + AI ในเครื่องตัวเดียวกันทุกผู้เขียน)
    python -m aipc.spikes.skill_author route --server http://127.0.0.1:8080 \
        --out <ไฟล์.json> <โฟลเดอร์ผู้เขียน>...

AI ในเครื่องตอบแบบบังคับรูป JSON (response_format json_schema ของ llama-server) · แอปจริงก็จะใช้แบบนี้ ·
Claude ไม่ต้องบังคับ (ตอบ JSON ได้เองจากคำสั่งในแม่แบบ)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

from aipc.skills import catalog, forge, manifest, router
from aipc.spikes import skill_select

REPO = Path(__file__).resolve().parents[3]
DATASET = REPO / "tests" / "data" / "skill_authoring.json"
SELECTION = REPO / "tests" / "data" / "skill_selection.json"
# ค่าเดียวกับตัววัดการเลือกสกิล · ไฟล์สกิล + ประโยคทดสอบ 12 ประโยค ≈ 1,500 token จึงเผื่อ 3,000
SAMPLING = {"temperature": 0.6, "top_p": 0.95, "max_tokens": 3000}
LOCAL_TIMEOUT = 1800
RAW_KEEP = 8000  # 3,000 token ที่ ~4.6 token/วิ ≈ 11 นาที + อ่านคำขอ ~2 นาที
SCHEMA = {
    "type": "object",
    "properties": {
        "skill_md": {"type": "string"},
        "should_trigger": {"type": "array", "items": {"type": "string"}},
        "should_not_trigger": {"type": "array", "items": {"type": "string"}},
        "note": {"type": "string"},
    },
    "required": ["skill_md", "should_trigger", "should_not_trigger", "note"],
}


def local_runner(server: str, label: str, calls: list, opener=urllib.request.urlopen):
    """forge.Runner ที่ถาม llama-server แทน `claude -p` · ห่อคำตอบให้หน้าตาเหมือน JSON ของ claude -p.

    calls: ต่อท้ายเวลา/ตัวเลขของ llama-server ทุกครั้งที่ถาม (ไว้รายงาน)
    """

    def run(args, prompt, cwd, timeout):
        body = {
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "cache_prompt": True,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "skill", "schema": SCHEMA},
            },
            **SAMPLING,
        }
        req = urllib.request.Request(
            server.rstrip("/") + "/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        t0 = time.monotonic()
        try:
            with opener(req, timeout=LOCAL_TIMEOUT) as resp:
                data = json.loads(resp.read())
        except (OSError, ValueError) as e:
            calls.append({"seconds": round(time.monotonic() - t0, 2), "error": str(e)[:300]})
            return 1, "", f"llama-server ล้ม: {e}"
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content") or ""
        calls.append(
            {
                "seconds": round(time.monotonic() - t0, 2),
                "finish": choice.get("finish_reason"),
                "timings": data.get("timings", {}),
                "text": text[:RAW_KEEP],  # คำตอบดิบ ไว้ดูว่าไม่ผ่านตัวตรวจเพราะอะไร
            }
        )
        wrapped = {
            "result": text,
            "is_error": False,
            "total_cost_usd": 0,
            "modelUsage": {label: {}},
        }
        return 0, json.dumps(wrapped, ensure_ascii=False), ""

    return run


def structure(skill_md: str, item: dict) -> tuple[bool, str]:
    """ชนิดสกิลตรงคำขอไหม · สกิลขั้นตอน: ขั้นสั่งเครื่องต้องตรง actions ครบ ไม่ขาดไม่เกิน (ไม่สนลำดับ)."""
    m, errors = forge._validate(skill_md)
    if m is None:
        return False, "ไม่ผ่านตัวตรวจ: " + "; ".join(errors)[:200]
    acting = [s.plan for s in m.steps if s.plan is not None]
    if item["kind"] == "llm":
        if m.worker != "llm" or not m.prompt or acting:
            return (
                False,
                (
                    f"ควรเป็นสกิลงานภาษา (worker {m.worker} · prompt {bool(m.prompt)}"
                    f" · ขั้นสั่งเครื่อง {len(acting)})"
                ),
            )
        return True, ""

    def key(action: str, params: dict) -> str:
        return action + json.dumps(params, sort_keys=True, ensure_ascii=False)

    got = Counter(key(p.action, p.params) for p in acting)
    want = Counter(key(a["action"], a["params"]) for a in item["actions"])
    if got != want:
        return False, f"ขั้นสั่งเครื่องไม่ตรง: ได้ {sorted(got)} · ต้องการ {sorted(want)}"
    return True, ""


def author(items: list[dict], ask, *, label: str, out: Path, claude_version: str = "") -> dict:
    """ให้ผู้เขียน 1 ตัวเขียนสกิลทุกข้อ · ask(request, skills) → forge.Proposal."""
    skills = manifest.load_builtin()
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for it in items:
        t0 = time.monotonic()
        p = ask(it["request"], skills)
        secs = round(time.monotonic() - t0, 2)
        ok_struct, why = structure(p.skill_md, it) if p.skill_md else (False, "ไม่ได้ไฟล์สกิล")
        if p.skill_md:
            (out / f"{it['id']}.md").write_text(p.skill_md, encoding="utf-8", newline="\n")
        row = {
            "id": it["id"],
            "kind": it["kind"],
            "valid": bool(p.skill_md),
            "skill_id": p.skill_id,
            "structure": ok_struct,
            "structure_why": why,
            "attempts": p.attempts,
            "seconds": secs,
            "cost_usd": round(p.cost_usd, 4),
            "errors": p.errors,
            "self_trial_ok": p.ok,
            "note": p.note,
        }
        rows.append(row)
        print(
            f"{label} {it['id']}: {'ผ่านตัวตรวจ' if row['valid'] else 'ไม่ผ่าน'}"
            f" · โครงสร้าง{'ถูก' if ok_struct else 'ผิด'} · {p.attempts} รอบ · {secs} วิ"
            + (f" · {why}" if why else ""),
            flush=True,
        )
    n = len(rows)
    secs = sorted(r["seconds"] for r in rows)
    res = {
        "label": label,
        "claude_version": claude_version,
        "n": n,
        "valid": sum(r["valid"] for r in rows),
        "structure": sum(r["structure"] for r in rows),
        "seconds_median": secs[n // 2] if n else None,
        "seconds_total": round(sum(secs), 1),
        "cost_usd": round(sum(r["cost_usd"] for r in rows), 4),
        "rows": rows,
    }
    (out / "author.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
    )
    return res


def load_new(folder: Path, item: dict, base: list[manifest.Manifest]) -> manifest.Manifest | None:
    """สกิลที่ผู้เขียนเขียนสำหรับข้อนี้ · ไม่มี / ไม่ผ่านตัวตรวจ / id ซ้ำสกิลระบบ = None."""
    md = folder / f"{item['id']}.md"
    if not md.exists():
        return None
    try:
        m = manifest.load(md)
    except manifest.InvalidSkill:
        return None
    return None if m.id in {s.id for s in base} else m


def picker(ai, pool: list[manifest.Manifest]):
    """ตัวเลือกสกิลของแอปจริง (SkillsController.handle): คำสั่งเครื่องทำเลย · ที่เหลือให้ AI เลือก."""
    tools = catalog.tools(pool, {"llm"})
    known = {t["function"]["name"] for t in tools}

    def pick(text: str) -> str:
        r = router.route_ai_first(text, pool)
        if r.skill is not None:
            return r.skill.id
        name = ai(text, tools)["tool"]
        return name if name in known else "none"

    return pick


def route(folder: Path, items: list[dict], ai, base: list[manifest.Manifest]) -> dict:
    rows = []
    for it in items:
        new = load_new(folder, it, base)
        if new is None:
            rows += [
                {"id": it["id"], "text": s, "want": "new", "got": "", "ok": False, "valid": False}
                for s in it["should"]
            ]
            rows += [
                {
                    "id": it["id"],
                    "text": s,
                    "want": "not-new",
                    "got": "",
                    "ok": True,
                    "valid": False,
                }
                for s in it["should_not"]
            ]
            continue
        pick = picker(ai, [*base, new])
        for s in it["should"]:
            got = pick(s)
            rows.append(
                {
                    "id": it["id"],
                    "text": s,
                    "want": "new",
                    "got": got,
                    "ok": got == new.id,
                    "valid": True,
                }
            )
        for s in it["should_not"]:
            got = pick(s)
            rows.append(
                {
                    "id": it["id"],
                    "text": s,
                    "want": "not-new",
                    "got": got,
                    "ok": got != new.id,
                    "valid": True,
                }
            )
    should = [r for r in rows if r["want"] == "new"]
    not_ = [r for r in rows if r["want"] == "not-new"]
    return {
        "should_hit": sum(r["ok"] for r in should),
        "should_total": len(should),
        "should_not_false": sum(not r["ok"] for r in not_),
        "should_not_total": len(not_),
        "rows": rows,
    }


def regression(
    folder: Path, items: list[dict], ai, base: list[manifest.Manifest], sel: list[dict]
) -> dict:
    """ชุดเลือกสกิล 58 ข้อ เมื่อเพิ่มสกิลที่ผ่านตัวตรวจทั้งหมดของผู้เขียนนี้ (id ซ้ำกันเอง = เอาตัวแรก)."""
    added, seen = [], {s.id for s in base}
    for it in items:
        m = load_new(folder, it, base)
        if m is not None and m.id not in seen:
            added.append(m)
            seen.add(m.id)
    res = skill_select.evaluate(sel, [*base, *added], lambda t, tools: ai(t, tools), "ai-first")
    return {
        "added": [m.id for m in added],
        "correct": res["correct"],
        "total": res["total"],
        "false_calls": res["false_calls"],
        "none_total": res["none_total"],
        "rows": [
            {"text": r["text"], "expect": r["expect"], "got": r["got"], "ok": r["ok"]}
            for r in res["rows"]
        ],
    }


def verdict(author_res: dict, route_res: dict, reg: dict, base_reg: dict, crit: dict) -> dict:
    n = author_res["n"]
    before = {r["text"]: r["ok"] for r in base_reg["rows"]}
    lost = [r["text"] for r in reg["rows"] if before.get(r["text"]) and not r["ok"]]
    checks = {
        "valid": author_res["valid"] / n >= crit["valid_min"],
        "structure": author_res["structure"] / n >= crit["structure_min"],
        "should_hit": route_res["should_hit"] / route_res["should_total"] >= crit["should_hit_min"],
        "should_not_false": route_res["should_not_false"] / route_res["should_not_total"]
        <= crit["should_not_false_max"],
        "regression": len(lost) <= crit["regression_lost_max"],
    }
    return {"checks": checks, "pass": all(checks.values()), "regression_lost": lost}


def _machine() -> dict:
    from aipc.bench import machine

    commit, dirty = machine.git_commit(REPO)
    return {
        "board": machine.board_model(),
        "ram_mb": machine.ram_total_mb(),
        "temp_c": machine.cpu_temp_c(),
        "throttled": machine.throttled_raw(),
        "commit": commit,
        "dirty": dirty,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.spikes.skill_author")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("author", help="ให้ผู้เขียน 1 ตัวเขียนสกิลตามชุดคำขอ")
    a.add_argument("--label", required=True)
    a.add_argument("--server", default="", help="llama-server ของ AI ในเครื่อง · ว่าง = ใช้ --claude")
    a.add_argument("--claude", default="", help="คำสั่ง claude (Claude Code)")
    a.add_argument("--model", default=None, help="โมเดลของ Claude · ว่าง = ค่าเริ่มต้นของบัญชี")
    a.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("route", help="ตัดสินสกิลของผู้เขียนแต่ละตัวด้วยตัวเลือกสกิลของแอปจริง")
    r.add_argument("--server", required=True, help="llama-server ของตัวเลือกสกิล (โมเดลของแอป)")
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("folders", type=Path, nargs="+")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    items = data["items"]

    if args.cmd == "author":
        if args.server:
            calls: list = []
            run = local_runner(args.server, args.label, calls)
            version = f"llama-server {args.server}"

            def ask(request, skills):
                return forge.forge(request, skills=skills, runner=run, claude_version=version)
        else:
            claude = shutil.which(args.claude or "claude")
            if claude is None:
                print("ไม่พบคำสั่ง claude", file=sys.stderr)
                return 1
            calls = []
            version = forge.run_process([claude, "--version"], "", ".", 30)[1].strip()

            def ask(request, skills):
                return forge.forge(
                    request, skills=skills, claude=claude, model=args.model, claude_version=version
                )

        res = author(items, ask, label=args.label, out=args.out, claude_version=version)
        res["calls"] = calls
        res["machine"] = _machine()
        (args.out / "author.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
        )
        print(
            f"{args.label}: ผ่านตัวตรวจ {res['valid']}/{res['n']}"
            f" · โครงสร้างถูก {res['structure']}/{res['n']}"
            f" · median {res['seconds_median']} วิ/สกิล · รวม {res['seconds_total']} วิ"
        )
        return 0

    info = skill_select.server_info(args.server)
    if not info["supports_tools"]:
        print("หยุด: chat template ของ server ไม่รับรายการเครื่องมือ", file=sys.stderr)
        return 2

    def ai(text, tools):
        return skill_select.ask_ai(args.server, text, tools)

    base = manifest.load_builtin()
    sel = json.loads(SELECTION.read_text(encoding="utf-8"))["items"]
    out = {"server": info, "machine_start": _machine(), "criteria": data["criteria"], "authors": {}}
    t0 = time.monotonic()
    base_reg = regression(Path("/nonexistent"), [], ai, base, sel)
    out["baseline"] = base_reg
    print(f"ฐาน (ไม่เพิ่มสกิล): ถูก {base_reg['correct']}/{base_reg['total']}", flush=True)
    for folder in args.folders:
        ares = json.loads((folder / "author.json").read_text(encoding="utf-8"))
        rres = route(folder, items, ai, base)
        reg = regression(folder, items, ai, base, sel)
        v = verdict(ares, rres, reg, base_reg, data["criteria"])
        label = ares["label"]
        out["authors"][label] = {
            "author": {
                k: ares[k]
                for k in ("valid", "structure", "n", "seconds_median", "seconds_total", "cost_usd")
            },
            "route": rres,
            "regression": reg,
            "verdict": v,
        }
        print(
            f"{label}: ผ่านตัวตรวจ {ares['valid']}/{ares['n']}"
            f" · โครงสร้างถูก {ares['structure']}/{ares['n']}"
            f" · ควรเรียก {rres['should_hit']}/{rres['should_total']}"
            f" · เรียกผิด {rres['should_not_false']}/{rres['should_not_total']}"
            f" · ชุด 58 ข้อ {reg['correct']}/{reg['total']} (เสีย {len(v['regression_lost'])})"
            f" → {'ผ่าน' if v['pass'] else 'ไม่ผ่าน'}",
            flush=True,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(out, ensure_ascii=False, indent=1, default=str),
            encoding="utf-8",
            newline="\n",
        )
    out["seconds"] = round(time.monotonic() - t0, 1)
    out["machine_end"] = _machine()
    args.out.write_text(
        json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8", newline="\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
