"""จอล็อกรุ่น 2 (การ์ด 0055 · เกณฑ์ L2–L5 L8 ส่วนเทสต์) · ไม่มี gtklock/กล้อง/socket จริง."""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aipc.ui import lockscreen
from aipc.vision import daemon, face_unlock, service, store
from tests.test_vision_service import FakeScanner, vec

GREETER, NAMFON, BOSS = 120, 1001, 1002


class AssetsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def test_layout_has_every_id_gtklock_needs_and_escapes_text(self):
        ui = lockscreen.layout(self.dir / "l.ui", 'งาน <ยังอยู่> & "ครบ"', False, "น้ำฝน")
        s = ui.read_text(encoding="utf-8")
        needed_ids = ("window-box", "info-box", "time-box", "clock-label", "date-label",
                      "body-revealer", "body-grid", "input-label", "input-field",
                      "message-revealer", "message-scrolled-window", "message-box",
                      "unlock-button", "error-label", "warning-label", "window_pw_check",
                      "window_pw_toggle_vis")  # fmt: skip
        for needed in needed_ids:
            self.assertIn(f'"{needed}"', s, needed)
        self.assertIsNone(re.search(r"\{[a-z_]+\}", s))  # ไม่มีช่องที่ลืมแทน
        self.assertIn("&lt;ยังอยู่&gt; &amp; &quot;ครบ&quot;", s)
        self.assertIn(">น้ำฝน<", s)
        self.assertIn(">น<", s)  # วงกลมอักษรแรก

    def test_style_scales_to_screen_height(self):
        # จอ 720 แถว: เนื้อหาสูงกว่าจอ = Wayland protocol error จอดำ (พบบน Pi 5) → ย่อทุกขนาดตามความสูงจอ
        big = lockscreen.style(self.dir / "a.css", 1080).read_text(encoding="utf-8")
        small = lockscreen.style(self.dir / "b.css", 720).read_text(encoding="utf-8")
        self.assertIn("font-size: 132pt", big)
        self.assertIn("font-size: 88pt", small)
        self.assertIn("border-radius: 50%", small)  # % ไม่ถูกย่อ
        self.assertIn("#16171e", small)  # สีไม่ถูกแตะ
        tiny = lockscreen.style(self.dir / "c.css", 200).read_text(encoding="utf-8")
        self.assertIn("font-size: 66pt", tiny)  # ไม่ต่ำกว่าครึ่ง

    def test_warning_class_when_logout_is_on(self):
        s = lockscreen.layout(self.dir / "l.ui", "จะหาย", True, "a").read_text(encoding="utf-8")
        self.assertIn('<class name="warn"/>', s)
        self.assertIn(">! จะหาย<", s)

    def test_command_uses_thai_locale_when_it_can_be_built(self):
        def localedef(args, **kw):
            target = Path(args[-1])
            target.mkdir(parents=True)
            (target / "LC_TIME").write_text("x")
            return subprocess.CompletedProcess(args, 0)

        cmd = lockscreen.prepare(self.dir, "งานยังอยู่", False, "น้ำฝน", run=localedef)
        self.assertEqual(cmd[0], "env")
        self.assertIn("LC_ALL=th_TH.UTF-8", cmd)
        self.assertEqual(cmd[cmd.index("-D") + 1], lockscreen.DATE_THAI)
        self.assertEqual(cmd[cmd.index("-t") + 1], "%H:%M")
        self.assertIn("-d", cmd)  # แยกตัว (swayidle ไม่ค้าง)
        self.assertNotIn("userinfo-module", cmd)  # ล้มเมื่อใช้ฟอนต์ไทย (ทดสอบบน Pi 5)
        self.assertTrue((self.dir / "gtklock.ui").exists())
        self.assertIn(str(lockscreen.FONTS), (self.dir / "fonts.conf").read_text(encoding="utf-8"))

    def test_clock_only_until_a_key_and_module_only_when_installed(self):
        # Pakon: "ไม่ต้องมีกรอบอะไรเลย" → เริ่มแบบซ่อนกล่องรหัส · กดปุ่ม = กล่องขึ้น · ไม่แตะ 20 วิ = ซ่อน
        def fails(args, **kw):
            raise OSError

        mod = self.dir / "aipc-autounlock.so"
        cmd = lockscreen.prepare(self.dir, "x", False, "a", run=fails, auto=True, module=mod)
        self.assertIn("-S", cmd)
        self.assertIn("-H", cmd)
        self.assertNotIn(str(mod), cmd)  # ยังไม่ได้ติดตั้งโมดูล = ไม่ปลดเอง
        self.assertIn(lockscreen.HINT_KEY, (self.dir / "gtklock.ui").read_text(encoding="utf-8"))
        mod.write_bytes(b"so")
        cmd = lockscreen.prepare(self.dir, "x", False, "a", run=fails, auto=True, module=mod)
        self.assertEqual(cmd[cmd.index(str(mod)) - 1], "-m")
        self.assertIn(lockscreen.HINT_AUTO, (self.dir / "gtklock.ui").read_text(encoding="utf-8"))
        cmd = lockscreen.prepare(self.dir, "x", False, "a", run=fails, auto=False, module=mod)
        self.assertNotIn(str(mod), cmd)  # ปิดในตั้งค่า = กล้องไม่เปิดตอนล็อก

    def test_no_locale_means_numeric_date_not_a_guess(self):
        def fails(args, **kw):
            raise OSError("no localedef")

        cmd = lockscreen.prepare(self.dir, "x", False, "a", run=fails)
        self.assertNotIn("LC_ALL=th_TH.UTF-8", cmd)
        self.assertEqual(cmd[cmd.index("-D") + 1], lockscreen.DATE_PLAIN)


