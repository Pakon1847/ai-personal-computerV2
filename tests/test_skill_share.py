"""แชร์สกิลด้วย QR (การ์ด 0080) · H1 (ผ่านด่านทุกครั้ง) · H2 ส่วนดิจิทัล (สร้างรูปแล้วอ่านกลับตรงทุกไบต์) · ไม่ต่อเน็ต.

H2 ตัวจริงต้องอ่านด้วยกล้อง Pi ( ยังไม่ได้วัด ) · ตรงนี้ตรวจว่ารูป PNG ที่ระบบสร้างอ่านกลับได้ตรงทุกไบต์
"""

import io
import json
import os
import tempfile
import time
import unittest
import urllib.error
import zlib
from pathlib import Path
from unittest import mock

from aipc.cloud.ledger import Ledger
from aipc.skills import share

ROOT = Path(__file__).resolve().parent.parent
SETS = sorted((ROOT / "tests/data").glob("skill_guard_*s1.json"))
ITEMS = [i for p in SETS for i in json.loads(p.read_text(encoding="utf-8"))["items"]]
GOOD = [i for i in ITEMS if i["label"] == "good"]
BAD = [i for i in ITEMS if i["label"] == "bad"]


class CodecTest(unittest.TestCase):
    def test_round_trip_and_size(self):
        md = (ROOT / "docs/benchmarks/2026-09-30-skill-author/claude/s2.md").read_text(
            encoding="utf-8"
        )
        text = share.encode(md)
        self.assertTrue(text.startswith(share.PREFIX))
        self.assertLess(len(text), len(md.encode("utf-8")), "บีบแล้วต้องเล็กกว่าไฟล์เดิม")
        self.assertEqual(share.decode(text), md)

    def test_too_big_for_one_qr(self):
        import os

        noise = os.urandom(4000).hex()  # บีบไม่ลง
        with self.assertRaises(share.ShareError) as ctx:
            share.encode("---\nid: x\n---\n" + noise)
        self.assertIn("ส่งออกเป็นไฟล์", str(ctx.exception))

    def test_bad_payloads_are_refused_with_reasons(self):
        for text, word in (("https://example.com", "ไม่ใช่สกิล"), (share.PREFIX + "!!!", "ข้อมูลเสีย"),
                           (share.PREFIX + "aGVsbG8=", "ข้อมูลเสีย")):  # fmt: skip
            with self.assertRaises(share.ShareError) as ctx:
                share.decode(text)
            self.assertIn(word, str(ctx.exception))
        import base64

        bomb = share.PREFIX + base64.urlsafe_b64encode(zlib.compress(b"a" * 10_000_000)).decode()
        with self.assertRaises(share.ShareError) as ctx:
            share.decode(bomb)
        self.assertIn("ใหญ่ผิดปกติ", str(ctx.exception))


class ImageTest(unittest.TestCase):
    def test_h2_digital_every_good_skill_reads_back_byte_exact(self):
        """สกิลดีทุกตัวจากชุดวัด 0074 (คนอื่นเขียน) → PNG → อ่านกลับ = ตรงทุกไบต์ · ใหญ่เกิน 1 QR นับแยก."""
        exact, too_big = 0, 0
        with tempfile.TemporaryDirectory() as d:
            for i, it in enumerate(GOOD):
                path = Path(d) / f"ภาพ-{i}.png"  # ชื่อไทย: วินโดวส์ต้องเขียน/อ่านได้
                try:
                    share.write_png(it["md"], path)
                except share.ShareError:
                    too_big += 1
                    continue
                exact += share.read_image(path) == it["md"]
        self.assertGreaterEqual(len(GOOD), 20)
        self.assertEqual(exact + too_big, len(GOOD), "ที่สร้าง QR ได้ต้องอ่านกลับตรงทุกตัว")
        self.assertEqual(too_big, 0, f"สกิลดีที่ใหญ่เกิน 1 QR: {too_big}")

    def test_image_without_qr(self):
        import cv2
        import numpy as np

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "blank.png"
            p.write_bytes(cv2.imencode(".png", np.full((200, 200), 255, np.uint8))[1].tobytes())
            with self.assertRaises(share.ShareError) as ctx:
                share.read_image(p)
            self.assertIn("ไม่พบ QR", str(ctx.exception))
            (Path(d) / "x.png").write_bytes(b"not an image")
            with self.assertRaises(share.ShareError):
                share.read_image(Path(d) / "x.png")


