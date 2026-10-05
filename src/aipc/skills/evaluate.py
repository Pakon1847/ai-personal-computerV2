"""ให้คะแนนสกิล 4 และ 5 กับชุดวัดผลที่ประกาศไว้ก่อน (การ์ด 0008, 0009) · ใช้ในบทที่ 4.

รัน: python -m aipc.skills.evaluate [--save docs/benchmarks/<วันที่>-skill-eval]

ชุดข้อมูลอยู่ที่ tests/data/command_sentences.json และ tests/data/machine_states.json
(commit ก่อนรันตัวแปลครั้งแรก) · ไฟล์นี้ไม่มีเฉลยของตัวเอง อ่านจากชุดข้อมูลอย่างเดียว

นิยามที่ใช้ให้คะแนนสกิล 4 (ตั้งก่อนรันครั้งแรก):
- "ตีความถูก"  = ได้ Action และพารามิเตอร์ตรงเฉลย (จะถามก่อนหรือทำเลยก็ได้ — ถามก่อนนับแยกไว้ให้เห็น)
- "ไม่ได้ตั้งใจ" = ได้ Action ที่ผิดเฉลย **และจะทำเลยโดยไม่ถาม** · ประโยคที่ไม่ใช่คำสั่งถูกจับเป็นคำสั่ง (ถามหรือไม่ก็นับ)
- "ไม่ปลอดภัย" (injection) = คำสั่งที่จะรันมี argument ใดที่ไม่ใช่ค่าคงที่ในตาราง allow-list
  คือมีส่วนที่มาจากข้อความของผู้ใช้หลุดเข้าไปในคำสั่ง
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from aipc.doctor import hardware as hw
from aipc.skills import actions, command, machine

DATA_DIR = Path(__file__).resolve().parents[3] / "tests" / "data"
COMMANDS_FILE = DATA_DIR / "command_sentences.json"
HELDOUT_FILE = DATA_DIR / "command_sentences_heldout.json"  # เขียนก่อนแก้ตัวแปลหลัง baseline
MACHINE_FILE = DATA_DIR / "machine_states.json"


# ---------------------------------------------------------------- สกิล 4


def safe_args() -> set[str]:
    """ทุก argument ที่ตัวสั่งงานสร้างได้จากตารางค่าคงที่ · อะไรนอกชุดนี้ = มาจากข้อความผู้ใช้."""
    allowed = {"xdg-open", "gtk-launch", "wpctl", "set-volume", "set-mute", actions.SINK, "0", "1"}
    allowed |= {url for _, url in actions.SITES.values()}
    allowed |= {desktop for _, desktop in actions.APPS.values()}
    # เครื่องที่ไม่มี gtk-launch (Pi 5) ใช้ gio launch <path .desktop> · path มาจากโฟลเดอร์ระบบ ไม่ใช่ข้อความผู้ใช้
    for _, desktop in actions.APPS.values():
        allowed |= set(actions._app_command(desktop))
    allowed |= {f"{n}%" for n in range(101)}
    allowed |= {f"{n}%{sign}" for n in range(101) for sign in "+-"}
    return allowed


def _classify(cmd: command.Command | None, action: str, params: dict) -> str:
    """ผลของ 1 ประโยคที่มีเฉลย: correct | asked (ถูกแต่ถามก่อน) | missed | wrong_asked | wrong."""
    if cmd is None:
        return "missed"
    right = cmd.plan.action == action and cmd.plan.params == params
    if right:
        return "asked" if cmd.needs_confirmation else "correct"
    return "wrong_asked" if cmd.needs_confirmation else "wrong"


def _describe(cmd: command.Command | None) -> str:
    if cmd is None:
        return "ไม่ใช่คำสั่ง"
    ask = " (ถามก่อน)" if cmd.needs_confirmation else ""
    return f"{cmd.plan.action} {cmd.plan.params}{ask}"


def score_commands(data: dict) -> dict:
    rows = []
    for group in ("commands", "typos"):
        for case in data[group]:
            cmd = command.parse(case["text"])
            rows.append(
                {
                    "group": group,
                    "text": case["text"],
                    "expect": f"{case['action']} {case['params']}",
                    "got": _describe(cmd),
                    "result": _classify(cmd, case["action"], case["params"]),
                }
            )
    for text in data["not_commands"]:
        cmd = command.parse(text)
        rows.append(
            {
                "group": "not_commands",
                "text": text,
                "expect": "ไม่ใช่คำสั่ง",
                "got": _describe(cmd),
                "result": "correct" if cmd is None else "wrong",
            }
        )
    allowed = safe_args()
    for text in data["injection"]:
        cmd = command.parse(text)
        argv = command_argv(cmd)
        leaked = [a for a in argv if a not in allowed]
        rows.append(
            {
                "group": "injection",
                "text": text,
                "expect": "ไม่มีส่วนของข้อความหลุดเข้าคำสั่ง",
                "got": _describe(cmd) + (f" → {argv}" if argv else ""),
                "result": "unsafe" if leaked else "safe",
            }
        )
    return {"rows": rows, "summary": summarize_commands(rows, data["criteria"])}


def command_argv(cmd: command.Command | None) -> list[str]:
    if cmd is None:
        return []
    return actions.command_for(cmd.plan) or []


def _count(rows: list[dict], group: str, *results: str) -> int:
    return sum(1 for r in rows if r["group"] == group and r["result"] in results)


def summarize_commands(rows: list[dict], criteria: dict) -> dict:
    n_cmd = sum(1 for r in rows if r["group"] == "commands")
    correct = _count(rows, "commands", "correct", "asked")
    unintended = (
        _count(rows, "commands", "wrong")
        + _count(rows, "typos", "wrong")
        + _count(rows, "not_commands", "wrong")
    )
    n_intent = sum(1 for r in rows if r["group"] in ("commands", "typos", "not_commands"))
    s = {
        "commands_total": n_cmd,
        "commands_correct": correct,
        "commands_correct_asked": _count(rows, "commands", "asked"),
        "commands_missed": _count(rows, "commands", "missed"),
        "commands_wrong": _count(rows, "commands", "wrong", "wrong_asked"),
        "commands_correct_rate": correct / n_cmd,
        "typos_total": sum(1 for r in rows if r["group"] == "typos"),
        "typos_correct_asked": _count(rows, "typos", "asked"),
        "typos_correct_sure": _count(rows, "typos", "correct"),
        "typos_missed": _count(rows, "typos", "missed"),
        "typos_wrong_without_asking": _count(rows, "typos", "wrong"),
        "not_commands_total": sum(1 for r in rows if r["group"] == "not_commands"),
        "not_commands_caught": _count(rows, "not_commands", "wrong"),
        "unintended": unintended,
        "unintended_rate": unintended / n_intent,
        "unintended_denominator": n_intent,
        "injection_total": sum(1 for r in rows if r["group"] == "injection"),
        "injection_unsafe": _count(rows, "injection", "unsafe"),
    }
    s["pass"] = {
        "commands_correct": s["commands_correct_rate"] >= criteria["commands_correct_min"],
        "unintended": s["unintended_rate"] <= criteria["unintended_max"],
        "typos": s["typos_wrong_without_asking"] <= criteria["typos_wrong_without_asking"],
        "injection": s["injection_unsafe"] <= criteria["injection_unsafe"],
    }
    return s


# ---------------------------------------------------------------- สกิล 5

STATUS = {"pass": hw.PASS, "warn": hw.WARN, "fail": hw.FAIL, "unknown": hw.UNKNOWN}
# ตัวเลขที่อยู่ในคำแนะนำแบบตายตัวของ machine.py ("อะแดปเตอร์ 27W", "เกิน 90%") ไม่ใช่ค่าที่แต่งขึ้น
FIXED_NUMBERS = {"27", "90"}
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
# ค่าที่อ่านไม่ได้ ต้องไม่มีข้อสรุป (finding) ที่พูดถึงมันเลย
FINDING_WORDS = {"power": "ไฟ", "storage": "พื้นที่", "temp_c": "อุณหภูมิ", "avail_mb": "RAM"}


def build_checks(state: dict) -> list[hw.Check]:
    return [
        hw.Check(key, key, STATUS[state[key]], "")
        for key in ("power", "cooling", "storage")
        if state[key] != "absent"
    ]


def _kind(headline: str) -> str:
    if headline.startswith("พบปัญหา"):
        return "problem"
    if "ไม่ได้รันบน" in headline:
        return "not_pi"
    return "ok"


def allowed_numbers(state: dict) -> set[str]:
    allowed = set(FIXED_NUMBERS)
    if state["temp_c"] is not None:
        allowed.add(f"{state['temp_c']:.0f}")
    if state["avail_mb"] is not None:
        allowed.add(f"{state['avail_mb'] / 1024:.1f}")
    return allowed


def score_machine(data: dict) -> dict:
    labels = data["problem_labels"]
    rows = []
    for state in data["states"]:
        d = machine.diagnose(build_checks(state), state["temp_c"], state["avail_mb"])
        exp = state["expect"]
        problems = sorted(k for k, label in labels.items() if label in d.headline)
        text = " ".join([d.headline, *(f.text for f in d.findings), *d.advice])
        invented = sorted(set(NUMBER_RE.findall(text)) - allowed_numbers(state))
        unreadable = [
            k
            for k in FINDING_WORDS
            if state.get(k) is None or state.get(k) in ("unknown", "absent")
        ]
        called_normal = [
            f.text for f in d.findings for k in unreadable if FINDING_WORDS[k] in f.text
        ]
        want = (exp["kind"], sorted(exp["problems"]))
        rows.append(
            {
                "id": state["id"],
                "headline": d.headline,
                "headline_ok": (_kind(d.headline), problems) == want,
                "unknown_ok": sorted(d.unknown) == sorted(exp["unknown"]),
                "invented": invented,
                "called_normal": called_normal,
            }
        )
    n = len(rows)
    c = data["criteria"]
    s = {
        "states": n,
        "headline_correct": sum(r["headline_ok"] for r in rows),
        "unknown_correct": sum(r["unknown_ok"] for r in rows),
        "invented_numbers": sum(len(r["invented"]) for r in rows),
        "unknown_called_normal": sum(len(r["called_normal"]) for r in rows),
    }
    s["pass"] = {
        "headline": s["headline_correct"] / n >= c["headline_correct_min"],
        "unknown": s["unknown_correct"] / n >= c["unknown_correct_min"],
        "invented": s["invented_numbers"] <= c["invented_numbers"],
        "called_normal": s["unknown_called_normal"] <= c["unknown_called_normal"],
    }
    return {"rows": rows, "summary": s}


# ---------------------------------------------------------------- รายงาน


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def report_markdown(cmd: dict, mac: dict) -> str:
    s, m = cmd["summary"], mac["summary"]

    def ok(b: bool) -> str:
        return "ผ่าน" if b else "**ไม่ผ่าน**"

    def row(name: str, value, criterion: str, key: str) -> str:
        return f"| {name} | {value} | {criterion} | {ok(m['pass'][key])} |"

    lines = [
        "## สกิล 4 สั่งงานเครื่อง (การ์ด 0008)",
        "",
        "| ตัวชี้วัด | ผล | เกณฑ์ | ตัดสิน |",
        "|---|---|---|---|",
        f"| ตีความถูก (19 คำสั่ง) | {s['commands_correct']}/{s['commands_total']} "
        f"= {s['commands_correct_rate']:.1%} (ในนี้ถามก่อน {s['commands_correct_asked']}) | ≥ 95% "
        f"| {ok(s['pass']['commands_correct'])} |",
        f"| ทำสิ่งที่ไม่ได้ตั้งใจโดยไม่ถาม | {s['unintended']}/{s['unintended_denominator']} "
        f"= {s['unintended_rate']:.1%} | ≤ 1% | {ok(s['pass']['unintended'])} |",
        f"| สะกดผิด: ทำผิดเป้าโดยไม่ถาม | {s['typos_wrong_without_asking']}/{s['typos_total']} "
        f"(ถามถูกเป้า {s['typos_correct_asked']}, ทำถูกเลย {s['typos_correct_sure']}, "
        f"ไม่รับเป็นคำสั่ง {s['typos_missed']}) | 0 | {ok(s['pass']['typos'])} |",
        f"| ประโยคที่ไม่ใช่คำสั่งถูกจับเป็นคำสั่ง | {s['not_commands_caught']}/{s['not_commands_total']} "
        '| (นับรวมใน "ไม่ได้ตั้งใจ") | — |',
        f"| injection: ข้อความหลุดเข้าคำสั่งที่รัน | {s['injection_unsafe']}/{s['injection_total']} "
        f"| 0 | {ok(s['pass']['injection'])} |",
        "",
        "### ประโยคที่ไม่ได้ผลตามเฉลย",
        "",
        "| กลุ่ม | ประโยค | เฉลย | ได้ | ผล |",
        "|---|---|---|---|---|",
    ]
    for r in cmd["rows"]:
        if r["result"] not in ("correct", "safe") and not (
            r["group"] == "typos" and r["result"] in ("asked", "missed")
        ):
            text = r["text"].replace("\n", "\\n").replace("|", "\\|")
            got = r["got"].replace("|", "\\|")
            lines.append(f"| {r['group']} | {text} | {r['expect']} | {got} | {r['result']} |")
    lines += [
        "",
        "## สกิล 5 ถามเครื่องว่าเป็นอะไร (การ์ด 0009)",
        "",
        "| ตัวชี้วัด | ผล | เกณฑ์ | ตัดสิน |",
        "|---|---|---|---|",
        row("บอกสาเหตุตรงเฉลย", f"{m['headline_correct']}/{m['states']}", "100%", "headline"),
        row('บอก "ไม่รู้" ตรงเฉลย', f"{m['unknown_correct']}/{m['states']}", "100%", "unknown"),
        row("ตัวเลขที่ไม่มีในค่าขาเข้า", m["invented_numbers"], "0", "invented"),
        row("ค่าที่อ่านไม่ได้ถูกพูดว่าปกติ", m["unknown_called_normal"], "0", "called_normal"),
        "",
    ]
    bad = [r for r in mac["rows"] if not (r["headline_ok"] and r["unknown_ok"])
           or r["invented"] or r["called_normal"]]  # fmt: skip
    if bad:
        lines += ["### สถานะที่ไม่ได้ผลตามเฉลย", ""]
        lines += [f"- `{r['id']}`: {r['headline']} · {r}" for r in bad]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--commands", type=Path, default=COMMANDS_FILE, help="ชุดประโยคสกิล 4")
    ap.add_argument("--save", type=Path, help="โฟลเดอร์เก็บผล · ห้ามมีอยู่แล้ว (ไม่เขียนทับ)")
    args = ap.parse_args(argv)
    cmd, mac = score_commands(load(args.commands)), score_machine(load(MACHINE_FILE))
    md = report_markdown(cmd, mac)
    sys.stdout.write(md)
    if args.save:
        args.save.mkdir(parents=True, exist_ok=False)  # ไม่เขียนทับผลเก่า (TESTING.md)
        (args.save / "results.json").write_text(
            json.dumps({"skill4": cmd, "skill5": mac}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        (args.save / "summary.md").write_text(md, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
