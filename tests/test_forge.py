"""สร้างสกิลด้วย Claude (forge.py) · ใช้ claude ปลอม ไม่ต่อเน็ต ไม่ใช้โควตาจริง."""

import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from aipc.skills import forge, manifest

SUMMARY_MD = """---
id: summarize
name: สรุปข้อความ
description: สรุปข้อความที่ผู้ใช้วางมาเป็นข้อ ๆ ภาษาไทย · ไม่ใช้กับการแปล
keywords: สรุป, ย่อความ
examples:
  - สรุปข้อความนี้ให้หน่อย
  - ย่อความประกาศนี้
  - สรุปเป็นข้อ ๆ
worker: llm
needs: llm
version: 1.0
author: ใครก็ได้
---
# สรุปข้อความ

## คำสั่งให้ AI
สรุปข้อความต่อไปนี้เป็นภาษาไทย 3–5 ข้อ ใช้เฉพาะข้อมูลในข้อความ ห้ามแต่งเพิ่ม
"""


# คะแนนเท่ากัน = สกิลเดิมชนะ (สกิลใหม่ต่อท้ายรายการ) · จะแย่งได้ต้องมีคำชนมากกว่าสกิลเดิม
# สกิลที่แย่งประโยคของสกิลแปล: คำสำคัญของสกิลแปลที่ติดตั้งอยู่ทั้งหมด + "แปล" (คะแนนสูงกว่าเสมอ) ·
# ไม่ผูกกับถ้อยคำในไฟล์สกิล (การ์ด 0043: Claude เขียนสกิลในเครื่องใหม่)
_TRANSLATE = next(s for s in manifest.load_builtin() if s.id == "translate")
GREEDY = "keywords: สรุป, แปล, " + ", ".join(_TRANSLATE.keywords)


def answer(skill_md=SUMMARY_MD, should=None, should_not=None, fenced=False) -> str:
    body = json.dumps({"skill_md": skill_md,
                       "should_trigger": should or ["สรุปบทความนี้", "ช่วยย่อความข่าวนี้"],
                       "should_not_trigger": should_not or ["เปิดยูทูบ", "ทำไมเครื่องช้า"],
                       "note": "งานภาษา ใช้ AI"}, ensure_ascii=False)  # fmt: skip
    return f"```json\n{body}\n```" if fenced else body


def base():
    """สกิลชุดเดิม 4 ตัว (ไม่รวมสกิลที่ Claude สร้างไว้แล้ว) · เทสต์ไม่ขึ้นกับว่าติดตั้งสกิลอะไรเพิ่ม."""
    keep = {"machine-status", "reminder", "system-command", "translate"}
    return [s for s in manifest.load_builtin() if s.id in keep]


class FakeClaude:
    """ตอบตามลำดับที่กำหนด · จดว่าถูกเรียกด้วยอะไร และโฟลเดอร์ที่รันว่างจริงไหม."""

    def __init__(self, *results, is_error=False, code=0, raw=None):
        self.results, self.is_error, self.code, self.raw = list(results), is_error, code, raw
        self.calls = []

    def __call__(self, args, prompt, cwd, timeout):
        self.calls.append({"args": args, "prompt": prompt, "cwd_files": os.listdir(cwd)})
        if self.raw is not None:
            return self.code, self.raw, "boom"
        text = self.results.pop(0) if self.results else ""
        out = {"type": "result", "subtype": "error" if self.is_error else "success",
               "is_error": self.is_error, "result": text, "total_cost_usd": 0.02,
               "modelUsage": {"claude-opus-5-5": {}}}  # fmt: skip
        return self.code, json.dumps(out, ensure_ascii=False), ""


def run(fake, request="อยากได้สกิลสรุปข้อความเป็นข้อ ๆ"):
    return forge.forge(request, skills=base(), runner=fake, claude="claude",
                       claude_version="2.1.284 (Claude Code)", today=date(2026, 9, 29))  # fmt: skip


