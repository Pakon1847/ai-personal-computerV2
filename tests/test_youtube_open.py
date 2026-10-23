"""การ์ด 0057: "เปิดช่อง 8" ใน YouTube = ค้นจริง · ไม่ส่งงานที่ต้องพิมพ์ให้ Claude ทำสกิล · บอกผลตามจริง (Y5)."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aipc.browser import control
from aipc.browser.control import BrowserControl
from aipc.skills import browse
from aipc.skills.browse import BrowseCommand
from tests.test_browser_control import FakeCdp, FakeProc

try:
    from PySide6.QtGui import QGuiApplication

    from aipc.skills import actions, userskills
    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None

WATCH = "https://www.youtube.com/watch?v=abc"


def cmds(text):
    return [c.as_dict() for c in browse.parse(text)]


class RuleTest(unittest.TestCase):
    def test_watch_in_service_is_a_search_there(self):
        yt = [{"kind": "site_search", "query": "ช่อง 8", "site": "youtube"}]
        self.assertEqual(cmds("เปิดช่อง 8 ในยูทูบ"), yt)
        self.assertEqual(cmds("เปิดยูทูบช่อง 8"), yt)
        self.assertEqual(cmds("ดูช่อง 8 ในยูทูบหน่อย"), yt)
        self.assertEqual(cmds("เปิดยูทูบแล้วดูข่าวเช้า")[0]["query"], "ข่าวเช้า")
        self.assertEqual(cmds("ฟังเพลงบอดี้สแลมในสปอติฟาย")[0]["site"], "spotify")

    def test_old_meanings_do_not_change(self):
        self.assertEqual(cmds("เปิดยูทูบให้หน่อย"), [{"kind": "site", "site": "youtube"}])
        self.assertEqual(cmds("เปิดยูทูบแล้วเปิดคลิปแรก")[1]["kind"], "open")  # คำสั่ง ไม่ใช่คำค้น
        self.assertEqual(cmds("ค้นหาช่อง 8 ในยูทูบ")[0]["query"], "ช่อง 8")
        self.assertEqual(cmds("เปิดคลิปแรก"), [{"kind": "open", "n": 1, "direction": "clip"}])

    def test_problems_and_site_names_are_not_searched(self):
        for t in ("เปิดยูทูบไม่ได้", "ดูในยูทูบไม่ออก", "ดูแผนที่ในกูเกิลแมพ"):
            self.assertFalse(any(c["kind"] == "site_search" for c in cmds(t)), t)

    def test_on_youtube_open_something_searches_youtube(self):
        c = browse.on_site_search("ดูการ์ตูนโดราเอมอน", "youtube")
        self.assertEqual(c, BrowseCommand("site_search", query="การ์ตูนโดราเอมอน", site="youtube"))
        self.assertEqual(browse.on_site_search("เล่นเพลงลิซ่า", "youtube").query, "เพลงลิซ่า")
        self.assertEqual(browse.on_site_search("ดูข่าวเช้า", "google").kind, "search")
        self.assertIsNone(browse.on_site_search("เปิดช่อง 8", "youtube"))  # กฎช่องทีวีทำแล้ว (รอบ 2)

    def test_on_site_never_searches_commands_questions_or_nothing(self):
        for t in ("เปิดคลิปแรก", "หยุดก่อน", "ย้อนกลับ", "ดูไม่ออก", "เปิดไม่ได้ทำไม", "เปิดแล้วค้าง",
                  "เปิดหน่อย", "ดู", "เปิดยูทูบ"):  # fmt: skip
            self.assertIsNone(browse.on_site_search(t, "youtube"), t)
        self.assertIsNone(browse.on_site_search("เปิดช่อง 8", "calendar"))  # เว็บที่ค้นไม่ได้


class TvChannelTest(unittest.TestCase):
    """การ์ด 0057 รอบ 2 (Pakon ที่จอ): "เปิดช่อง 8" = ค้นใน YouTube ทันที ไม่ขึ้นกับหน้าที่เปิด · ไม่ถาม."""

    def test_channel_number_searches_youtube_anywhere(self):
        for t, q in (("เปิดช่อง 8", "ช่อง 8"), ("เปิดช่องแปด", "ช่องแปด"), ("ดูช่องสาม", "ช่องสาม"),
                     ("เปิดช่อง 3 สด", "ช่อง 3 สด"), ("เปิดช่อง8หน่อย", "ช่อง8")):  # fmt: skip
            self.assertEqual(cmds(t), [{"kind": "site_search", "query": q, "site": "youtube"}], t)

    def test_other_channel_words_unchanged(self):
        self.assertEqual(cmds("เปิดช่องค้นหา"), [{"kind": "search", "query": "เปิดช่อง"}])  # เดิม


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class QueueWhileBusyTest(unittest.TestCase):
    """พูด "เปิดช่อง 8" ระหว่างหน้า YouTube ยังโหลด → ไม่หาย · ทำต่อเมื่อคำสั่งก่อนหน้าเสร็จ."""

    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_command_said_while_busy_runs_next(self):
        import threading

        from PySide6.QtCore import QCoreApplication

        from aipc.browser.control import Result
        from aipc.ui.handsfree import BrowserController

        gate, ran = threading.Event(), []

        class Slow:
            running = True

            def run(self, cmd):
                ran.append(cmd.as_dict())
                if len(ran) == 1:
                    gate.wait(5)  # หน้าแรกยังโหลด
                return Result(True, "ok")

            def close(self):
                pass

        b = BrowserController(active=True, control=Slow())
        self.assertTrue(b.handle("เปิดยูทูบ"))
        self.assertTrue(b.handle("เปิดช่อง 8"))  # ระหว่างยังโหลด
        gate.set()
        for _ in range(300):
            QCoreApplication.processEvents()
            if len(ran) == 2 and not b.busy:
                break
            import time

            time.sleep(0.01)
        self.assertEqual([r["kind"] for r in ran], ["site", "site_search"])


class HonestResultTest(unittest.TestCase):
    def test_landed(self):
        t = "https://www.youtube.com/results?search_query=" + "%E0%B8%8A 8".replace(" ", "+")
        home = "https://www.youtube.com/"
        self.assertTrue(control.landed(t, t, home))
        maps = "https://www.google.com/maps/"  # ผลเดียวเด้งไปหน้าสถานที่
        self.assertTrue(control.landed(maps + "place/x", maps + "search/x", home))
        self.assertFalse(control.landed(home, t, home))  # หน้าไม่เปลี่ยน
        self.assertFalse(control.landed("chrome-error://chromewebdata/", t, home))
        self.assertFalse(control.landed("", t, home))

    def test_search_that_never_loads_is_not_reported_done(self):
        class Stuck(FakeCdp):
            def call(self, method, params=None, session="", timeout=15.0):
                if method == "Page.navigate":  # เน็ตหลุด: หน้าไม่เปลี่ยน
                    return {}
                return super().call(method, params, session, timeout)

        cdp = Stuck({}, "https://www.youtube.com/")
        bc = BrowserControl(launcher=lambda argv: (FakeProc(), cdp), load_timeout=0.5)
        bc._start("https://www.youtube.com/")
        r = bc.run(BrowseCommand("site_search", query="ช่อง 8", site="youtube"))
        self.assertFalse(r.ok)
        self.assertIn("ไม่สำเร็จ", r.say)


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class NoTypingSkillTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_typing_requests_are_not_sent_to_claude(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        sent = []
        s = SkillsController(executor=actions.Executor(dry_run=True), run_timer=False,
                             reminders_path=Path(d.name) / "r.json", llm_ready=lambda: True,
                             forge=lambda request, **kw: sent.append(request),
                             user_skills=userskills.UserSkills(Path(d.name) / "u"))  # fmt: skip
        s._claude_on = lambda: True
        card = s.siteLearn("ค้นหาสูตรต้มยำ", WATCH)
        self.assertNotIn("confirmToken", card)
        self.assertIn("พิมพ์ข้อความไม่ได้", card["say"])
        self.assertIn("confirmToken", s.siteLearn("ซ่อนแชทสด", WATCH))  # งานปุ่มยังถามได้เหมือนเดิม
        self.assertIn("ห้ามทำคำสั่งที่แค่วางเคอร์เซอร์", s._site_request("youtube", "x", ""))
        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()
