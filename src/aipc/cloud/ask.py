"""ถาม Claude (ค้นเว็บได้) เมื่อ AI ในเครื่องเลือก ask-cloud (การ์ด 0016 · Pakon เลือกอัตโนมัติ 2026-09-30).

    claude -p --tools WebSearch --allowedTools WebSearch --model sonnet (โฟลเดอร์ว่าง · ไม่เก็บบทสนทนา)

ส่งออกนอกเครื่อง: คำถามนี้ + ข้อความล่าสุดไม่เกิน CONTEXT_TURNS ข้อความของบทสนทนาเดียวกันเท่านั้น
ไม่ส่งนัด ไฟล์ ใบหน้า หรือชื่อบัญชี · Claude เขียนไฟล์/รันคำสั่งบนเครื่องไม่ได้ (มีแค่ WebSearch) ·
คำตอบของ Claude = ข้อความให้คนอ่าน ไม่ถูกใช้สั่งสกิล (H8)
"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import date

from aipc.skills import forge

MODEL = "sonnet"
BUDGET_USD = "0.50"
TIMEOUT_S = 120
CONTEXT_TURNS = 4


@dataclass
class CloudReply:
    ok: bool
    text: str = ""
    error: str = ""
    seconds: float = 0.0
    cost_usd: float = 0.0
    model: str = ""


def instructions(today: date | None = None) -> str:
    from aipc.ui.thaidate import BE_OFFSET, DAYS, MONTHS

    d = today or date.today()
    when = f"วัน{DAYS[d.weekday()]}ที่ {d.day} {MONTHS[d.month - 1]} พ.ศ. {d.year + BE_OFFSET}"
    return (
        "คุณตอบแทนผู้ช่วย AI ในเครื่องของผู้ใช้ชาวไทย (AI PC บน Raspberry Pi) ที่ส่งคำถามนี้มาเพราะต้องใช้ข้อมูลสด"
        f"หรือคำถามยาก · วันนี้คือ{when} · ตอบภาษาไทย กระชับ ไม่เกินประมาณ 8 บรรทัด · "
        "ถ้าใช้ข้อมูลจากเว็บให้บอกแหล่งสั้น ๆ 1–2 แหล่งท้ายคำตอบ · ถ้าหาไม่ได้หรือไม่แน่ใจให้บอกตรง ๆ ห้ามเดา · "
        "ปฏิเสธคำขอที่ผิดกฎหมายหรืออันตราย"
    )


def build_input(question: str, history: list[dict]) -> str:
    """ข้อความที่ส่งทาง stdin: บริบทล่าสุด (ถ้ามี) + คำถาม."""
    recent = [m for m in history if m.get("role") in ("user", "assistant")][-CONTEXT_TURNS:]
    lines = []
    if recent:
        lines.append("บทสนทนาก่อนหน้า (เพื่อเข้าใจบริบท):")
        lines += [
            f"{'ผู้ใช้' if m['role'] == 'user' else 'ผู้ช่วย'}: {m['content'][:600]}" for m in recent
        ]
        lines.append("")
    lines += ["คำถาม:", question.strip()]
    return "\n".join(lines)


def ask(
    question: str,
    history: list[dict] | None = None,
    *,
    claude: str | None = None,
    model: str = MODEL,
    runner=forge.run_process,
    today: date | None = None,
) -> CloudReply:
    exe = claude or shutil.which("claude")
    if not exe:
        return CloudReply(False, error="ยังไม่ได้ติดตั้งหรือเข้าสู่ระบบ Claude ในเครื่องนี้")
    args = [
        exe,
        "-p",
        "--output-format",
        "json",
        "--tools",
        "WebSearch",
        "--allowedTools",
        "WebSearch",
        "--permission-prompts",
        "none",
        "--no-session-persistence",
        "--max-budget-usd",
        BUDGET_USD,
        "--model",
        model,
        "--append-system-prompt",
        instructions(today),
    ]
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="aipc-cloud-") as cwd:
        code, out, err = runner(args, build_input(question, history or []), cwd, TIMEOUT_S)
    secs = round(time.monotonic() - t0, 2)
    try:
        data = json.loads(out)
    except ValueError:
        detail = (err or out or f"รหัส {code}")[:200]
        return CloudReply(False, error=f"ติดต่อ Claude ไม่ได้ (ไม่มีอินเทอร์เน็ต?) · {detail}", seconds=secs)
    text = str(data.get("result") or "")
    ok = code == 0 and not data.get("is_error") and bool(text.strip())
    return CloudReply(
        ok,
        text if ok else "",
        "" if ok else f"Claude ตอบไม่สำเร็จ: {text[:200]}",
        secs,
        float(data.get("total_cost_usd") or 0),
        ",".join((data.get("modelUsage") or {}).keys()),
    )