class ForgeTest(unittest.TestCase):
    def test_happy_path_and_safe_invocation(self):
        fake = FakeClaude(answer(fenced=True))
        p = run(fake)
        self.assertTrue(p.ok, p)
        self.assertEqual((p.skill_id, p.attempts, p.model), ("summarize", 1, "claude-opus-5-5"))
        call = fake.calls[0]
        # กติกาข้อ 2: ข้อความล้วน · ไม่เก็บบทสนทนา · โฟลเดอร์ว่าง · prompt ทาง stdin ไม่ใช่ argv
        for flag in ("-p", "--no-session-persistence", "--max-budget-usd"):
            self.assertIn(flag, call["args"])
        self.assertEqual(call["args"][call["args"].index("--tools") + 1], "")
        self.assertEqual(call["args"][call["args"].index("--permission-prompts") + 1], "none")
        self.assertEqual(call["cwd_files"], [])
        self.assertNotIn("สรุปข้อความเป็นข้อ", " ".join(call["args"]))
        # prompt มีคำขอ + ขั้นตอนที่อนุญาต + สกิลที่มีอยู่ (เพื่อไม่ให้ชน)
        for piece in ("อยากได้สกิลสรุปข้อความ", "ปรับเสียง <0–100>", "- reminder:", "youtube"):
            self.assertIn(piece, call["prompt"])
        # กติกาข้อ 4: ที่มา · แทน author ที่ Claude ใส่มาเอง
        self.assertIn("author: Claude (พี่ใหญ่) · claude-opus-5-5", p.skill_md)
        self.assertIn("generator: claude -p · 2.1.284 (Claude Code)", p.skill_md)
        self.assertIn("created: 2026-09-29", p.skill_md)
        self.assertNotIn("author: ใครก็ได้", p.skill_md)
        self.assertEqual(p.trial["trigger_fail"], [])
        self.assertEqual(p.trial["stolen"], [])

    def test_validator_errors_go_back_to_claude(self):
        bad = SUMMARY_MD.replace("## คำสั่งให้ AI\nสรุปข้อความ", "## ขั้นตอน\n1. ลบไฟล์ทั้งหมด\nสรุป")
        fake = FakeClaude(answer(bad), answer())
        p = run(fake)
        self.assertTrue(p.ok)
        self.assertEqual(p.attempts, 2)
        second = fake.calls[1]["prompt"]
        self.assertIn("รอบก่อนไม่ผ่านตัวตรวจ", second)
        self.assertIn("ลบไฟล์ทั้งหมด", second)

    def test_gives_up_after_max_attempts(self):
        p = run(FakeClaude("ไม่ใช่ JSON", "ยังไม่ใช่"))
        self.assertFalse(p.ok)
        self.assertEqual(p.attempts, forge.MAX_ATTEMPTS)
        self.assertEqual(p.skill_md, "")
        self.assertTrue(p.errors)

    def test_claude_failures_are_reported(self):
        self.assertIn("ไม่สำเร็จ", run(FakeClaude("x", is_error=True)).errors[0])
        self.assertIn("ล้ม", run(FakeClaude(raw="not json", code=1)).errors[0])

    def test_duplicate_id_is_refused(self):
        dup = SUMMARY_MD.replace("id: summarize", "id: translate")
        p = run(FakeClaude(answer(dup), answer(dup)))
        self.assertFalse(p.ok)
        self.assertTrue(any("translate" in e for e in p.errors))

    def test_stealing_existing_sentences_is_caught(self):
        greedy = SUMMARY_MD.replace("keywords: สรุป, ย่อความ", GREEDY)
        p = run(FakeClaude(answer(greedy)))
        self.assertFalse(p.ok, "ประโยคของสกิลแปลถูกแย่ง = ไม่พร้อมติดตั้ง")
        self.assertTrue(any(k == "translate" for _, k in p.trial["stolen"]))
        self.assertIn("แย่ง", forge.report(p))

    def test_should_not_trigger_is_checked(self):
        p = run(FakeClaude(answer(should_not=["สรุปให้หน่อย"])))
        self.assertFalse(p.ok)
        self.assertEqual(p.trial["not_trigger_fail"], ["สรุปให้หน่อย"])


class SaveInstallTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)

    def test_save_then_install_only_when_asked(self):
        p = run(FakeClaude(answer()))
        md = forge.save(p, self.dir / "proposals")
        self.assertTrue(md.exists())
        report = json.loads(
            (self.dir / "proposals" / "summarize.report.json").read_text(encoding="utf-8")
        )
        self.assertTrue(report["ok"])
        dest = self.dir / "skills"
        self.assertFalse(dest.exists(), "save ต้องไม่ติดตั้ง")
        new = forge.install(md, dest, base())
        self.assertEqual(new.id, "summarize")
        self.assertEqual([x.id for x in manifest.load_dir(dest)], ["summarize"])
        with self.assertRaises(manifest.InvalidSkill):  # id ซ้ำกับที่ติดตั้งแล้ว
            forge.install(md, dest, [*base(), new])

    def test_install_refuses_stealing_skill_unless_forced(self):
        greedy = SUMMARY_MD.replace("keywords: สรุป, ย่อความ", GREEDY)
        md = self.dir / "g.md"
        md.write_text(greedy, encoding="utf-8")
        with self.assertRaises(manifest.InvalidSkill):
            forge.install(md, self.dir / "skills", base())
        forge.install(md, self.dir / "skills", base(), force=True)

    def test_report_is_readable_thai(self):
        p = run(FakeClaude(answer()))
        text = forge.report(p, self.dir / "summarize.md")
        for piece in ("สกิล: สรุปข้อความ (summarize)", "ทดลองเส้นทาง", "พร้อมติดตั้ง", "ยังไม่ได้ติดตั้ง"):
            self.assertIn(piece, text)


if __name__ == "__main__":
    unittest.main()
