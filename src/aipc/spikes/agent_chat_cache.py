"""เกณฑ์ข้อ 5 การ์ด 0025: ใช้ผู้ช่วยเว็บแล้วแชทไม่ช้าลง (llama-server ค่าเดียวกับแอป · -np 1 -cram 512).

ลำดับเหมือนใช้จริง: แชทอุ่น → แชทถาม → ผู้ช่วยวางแผน (A) → อ่านหน้าไว้ก่อน (B) → ถามเรื่องในหน้า (B)
→ แชทถามต่อ · ผ่าน = ข้อความแชทหลังใช้ผู้ช่วยอ่าน prompt ใหม่ ≤ 50 token
system prompt ของแชทจริง: ChatController._system() ของแอป (รายการสกิลจริง) · ไม่ต้องเปิดหน้าจอ
"""

from __future__ import annotations

import argparse
import json
from datetime import date

from aipc.browser import agent
from aipc.chat.client import Target


def chat_system() -> str:
    from PySide6.QtCore import QCoreApplication

    from aipc.ui.backend import ChatController

    QCoreApplication.instance() or QCoreApplication([])
    c = ChatController(active=False)
    return c._system(c._all_tools())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:18080")
    ap.add_argument("--pages", default="tests/data/agent_pages.json")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    llm = agent.Llm(Target(url=a.url), timeout=900)
    page = json.load(open(a.pages, encoding="utf-8"))["pages"]["goldtraders"]
    system = chat_system()
    chat1 = [{"role": "system", "content": system}, {"role": "user", "content": "สวัสดีครับ"}]
    chat2 = chat1 + [{"role": "assistant", "content": "สวัสดีครับ มีอะไรให้ช่วยไหม"},
                     {"role": "user", "content": "พรุ่งนี้วันอะไร"}]  # fmt: skip
    steps = [
        ("แชทอุ่น (login)", lambda: llm.preread(chat1)),
        ("แชทถาม", lambda: llm.ask(chat2, "", 1)[1]),
        ("ผู้ช่วยวางแผน A", lambda: llm.ask(agent.plan_messages("ทองแท่งขายออกเท่าไหร่",
                                                               page), agent.PLAN_GRAMMAR, 30)[1]),
        ("อ่านหน้าไว้ก่อน B", lambda: llm.preread(agent.preread_messages(page))),
        ("ถามเรื่องในหน้า B", lambda: llm.ask(agent.look_messages("ทองแท่งขายออกเท่าไหร่", page,
                                                                  date(2026, 10, 13)),
                                              agent.look_grammar(page), 60)[1]),
        ("แชทถามต่อ (หลังใช้ผู้ช่วย)", lambda: llm.ask(chat2 + [
            {"role": "assistant", "content": "พรุ่งนี้วันพุธครับ"},
            {"role": "user", "content": "ขอบคุณ"}], "", 1)[1]),
    ]  # fmt: skip
    rows = []
    for name, fn in steps:
        t = fn()
        rows.append({"step": name, "prompt_n": t.get("prompt_n"),
                     "prompt_s": round((t.get("prompt_ms") or 0) / 1000, 2)})  # fmt: skip
        print(f"{name:32} อ่านใหม่ {t.get('prompt_n')} token · {rows[-1]['prompt_s']} วิ", flush=True)
    ok = (rows[-1]["prompt_n"] or 0) <= 50
    print("ผ่าน" if ok else "ไม่ผ่าน", flush=True)
    if a.out:
        json.dump({"ok": ok, "rows": rows, "chat_system_chars": len(system)},
                  open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)  # fmt: skip


if __name__ == "__main__":
    main()
