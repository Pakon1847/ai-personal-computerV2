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

    def test_logout_zero_locks_only(self):
        # การ์ด 0051: ค่าออก 0 = ล็อกอย่างเดียว · ไม่มีคำสั่งออกจากระบบใน swayidle เลย
        args = idle.swayidle_args(300, 0, ["swaylock"])
        self.assertEqual(args, ["swayidle", "-w", "timeout", "300", "swaylock"])
        self.assertNotIn(idle.EXIT_CMD, args)

    def test_lock_only_text_says_work_is_kept(self):
        lines = idle.lock_lines("น้ำฝน", 5, 0)
        self.assertIn("ไม่ออกจากระบบเอง", lines[-1])
        self.assertFalse(any("จะหาย" in x for x in lines))

    def test_ring_matches_the_theme_and_is_always_visible(self):
        # Pakon 2026-10-23: จอล็อกสวยขึ้น · วงแหวนขึ้นตลอดให้รู้ว่าพิมพ์รหัสตรงไหน · สีจากธีมดำ
        cmd = idle.lock_command(None)
        self.assertIn("--indicator-idle-visible", cmd)
        self.assertEqual(cmd[cmd.index("--key-hl-color") + 1], "A5B4FC")
        self.assertEqual(cmd[cmd.index("--ring-wrong-color") + 1], "F28B80")
        self.assertNotIn("-i", cmd)

    def test_lock_text_tells_what_to_do(self):
        lines = idle.lock_lines("น้ำฝน", 5, 10)
        self.assertEqual(lines[0], "หน้าจอล็อกอยู่")
        self.assertIn("น้ำฝน", lines[1])
        self.assertTrue(any("รหัสผ่าน" in x and "Enter" in x for x in lines))
        self.assertTrue(any("~" in x for x in lines))  # แป้นไทย → บอกวิธีสลับ
        self.assertTrue(any("10 นาที" in x and "ออกจากระบบ" in x for x in lines))


class IdleLockTest(unittest.TestCase):
    def make(self, which=lambda t: None if t == "gtklock" else f"/usr/bin/{t}", render=None,
             prepare=None):  # fmt: skip
        # ค่าเริ่มต้น = เครื่องไม่มี gtklock → จอล็อกรุ่น 1 (swaylock) แบบเดิม
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

        self.dir = Path(d.name)
        return idle.IdleLock(spawn=spawn, which=which, image_dir=self.dir,
                             render=render or fake_render, prepare=prepare)  # fmt: skip

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

    def test_gtklock_when_installed_and_remembered_for_other_locks(self):
        # การ์ด 0055: มี gtklock = จอล็อกรุ่น 2 · คำสั่งถูกจำไว้ให้สั่งเสียง/ตัวตรวจด้วยกล้องใช้ตัวเดียวกัน
        seen = []

        def prepare(folder, keep, warn, name, height, auto):
            seen.append((keep, warn, name))
            return ["env", "X=1", "gtklock", "-d"]

        lock = self.make(which=lambda t: f"/usr/bin/{t}", prepare=prepare)
        args = lock.apply(5, 0, "น้ำฝน")
        self.assertEqual(args[4], "env X=1 gtklock -d")
        self.assertEqual(seen, [(idle.lock_lines("น้ำฝน", 5, 0)[-1], False, "น้ำฝน")])
        saved = json.loads((self.dir / "lock-command.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, ["env", "X=1", "gtklock", "-d"])
        lock.apply(5, 10, "น้ำฝน")
        self.assertTrue(seen[-1][1])  # ตั้งให้ออกเอง = บรรทัดเตือนสีส้ม

    def test_voice_lock_gets_gtklock_even_when_timer_lock_is_off(self):
        # พบบน Pi 5 2026-10-23: Pakon ปิดล็อกตามเวลา (lock_min 0) → "ล็อกหน้าจอ" ได้จอรุ่น 1
        def prepare(folder, keep, warn, name, height, auto):
            return ["gtklock", "-d"]

        lock = self.make(which=lambda t: f"/usr/bin/{t}", prepare=prepare)
        self.assertIsNone(lock.apply(0, 0, "Pakon"))  # ไม่มีตัวจับเวลา
        self.assertEqual(lock.status, "ปิดอยู่")
        saved = json.loads((self.dir / "lock-command.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, ["gtklock", "-d"])
        self.assertIn("ล็อกหน้าจอแล้ว", idle.lock_lines("Pakon", 0, 0)[1])  # ไม่ใช่ "เกิน 0 นาที"

    def test_gtklock_failure_falls_back_to_swaylock(self):
        def broken(folder, keep, warn, name, height, auto):
            raise OSError("no gtklock assets")

        lock = self.make(which=lambda t: f"/usr/bin/{t}", prepare=broken)
        args = lock.apply(5, 0)
        self.assertTrue(args[4].startswith("swaylock -f"))

    def test_missing_tools_is_reported_not_silent(self):
        lock = self.make(which=lambda t: None if t in ("swaylock", "gtklock") else "/usr/bin/x")
        self.assertIsNone(lock.apply(5, 10))
        self.assertEqual(self.spawned, [])
        self.assertIn("swaylock", lock.status)

    def test_lock_still_works_when_image_fails(self):
        def broken(path, lines, size):
            raise OSError("no font")

        lock = self.make(render=broken)
        args = lock.apply(5, 10)
        self.assertFalse(any("-i" in a.split() for a in args))  # จอสีพื้น · ล็อกได้เหมือนเดิม
        self.assertTrue(any(a.startswith("swaylock -f") for a in args))


class LockPrefsTest(unittest.TestCase):
    def test_defaults_round_trip_and_bad_values(self):
        # การ์ด 0051: ค่าเริ่มต้น = ล็อก 5 นาที · ไม่ออกจากระบบเอง
        self.assertEqual((settings.UiPrefs().lock_min, settings.UiPrefs().logout_min), (5, 0))
        self.assertEqual(settings.UiPrefs().gcal_alert_min, 10)  # การ์ด 0032
        self.assertEqual(settings.UiPrefs(gcal_alert_min=7).cleaned().gcal_alert_min, 10)
        self.assertEqual(settings.UiPrefs(gcal_alert_min=True).cleaned().gcal_alert_min, 10)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ui.json"
            settings.save(settings.UiPrefs(lock_min=0, logout_min=30), p)
            got = settings.load(p)
            self.assertEqual((got.lock_min, got.logout_min), (0, 30))
            p.write_text(json.dumps({"lock_min": 7, "logout_min": True}), encoding="utf-8")
            got = settings.load(p)
            self.assertEqual((got.lock_min, got.logout_min), (5, 0))

    def test_old_file_moves_to_lock_only_once(self):
        # ไฟล์ก่อนการ์ด 0051 (ไม่มี lock_policy) ที่มีค่าออกเดิม → ไม่ออกเอง · ค่าล็อกและค่าอื่นคงเดิม
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ui.json"
            old = {"lock_min": 10, "logout_min": 30, "presence_logout_s": 60, "theme": "light"}
            p.write_text(json.dumps(old), encoding="utf-8")
            got = settings.load(p)
            self.assertEqual((got.lock_min, got.logout_min, got.presence_logout_s), (10, 0, 0))
            self.assertEqual(got.theme, "light")
            # ผู้ใช้เลือกออกเองหลังย้ายแล้ว → จำไว้ ไม่ถูกย้ายซ้ำ
            got.logout_min = 30
            settings.save(got, p)
            self.assertEqual(settings.load(p).logout_min, 30)


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