try:
    from PySide6.QtCore import QCoreApplication

    from aipc.skills import manifest, userskills
    from aipc.ui.backend import SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class ControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root = Path(d.name)
        self.store = userskills.UserSkills(self.root / "skills")
        self.s = SkillsController(reminders_path=self.root / "r.json", run_timer=False,
                                  llm_ready=lambda: True, user_skills=self.store)  # fmt: skip

    def test_h1_every_bad_skill_via_qr_still_meets_the_gate(self):
        """สกิลเสียทุกตัวของชุดวัด 0074 ส่งผ่าน QR → ทาง QR ต้องไม่รับตัวที่ด่านไม่รับ (ทางเดียวกับไฟล์ .md).

        อ่าน QR ไม่ได้ = ไม่ติดตั้ง (ปลอดภัย) · นับแยกไว้ (วัด 2026-11-07: 1 จาก 211 รูปของทุกชุด)
        """
        builtin = manifest.load_builtin()
        leaked, unreadable = [], []
        for i, it in enumerate(BAD):
            try:
                path = self.root / f"bad-{i}.png"
                share.write_png(it["md"], path)
            except share.ShareError:
                continue  # ใหญ่เกิน QR = แชร์ทางนี้ไม่ได้เลย
            msg = self.s.importSkill(str(path), False)
            if msg.startswith("ไม่พบ QR"):
                unreadable.append(it["id"])
            elif "กดอีกครั้ง" in msg and userskills.gate(it["md"], builtin)[0] is None:
                leaked.append(it["id"])
        self.assertEqual(leaked, [])
        self.assertLessEqual(len(unreadable), 2, unreadable)
        self.assertEqual(self.store.load_all(), [], "ดูก่อน (install=False) ต้องไม่ติดตั้งอะไร")

    def test_share_then_import_on_another_account(self):
        md = (ROOT / "docs/benchmarks/2026-09-30-skill-author/claude/l3.md").read_text(
            encoding="utf-8"
        )
        self.store.install(md, manifest.load_builtin(), request="คิดเมนู")
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"HOME": str(self.root), "USERPROFILE": str(self.root)}):
            r = self.s.shareSkillQr("fridge-menu")
        self.assertTrue(r["path"], r["message"])
        self.assertIn("ติดตั้งสกิลจาก QR", r["message"])
        friend = userskills.UserSkills(self.root / "friend")
        f = SkillsController(reminders_path=self.root / "r2.json", run_timer=False,
                             llm_ready=lambda: True, user_skills=friend)  # fmt: skip
        self.assertIn("กดอีกครั้ง", f.importSkill(r["path"], False))
        self.assertEqual(friend.load_all(), [])
        self.assertIn("ติดตั้งสกิล", f.importSkill(r["path"], True))
        self.assertEqual(friend.current_md("fridge-menu"), md)
        self.assertIn("แชร์ได้เฉพาะ", self.s.shareSkillQr("translate")["message"])


if __name__ == "__main__":
    unittest.main()


class FakeServer:
    """แทน urlopen · พฤติกรรมเดียวกับ server/share-worker · ไม่ออกเน็ต."""

    def __init__(self):
        self.files, self.requests = {}, []
        self.fail = None  # ตั้งเป็น HTTPError หรือ OSError = ล้มทุกคำขอ

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        if self.fail is not None:
            raise self.fail
        if request.get_method() == "POST":
            code = f"{len(self.files) + 10000000:08d}"
            self.files[code] = request.data
            return io.BytesIO(json.dumps({"code": code}).encode())
        code = request.full_url.rsplit("/", 1)[1]
        if code not in self.files:
            raise urllib.error.HTTPError(request.full_url, 404, "not found", None, None)
        return io.BytesIO(self.files[code])


URL = "https://share.test"


