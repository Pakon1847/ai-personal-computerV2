"""สกิลแบบไฟล์ .md (ข้อเสนอ 2026-09-29 หัวข้อ 10.1) · ตัวอ่าน + ตัวตรวจขั้นตอน."""

import tempfile
import unittest
from pathlib import Path

from aipc.skills import manifest, mdskill

HEAD = """---
id: start-work
name: เริ่มวันทำงาน
description: เปิดอีเมลและลดเสียง สำหรับเริ่มงานตอนเช้า
keywords: เริ่มงาน, เริ่มวันทำงาน
examples:
  - เริ่มวันทำงาน
  - เริ่มงานได้เลย, ช่วยเปิดของ
  - เปิดของที่ใช้ทำงาน
permissions: run_actions
---
# เริ่มวันทำงาน

ข้อความนี้เป็นคำอธิบายให้คนอ่าน ระบบไม่ใช้
"""


def skill(steps: str = "", head: str = HEAD, extra: str = "") -> str:
    return head + extra + ("\n## ขั้นตอน\n" + steps if steps else "")


def parse(text: str):
    return mdskill.parse(text)


class ParseTest(unittest.TestCase):
    def test_steps_skill(self):
        data, errors = parse(skill("1. เปิดเว็บ gmail\n2. เปิดหน้า ตั้งค่า\n3. ปรับเสียง 30\n"))
        self.assertEqual(errors, [])
        self.assertEqual(data["id"], "start-work")
        self.assertEqual(data["keywords"], ["เริ่มงาน", "เริ่มวันทำงาน"])
        # รายการแบบขึ้นบรรทัด "- …" · มี , ในตัวอย่างได้
        self.assertEqual(data["examples"][1], "เริ่มงานได้เลย, ช่วยเปิดของ")
        self.assertEqual(data["worker"], "code")
        self.assertEqual(data["actions"], ["open_page", "open_url", "set_volume"])
        texts = [s.text for s in data["steps"]]
        self.assertEqual(texts, ["เปิด Gmail", "เปิดหน้าตั้งค่า", "ปรับเสียงเป็น 30%"])
        self.assertEqual(data["steps"][0].plan.params, {"site": "gmail"})

    def test_examples_inline_use_pipe(self):
        block = "examples:\n  - เริ่มวันทำงาน\n  - เริ่มงานได้เลย, ช่วยเปิดของ\n  - เปิดของที่ใช้ทำงาน\n"
        head = HEAD.replace(block, "examples: ก, ข | ค | ง\n")
        data, errors = parse(skill("1. ปิดเสียง\n", head=head))
        self.assertEqual(errors, [])
        self.assertEqual(data["examples"], ["ก, ข", "ค", "ง"])

    def test_every_step_kind(self):
        data, errors = parse(skill("1. เปิดเว็บ https://pantip.com/forum\n2. เปิดแอป เบราว์เซอร์\n"
                                   "3. เพิ่มเสียง 10\n4. ลดเสียง 5%\n5. ปิดเสียง\n6. เปิดเสียง\n"
                                   "7. บอก: อย่าลืมดื่มน้ำ\n8. ถาม AI: สรุปข้อความนี้\n"))  # fmt: skip
        self.assertEqual(errors, [])
        kinds = [s.kind for s in data["steps"]]
        self.assertEqual(kinds, ["action"] * 6 + ["say", "llm"])
        self.assertEqual(data["steps"][0].plan.params, {"url": "https://pantip.com/forum"})
        self.assertEqual(data["steps"][0].text, "เปิดเว็บ pantip.com")
        self.assertEqual(data["steps"][2].plan.params, {"step": 10})
        self.assertEqual(data["steps"][3].plan.params, {"step": -5})
        self.assertEqual(data["worker"], "code+llm")
        self.assertEqual(data["prompt"], "สรุปข้อความนี้")
        self.assertIn("llm", data["needs"])

    def test_unknown_step_is_refused_with_line_number(self):
        _, errors = parse(skill("1. เปิดเว็บ gmail\n2. ลบไฟล์ทั้งหมด\n"))
        self.assertEqual(len(errors), 1)
        self.assertIn("บรรทัด", errors[0])
        self.assertIn("ลบไฟล์ทั้งหมด", errors[0])
        # ส่วนหัว → บรรทัดว่าง → ## ขั้นตอน → ข้อ 1 → ข้อ 2
        line_no = HEAD.count("\n") + 4
        self.assertIn(f"บรรทัด {line_no}:", errors[0])

    def test_unsafe_or_unknown_targets(self):
        bad = ["เปิดเว็บ http://example.com", "เปิดเว็บ https://user:pw@example.com",
               "เปิดเว็บ https://localhost", "เปิดเว็บ example.com", "เปิดแอป โปรแกรมลับ",
               "เปิดหน้า ห้องลับ", "ปรับเสียง 150", "เพิ่มเสียง 0", "รัน rm -rf ~"]  # fmt: skip
        for step in bad:
            with self.subTest(step=step):
                _, errors = parse(skill(f"1. {step}\n"))
                self.assertTrue(errors, step)

    def test_steps_must_be_numbered(self):
        _, errors = parse(skill("เปิดเว็บ gmail\n"))
        self.assertTrue(any("เลข" in e for e in errors))

    def test_ask_ai_only_as_last_step(self):
        _, errors = parse(skill("1. ถาม AI: สรุป\n2. ปิดเสียง\n"))
        self.assertTrue(any("ขั้นสุดท้าย" in e for e in errors))

    def test_action_steps_need_run_actions(self):
        _, errors = parse(skill("1. ปิดเสียง\n", head=HEAD.replace("permissions: run_actions\n", "")))
        self.assertTrue(any("run_actions" in e for e in errors))

    def test_front_matter_problems(self):
        self.assertTrue(parse("# ไม่มีส่วนหัว\n")[1])
        self.assertTrue(parse("---\nid: x\n")[1], "ไม่มี --- ปิด")
        self.assertTrue(parse(HEAD.replace("name: เริ่มวันทำงาน\n", "name: ก\nname: ข\n"))[1], "ช่องซ้ำ")
        self.assertTrue(parse("---\n- ลอย\n---\n")[1], "รายการที่ไม่มีชื่อช่อง")
        self.assertTrue(parse("---\nไม่มีเครื่องหมาย\n---\n")[1])

    def test_llm_skill_prompt_section(self):
        head = HEAD.replace("permissions: run_actions\n", "worker: llm\nneeds: llm\n")
        data, errors = parse(head + "\n## คำสั่งให้ AI\n\nสรุปข้อความ 3 ข้อ\nห้ามแต่งเพิ่ม\n")
        self.assertEqual(errors, [])
        self.assertEqual(data["prompt"], "สรุปข้อความ 3 ข้อ\nห้ามแต่งเพิ่ม")
        self.assertEqual(data["steps"], [])

    def test_too_many_steps(self):
        _, errors = parse(skill("".join(f"{i}. ปิดเสียง\n" for i in range(1, mdskill.MAX_STEPS + 2))))
        self.assertTrue(any("มากเกิน" in e for e in errors))


class LoadTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)

    def test_md_goes_through_the_same_validator(self):
        (self.dir / "a.md").write_text(skill("1. ปิดเสียง\n"), encoding="utf-8")
        s = manifest.load(self.dir / "a.md")
        self.assertEqual(s.id, "start-work")
        self.assertEqual(len(s.steps), 1)
        broad = skill("1. ปิดเสียง\n").replace("description:", "description: ใช้กับทุกคำขอ")
        (self.dir / "b.md").write_text(broad, encoding="utf-8")
        with self.assertRaises(manifest.InvalidSkill):  # ตัวตรวจเดิม: ห้ามอ้างขอบเขตกว้างเกิน
            manifest.load(self.dir / "b.md")

    def test_duplicate_ids_are_refused(self):
        for name in ("a.md", "b.md"):
            (self.dir / name).write_text(skill("1. ปิดเสียง\n"), encoding="utf-8")
        with self.assertRaises(manifest.InvalidSkill):
            manifest.load_dir(self.dir)

    def test_builtins_are_md_and_keep_their_prompt(self):
        files = sorted(p.name for p in manifest.BUILTIN_DIR.iterdir() if p.is_file())
        want = [
            "letter-writer.md",
            "machine-status.md",
            "reminder.md",
            "summarize-text.md",
            "system-command.md",
            "translate.md",
        ]  # สกิลประจำเว็บสร้างโดย Claude ในเครื่องของผู้ใช้ (การ์ด 0050)
        self.assertEqual(files, want)
        tr = next(s for s in manifest.load_builtin() if s.id == "translate")
        # การ์ด 0043: Claude เขียน prompt เอง · ตรวจว่ามี prompt และพูดถึงทั้งสองภาษา (ไม่ผูกถ้อยคำ)
        self.assertIn("ไทย", tr.prompt)
        self.assertIn("อังกฤษ", tr.prompt)
        self.assertIn("Claude", tr.author)
        self.assertEqual(tr.needs, ("llm",))


if __name__ == "__main__":
    unittest.main()
