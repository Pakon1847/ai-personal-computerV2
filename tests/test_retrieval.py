"""ส่งให้ AI เฉพาะสกิลของผู้ใช้ที่เกี่ยวข้อง (การ์ด 0018) · สกิลจริงที่ Claude สร้างในชุดวัด."""

import tempfile
import unittest
from pathlib import Path

from aipc.skills import manifest, retrieval, userskills

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = sorted((ROOT / "docs/benchmarks/2026-09-30-skill-author/claude").glob("*.md"))


def user_pool() -> list[manifest.Manifest]:
    builtin = manifest.load_builtin()
    with tempfile.TemporaryDirectory() as d:
        store = userskills.UserSkills(Path(d))
        for p in CLAUDE:
            try:
                store.install(p.read_text(encoding="utf-8"), builtin + store.load(), request="x")
            except manifest.InvalidSkill:
                pass
        return store.load()


class PickTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool = user_pool()

    def test_few_skills_all_sent_many_skills_top_k(self):
        self.assertGreater(len(self.pool), retrieval.TOP_K)
        few = self.pool[:3]
        self.assertEqual(retrieval.pick(few, "อะไรก็ได้"), few)
        got = retrieval.pick(self.pool, "เข้าโหมดประชุมให้หน่อย")
        self.assertEqual(len(got), retrieval.TOP_K)
        self.assertEqual(got[0].id, "meeting-mode")
        self.assertEqual(retrieval.pick(self.pool, ""), [])  # อุ่นแคช: ส่วนต้นคงที่ ไม่มีสกิลของผู้ใช้

    def test_controller_keeps_builtin_and_adds_relevant_user_skills(self):
        from aipc.ui.backend import SkillsController

        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        store = userskills.UserSkills(Path(d.name))
        builtin = manifest.load_builtin()
        for p in CLAUDE:
            try:
                store.install(p.read_text(encoding="utf-8"), builtin + store.load(), request="x")
            except manifest.InvalidSkill:
                pass
        s = SkillsController(run_timer=False, llm_ready=lambda: True, user_skills=store)
        tools = s.tool_catalog("คิดเมนูจากของในตู้เย็นหน่อย")
        names = [t["function"]["name"] for t in tools]
        self.assertIn("translate", names)  # สกิลในตัวส่งเสมอ
        # การ์ด 0049: เกิน TOP_K ตัว = เครื่องมือเดียว user-skill (รายการสั้นคงที่) แทนการเลือก 5 ตัวตามข้อความ
        self.assertGreater(len(store.load()), retrieval.TOP_K)
        self.assertNotIn("fridge-menu", names)
        one = next(t for t in tools if t["function"]["name"] == "user-skill")
        self.assertIn("fridge-menu = ", one["function"]["description"])


if __name__ == "__main__":
    unittest.main()
