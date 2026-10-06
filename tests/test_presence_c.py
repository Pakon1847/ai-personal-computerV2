"""ขั้น C: ตัวตัดสินใจ (aipc.ui.presence.Decider) + การต่อกับ swayidle · ไม่ใช้กล้อง.

กฎจากขั้น B (docs/benchmarks/2026-10-06-presence-b): ไม่เห็นเจ้าของ → ล็อก → ไม่มีใครอีก → ออก ·
เห็นคนอื่น → ล็อกเท่านั้น (ห้ามออก) · เทียบทุกหน้า · กล้องเปิดเฉพาะตอนไม่ได้แตะเครื่อง
"""

import tempfile
import unittest
from pathlib import Path, PurePosixPath

from aipc.ui import idle, presence, settings
from aipc.ui.presence import Decider, Seen

OWNER, STRANGER, NOBODY = Seen(1, True, False), Seen(1, False, True), Seen(0)
NOT_CHECKED = Seen(1)  # มีหน้า แต่รอบนี้ไม่ได้เทียบ


def drive(d, steps, start=0.0, step=0.5, idle=True):
    """ส่ง Seen ทีละ 0.5 วิ · จำลอง swaylock ขึ้นหลังสั่ง "lock" (และค้างจนกว่าเทสต์จะปลดเอง) · คืน [(เวลา, คำสั่ง)]."""
    out, t = [], start
    for seen in steps:
        a = d.tick(t, idle, d.state == "locked", seen)
        if a:
            out.append((t, a))
        t += step
    return out


class DeciderTest(unittest.TestCase):
    def test_owner_present_never_locks(self):
        self.assertEqual(drive(Decider(), [OWNER, NOT_CHECKED, NOT_CHECKED, NOT_CHECKED] * 100), [])

    def test_absent_locks_after_30s_then_logout_after_30s(self):
        d = Decider(30, 30)
        acts = drive(d, [NOBODY] * 200)
        self.assertEqual(acts, [(30.0, "lock"), (60.0, "logout")])
        self.assertEqual(d.reason, "absent")

    def test_looking_down_shorter_than_threshold_is_fine(self):
        # ขั้น B: ระหว่างนั่งใช้ ไม่เห็นหน้านานสุด 14.5 วิ
        self.assertEqual(drive(Decider(), ([OWNER] + [NOBODY] * 29) * 20), [])

    def test_stranger_locks_fast_but_never_logs_out(self):
        d = Decider(30, 30)
        acts = drive(d, ([STRANGER] + [NOT_CHECKED] * 3) * 60)  # เทียบทุก 2 วิ
        self.assertEqual(acts[0], (4.0, "lock"))  # 3 ครั้งติด = 0, 2, 4 วิ
        self.assertEqual([a for _, a in acts], ["lock"])  # ห้ามออกจากระบบจากการจำหน้า (M3 ไม่ผ่าน)
        self.assertEqual(d.reason, "stranger")

    def test_owner_among_several_faces_counts_as_present(self):
        both = Seen(2, owner=True, stranger=False)  # เจ้าของ + คนชะโงกมาดู
        self.assertEqual(drive(Decider(), ([both] + [NOT_CHECKED] * 3) * 50), [])

    def test_face_during_lock_cancels_auto_logout(self):
        d = Decider(30, 30)
        acts = drive(d, [NOBODY] * 70 + [NOT_CHECKED] + [NOBODY] * 200)
        self.assertEqual([a for _, a in acts], ["lock"])  # มีคนกลับมาหน้าจอ → ไม่ออก (ปลดด้วยรหัสผ่านเอง)

    def test_touching_input_resets_and_camera_off(self):
        d = Decider(30, 30)
        drive(d, [NOBODY] * 50)  # 25 วิ
        self.assertIsNone(d.tick(25.0, False, False, None))
        self.assertEqual(d.state, "active")
        acts = drive(d, [NOBODY] * 70, start=26.0)
        self.assertEqual(acts[0], (56.0, "lock"))  # นับใหม่จากตอนกลับมาว่าง

    def test_unlocked_with_password_returns_to_active(self):
        d = Decider(30, 30)
        drive(d, [NOBODY] * 61)
        self.assertEqual(d.state, "locked")
        d.tick(31.0, False, False, None)  # ภายใน 3 วิหลังสั่งล็อก: ยังไม่นับว่าปลด
        self.assertEqual(d.state, "locked")
        d.tick(40.0, False, False, None)  # swaylock จบแล้ว (รหัสถูก)
        self.assertEqual(d.state, "active")

    def test_existing_lock_from_step_a_is_left_alone(self):
        d = Decider(30, 30)
        self.assertIsNone(d.tick(0.0, True, True, NOBODY))
        self.assertEqual(d.state, "active")


