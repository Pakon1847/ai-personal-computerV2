"""ล็อกจอเมื่อไม่ได้ใช้เครื่อง แล้วออกเอง (aipc.ui.idle · ขั้น A 2026-10-06)."""

import json
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from aipc.ui import idle, settings

try:
    from PySide6.QtGui import QGuiApplication, QImage
except ImportError:  # วินโดวส์ที่ไม่มี PySide6
    QGuiApplication = None


class FakeProc:
    def __init__(self, args):
        self.args, self.terminated = args, False

    def poll(self):
        return 0 if self.terminated else None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0


class IdleArgsTest(unittest.TestCase):
    def test_off_means_no_swayidle(self):
        self.assertIsNone(idle.swayidle_args(0, 600, ["swaylock"]))

    def test_lock_then_logout_counted_from_last_use(self):
        args = idle.swayidle_args(
            300, 600, idle.lock_command(PurePosixPath("/run/user/1/aipc/lock.png"))
        )
        self.assertEqual(args[:2], ["swayidle", "-w"])
        self.assertEqual(args[2:4], ["timeout", "300"])
        self.assertIn("swaylock -f -e -k -l", args[4])
        self.assertIn("-i /run/user/1/aipc/lock.png -s fill", args[4])
        self.assertEqual(args[5:], ["timeout", "900", "labwc --exit"])  # ล็อก 5 นาที + ออกอีก 10 นาที

    def test_lock_text_tells_what_to_do(self):
        lines = idle.lock_lines("น้ำฝน", 5, 10)
        self.assertEqual(lines[0], "หน้าจอล็อกอยู่")
        self.assertIn("น้ำฝน", lines[1])
        self.assertTrue(any("รหัสผ่าน" in x and "~" in x for x in lines))
        self.assertTrue(any("10 นาที" in x and "ออกจากระบบ" in x for x in lines))


class IdleLockTest(unittest.TestCase):
    def make(self, which=lambda t: f"/usr/bin/{t}", render=None):
        self.spawned = []
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)

        def spawn(args):
            p = FakeProc(args)
            self.spawned.append(p)
            return p

        def fake_render(path, lines, size):
            path.write_text("png", encoding="utf-8")
            return path

        return idle.IdleLock(
            spawn=spawn, which=which, image_dir=Path(d.name), render=render or fake_render
        )

    def test_start_once_restart_on_change_stop_when_off(self):
        lock = self.make()
        self.assertIsNotNone(lock.apply(5, 10, "ก"))
        self.assertIsNone(lock.apply(5, 10, "ก"))  # ค่าเดิม (เช่นเปลี่ยนธีม) = ไม่เริ่มใหม่
        self.assertEqual(len(self.spawned), 1)
        lock.apply(1, 10, "ก")
        self.assertTrue(self.spawned[0].terminated)
        self.assertEqual(self.spawned[1].args[3], "60")
        self.assertIsNone(lock.apply(0, 10, "ก"))
        self.assertTrue(self.spawned[1].terminated)
        self.assertEqual(lock.status, "ปิดอยู่")

    def test_missing_tools_is_reported_not_silent(self):
        lock = self.make(which=lambda t: None if t == "swaylock" else "/usr/bin/x")
        self.assertIsNone(lock.apply(5, 10))
        self.assertEqual(self.spawned, [])
        self.assertIn("swaylock", lock.status)

    def test_lock_still_works_when_image_fails(self):
        def broken(path, lines, size):
            raise OSError("no font")

        lock = self.make(render=broken)
        args = lock.apply(5, 10)
        self.assertNotIn("-i", args[4])  # จอสีพื้น · ล็อกได้เหมือนเดิม


class LockPrefsTest(unittest.TestCase):
    def test_defaults_round_trip_and_bad_values(self):
        self.assertEqual((settings.UiPrefs().lock_min, settings.UiPrefs().logout_min), (5, 10))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ui.json"
            settings.save(settings.UiPrefs(lock_min=0, logout_min=30), p)
            got = settings.load(p)
            self.assertEqual((got.lock_min, got.logout_min), (0, 30))
            p.write_text(json.dumps({"lock_min": 7, "logout_min": True}), encoding="utf-8")
            got = settings.load(p)
            self.assertEqual((got.lock_min, got.logout_min), (5, 10))


@unittest.skipIf(QGuiApplication is None, "ไม่มี PySide6")
class LockImageTest(unittest.TestCase):
    def test_png_has_screen_size(self):
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QGuiApplication.instance() or QGuiApplication([])
        from aipc.ui import app as uiapp

        uiapp.load_fonts()
        with tempfile.TemporaryDirectory() as d:
            out = idle.render_lock_image(
                Path(d) / "lock.png", idle.lock_lines("ทดสอบ", 5, 10), (1280, 720)
            )
            img = QImage(str(out))
            self.assertEqual((img.width(), img.height()), (1280, 720))
        self.assertIsNotNone(app)