class NumberTest(unittest.TestCase):
    def test_r1_good_skills_round_trip_byte_exact(self):
        server = FakeServer()
        exact, refused = 0, []
        for it in GOOD:
            try:
                code = share.upload(it["md"], URL, server)
            except share.NotSent:
                refused.append(it["id"])
                continue
            exact += share.download(code, URL, server) == it["md"]
        self.assertGreaterEqual(exact, 20, f"ไม่ถูกส่ง {refused}")
        self.assertEqual(exact, len(GOOD) - len(refused))

    def test_requests_do_not_use_the_default_python_identity(self):
        # Cloudflare ตอบ 403 (error 1010) ถ้าไม่บอกชื่อ เพราะ urllib ใส่ "Python-urllib" ให้เอง
        server = FakeServer()
        code = share.upload("---\nid: x\n---\n", URL, server)
        share.download(code, URL, server)
        self.assertEqual(len(server.requests), 2)
        for request in server.requests:
            agent = request.get_header("User-agent") or "python-urllib (default)"
            self.assertNotIn("python", agent.lower())

    def test_r4_skill_with_a_secret_is_never_sent(self):
        server = FakeServer()
        for word in ("รหัสผ่านคือ abc", "OTP 123456", "เลขบัตร 1234567890123"):
            with self.subTest(word=word), self.assertRaises(share.NotSent):
                share.upload(f"---\nid: x\n---\n{word}", URL, server)
        self.assertEqual(server.requests, [])

    def test_too_big_or_no_server_sends_nothing(self):
        server = FakeServer()
        with self.assertRaises(share.NotSent):
            share.upload("---\n" + "ก" * 6000, URL, server)
        with self.assertRaises(share.NotSent):
            share.upload("---\nid: x\n---\n", "", server)
        self.assertEqual(server.requests, [])

    def test_cloud_off_means_no_server_even_when_configured(self):
        with mock.patch.dict(os.environ, {"AIPC_CLOUD": "0", "AIPC_SHARE_URL": URL}):
            self.assertEqual(share.server_url(), "")
        with mock.patch.dict(os.environ, {"AIPC_CLOUD": "1", "AIPC_SHARE_URL": URL + "/"}):
            self.assertEqual(share.server_url(), URL)

    def test_code_is_cleaned_or_refused(self):
        for text in ("1234 5678", "1234-5678", " 12345678 ", "๑๒๓๔๕๖๗๘"):
            self.assertEqual(share.clean_code(text), "12345678")
        for text in ("1234567", "123456789", "abcd5678", ""):
            with self.subTest(text=text), self.assertRaises(share.ShareError):
                share.clean_code(text)
        self.assertEqual(share.pretty_code("12345678"), "1234 5678")

    def test_server_errors_become_plain_reasons(self):
        server = FakeServer()
        for status, word in ((404, "หมดอายุ"), (429, "รอสักชั่วโมง"), (500, "500")):
            server.fail = urllib.error.HTTPError(URL, status, "x", None, None)
            with self.subTest(status=status), self.assertRaises(share.ShareError) as ctx:
                share.download("12345678", URL, server)
            self.assertIn(word, str(ctx.exception))
        server.fail = OSError("no network")
        with self.assertRaises(share.ShareError):
            share.download("12345678", URL, server)
        with self.assertRaises(share.ShareError) as ctx:
            share.upload("---\nid: x\n---\n", URL, server)
        self.assertNotIsInstance(ctx.exception, share.NotSent, "อาจส่งออกไปแล้ว ต้องลงสมุด")

    def test_oversized_download_is_refused(self):
        server = FakeServer()
        server.files["12345678"] = b"x" * (share.MAX_UPLOAD + 1)
        with self.assertRaises(share.ShareError):
            share.download("12345678", URL, server)

    def test_qr_of_number_reads_back_and_downloads(self):
        server = FakeServer()
        code = share.upload("---\nid: x\n---\nเนื้อหา", URL, server)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "เลข.png"
            share.write_code_png(code, path)
            self.assertEqual(share.read_image_text(path), share.CODE_PREFIX + code)
            self.assertEqual(share.read_image(path, URL, server), "---\nid: x\n---\nเนื้อหา")


class NumberControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root = Path(d.name)
        self.store = userskills.UserSkills(self.root / "skills")
        self.ledger = Ledger(self.root / "outbound.json")
        self.s = SkillsController(reminders_path=self.root / "r.json", run_timer=False,
                                  llm_ready=lambda: True, user_skills=self.store,
                                  ledger=self.ledger)  # fmt: skip
        self.results = []
        self.s.shareCodeDone.connect(self.results.append)
        self.s.skillReceived.connect(self.results.append)
        self.enterContext(mock.patch.dict(os.environ, {"HOME": str(self.root),
                                                       "USERPROFILE": str(self.root)}))  # fmt: skip

    def wait(self, count=1):
        end = time.monotonic() + 5
        while len(self.results) < count and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertEqual(len(self.results), count)
        return self.results[-1]

    def good_skill(self):
        md = (ROOT / "docs/benchmarks/2026-09-30-skill-author/claude/l3.md").read_text(
            encoding="utf-8"
        )
        self.store.install(md, manifest.load_builtin(), request="คิดเมนู")
        self.s._reload()
        return md

    def test_r3_every_send_is_written_to_the_ledger_exactly(self):
        md = self.good_skill()
        with mock.patch.object(share, "upload", return_value="12345678"):
            self.s.shareSkillCode("fridge-menu")
            r = self.wait()
        self.assertEqual(r["code"], "1234 5678")
        self.assertTrue(Path(r["path"]).exists())
        entry = self.ledger.entries()[0]
        self.assertEqual((entry["kind"], entry["sent"], entry["ok"]), ("share", md, True))

    def test_r3_failed_send_is_recorded_but_refused_send_is_not(self):
        md = self.good_skill()
        with mock.patch.object(share, "upload", side_effect=share.ShareError("เน็ตหลุด")):
            self.s.shareSkillCode("fridge-menu")
            self.assertEqual(self.wait()["code"], "")
        self.assertEqual(
            (self.ledger.entries()[0]["sent"], self.ledger.entries()[0]["ok"]), (md, False)
        )
        with mock.patch.object(share, "upload", side_effect=share.NotSent("มีรหัสผ่าน")):
            self.s.shareSkillCode("fridge-menu")
            self.assertIn("รหัสผ่าน", self.wait(2)["message"])
        self.assertEqual(len(self.ledger.entries()), 1, "ไม่ได้ส่ง = ไม่ลงสมุด")

    def test_only_user_skills_can_be_shared(self):
        with mock.patch.object(share, "upload") as upload:
            self.s.shareSkillCode("translate")
            self.assertEqual(self.wait()["code"], "")
        upload.assert_not_called()

    def test_r2_every_bad_skill_received_by_number_stops_at_the_gate(self):
        builtin = manifest.load_builtin()
        leaked = []
        with mock.patch.object(share, "download") as download:
            for n, it in enumerate(BAD, start=1):
                download.return_value = it["md"]
                self.s.receiveSkillCode("12345678")
                r = self.wait(n)
                allowed = userskills.gate(it["md"], builtin)[0] is not None
                if r["ready"] and not allowed:
                    leaked.append(it["id"])
                self.assertEqual(r["ready"], allowed, it["id"])
        self.assertEqual(leaked, [])

    def test_receive_previews_first_then_installs_once(self):
        md = (ROOT / "docs/benchmarks/2026-09-30-skill-author/claude/l3.md").read_text(
            encoding="utf-8"
        )
        with mock.patch.object(share, "download", return_value=md) as download:
            self.s.receiveSkillCode("1234 5678")
            r = self.wait()
            self.assertTrue(r["ready"])
            self.assertEqual(self.store.load_all(), [], "ตรวจก่อน ยังไม่ติดตั้ง")
            self.assertIn("ติดตั้งสกิล", self.s.installReceivedSkill())
            download.assert_called_once_with("12345678")
        self.assertEqual(len(self.store.load_all()), 1)
        self.assertIn("ยังไม่มี", self.s.installReceivedSkill(), "กดซ้ำต้องไม่ติดตั้งซ้ำ")

    def test_wrong_number_never_touches_the_network(self):
        with mock.patch.object(share, "download") as download:
            self.s.receiveSkillCode("123")
            r = self.wait()
        self.assertFalse(r["ready"])
        self.assertIn("8 หลัก", r["message"])
        download.assert_not_called()

    def test_camera_results_become_reasons_or_a_preview(self):
        from aipc.vision import client as vision_client

        md = (ROOT / "docs/benchmarks/2026-09-30-skill-author/claude/l3.md").read_text(
            encoding="utf-8"
        )
        cases = (
            ({"ok": False, "state": "busy"}, False, "ใช้งานอยู่"),
            ({"ok": False, "state": "unavailable"}, False, "ใช้กล้องไม่ได้"),
            ({"ok": True, "text": ""}, False, "ไม่พบ QR"),
            ({"ok": True, "text": share.encode(md)}, True, "ตรวจแล้วผ่าน"),
        )
        for n, (reply, ready, word) in enumerate(cases, start=1):
            with (
                self.subTest(reply=reply),
                mock.patch.object(vision_client, "scan_qr", return_value=reply),
            ):
                self.s.scanSkillQr()
                r = self.wait(n)
                self.assertEqual(r["ready"], ready)
                self.assertIn(word, r["message"])