class FaceUnlockDecisionTest(unittest.TestCase):
    def ask(self, ok=True, user="namfon"):
        self.asked = []

        def ask(req):
            self.asked.append(req)
            return {"ok": ok, "user": user}

        return ask

    def test_empty_field_asks_visiond_for_own_account(self):
        self.assertEqual(face_unlock.decide(b"\0", "namfon", "namfon", self.ask()), 0)
        self.assertEqual(self.asked, [{"op": "unlock", "username": "namfon"}])

    def test_typed_password_skips_camera(self):
        self.assertEqual(face_unlock.decide(b"secret\0", "namfon", "namfon", self.ask()), 1)
        self.assertEqual(self.asked, [])

    def test_never_unlocks_on_doubt(self):
        self.assertEqual(face_unlock.decide(b"", "namfon", "boss", self.ask()), 1)  # ชื่อไม่ตรงผู้รัน
        self.assertEqual(face_unlock.decide(b"", "", "namfon", self.ask()), 1)
        self.assertEqual(face_unlock.decide(b"", "namfon", "namfon", self.ask(ok=False)), 1)
        self.assertEqual(face_unlock.decide(b"", "namfon", "namfon", self.ask(user="boss")), 1)


class UnlockOpTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        gallery = service.Gallery(Path(tmp.name) / "face-login", model_sha256="m1")
        gallery.folder.mkdir(parents=True)
        gallery.store("namfon").save(vec(1), 6, "x", store.Consent("2026-09-30T09:00:00+07:00"))
        gallery.store("boss").save(vec(2), 6, "x", store.Consent("2026-09-30T09:00:00+07:00"))
        self.scanner = FakeScanner("namfon")
        self.face = service.FaceLogin(self.scanner, gallery, lambda u, p: False)
        uids = {"namfon": NAMFON, "boss": BOSS}
        self.h = daemon.Handler(self.face, lambda s: iter(()), GREETER, uid_of=uids.get)

    def unlock(self, uid, user="namfon"):
        return self.h.public({"op": "unlock", "username": user}, uid, lambda m: None)

    def test_l2_owner_face_unlocks(self):
        r = self.unlock(NAMFON)
        self.assertEqual((r["ok"], r["user"]), (True, "namfon"))
        self.assertEqual(list(self.scanner.seen_templates), ["namfon"])  # เทียบแค่แม่แบบของบัญชีนั้น

    def test_l8_only_the_owner_may_ask(self):
        for uid in (BOSS, GREETER, 0):
            self.assertFalse(self.unlock(uid)["ok"], uid)
        self.assertEqual(self.scanner.scans, 0)

    def test_l4_someone_else_does_not_unlock(self):
        self.scanner.who = "boss"  # หน้าที่กล้องเห็นเป็นของ boss แต่ขอปลดของ namfon
        self.assertFalse(self.unlock(NAMFON)["ok"])

    def test_l3_photo_is_rejected_and_counted(self):
        self.scanner.reason = "spoof"
        for _ in range(service.LOCK_AFTER):
            self.assertEqual(self.unlock(NAMFON)["state"], "spoof")
        self.scanner.reason = "matched"
        self.assertEqual(self.unlock(NAMFON)["state"], "locked")  # ผิดครบ = ใช้รหัสผ่าน
        with mock.patch.object(service.time, "monotonic", return_value=10**9):
            self.assertTrue(self.unlock(NAMFON)["ok"])  # พักครบ 10 นาที = ลองใบหน้าได้อีก

    def test_no_face_does_not_count_as_a_failure(self):
        self.scanner.reason = "not_enough_frames"
        for _ in range(service.LOCK_AFTER + 2):
            self.assertEqual(self.unlock(NAMFON)["state"], "no-face")
        self.scanner.reason = "matched"
        self.assertTrue(self.unlock(NAMFON)["ok"])



if __name__ == "__main__":
    unittest.main()


class FaceWatchTest(unittest.TestCase):
    def fake_watch(self, rounds):
        it = iter(rounds)

        def watch(user, on_seen, stop, seconds=60.0):
            msgs, final = next(it)
            for m in msgs:
                on_seen(m)
                if stop.is_set():
                    break
            return final

        return watch

    def test_prints_owner_and_stops_at_first_sight(self):
        import io

        from aipc.vision import face_watch

        out = io.StringIO()
        nobody = [{"faces": 0, "owner": False}]  # รอบแรกไม่มีใคร (หมด 60 วิ)
        arrives = [{"faces": 1, "owner": False}, {"faces": 1, "owner": True}]
        rounds = [(nobody, {"ok": True}), (arrives, {"ok": True})]
        self.assertEqual(face_watch.run("namfon", self.fake_watch(rounds), out), 0)
        self.assertEqual(out.getvalue(), "OWNER\n")

    def test_unusable_exits_so_module_backs_off(self):
        import io

        from aipc.vision import face_watch

        out = io.StringIO()
        rounds = [([], {"ok": False, "state": "no-templates"})]
        self.assertEqual(face_watch.run("namfon", self.fake_watch(rounds), out), 2)
        self.assertEqual(out.getvalue(), "")
