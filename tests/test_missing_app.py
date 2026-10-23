"""เปิดแอปที่ไม่มีในเครื่อง → ถามติดตั้ง → ถามเปิดเว็บ (การ์ด 0054 · เกณฑ์ A1 A5 ส่วนเทสต์)."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aipc.skills import apps, command  # noqa: E402

try:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None


def wait_until(cond, timeout=5.0):
    app = QCoreApplication.instance() or QGuiApplication([])
    end = time.monotonic() + timeout
    while not cond() and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
    return cond()


class ParseTest(unittest.TestCase):
    # tests/__init__.py ตั้ง AIPC_APP_DIRS="" = ไม่มีแอปติดตั้งเลย (ผลเหมือนกันทุกเครื่อง)
    def test_known_but_missing_app(self):
        for text, key in (("เปิดซูม", "zoom"), ("เปิด VLC หน่อย", "vlc"), ("ช่วยเปิดทอนนี่", "thonny"),
                          ("เปิดโปรแกรมแต่งรูป", "gimp"), ("เปิดแคนวา", "canva")):  # fmt: skip
            c = command.parse(text)
            self.assertEqual((c.plan.action, c.plan.params), ("missing_app", {"app": key}), text)
            self.assertFalse(c.needs_confirmation, text)  # คำถามอยู่ที่การ์ดเอง ไม่ต้องถามซ้ำ

    def test_not_a_known_app(self):
        for text in ("เปิดซูมภาพ", "ซูมคืออะไร", "อย่าเปิดซูม"):
            c = command.parse(text)
            self.assertFalse(c and c.plan.action == "missing_app", text)

    def test_installed_app_opens_with_thai_name(self):
        with tempfile.TemporaryDirectory() as d:
            desk = "[Desktop Entry]\nType=Application\nName=VLC media player\nExec=vlc\n"
            (Path(d) / "vlc.desktop").write_text(desk, encoding="utf-8")
            with mock.patch.object(apps, "REGISTRY", apps.Registry([Path(d)])):
                c = command.parse("เปิดวีแอลซี")
            want = ("open_app", {"app": "desk:vlc.desktop"})
            self.assertEqual((c.plan.action, c.plan.params), want)


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class FlowTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.sent = []
        self.result = {"ok": True, "message": "ติดตั้ง VLC แล้ว"}
        self.opened = []

        class Exec:
            dry_run = False

            def execute(inner, plan):  # noqa: N805
                from aipc.skills.actions import Outcome

                self.opened.append((plan.action, dict(plan.params)))
                return Outcome(True, plan.summary)

        self.s = SkillsController(executor=Exec(), reminders_path=Path(tmp.name) / "r.json",
                                  run_timer=False, installer=self.install)  # fmt: skip
        self.done = []
        self.s.appInstallDone.connect(self.done.append)

    def install(self, req, on_progress=None):
        self.sent.append(req)
        if on_progress:
            for pct in (0, 27.5, 60.0):
                on_progress({"state": "progress", "stage": "กำลังดาวน์โหลด", "percent": pct})
        return self.result

    def test_a1_install_no_then_web_yes(self):
        # Zoom: ไม่มีแพ็กเกจ → ถามเว็บเลย · ใช่ = เปิดลิงก์จากรายการ
        card = self.s.handle("เปิดซูม")
        self.assertIn("เบราว์เซอร์", card["title"])
        out = self.s.confirm(card["confirmToken"], True)
        web = {"url": "https://app.zoom.us/wc", "site": "zoom"}
        self.assertEqual(self.opened, [("open_url", web)])
        self.assertTrue(out["title"])

    def test_a1_install_no_web_no_does_nothing(self):
        card = self.s.handle("เปิด vlc")
        self.assertIn("ติดตั้งไหม", card["title"])
        out = self.s.confirm(card["confirmToken"], False)  # VLC ไม่มีเว็บ → จบ
        self.assertEqual(out["confirmToken"], "")
        self.assertEqual((self.opened, self.sent), ([], []))

    def test_asks_again_every_time(self):
        for _ in range(3):
            card = self.s.handle("เปิดซูม")
            self.assertTrue(card["confirmToken"])
            self.s.confirm(card["confirmToken"], False)
        self.assertEqual(self.opened, [])

    def test_install_yes_then_ok_installs_and_opens(self):
        card = self.s.handle("เปิด vlc")
        out = self.s.confirm(card["confirmToken"], True)
        self.assertEqual((out["kind"], out["appInstall"]), ("app-install", "vlc"))
        self.assertEqual(self.sent, [])  # ตอบใช่อย่างเดียวยังไม่ติดตั้ง ต้องกด "ตกลง" อีกครั้ง
        self.assertTrue(self.s.installApp("vlc"))
        self.assertFalse(self.s.installApp("vlc"))  # กำลังติดตั้ง = ไม่ซ้อน
        self.assertTrue(wait_until(lambda: self.done))
        self.assertEqual(self.sent, [{"app": "vlc"}])  # ไม่มีรหัส (Pakon 2026-10-23)
        self.assertEqual(self.done[0]["chips"][0]["text"], "ติดตั้งแล้ว")
        self.assertEqual(self.s.installPercent, 60.0)  # ตัวเลขจากตัวติดตั้ง (ของจริงมาจาก apt)
        self.assertEqual(self.s.installStage, "กำลังดาวน์โหลด")

    def test_install_refused_by_helper_is_shown(self):
        self.result = {"ok": False, "message": "ดาวน์โหลดไม่ได้ · ตรวจอินเทอร์เน็ตแล้วลองใหม่"}
        self.s.installApp("vlc")
        self.assertTrue(wait_until(lambda: self.done))
        self.assertEqual(self.done[0]["title"], self.result["message"])
        self.assertEqual(self.opened, [])

    def test_only_listed_apps_with_package(self):
        self.assertFalse(self.s.installApp("zoom"))  # มีแต่เว็บ
        self.assertFalse(self.s.installApp("vlc; rm -rf /"))
        self.assertEqual(self.sent, [])


if __name__ == "__main__":
    unittest.main()


# ใช้ตัวเปิดหน้าจอเดียวกัน · import ทั้งโมดูล ไม่ให้เทสต์ของมันถูกรันซ้ำที่นี่
from tests import test_ui_qml as uiq  # noqa: E402


@unittest.skipIf(SkillsController is None or uiq.uiapp is None, "ไม่มี PySide6")
class InstallPopupQmlTest(unittest.TestCase):
    open_shell = uiq.ShellCardTest.open_shell

    def test_yes_opens_admin_popup_without_warnings(self):
        from PySide6.QtCore import Q_ARG, QMetaObject

        engine, win, warnings = self.open_shell("workspace")
        skills = engine._backends["skills"]
        page = uiq.find_all(win, "workspace")[0]
        card = skills.handle("เปิด vlc")
        out = skills.confirm(card["confirmToken"], True)
        QMetaObject.invokeMethod(page, "showCard", Q_ARG("QVariant", out))
        uiq.settle()
        popup = uiq.find_all(win, "installPopup")[0]
        self.assertTrue(popup.property("opened"))
        self.assertEqual(popup.property("key"), "vlc")
        self.assertEqual(warnings, [])
