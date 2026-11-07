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
        names = [t["function"]["name"] for t in s.tool_catalog("คิดเมนูจากของในตู้เย็นหน่อย")]
        self.assertIn("fridge-menu", names)
        self.assertIn("translate", names)  # สกิลในตัวส่งเสมอ
        mine = {m.id for m in store.load()}
        user_names = [n for n in names if n in mine]
        self.assertTrue(1 <= len(user_names) <= retrieval.TOP_K, user_names)
        # การ์ด 0074: ไม่มีสกิลผู้ใช้ใกล้ข้อความ = รายการเท่ากับไม่มีสกิลผู้ใช้ (แคชของ llama-server ใช้ได้)
        far = [t["function"]["name"] for t in s.tool_catalog("12345")]
        self.assertEqual(far, [t["function"]["name"] for t in s.tool_catalog("12345", user=False)])
        self.assertFalse(set(far) & mine)

    def test_near_keeps_only_skills_close_to_the_text(self):
        got = retrieval.near(self.pool, "คิดเมนูจากของในตู้เย็นหน่อย")
        self.assertTrue(1 <= len(got) <= retrieval.TOP_K)
        values = retrieval.Index(self.pool).scores("คิดเมนูจากของในตู้เย็นหน่อย")
        scores = dict(zip((s.id for s in self.pool), values, strict=True))
        self.assertTrue(all(scores[s.id] >= retrieval.NEAR_MIN for s in got))
        self.assertEqual(retrieval.near(self.pool, ""), [])
        self.assertEqual(retrieval.near([], "อะไรก็ได้"), [])


if __name__ == "__main__":
    unittest.main()
