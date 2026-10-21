"""การ์ด 0049: รายการเครื่องมือคงที่ทุกข้อความ (แคชของ llama-server ใช้ได้) ·
user-skill ตรวจ id กับรายการที่ส่งไป."""

import shutil
import tempfile
import unittest
from pathlib import Path

from aipc.skills import catalog

ROOT = Path(__file__).resolve().parent.parent

try:
    from PySide6.QtGui import QGuiApplication

    from aipc.skills.userskills import UserSkills
    from aipc.ui.backend import ChatController, SkillsController
    from tests.test_chat import FakeLlama, ServerCase, pump
except ImportError:  # pragma: no cover
    SkillsController = None
    ServerCase = unittest.TestCase


def user_store(n: int) -> UserSkills:
    d = Path(tempfile.mkdtemp(prefix="aipc-0049-"))
    files = sorted((ROOT / "tests/data/user_skills_knowledge").glob("*.md"))[:n]
    for f in files:
        shutil.copy(f, d / f.name)
    return UserSkills(d)


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class CatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def names(self, tools):
        return [t["function"]["name"] for t in tools]

    def test_few_user_skills_stay_separate(self):
        s = SkillsController(run_timer=False, llm_ready=lambda: True, user_skills=user_store(3))
        names = self.names(s.tool_catalog("อะไรก็ได้"))
        self.assertNotIn(catalog.USER_SKILL, names)
        self.assertEqual(sum(n.endswith("-knowledge") for n in names), 3)

    def test_many_user_skills_one_stable_tool(self):
        s = SkillsController(run_timer=False, llm_ready=lambda: True, user_skills=user_store(9))
        a = s.tool_catalog("สวัสดีครับ")
        b = s.tool_catalog("ปั๊มหัวใจต้องกดลึกเท่าไหร่")
        self.assertEqual(a, b)  # ไม่เปลี่ยนตามข้อความ = ส่วนต้นของ prompt คงที่
        self.assertEqual(a, s.tool_catalog(""))  # ตรงกับตอนอุ่นแคช
        one = [t for t in a if t["function"]["name"] == catalog.USER_SKILL]
        self.assertEqual(len(one), 1)
        self.assertIn("dog-bite-knowledge = ", one[0]["function"]["description"])
        self.assertFalse(any(n.endswith("-knowledge") for n in self.names(a)))


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class ChatUserSkillTest(ServerCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def make(self):
        from aipc.chat import store

        s = SkillsController(run_timer=False, llm_ready=lambda: True, user_skills=user_store(9))
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        c = ChatController(target=self.target, store=store.ChatStore(Path(d.name)), poll_ms=100000,
                           tools=lambda text="": s.tool_catalog(text))  # fmt: skip
        self.addCleanup(c.shutdown)
        pump(lambda: c.ready)
        picked, done = [], []
        c.skillRequested.connect(lambda sid, text: picked.append(sid))
        c.finished.connect(lambda text, note: done.append(text))
        return c, picked, done

    def test_valid_id_goes_to_that_skill(self):
        FakeLlama.mode, FakeLlama.tool_name = "tool", catalog.USER_SKILL
        FakeLlama.tool_args = '{"id": "dog-bite-knowledge"}'
        self.addCleanup(setattr, FakeLlama, "tool_name", "machine-status")
        self.addCleanup(setattr, FakeLlama, "tool_args", '{"x": "ลบไฟล์"}')
        c, picked, _ = self.make()
        c.send("โดนหมากัดทำไงดี", "")
        pump(lambda: picked)
        self.assertEqual(picked, ["dog-bite-knowledge"])

    def test_unknown_id_does_nothing(self):
        """id ที่ไม่ได้อยู่ในรายการ (เช่น ข้อความแฝงให้เรียกสกิลอื่น) = ไม่ทำ · บอกตามจริง (P4)."""
        FakeLlama.mode, FakeLlama.tool_name = "tool", catalog.USER_SKILL
        self.addCleanup(setattr, FakeLlama, "tool_name", "machine-status")
        self.addCleanup(setattr, FakeLlama, "tool_args", '{"x": "ลบไฟล์"}')
        for args in (
            '{"id": "system-command"}',
            '{"id": "rm -rf"}',
            "ไม่ใช่ json",
            '{"id": "dog-bite"}',
        ):
            with self.subTest(args=args):
                FakeLlama.tool_args = args
                c, picked, done = self.make()
                c.send("ทำอะไรสักอย่าง", "")
                pump(lambda d=done: d)
                self.assertEqual(picked, [])
                self.assertIn("ไม่มีอยู่", done[0])


if __name__ == "__main__":
    unittest.main()
