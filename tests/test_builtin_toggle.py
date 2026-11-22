"""เปิด/ปิดสกิลในตัว (การ์ด 0086 เกณฑ์ B1–B5) · ไม่ใช้ AI จริง ไม่ต่อเน็ต."""

import json
import tempfile
import unittest
from pathlib import Path

from aipc.skills import actions, manifest, userskills

try:
    from PySide6.QtGui import QGuiApplication

    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None

BUILTIN = manifest.load_builtin()


class StoreTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)

    def test_off_list_persists_per_folder(self):
        a = userskills.UserSkills(self.dir / "a")
        self.assertEqual(a.builtin_off(), set())
        self.assertTrue(a.set_builtin("translate", False))
        self.assertEqual(userskills.UserSkills(self.dir / "a").builtin_off(), {"translate"})
        self.assertEqual(userskills.UserSkills(self.dir / "b").builtin_off(), set(), "ของใครของมัน")
        a.set_builtin("translate", True)
        self.assertEqual(userskills.UserSkills(self.dir / "a").builtin_off(), set())

    def test_broken_file_means_all_on(self):
        (self.dir / "a").mkdir()
        (self.dir / "a" / userskills.BUILTIN_OFF_FILE).write_text("{oops", encoding="utf-8")
        self.assertEqual(userskills.UserSkills(self.dir / "a").builtin_off(), set())
        (self.dir / "a" / userskills.BUILTIN_OFF_FILE).write_text(
            json.dumps({"x": 1}), encoding="utf-8"
        )
        self.assertEqual(userskills.UserSkills(self.dir / "a").builtin_off(), set())


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class ControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def make(self, llm=False):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.ran = []
        ex = actions.Executor(runner=lambda a: self.ran.append(a) or 0, dry_run=False)
        self.store = userskills.UserSkills(Path(d.name) / "skills")
        return SkillsController(executor=ex, reminders_path=Path(d.name) / "r.json",
                                run_timer=False, llm_ready=lambda: llm,
                                user_skills=self.store)  # fmt: skip

    def tile(self, s, sid):
        """ไทล์ของสกิล · สกิลประจำเว็บอยู่ในแถวของเว็บ (webCommands) ไม่ใช่ไทล์."""
        hit = next((t for t in s.skills if t.get("id") == sid), None)
        if hit is not None:
            return hit
        row = next(r for r in s.webCommands for b in r.get("builtin", []) if b["id"] == sid)
        return next(b for b in row["builtin"] if b["id"] == sid)

    def test_each_builtin_off_stops_its_examples(self):
        """B1: ตัวอย่างในไฟล์ของสกิลที่ปิด ไม่ไปสกิลนั้นเลย · การ์ดบอกว่าปิดไว้ · ไม่สั่งเครื่อง."""
        for skill in BUILTIN:
            with self.subTest(skill.id):
                s = self.make()
                s.setSkillEnabled(skill.id, False)
                self.assertNotIn(skill.id, [t["function"]["name"] for t in s.tool_catalog()])
                self.assertFalse(self.tile(s, skill.id)["enabled"])
                if skill.site:  # สกิลประจำเว็บ: คำพูดในเว็บนั้นต้องไม่ถึงสกิลที่ปิด
                    from aipc.skills import sitecmd

                    url = (
                        "https://"
                        + {"spotify": "open.spotify.com", "youtube": "www.youtube.com"}[skill.site]
                    )
                    for c in skill.commands:
                        hit = sitecmd.match(c.phrases[0], s._skills, url)[0]
                        self.assertNotEqual(getattr(hit, "id", ""), skill.id, c.phrases[0])
                    continue
                for ex in skill.examples:
                    card = s.handle(ex)
                    self.assertNotEqual((card.get("badge") or {}).get("id"), skill.id, ex)
                self.assertEqual(self.ran, [], "สกิลที่ปิดต้องไม่สั่งเครื่อง")
                self.assertEqual(s.handleAs(skill.id, skill.examples[0])["kind"], "skill-off")

    def test_command_off_says_so(self):
        s = self.make()
        s.setSkillEnabled("system-command", False)
        card = s.handle("ปิดเสียง")
        self.assertEqual(card["kind"], "skill-off")
        self.assertIn("หน้า Skill", " ".join(card["lines"]))
        self.assertEqual(self.ran, [])

    def test_on_again_routes_like_before(self):
        """B2: เปิดคืน = ทางของตัวอย่างทุกสกิลเหมือนก่อนปิด."""
        before = self.make()
        sentences = [e for k in BUILTIN for e in k.examples]

        def routes(s):
            return [
                ((s.handle(t).get("badge") or {}).get("id"), s.handle(t).get("kind"))
                for t in sentences
            ]

        want = routes(before)
        s = self.make()
        for k in BUILTIN:
            s.setSkillEnabled(k.id, False)
        for k in BUILTIN:
            s.setSkillEnabled(k.id, True)
        self.assertEqual(routes(s), want)

    def test_voice_paths_respect_off(self):
        """B4: คีย์ลัดเสียง: ตั้งเตือน / งานที่ใช้ AI ของสกิลที่ปิด = บอกว่าปิดไว้."""
        s = self.make()
        s.setSkillEnabled("reminder", False)
        self.assertEqual(s.voiceReminder("เตือนพรุ่งนี้ 9 โมงไปหาหมอ")["kind"], "skill-off")
        s.setSkillEnabled("translate", False)
        self.assertEqual(s.voiceToChat("แปลว่า good morning")["kind"], "skill-off")

    def test_builtin_is_never_treated_as_user_skill_when_off(self):
        s = self.make()
        s.setSkillEnabled("translate", False)
        self.assertFalse(s.removeSkill("translate")["title"].startswith("ลบสกิลนี้แล้ว"))
        self.assertFalse(self.tile(s, "translate")["byClaude"])


if __name__ == "__main__":
    unittest.main()
