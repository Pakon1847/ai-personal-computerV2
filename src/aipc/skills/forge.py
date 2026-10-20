"""สร้างสกิลด้วย Claude ("พี่ใหญ่") ผ่าน `claude -p` · ความต้องการของอาจารย์ (ข้อเสนอ 2026-09-29 หัวข้อ 11).

    python -m aipc.skills.forge new "อยากได้สกิลสรุปข้อความเป็นข้อ ๆ" [--model sonnet] [--out โฟลเดอร์]
    python -m aipc.skills.forge install <ไฟล์ .md ที่ได้> --dest <โฟลเดอร์สกิล>

ลำดับ: คำขอ → ประกอบคำขอให้ Claude (แม่แบบ forge_prompt.md + สกิล/เว็บ/แอป/หน้าที่มี) → `claude -p`
      → ไฟล์ .md + ประโยคทดสอบ → ตัวตรวจเดิม (mdskill + manifest)
      → ไม่ผ่าน = ส่งข้อผิดพลาดกลับให้ Claude แก้ (สูงสุด 2 รอบ) → ทดลองเส้นทางกับตัวคัดสกิลจริง
      → รายงานให้คนอ่าน → **ติดตั้งเมื่อคนสั่ง install เท่านั้น**

กติกาความปลอดภัย (แนวคิด LATM: โมเดลใหญ่สร้างเครื่องมือ โมเดลเล็กใช้):
1. Claude เห็นแค่คำขอสร้างสกิล + รายชื่อสกิล/เว็บ/แอป/หน้าที่ระบบมี · ไม่เห็นแชท นัด ไฟล์ หรือข้อมูลผู้ใช้
2. รัน `claude -p` จากโฟลเดอร์ว่าง (ไม่เห็นไฟล์โปรเจกต์) · ปิดเครื่องมือทั้งหมด (`--tools ""`) · ไม่เก็บบทสนทนา ·
   Claude เขียนไฟล์หรือรันคำสั่งบนเครื่องไม่ได้ · โค้ดนี้เป็นคนบันทึกหลังตรวจแล้ว
3. ผลของ Claude = ข้อมูลจากภายนอก → ผ่านตัวตรวจเดียวกับสกิลอื่นทุกข้อ + ทดลองเส้นทาง + คนอนุมัติ (ADR-011 ข้อ 3)
4. บันทึกที่มาในไฟล์: Claude Code รุ่นไหน · โมเดล · วันที่ · คำขอ · สกิลที่แย่งประโยคของสกิลเดิม = ติดตั้งไม่ได้
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from string import Template

from aipc import fsutil
from aipc.skills import manifest, mdskill, router
from aipc.skills.actions import APPS, PAGES, SITES

MAX_ATTEMPTS = 2
TIMEOUT_S = 300
MAX_SKILL_BYTES = 8000
BUDGET_USD = "1.00"  # เพดานต่อครั้ง (--max-budget-usd) · บัญชี subscription ไม่เสียเงินเพิ่ม แต่กันวนไม่รู้จบ

# runner(args, prompt, cwd, timeout) → (รหัสจบ, stdout, stderr) · เทสต์ใส่ตัวปลอมแทนได้ ไม่ต้องต่อเน็ต
Runner = Callable[[list[str], str, str, int], tuple[int, str, str]]


def run_process(args: list[str], prompt: str, cwd: str, timeout: int) -> tuple[int, str, str]:
    try:
        r = subprocess.run(args, input=prompt, capture_output=True, text=True, encoding="utf-8",
                           cwd=cwd, timeout=timeout, check=False)  # fmt: skip
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"หมดเวลา {timeout} วิ"
    except OSError as e:
        return 127, "", str(e)


@dataclass
class Reply:
    ok: bool
    text: str = ""
    error: str = ""
    cost_usd: float = 0.0
    model: str = ""


def ask_claude(prompt: str, *, claude: str, model: str | None, runner: Runner) -> Reply:
    """เรียก `claude -p` แบบข้อความล้วน จากโฟลเดอร์ว่าง · prompt ส่งทาง stdin (ไม่อยู่ใน argv)."""
    args = [claude, "-p", "--output-format", "json", "--tools", "", "--permission-prompts", "none",
            "--no-session-persistence", "--max-budget-usd", BUDGET_USD,
            "--strict-mcp-config", "--disable-slash-commands"]  # fmt: skip
    # --strict-mcp-config --disable-slash-commands: ไม่โหลด MCP/สกิลของบัญชี (การ์ด 0016)
    if model:
        args += ["--model", model]
    with tempfile.TemporaryDirectory(prefix="aipc-forge-") as cwd:
        code, out, err = runner(args, prompt, cwd, TIMEOUT_S)
    try:
        data = json.loads(out)
    except ValueError:
        return Reply(False, error=f"claude -p ล้ม (รหัส {code}): {(err or out)[:300]}")
    models = list((data.get("modelUsage") or {}).keys())
    ok = not data.get("is_error") and code == 0
    cost = float(data.get("total_cost_usd") or 0)
    reply = Reply(ok, text=data.get("result") or "", cost_usd=cost, model=",".join(models))
    if not reply.ok:
        reply.error = f"Claude ตอบไม่สำเร็จ ({data.get('subtype')}): {reply.text[:300]}"
    return reply


def extract_json(text: str) -> dict | None:
    """ผลของ Claude → JSON object (ตัด ``` ออก · ถือเอา { แรกถึง } สุดท้าย)."""
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    i, j = t.find("{"), t.rfind("}")
    if i == -1 or j <= i:
        return None
    try:
        data = json.loads(t[i : j + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


PROMPT_FILE = Path(__file__).parent / "forge_prompt.md"


def build_prompt(request: str, skills: list[manifest.Manifest], fix: list[str] | None = None,
                 previous: str = "") -> str:  # fmt: skip
    """คำขอที่ส่งให้ Claude = แม่แบบ forge_prompt.md + ของที่ระบบมีจริง · ไม่มีข้อมูลผู้ใช้."""
    existing = "\n".join(
        f"- {s.id}: {s.description} · คำสำคัญ: {', '.join(s.keywords) or '—'}" for s in skills
    )
    body = Template(PROMPT_FILE.read_text(encoding="utf-8")).substitute(
        steps=mdskill.STEP_HELP,
        sites=", ".join(f"{k} ({v[0]})" for k, v in SITES.items()),
        apps=", ".join(v[0] for v in APPS.values()),
        pages=", ".join(PAGES.values()),
        perms=", ".join(f"{k} ({v})" for k, v in manifest.PERMISSIONS.items()),
        existing=existing,
    )
    parts = [body.rstrip()]
    if fix:
        parts += [
            "",
            "## รอบก่อนไม่ผ่านตัวตรวจ แก้ให้ผ่าน",
            *[f"- {e}" for e in fix],
            "ไฟล์รอบก่อน:",
            previous,
        ]
    parts += ["", "## คำขอ", "", request.strip()]
    return "\n".join(parts)


@dataclass
class Trial:
    trigger_fail: list[str] = field(default_factory=list)
    not_trigger_fail: list[str] = field(default_factory=list)
    stolen: list[list[str]] = field(default_factory=list)  # [ประโยค, สกิลเดิม] ที่เปลี่ยนไปเป็นสกิลใหม่

    @property
    def ok(self) -> bool:
        return not (self.trigger_fail or self.not_trigger_fail or self.stolen)


def trial(new: manifest.Manifest, skills: list[manifest.Manifest], should: list[str],
          should_not: list[str], extra: list[str] = ()) -> Trial:  # fmt: skip
    """ลองกับตัวคัดสกิลจริง (มี AI) · ประโยคของสกิลเดิมต้องไปที่เดิมหลังเพิ่มสกิลใหม่."""
    avail = {"llm"}

    def pick(text: str, pool) -> str:
        r = router.route(text, pool, avail)
        return r.skill.id if r.skill else ""

    pool = [*skills, new]
    t = Trial()
    if new.site:  # สกิลประจำเว็บ (การ์ด 0046) ไม่เข้าตัวคัดสกิล (ทางเข้า = คำพูดในเว็บนั้น) จึงไม่แย่งและไม่ถูกเรียก
        return t
    t.trigger_fail = [s for s in [*new.examples, *should] if pick(s, pool) != new.id]
    t.not_trigger_fail = [s for s in should_not if pick(s, pool) == new.id]
    for s in [*(e for k in skills for e in k.examples), *extra]:
        before = pick(s, skills)
        if before != new.id and pick(s, pool) == new.id:
            t.stolen.append([s, before or "คุยทั่วไป"])
    return t


def stamp(skill_md: str, *, request: str, claude_version: str, model: str, today: date) -> str:
    """เขียนที่มาลงส่วนหัว (แทน author/created/request เดิมถ้า Claude ใส่มา)."""
    lines = skill_md.strip("\n").split("\n")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), -1)
    if not lines or lines[0].strip() != "---" or end == -1:
        return skill_md
    keep = [x for x in lines[1:end] if not re.match(r"(author|created|request|generator)\s*:", x)]
    one_line = " ".join(request.split())[:200]
    meta = [
        f"author: Claude (พี่ใหญ่) · {model or 'ไม่ทราบรุ่น'}",
        f"generator: claude -p · {claude_version}",
        f"created: {today.isoformat()}",
        f"request: {one_line}",
    ]
    return "\n".join(["---", *keep, *meta, *lines[end:]]) + "\n"


# ส่วนหัวเรื่องสิทธิ์ (การ์ด 0043): ระบบเป็นคนกำหนด ไม่ใช่ Claude (H7) · สกิลในเครื่องที่ Claude เขียนใหม่ใช้ค่าเดิมเสมอ
PINNED_KEYS = ("id", "worker", "needs", "permissions", "actions")


def pin_header(skill_md: str, fixed: dict[str, str]) -> tuple[str, list[str]]:
    """แทนส่วนหัวตาม fixed (ค่า "" = ลบบรรทัดนั้น) · คืน (ไฟล์ใหม่, คีย์ที่ Claude ใส่ต่างจากระบบ)."""
    lines = skill_md.strip("\n").split("\n")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), -1)
    if not lines or lines[0].strip() != "---" or end == -1:
        return skill_md, []
    head = lines[1:end]
    changed = []
    for key, value in fixed.items():
        rows = [i for i, x in enumerate(head) if re.match(rf"{key}\s*:", x)]
        got = head[rows[0]].split(":", 1)[1].strip() if rows else ""
        if got != value:
            changed.append(key)
        for i in reversed(rows):
            del head[i]
        if value:
            head.insert(0 if key == "id" else len(head), f"{key}: {value}")
    return "\n".join(["---", *head, *lines[end:]]) + "\n", changed


@dataclass
class Proposal:
    ok: bool
    request: str
    skill_md: str = ""
    skill_id: str = ""
    errors: list[str] = field(default_factory=list)
    trial: dict = field(default_factory=dict)
    note: str = ""
    attempts: int = 0
    cost_usd: float = 0.0
    model: str = ""
    claude_version: str = ""
    pinned_changed: list[str] = field(default_factory=list)  # คีย์สิทธิ์ที่ Claude ใส่ต่างไป (ระบบแทนแล้ว)
    volatile: bool = False  # Claude บอกว่าเรื่องนี้เปลี่ยนตามเวลา จึงไม่สร้างสกิลความรู้ (การ์ด 0047)


def _validate(skill_md: str) -> tuple[manifest.Manifest | None, list[str]]:
    if len(skill_md.encode("utf-8")) > MAX_SKILL_BYTES:
        return None, [f"ไฟล์สกิลใหญ่เกิน {MAX_SKILL_BYTES} ไบต์"]
    with tempfile.TemporaryDirectory(prefix="aipc-forge-check-") as d:
        p = Path(d) / "skill.md"
        p.write_text(skill_md, encoding="utf-8")
        try:
            return manifest.load(p), []
        except manifest.InvalidSkill as e:
            return None, [x.removeprefix("skill.md: ") for x in e.errors]


def forge(request: str, *, skills: list[manifest.Manifest], runner: Runner = run_process,
          claude: str = "claude", model: str | None = None, claude_version: str = "",
          today: date | None = None, extra_sentences: list[str] = (),
          revise: tuple[str, str] | None = None,
          check: Callable[[str], list[str]] | None = None,
          pin: dict[str, str] | None = None) -> Proposal:  # fmt: skip
    """revise = (ไฟล์รุ่นที่ใช้อยู่, คำติของผู้ใช้) → รุ่นใหม่ id เดิม (การ์ด 0017 ชั้นที่ 2) · skills ต้องไม่มีสกิลตัวที่แก้."""
    p = Proposal(False, request, claude_version=claude_version)
    fix: list[str] = []
    previous = ""
    revise_id = ""
    if revise is not None:
        previous = revise[0]
        old, _ = _validate(previous)
        revise_id = old.id if old is not None else ""
        fix = [f"ผู้ใช้ใช้สกิลนี้แล้วบอกว่าไม่ถูก: “{' '.join(revise[1].split())[:300]}” · "
               "แก้ให้ตรงกับที่ผู้ใช้ต้องการ · ใช้ id เดิม"]  # fmt: skip
    ids = {s.id for s in skills}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        p.attempts = attempt
        reply = ask_claude(build_prompt(request, skills, fix, previous), claude=claude, model=model,
                           runner=runner)  # fmt: skip
        p.cost_usd += reply.cost_usd
        p.model = reply.model or p.model
        if not reply.ok:
            p.errors = [reply.error]
            return p
        data = extract_json(reply.text)
        # การ์ด 0047: Claude บอกว่าเรื่องนี้เปลี่ยนตามเวลา = ไม่สร้างสกิลความรู้ · ไม่ให้แก้ซ้ำ
        if data is not None and data.get("volatile") is True:
            p.volatile = True
            p.errors = ["เรื่องนี้เปลี่ยนตามเวลา จึงไม่จำไว้ในเครื่อง · " + str(data.get("note", ""))[:200]]
            return p
        if data is None or not isinstance(data.get("skill_md"), str):
            fix, previous = ["ตอบกลับต้องเป็น JSON object ที่มี skill_md เป็นข้อความ"], reply.text[:2000]
            p.errors = fix
            continue
        previous = data["skill_md"]
        if pin is not None:  # การ์ด 0043: ส่วนหัวเรื่องสิทธิ์ = ค่าของระบบ
            previous, changed = pin_header(previous, pin)
            p.pinned_changed = sorted(set(p.pinned_changed) | set(changed))
        new, errors = _validate(previous)
        if new is not None and revise_id and new.id != revise_id:
            # รุ่นแก้ต้องเป็นสกิลเดิม: Claude ตั้ง id ใหม่เอง (พบบน Pi 5
            # · work-mode → open-terminal-help) → ใช้ id เดิม
            previous = re.sub(r"(?m)^id:\s*\S+", f"id: {revise_id}", previous, count=1)
            new, errors = _validate(previous)
        if new is not None and new.id in ids:
            new, errors = None, [f"id {new.id} ซ้ำกับสกิลที่มีอยู่"]
        if new is None:
            fix = p.errors = errors
            continue
        if check is not None and (
            errors := check(previous)
        ):  # ประตูของผู้เรียก (สกิลอัตโนมัติ · การ์ด 0017)
            fix = p.errors = errors
            continue
        should = [s for s in data.get("should_trigger", []) if isinstance(s, str)]
        should_not = [s for s in data.get("should_not_trigger", []) if isinstance(s, str)]
        t = trial(new, skills, should, should_not, extra_sentences)
        p.skill_md = stamp(previous, request=request, claude_version=claude_version, model=p.model,
                           today=today or date.today())  # fmt: skip
        p.skill_id, p.note, p.errors = new.id, str(data.get("note", ""))[:500], []
        p.trial = {**asdict(t), "should_trigger": should, "should_not_trigger": should_not}
        p.ok = t.ok
        # อัตโนมัติ: เรียกผิด/แย่งประโยค = ให้ Claude แก้อีกรอบ · "ควรเรียกแต่ไม่เรียก" ไม่แก้ (วัดด้วยตัวคัดแบบกฎ
        # แต่ในแอป AI เลือกจากคำอธิบาย · สกิลดีของ Claude เช่น ตัวอย่าง "meeting mode" กฎจับไม่ได้
        # ไม่ใช่เรื่องความปลอดภัย)
        if (t.not_trigger_fail or t.stolen) and check is not None and attempt < MAX_ATTEMPTS:
            fix = p.errors = [f"ประโยคนี้ไม่ควรเรียกสกิลใหม่แต่เรียก: {x}" for x in t.not_trigger_fail] + [
                f"แย่งประโยคของสกิลเดิม: {x} (เดิมคือ {k})" for x, k in t.stolen
            ]
            continue
        return p
    return p


def save(p: Proposal, out: Path) -> Path:
    """เก็บข้อเสนอไว้ให้คนอ่าน (ยังไม่ติดตั้ง): <id>.md + <id>.report.json."""
    out.mkdir(parents=True, exist_ok=True)
    name = p.skill_id or "failed-" + date.today().isoformat()
    md = out / f"{name}.md"
    if p.skill_md:
        md.write_text(p.skill_md, encoding="utf-8", newline="\n")
    fsutil.write_json(out / f"{name}.report.json", asdict(p), mode=0o644)
    return md


def install(
    md: Path, dest: Path, skills: list[manifest.Manifest], force: bool = False
) -> manifest.Manifest:
    """ติดตั้งเมื่อคนสั่งเท่านั้น · ตรวจซ้ำทุกครั้ง.

    id ซ้ำ หรือแย่งประโยคของสกิลเดิม = ไม่ติดตั้ง (เว้นแต่ --force)
    """
    new = manifest.load(md)
    if new.id in {s.id for s in skills}:
        raise manifest.InvalidSkill([f"มีสกิล id {new.id} อยู่แล้ว"])
    t = trial(new, skills, [], [])
    if t.stolen and not force:
        raise manifest.InvalidSkill([f"แย่งประโยคของสกิลเดิม: {s} (เดิมคือ {k})" for s, k in t.stolen])
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"{new.id}.md"
    tmp = target.with_suffix(".md.tmp")
    tmp.write_text(md.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    os.replace(tmp, target)
    return new


def report(p: Proposal, path: Path | None = None) -> str:
    """สรุปภาษาไทยให้ผู้ดูแลอ่านก่อนตัดสินใจติดตั้ง."""
    out = [f"คำขอ: {p.request}"]
    if not p.skill_md:
        out += ["สร้างไม่สำเร็จ:", *[f"  - {e}" for e in p.errors]]
    else:
        new, _ = _validate(p.skill_md)
        needs = ", ".join(new.needs) or "—"
        perms = ", ".join(new.permission_labels()) or "—"
        out += [f"สกิล: {new.name} ({new.id}) · worker {new.worker} · ต้องใช้: {needs} · สิทธิ์: {perms}",
                f"คำอธิบาย: {new.description}"]  # fmt: skip
        if new.steps:
            out += ["ขั้นตอน:", *[f"  {i}. {s.text}" for i, s in enumerate(new.steps, 1)]]
        elif new.prompt:
            out += [f"คำสั่งให้ AI: {new.prompt}"]
        t = p.trial
        n_should = len(new.examples) + len(t["should_trigger"])
        hit = n_should - len(t["trigger_fail"])
        n_not = len(t["should_not_trigger"])
        miss = n_not - len(t["not_trigger_fail"])
        out += [f"ทดลองเส้นทาง: ควรเรียก {hit}/{n_should} · ไม่ควรเรียก {miss}/{n_not} · "
                f"แย่งประโยคของสกิลเดิม {len(t['stolen'])}"]  # fmt: skip
        out += [f"  เรียกไม่ถึง: {s}" for s in t["trigger_fail"]]
        out += [f"  เรียกผิด: {s}" for s in t["not_trigger_fail"]]
        out += [f"  แย่ง: {s} (เดิมคือ {k})" for s, k in t["stolen"]]
        if p.note:
            out.append(f"Claude อธิบาย: {p.note}")
        out.append("พร้อมติดตั้ง" if p.ok else "ยังไม่ควรติดตั้ง (ดูข้อที่ไม่ผ่านข้างบน)")
    out.append(f"ที่มา: {p.claude_version or 'Claude Code'} · {p.model or '—'} · {p.attempts} รอบ · "
               f"~{p.cost_usd:.3f} USD (ราคาอ้างอิง)")  # fmt: skip
    if path is not None:
        out.append(f"บันทึกข้อเสนอไว้ที่ {path} · **ยังไม่ได้ติดตั้ง**")
    return "\n".join(out)


def default_out() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "aipc" / "skill-proposals"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m aipc.skills.forge", description=__doc__.splitlines()[0]
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new", help="ให้ Claude สร้างสกิลจากคำขอ (ยังไม่ติดตั้ง)")
    n.add_argument("request")
    n.add_argument("--model", default=None)
    n.add_argument("--out", type=Path, default=None)
    i = sub.add_parser("install", help="ติดตั้งข้อเสนอที่อ่านแล้ว")
    i.add_argument("file", type=Path)
    i.add_argument("--dest", type=Path, required=True)
    i.add_argument("--force", action="store_true", help="ติดตั้งแม้แย่งประโยคของสกิลเดิม (ไม่แนะนำ)")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    skills = manifest.load_builtin()
    if a.cmd == "install":
        try:
            new = install(a.file, a.dest, skills, force=a.force)
        except manifest.InvalidSkill as e:
            print("ติดตั้งไม่ได้:", *e.errors, sep="\n  - ")
            return 1
        print(f"ติดตั้งแล้ว: {new.name} ({new.id}) → {a.dest}")
        return 0
    claude = shutil.which("claude")
    if claude is None:
        print("ไม่พบคำสั่ง claude (ติดตั้ง Claude Code และเข้าสู่ระบบก่อน)")
        return 1
    version = run_process([claude, "--version"], "", ".", 30)[1].strip()
    p = forge(a.request, skills=skills, claude=claude, model=a.model, claude_version=version)
    path = save(p, a.out or default_out())
    print(report(p, path))
    return 0 if p.ok else 1


if __name__ == "__main__":
    sys.exit(main())
