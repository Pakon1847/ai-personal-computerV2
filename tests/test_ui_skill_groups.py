"""การ์ด 0067 G1: หน้า Skill รวมสกิลประจำเว็บเป็นไทล์เดียวต่อเว็บ · แสดงผลอย่างเดียว (จัดการยังทีละสกิล)."""

import tempfile
import unittest
from pathlib import Path

from aipc.skills import actions, userskills

try:
    from PySide6.QtGui import QGuiApplication

    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None

MINE = """---
id: yt-mine
name: คำของฉัน
description: คำพ้องของผู้ใช้
site: youtube
permissions: page_actions
---
## คำสั่ง
- เพิ่มอีกหนึ่งแถบ → ทำคำสั่ง เปิดยูทูบอีกแท็บ
"""


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class SiteTileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def make(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        store = userskills.UserSkills(Path(d.name) / "u")
        s = SkillsController(executor=actions.Executor(dry_run=True), run_timer=False,
                             reminders_path=Path(d.name) / "r.json", llm_ready=lambda: True,
                             user_skills=store)  # fmt: skip
        store.install(MINE, s._skills, request="ทดสอบ")
        s._reload()
        return s

    def test_one_tile_per_site_with_every_command_and_its_source(self):
        s = self.make()
        tiles = s.skills
        site = {t["id"]: t for t in tiles if t["id"].startswith("site:")}
        self.assertEqual(sorted(site), ["site:spotify", "site:youtube"])
        yt = site["site:youtube"]
        self.assertEqual(yt["name"], "YouTube")
        self.assertEqual(yt["skills"], ["youtube-voice", "yt-mine"])  # สกิลของระบบ + ของผู้ใช้
        self.assertIn("“เพิ่มอีกหนึ่งแถบ” → ทำคำสั่ง “เปิดยูทูบอีกแท็บ” · Claude สร้าง", yt["commands"])
        builtin = [c for c in yt["commands"] if not c.endswith("Claude สร้าง")]
        self.assertGreater(len(builtin), 5)  # คำสั่งของสกิล YouTube ของระบบอยู่ครบในไทล์เดียว
        self.assertIn(f"{len(yt['commands'])} คำสั่ง จาก 2 สกิล", yt["description"])
        self.assertEqual(yt["subtitle"], f"{len(yt['commands'])} คำสั่ง")  # ไทล์บอกจำนวนคำสั่ง
        self.assertEqual(s.voiceSites, "สั่งด้วยเสียงได้ในเว็บ: YouTube, Gmail, Google และอื่น ๆ อีก 12 เว็บ")
        # ไม่มีไทล์แยกของสกิลประจำเว็บเหลืออยู่ · สกิลอื่นยังเป็นไทล์ของตัวเอง
        ids = [t["id"] for t in tiles]
        self.assertNotIn("youtube-voice", ids)
        self.assertNotIn("yt-mine", ids)
        self.assertTrue(any(not i.startswith("site:") for i in ids))

    def test_manage_list_still_one_row_per_skill(self):
        s = self.make()
        self.assertEqual([x["id"] for x in s.userSkills], ["yt-mine"])

    def test_web_rows_every_line_is_a_real_command(self):
        """ทุกคำพูดที่หน้าจอแสดงต้องแปลได้คำสั่งจริง (H5) · สกิลของผู้ใช้นับในแถวของเว็บนั้น."""
        from aipc.skills import browse
        from aipc.skills.actions import SITES

        s = self.make()
        rows = s.webCommands
        self.assertEqual([r["key"] for r in rows], ["all", *SITES])
        for r in rows:
            for g in r["groups"]:
                for line in g["lines"]:
                    if "→" in line:  # คำสั่งของสกิลประจำเว็บ (ตรวจด้วยตัวตรวจไฟล์สกิลแล้ว)
                        continue
                    said = line.strip("“”").replace("…", "แมว").replace("ค้นหา แมว", "ค้นหาแมว")
                    self.assertTrue(browse.parse(said), (r["key"], line))
        yt = next(r for r in rows if r["key"] == "youtube")
        self.assertEqual(yt["mine"], 1)
        self.assertEqual(next(r for r in rows if r["key"] == "gmail")["mine"], 0)
        self.assertEqual([u["site"] for u in s.userSkills], ["youtube"])

    def test_disabled_skill_commands_are_not_in_the_tile(self):
        s = self.make()
        s._user.set_enabled("yt-mine", False)
        s._reload()
        yt = next(t for t in s.skills if t["id"] == "site:youtube")
        self.assertEqual(yt["skills"], ["youtube-voice"])
        self.assertFalse(any("เพิ่มอีกหนึ่งแถบ" in c for c in yt["commands"]))


if __name__ == "__main__":
    unittest.main()
