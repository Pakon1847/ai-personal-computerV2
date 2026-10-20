"""สกิลแบบไฟล์ .md — 1 ไฟล์ = 1 สกิล (ข้อเสนอ 2026-09-29 หัวข้อ 10.1 · ADR-011: สกิลเป็นข้อมูล ไม่ใช่โค้ด).

    ---
    id: start-work
    name: เริ่มวันทำงาน
    description: เปิดอีเมลและลดเสียง สำหรับเริ่มงานตอนเช้า
    keywords: เริ่มงาน, เริ่มวันทำงาน
    examples:
      - เริ่มวันทำงาน
      - เริ่มงานได้เลย
      - เปิดของที่ใช้ทำงาน
    permissions: run_actions
    ---
    # เริ่มวันทำงาน              ← ข้อความนอกสองหัวข้อข้างล่างเป็นคำอธิบายให้คนอ่าน ระบบไม่ใช้

    ## ขั้นตอน                    ← โค้ดทำตามทีละข้อ (ไม่ใช่ให้ AI อ่านแล้วทำ)
    1. เปิดเว็บ gmail
    2. ปรับเสียง 30

    ## คำสั่งให้ AI              ← สกิลงานภาษา (worker: llm) = prompt ที่ส่งให้ AI ในเครื่อง

กติกา:
- ส่วนหัวเป็น "ชื่อ: ค่า" บรรทัดละช่อง · รายการคั่นด้วย , หรือขึ้นบรรทัดใหม่แบบ "- ค่า"
  (examples คั่นด้วย | เพราะตัวอย่างมี , ได้)
- ขั้นตอนต้องเป็นแบบที่รู้จักเท่านั้น (STEP_HELP) · บรรทัดที่ไม่รู้จัก = โหลดไม่ได้ทั้งไฟล์ พร้อมบอกบรรทัด
- เว็บ: ชื่อในรายการ SITES หรือ https://… ที่เขียนตายตัวในไฟล์ (ไม่ประกอบจากข้อความตอนใช้งาน · actions.py ข้อ 3)
- "ถาม AI:" ได้เฉพาะขั้นสุดท้าย · ส่งข้อความที่ผู้ใช้พิมพ์ไปกับคำสั่งนี้ · ผลเป็นข้อความเท่านั้น (H8)
- ขั้นตอนที่สั่งเครื่องต้องขอสิทธิ์ run_actions เอง (ไม่เติมให้ ผู้อนุมัติจะได้เห็นว่าสกิลขออะไร)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from aipc.skills.actions import PAGES, SITES, Plan, app_table

LIST_KEYS = ("keywords", "examples", "needs", "permissions", "actions")
SECTION_STEPS = "ขั้นตอน"
SECTION_PROMPT = "คำสั่งให้ AI"
MAX_STEPS = 10
MAX_URL = 300
STEP_HELP = " · ".join([
    "เปิดเว็บ <ชื่อในรายการ หรือ https://…>", "เปิดแอป <ชื่อ>", "เปิดหน้า <ชื่อ>", "ปรับเสียง <0–100>",
    "เพิ่มเสียง/ลดเสียง <1–100>", "ปิดเสียง", "เปิดเสียง", "ถาม AI: <คำสั่ง>", "บอก: <ข้อความ>",
    "บอกนัดวันนี้ / บอกนัดพรุ่งนี้ / บอกนัดสัปดาห์นี้",
])  # fmt: skip
# ขั้น "บอกนัด…" (การ์ด 0034): โค้ดอ่านนัดในเครื่อง + ปฏิทิน Google · ต้องขอสิทธิ์ read_agenda · สกิลละไม่เกิน 1 ขั้น
AGENDA_STEP = re.compile(r"บอกนัด(วันนี้|พรุ่งนี้|สัปดาห์นี้)")


@dataclass(frozen=True)
class Step:
    kind: str  # action | say | llm | agenda (บอกนัด · การ์ด 0034)
    text: str  # สิ่งที่ผู้ใช้เห็นในการ์ด (หรือคำสั่งให้ AI / ข้อความที่จะบอก)
    plan: Plan | None = None


def _lookup(name: str, table: dict, label=lambda v: v) -> str | None:
    """หา id จากรายการด้วย id หรือชื่อที่แสดง (ไม่สนตัวพิมพ์เล็ก/ใหญ่)."""
    key = name.strip().lower()
    for k, v in table.items():
        if key in (k.lower(), label(v).lower()):
            return k
    return None


def _site(target: str) -> tuple[Step | None, str]:
    if (k := _lookup(target, SITES, lambda v: v[0])) is not None:
        summary = f"เปิด {SITES[k][0]}"
        return Step("action", summary, Plan("open_url", {"site": k}, summary)), ""
    if target.lower().startswith("https://"):
        u = urlsplit(target)
        if len(target) > MAX_URL or not u.hostname or "." not in u.hostname:
            return None, f"URL ไม่ถูกต้อง: {target}"
        if u.username or u.password:
            return None, "URL ห้ามมีชื่อผู้ใช้หรือรหัสผ่าน"
        summary = f"เปิดเว็บ {u.hostname}"
        return Step("action", summary, Plan("open_url", {"url": target}, summary)), ""
    names = ", ".join(v[0] for v in SITES.values())
    return None, f"เว็บต้องเป็นชื่อในรายการ ({names}) หรือขึ้นต้นด้วย https://"


def _app(name: str) -> tuple[Step | None, str]:
    apps = app_table()  # ตารางคงที่ + แอปที่ติดตั้งจริงในเครื่องนี้ (ไฟล์ .desktop)
    k = _lookup(name, apps, lambda v: v[0])
    if k is None:
        want = name.strip().lower().removesuffix(".desktop")
        k = next(
            (a for a, v in apps.items() if want == v[1].lower().removesuffix(".desktop")), None
        )
    if k is None:
        return None, f"ไม่รู้จักแอป “{name}” · แอปที่รู้จัก: " + ", ".join(v[0] for v in apps.values())
    summary = f"เปิด{apps[k][0]}"
    return Step("action", summary, Plan("open_app", {"app": k}, summary)), ""


def _page(name: str) -> tuple[Step | None, str]:
    k = _lookup(name, PAGES)
    if k is None:
        return None, f"ไม่รู้จักหน้า “{name}” · หน้าที่มี: " + ", ".join(PAGES.values())
    summary = f"เปิดหน้า{PAGES[k]}"
    return Step("action", summary, Plan("open_page", {"page": k}, summary)), ""


def parse_step(t: str) -> tuple[Step | None, str]:
    """ขั้นตอน 1 บรรทัด → Step · คืน (None, เหตุผล) ถ้าไม่รู้จักหรือค่าไม่ถูก."""
    if m := re.fullmatch(r"เปิดเว็บ\s+(\S+)", t):
        return _site(m.group(1))
    if m := re.fullmatch(r"เปิดแอป\s*(.+)", t):
        return _app(m.group(1))
    if m := re.fullmatch(r"เปิดหน้า\s*(.+)", t):
        return _page(m.group(1))
    if m := re.fullmatch(r"ปรับเสียง\s*(\d{1,3})\s*%?", t):
        n = int(m.group(1))
        if n > 100:
            return None, "ปรับเสียงได้ 0–100"
        summary = f"ปรับเสียงเป็น {n}%"
        return Step("action", summary, Plan("set_volume", {"percent": n}, summary)), ""
    if m := re.fullmatch(r"(เพิ่ม|ลด)เสียง\s*(\d{1,3})\s*%?", t):
        n = int(m.group(2))
        if not 1 <= n <= 100:
            return None, "เพิ่ม/ลดเสียงได้ 1–100"
        summary = f"{m.group(1)}เสียง {n}%"
        plan = Plan("change_volume", {"step": n if m.group(1) == "เพิ่ม" else -n}, summary)
        return Step("action", summary, plan), ""
    if t in ("ปิดเสียง", "เปิดเสียง"):
        return Step("action", t, Plan("mute" if t == "ปิดเสียง" else "unmute", {}, t)), ""
    if m := re.fullmatch(r"ถาม AI\s*[:：]\s*(.+)", t):
        return Step("llm", m.group(1).strip()), ""
    if m := re.fullmatch(r"บอก\s*[:：]\s*(.+)", t):
        return Step("say", m.group(1).strip()), ""
    if m := AGENDA_STEP.fullmatch(re.sub(r"\s+", "", t)):
        return Step("agenda", f"บอกนัด{m.group(1)}"), ""
    return None, f"ไม่รู้จักขั้นตอน “{t}” · เขียนได้: {STEP_HELP}"


def _front_matter(lines: list[str], errors: list[str]) -> tuple[dict, int]:
    """อ่านส่วนหัวระหว่าง --- สองเส้น · คืน (ข้อมูล, เลขบรรทัดของ --- ปิด)."""
    if not lines or lines[0].strip() != "---":
        errors.append("บรรทัด 1: ไฟล์สกิลต้องขึ้นต้นด้วยส่วนหัวระหว่าง --- สองเส้น")
        return {}, -1
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), -1)
    if end == -1:
        errors.append("ส่วนหัวไม่มี --- ปิด")
        return {}, -1
    data: dict = {}
    current = None
    for n, raw in enumerate(lines[1:end], start=2):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if m := re.fullmatch(r"\s*-\s+(.*)", line):
            if current is None:
                errors.append(f"บรรทัด {n}: รายการ “- …” ต้องอยู่ใต้ชื่อช่องที่เป็นรายการ")
            else:
                data[current].append(m.group(1).strip())
            continue
        m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)", line)
        if not m:
            errors.append(f"บรรทัด {n}: ส่วนหัวต้องเป็นรูป “ชื่อ: ค่า”")
            current = None
            continue
        key, value = m.group(1), m.group(2).strip()
        if key in data:
            errors.append(f"บรรทัด {n}: ช่อง {key} ซ้ำ")
        if key in LIST_KEYS:
            sep = "|" if key == "examples" else ","
            data[key] = [v.strip() for v in value.split(sep) if v.strip()]
            current = key
        else:
            data[key] = value
            current = None
    return data, end


def _sections(lines: list[str], first_line_no: int) -> dict[str, list[tuple[int, str]]]:
    """หัวข้อระดับ ## → บรรทัดในหัวข้อนั้น (พร้อมเลขบรรทัดจริงของไฟล์)."""
    out: dict[str, list[tuple[int, str]]] = {}
    current = None
    for n, line in enumerate(lines, start=first_line_no):
        if m := re.fullmatch(r"##\s+(.+?)\s*", line):
            current = m.group(1)
            out.setdefault(current, [])
        elif re.match(r"#\s", line):
            current = None  # หัวเรื่องระดับ # = คำอธิบาย ไม่ใช่ส่วนที่ระบบใช้
        elif current is not None:
            out[current].append((n, line))
    return out


