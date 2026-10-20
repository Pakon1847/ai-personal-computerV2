"""การ์ด 0043: Claude เขียนสกิลในเครื่องใหม่ · ระบบล็อกส่วนหัวเรื่องสิทธิ์ (Claude ปลอม · ไม่ต่อเน็ต)."""

import json
import unittest

from aipc.skills import forge, manifest, rebuild

CLAIMS_MORE = """---
id: my-reminder
name: นัดหมายและเตือน
description: จดนัดและเตือนเมื่อถึงเวลา
keywords: เตือน, นัด, อย่าลืม, ปลุก
examples:
  - เตือนส่งงานพรุ่งนี้สิบโมง
  - นัดหมอวันศุกร์บ่ายสอง
  - อย่าลืมโทรหาแม่สองทุ่ม
worker: code
permissions: write_reminders, run_actions
version: 1.0
---
# นัดหมายและเตือน

จดนัดจากประโยคแล้วเตือน
"""


def fake_claude(skill_md):
    reply = {"skill_md": skill_md, "should_trigger": [], "should_not_trigger": [], "note": "ทดสอบ"}

    def runner(args, prompt, cwd, timeout):
        runner.prompts.append(prompt)
        body = {"result": json.dumps(reply, ensure_ascii=False), "is_error": False,
                "total_cost_usd": 0.0, "modelUsage": {"claude-test": {}}}  # fmt: skip
        return 0, json.dumps(body, ensure_ascii=False), ""

    runner.prompts = []
    return runner


class PinTest(unittest.TestCase):
    def test_permission_header_is_the_systems_not_claudes(self):
        fixed = rebuild.fixed_header(manifest.BUILTIN_DIR / "reminder.md")
        md, changed = forge.pin_header(CLAIMS_MORE, fixed)
        self.assertEqual(
            sorted(changed), ["id", "permissions"]
        )  # Claude ขอ run_actions เพิ่ม + id ใหม่
        skill = forge._validate(md)[0]
        self.assertEqual(skill.id, "reminder")
        self.assertEqual(skill.permissions, ("write_reminders",))

    def test_rebuild_uses_brief_not_the_old_file_and_pins(self):
        runner = fake_claude(CLAIMS_MORE)
        p = rebuild.rebuild("reminder", claude="claude", version="test", runner=runner)
        self.assertEqual(p.skill_id, "reminder")
        self.assertEqual(p.pinned_changed, ["id", "permissions"])
        self.assertIn("author: Claude", p.skill_md)
        old = (manifest.BUILTIN_DIR / "reminder.md").read_text(encoding="utf-8")
        old_desc = next(x for x in old.splitlines() if x.startswith("description:"))
        self.assertNotIn(old_desc, runner.prompts[0])  # ไม่ส่งไฟล์เดิมให้ Claude ลอก
        self.assertIn("reminder", runner.prompts[0])


class InstalledTest(unittest.TestCase):
    def test_every_builtin_skill_is_written_by_claude(self):
        """การ์ด 0043 S6: สกิลในเครื่องทุกไฟล์ Claude เขียน · มีที่มา (รุ่น วันที่ คำขอ) ·
        6 ไฟล์เดิม + สกิลประจำเว็บ 2 ไฟล์ (การ์ด 0046)."""
        skills = manifest.load_builtin()
        self.assertEqual(len(skills), 8)
        for s in skills:
            with self.subTest(skill=s.id):
                self.assertIn("Claude", s.author)
                self.assertTrue(s.extra.get("created"))
                self.assertTrue(s.extra.get("request"))

    def test_permission_header_matches_what_the_system_allows(self):
        """S2: สิทธิ์ของสกิลในเครื่อง = ค่าที่ระบบกำหนด (ไม่ใช่ที่ Claude ขอ)."""
        want = {"reminder": ("write_reminders",), "system-command": ("run_actions",),
                "machine-status": ("read_machine_status",), "translate": (), "summarize-text": (),
                "letter-writer": (), "youtube-voice": ("page_actions",),
                "spotify-voice": ("page_actions",)}  # fmt: skip
        for s in manifest.load_builtin():
            with self.subTest(skill=s.id):
                self.assertEqual(s.permissions, want[s.id])


if __name__ == "__main__":
    unittest.main()
