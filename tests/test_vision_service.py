"""แกนของ visiond (การ์ด 0015 หัวข้อ 12) · สแกนเนอร์ปลอม ไม่มีกล้อง ไม่มีโมเดล."""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from aipc.vision import pipeline, service, store


def vec(seed: int) -> np.ndarray:
    v = np.random.default_rng(seed).normal(size=128).astype(np.float32)
    return v / np.linalg.norm(v)


class FakeScanner:
    """scan → คนที่ตั้งไว้ (ถ้าอยู่ในแม่แบบ) · enroll → แม่แบบหรือ Rejected."""

    def __init__(self, who=None, reason="matched", enroll_result=None):
        self.who, self.reason, self.enroll_result = who, reason, enroll_result
        self.scans = self.enrolls = 0
        self.seen_templates = {}

    def scan(self, frames, templates, progress=None):
        self.scans += 1
        self.seen_templates = templates
        if self.who in templates and self.reason == "matched":
            return pipeline.ScanResult(self.who, "matched", 0.8, 0.2)
        return pipeline.ScanResult(
            None, self.reason if self.reason != "matched" else "below_threshold"
        )

    def enroll(self, frames, per_pose=2, progress=None):
        self.enrolls += 1
        return self.enroll_result or pipeline.Template(vec(1), 6, "2026-09-30T09:00:00+07:00")


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class TicketsTest(unittest.TestCase):
    def test_one_use_bound_to_user_and_expires(self):
        c = Clock()
        t = service.Tickets(ttl=30, clock=c)
        t.issue("namfon")
        self.assertFalse(t.consume("boss"), "ตั๋วของคนหนึ่งใช้เข้าอีกคนไม่ได้")
        self.assertTrue(t.consume("namfon"))
        self.assertFalse(t.consume("namfon"), "ใช้ซ้ำไม่ได้")
        t.issue("namfon")
        c.t = 31
        self.assertFalse(t.consume("namfon"), "หมดอายุ 30 วิ")


class FaceLoginTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "face-login"
        self.gallery = service.Gallery(self.dir, model_sha256="m1")
        self.passwords = {"namfon": "right-pass-1", "boss": "boss-pass-2"}
        self.logs = []

    def make(self, scanner):
        return service.FaceLogin(
            scanner, self.gallery, lambda u, p: self.passwords.get(u) == p, log=self.logs.append
        )

    def opt_in(self, user, seed):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.gallery.store(user).save(vec(seed), 6, "x", store.Consent("2026-09-30T09:00:00+07:00"))

    def test_found_issues_a_ticket_for_that_user_only(self):
        self.opt_in("namfon", 1)
        f = self.make(FakeScanner("namfon"))
        out = f.identify([])
        self.assertEqual((out.ok, out.state, out.user), (True, "found", "namfon"))
        self.assertFalse(f.consume("boss"))
        self.assertTrue(f.consume("namfon"))
        self.assertFalse(f.consume("namfon"))

    def test_only_opted_in_accounts_are_scanned(self):
        self.opt_in("namfon", 1)
        scanner = FakeScanner("boss")  # boss ลงทะเบียนในเซสชันเอง แต่ไม่ได้เปิดเข้าเครื่องด้วยใบหน้า
        out = self.make(scanner).identify([])
        self.assertEqual(list(scanner.seen_templates), ["namfon"])
        self.assertFalse(out.ok)

    def test_no_one_opted_in_means_camera_not_used(self):
        scanner = FakeScanner("namfon")
        out = self.make(scanner).identify([])
        self.assertEqual(out.state, "no-templates")
        self.assertEqual(scanner.scans, 0)

    def test_five_failures_lock_until_a_password_login(self):
        self.opt_in("namfon", 1)
        scanner = FakeScanner("namfon", reason="below_threshold")
        f = self.make(scanner)
        for _ in range(5):
            self.assertEqual(f.identify([]).state, "unknown")
        scanner.reason = "matched"
        self.assertEqual(f.identify([]).state, "locked")
        self.assertFalse(f.consume("namfon"), "ล็อกแล้วไม่มีตั๋ว")
        f.password_login()
        self.assertEqual(f.identify([]).state, "found")

    def test_no_face_is_not_counted_as_a_failure(self):
        self.opt_in("namfon", 1)
        f = self.make(FakeScanner(None, reason="not_enough_frames"))
        for _ in range(10):
            self.assertEqual(f.identify([]).state, "no-face")
        self.assertFalse(f.lockout.locked)

    def test_spoof_counts_and_gives_no_ticket(self):
        self.opt_in("namfon", 1)
        f = self.make(FakeScanner("namfon", reason="spoof"))
        self.assertEqual(f.identify([]).state, "spoof")
        self.assertEqual(f.lockout.failures, 1)
        self.assertFalse(f.consume("namfon"))

    def test_enroll_needs_the_right_password_before_the_camera(self):
        scanner = FakeScanner()
        f = self.make(scanner)
        out = f.enroll("namfon", "wrong", [], "2026-09-30T09:00:00+07:00")
        self.assertEqual(out.state, "bad-password")
        self.assertEqual(scanner.enrolls, 0, "รหัสผิด = ไม่เปิดกล้องเลย")
        self.assertFalse(self.gallery.path("namfon").exists())
        out = f.enroll("namfon", "right-pass-1", [], "2026-09-30T09:00:00+07:00")
        self.assertEqual(out.state, "saved")
        self.assertIn("namfon", self.gallery.templates())

    def test_enroll_other_account_needs_its_password(self):
        f = self.make(FakeScanner())
        self.assertEqual(f.enroll("boss", "right-pass-1", [], "t").state, "bad-password")

    def test_enroll_without_consent_is_refused(self):
        f = self.make(FakeScanner())
        self.assertEqual(f.enroll("namfon", "right-pass-1", [], "").state, "no-consent")

    def test_rejected_enroll_saves_nothing(self):
        rej = pipeline.Rejected(("front",), "ขาดท่าตรง", "too_dark")
        f = self.make(FakeScanner(enroll_result=rej))
        out = f.enroll("namfon", "right-pass-1", [], "t")
        self.assertFalse(out.ok)
        self.assertFalse(self.gallery.path("namfon").exists())

    def test_strange_names_never_touch_the_disk(self):
        f = self.make(FakeScanner())
        self.assertEqual(f.enroll("../etc/x", "p", [], "t").state, "bad-password")
        with self.assertRaises(ValueError):
            self.gallery.path("../../root")

    def test_remove_needs_password_and_kills_pending_ticket(self):
        self.opt_in("namfon", 1)
        f = self.make(FakeScanner("namfon"))
        f.identify([])
        self.assertEqual(f.remove("namfon", "wrong").state, "bad-password")
        self.assertTrue(self.gallery.path("namfon").exists())
        self.assertEqual(f.remove("namfon", "right-pass-1").state, "removed")
        self.assertFalse(self.gallery.path("namfon").exists())
        self.assertFalse(f.consume("namfon"), "ปิดแล้วตั๋วที่ค้างต้องใช้ไม่ได้")
        self.assertEqual(f.gallery.templates(), {})

    def test_logs_have_no_scores_or_vectors(self):
        self.opt_in("namfon", 1)
        f = self.make(FakeScanner("namfon"))
        f.identify([])
        self.assertTrue(self.logs)
        for line in self.logs:
            self.assertNotRegex(line, r"0\.\d{2}")

    def test_broken_or_other_model_files_are_skipped(self):
        self.opt_in("namfon", 1)
        (self.dir / "boss.json").write_text("{เสีย", encoding="utf-8")
        other = service.Gallery(self.dir, model_sha256="m2")
        self.assertEqual(list(self.gallery.templates()), ["namfon"])
        self.assertEqual(other.templates(), {}, "โมเดลเปลี่ยน = แม่แบบเดิมใช้ไม่ได้")


if __name__ == "__main__":
    unittest.main()