def parse(text: str) -> tuple[dict, list[str]]:
    """ไฟล์ .md → (ข้อมูลรูปเดียวกับไฟล์ JSON เดิม + "steps", รายการปัญหา) · ปัญหาว่าง = อ่านได้."""
    errors: list[str] = []
    lines = text.splitlines()
    data, end = _front_matter(lines, errors)
    if end == -1:
        return data, errors
    sections = _sections(lines[end + 1 :], end + 2)

    if SECTION_PROMPT in sections:
        if "prompt" in data:
            errors.append("มี prompt ทั้งในส่วนหัวและหัวข้อ “## คำสั่งให้ AI” · ใช้ที่เดียว")
        data["prompt"] = "\n".join(t for _, t in sections[SECTION_PROMPT]).strip()

    steps: list[Step] = []
    for n, line in sections.get(SECTION_STEPS, []):
        if not line.strip():
            continue
        m = re.fullmatch(r"\s*\d+[.)]\s+(.+?)\s*", line)
        if not m:
            errors.append(f"บรรทัด {n}: หัวข้อขั้นตอนต้องเป็นข้อที่มีเลข เช่น “1. เปิดเว็บ gmail”")
            continue
        step, err = parse_step(m.group(1))
        if step is None:
            errors.append(f"บรรทัด {n}: {err}")
        else:
            steps.append(step)
    if SECTION_STEPS in sections:
        if not steps and not errors:
            errors.append("หัวข้อขั้นตอนว่าง")
        if len(steps) > MAX_STEPS:
            errors.append(f"ขั้นตอนมากเกิน {MAX_STEPS} ขั้น")
        if any(s.kind == "llm" for s in steps[:-1]):
            errors.append("“ถาม AI:” ได้เฉพาะขั้นสุดท้าย")
    if steps:
        if "prompt" in data:
            errors.append("สกิลแบบขั้นตอนใช้ “ถาม AI:” เป็นขั้นสุดท้ายแทนหัวข้อ “## คำสั่งให้ AI”")
        uses_llm = steps[-1].kind == "llm"
        data.setdefault("worker", "code+llm" if uses_llm else "code")
        if data["worker"] not in ("code", "code+llm") or (data["worker"] == "code+llm") != uses_llm:
            errors.append("สกิลแบบขั้นตอนใช้ worker: code (หรือ code+llm เมื่อขั้นสุดท้ายเป็น “ถาม AI:”)")
        if uses_llm:
            data["prompt"] = steps[-1].text
            data["needs"] = sorted({*data.get("needs", []), "llm"})
        acts = {s.plan.action for s in steps if s.plan is not None}
        data["actions"] = sorted({*data.get("actions", []), *acts})
        if acts and "run_actions" not in data.get("permissions", []):
            errors.append("ขั้นตอนที่สั่งเครื่องต้องขอสิทธิ์ run_actions (permissions: run_actions)")
        agenda_steps = sum(s.kind == "agenda" for s in steps)
        if agenda_steps and "read_agenda" not in data.get("permissions", []):
            errors.append("ขั้น “บอกนัด…” ต้องขอสิทธิ์ read_agenda (permissions: read_agenda)")
        if agenda_steps > 1:
            errors.append("ขั้น “บอกนัด…” ใช้ได้ครั้งเดียวต่อสกิล")
    data["steps"] = steps
    # สกิลความรู้ (การ์ด 0047): ระบบเติมหัวคงที่หน้าคำสั่งให้ AI (Claude เขียนแทนไม่ได้) ·
    # จำกัดความยาวที่ Claude เขียน (Pi อ่าน prompt ช้า) · ใช้หัวนี้บอกที่มาของคำตอบในแชท (H5)
    from aipc.skills import knowledge

    if data.get("kind") == knowledge.KIND:
        body = str(data.get("prompt", "")).strip()
        if not body:
            errors.append("สกิลความรู้ต้องมีหัวข้อ “## คำสั่งให้ AI” ที่เขียนความรู้ไว้")
        elif len(body) > knowledge.MAX_KNOWLEDGE:
            errors.append(
                f"ความรู้ยาวเกิน {knowledge.MAX_KNOWLEDGE} ตัวอักษร (AI ในเครื่องอ่านช้า) · ย่อให้เหลือใจความ"
            )
        if steps:
            errors.append("สกิลความรู้ไม่มีขั้นตอนสั่งเครื่อง")
        data["prompt"] = knowledge.header(str(data.get("learned", ""))) + body
    # สกิลประจำเว็บ (การ์ด 0046): หัวข้อ "## คำสั่ง" + ช่อง site · คำพูด → กดคีย์ / คลิก ในเว็บนั้น
    from aipc.skills import sitecmd

    if sitecmd.SECTION in sections:
        commands, errs = sitecmd.parse_section(sections[sitecmd.SECTION])
        errors += errs
        data["commands"] = commands
        if steps or data.get("prompt"):
            errors.append("สกิลประจำเว็บใช้หัวข้อ “## คำสั่ง” อย่างเดียว (ไม่มีขั้นตอน/คำสั่งให้ AI)")
        if not data.get("site"):
            errors.append("สกิลที่มีหัวข้อ “## คำสั่ง” ต้องมีช่อง site: <เว็บ>")
        else:
            errors += sitecmd.check_site(data["site"])
        if sitecmd.PERMISSION not in data.get("permissions", []):
            errors.append("สกิลประจำเว็บต้องขอสิทธิ์ page_actions (permissions: page_actions)")
        data.setdefault("worker", "code")
        if not data.get("examples"):  # ตัวอย่าง = คำพูดแรกของคำสั่ง (คนอ่านเห็นว่าพูดอะไรได้)
            data["examples"] = [c.phrases[0] for c in commands][:6]
    elif data.get("site"):
        errors.append("ช่อง site ใช้คู่กับหัวข้อ “## คำสั่ง”")
    return data, errors
