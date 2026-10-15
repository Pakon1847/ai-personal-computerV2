"""ขั้น "บอกนัด…" ในสกิล .md → "โหมดเริ่มวัน" (การ์ด 0034) · ตัวสั่งงานปลอม · ปฏิทินตัวอย่างของเทสต์."""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aipc.skills import manifest, mdskill, userskills

try:
    from aipc.skills import actions, gcal
    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None

from tests.test_skill_gcal import ICS, LINK

NOW = datetime(2026, 10, 16, 7, 0).astimezone()  # ศุกร์เช้า: มี "ไปเชียงใหม่" (ทั้งวัน) + "โทรหาหมอ"

MORNING = """---
id: morning-mode
name: โหมดเริ่มวัน
description: บอกนัดวันนี้แล้วเปิดอีเมล สำหรับเริ่มวัน
keywords: โหมดเริ่มวัน, เริ่มวัน
examples:
  - เปิดโหมดเริ่มวัน
  - โหมดเริ่มวัน
  - เริ่มวันใหม่
permissions: run_actions, read_agenda
---
# โหมดเริ่มวัน

## ขั้นตอน
1. บอกนัดวันนี้
2. เปิดเว็บ gmail
"""


class AgendaStepParseTest(unittest.TestCase):
    def test_step_and_permission(self):
        data, errors = mdskill.parse(MORNING)
        self.assertEqual(errors, [])
        self.assertEqual([s.kind for s in data["steps"]], ["agenda", "action"])
        self.assertEqual(data["worker"], "code")  # อ่านนัดด้วยโค้ด ไม่ใช่งานของ AI
        m = manifest.from_dict(data)
        self.assertIn("อ่านนัดและปฏิทินของคุณ (ในเครื่อง)", m.permission_labels())
        for text in ("บอกนัด พรุ่งนี้", "บอกนัดสัปดาห์นี้"):
            self.assertEqual(mdskill.parse_step(text)[0].kind, "agenda")

    def test_rules(self):
        no_perm = MORNING.replace(
            "permissions: run_actions, read_agenda", "permissions: run_actions"
        )
        self.assertTrue(any("read_agenda" in e for e in mdskill.parse(no_perm)[1]))
        twice = MORNING.replace("2. เปิดเว็บ gmail", "2. บอกนัดพรุ่งนี้\n3. เปิดเว็บ gmail")
        self.assertTrue(any("ครั้งเดียว" in e for e in mdskill.parse(twice)[1]))
        self.assertIsNone(mdskill.parse_step("บอกนัดเดือนหน้า")[0])  # ช่วงอื่นยังไม่รับ
        self.assertIn("บอกนัดวันนี้", mdskill.STEP_HELP)  # Claude เห็นในคำสั่งตอนสร้างสกิล

    def test_gate_accepts_morning_mode_but_not_without_permission(self):
        builtin = manifest.load_builtin()
        m, errors = userskills.gate(MORNING, builtin)
        self.assertIsNotNone(m, errors)
        no_perm = MORNING.replace(
            "permissions: run_actions, read_agenda", "permissions: run_actions"
        )
        self.assertIsNone(userskills.gate(no_perm, builtin)[0])


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class AgendaStepRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.calls = []
        ex = actions.Executor(runner=lambda a: self.calls.append(a) or 0, dry_run=False)
        cal = gcal.GoogleCalendar(root / "l.json", root / "e.json", fetcher=lambda link: ICS,
                                  clock=lambda: NOW)  # fmt: skip
        self.assertTrue(cal.connect(LINK).ok)
        self.s = SkillsController(executor=ex, reminders_path=root / "r.json", clock=lambda: NOW,
                                  run_timer=False, gcal=cal)  # fmt: skip
        self.s._skills.append(manifest.from_dict(mdskill.parse(MORNING)[0]))

    def test_skill_reads_today_then_opens_gmail(self):
        card = self.s.handleAs("morning-mode", "เปิดโหมดเริ่มวัน")
        self.assertTrue(card["confirmToken"])  # มีขั้นที่เปิดเว็บ = ถามยืนยันก่อน (กติกาเดิม)
        self.assertEqual(card["lines"][0], "1. บอกนัดวันนี้")
        done = self.s.confirm(card["confirmToken"], True)
        text = "\n".join(done["lines"])
        self.assertIn("วันนี้ (", text)
        self.assertIn("ไปเชียงใหม่ · Google", text)
        self.assertIn("โทรหาหมอ · Google", text)
        self.assertEqual(len(self.calls), 1)  # เปิด Gmail ครั้งเดียว
        self.assertEqual(done["title"], "ทำครบ 2 ขั้นแล้ว")

    def test_voice_exact_phrase_reaches_the_skill(self):
        self.assertEqual(self.s.voiceSkill("เปิดโหมดเริ่มวัน"), "morning-mode")

    def test_agenda_only_skill_runs_without_confirm(self):
        only = MORNING.replace("2. เปิดเว็บ gmail\n", "").replace(
            "run_actions, read_agenda", "read_agenda"
        )
        only = only.replace("id: morning-mode", "id: today-only").replace(
            "- เปิดโหมดเริ่มวัน", "- บอกนัดหน่อย"
        )
        self.s._skills.append(manifest.from_dict(mdskill.parse(only)[0]))
        card = self.s.handleAs("today-only", "บอกนัดหน่อย")
        self.assertEqual(card["confirmToken"], "")  # อ่านอย่างเดียว ไม่แตะเครื่อง = ทำเลย
        self.assertIn("โทรหาหมอ", "\n".join(card["lines"]))
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