class WiringTest(unittest.TestCase):
    def test_swayidle_flag_only_when_presence(self):
        flag = PurePosixPath("/run/user/1/aipc/input-idle")
        args = idle.swayidle_args(0, 600, ["swaylock"], idle_flag=flag)
        self.assertEqual(args, ["swayidle", "-w", "timeout", "10", f"touch {flag}", "resume", f"rm -f {flag}"])
        self.assertIsNone(idle.swayidle_args(0, 600, ["swaylock"]))
        both = idle.swayidle_args(300, 600, ["swaylock"], idle_flag=flag)
        self.assertEqual(both[-6:], ["timeout", "300", "swaylock", "timeout", "900", "labwc --exit"])

    def test_idlelock_starts_monitor_only_when_enabled(self):
        spawned = []

        class P:
            def __init__(self, a):
                self.args, self.done = a, False

            def poll(self):
                return 0 if self.done else None

            def terminate(self):
                self.done = True

            def wait(self, timeout=None):
                return 0

        with tempfile.TemporaryDirectory() as d:
            lock = idle.IdleLock(spawn=lambda a: spawned.append(P(a)) or spawned[-1],
                                 which=lambda t: "/usr/bin/" + t, image_dir=Path(d),
                                 render=lambda path, lines, size: path)  # fmt: skip
            lock.apply(5, 10, "ก")
            self.assertEqual(len(spawned), 1)
            lock.apply(5, 10, "ก", presence=(30, 30))
            self.assertTrue(spawned[0].done)
            mon = spawned[2].args
            self.assertIn("aipc.ui.presence", mon)
            self.assertEqual(mon[mon.index("--lock-after") + 1], "30")
            lock.apply(0, 10, "ก", presence=(30, 30))  # ปิดขั้น A แต่ยังใช้กล้อง → swayidle มีแค่ธง
            self.assertNotIn("labwc --exit", spawned[3].args)
            lock.apply(0, 10, "ก")
            self.assertTrue(all(p.done for p in spawned))

    def test_lock_text_mentions_camera_when_presence(self):
        lines = idle.lock_lines("ก", 5, 10, presence_logout_s=30)
        self.assertIn("กล้อง", lines[1])
        self.assertIn("30 วินาที", lines[3])

    def test_prefs_default_off_and_validated(self):
        self.assertFalse(settings.UiPrefs().presence)
        p = settings.UiPrefs(presence=True, presence_lock_s=45, presence_logout_s=True).cleaned()
        self.assertEqual((p.presence, p.presence_lock_s, p.presence_logout_s), (True, 30, 30))

    def test_camera_claim_flag_removed_after(self):
        with tempfile.TemporaryDirectory() as d:
            flag = Path(d) / "camera-busy"
            with presence.camera_claim(wait_s=0, flag=flag, sleep=lambda s: None):
                self.assertTrue(flag.exists())
            self.assertFalse(flag.exists())

    def test_monitor_never_writes_images(self):
        import re

        src = Path(presence.__file__).read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"imwrite|imencode|VideoWriter\(", src))
