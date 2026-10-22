"""ตัวติดตั้งแอป (การ์ด 0054 · เกณฑ์ A3 A4 ส่วนเทสต์) · ระบบปลอม ไม่มี root หรือ apt จริง."""

import json
import tempfile
import unittest
from pathlib import Path

from aipc.accounts import apphelper
from aipc.skills import app_catalog


class FakeSystem(apphelper.System):
    def __init__(self, tmp: Path):
        self.state = tmp / "state"
        self.who = "nok"
        self.free = 10 * 1024**3
        self.apt_calls, self.logs = [], []
        self.apt_result = {"update": (0, ""), "install": (0, "")}

    def caller(self):
        return self.who

    def free_bytes(self):
        return self.free

    def apt(self, args):
        self.apt_calls.append(args)
        return self.apt_result[args[0]]

    def log(self, text):
        self.logs.append(text)

    def catalog(self):
        return app_catalog.load(admin=Path("/ไม่มีไฟล์นี้"))


def ask(system, **req):
    return apphelper.handle(json.dumps(req).encode(), system)


class InstallTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.sys = FakeSystem(Path(self._tmp.name))

    def test_any_user_installs_package_from_the_list_only(self):
        # Pakon 2026-10-23: ไม่ต้องใส่รหัส · ผู้ใช้ทั่วไป (nok) ติดตั้งแอปในรายการได้
        r = ask(self.sys, app="vlc")
        self.assertTrue(r["ok"], r)
        install = ["install", "-y", "--no-install-recommends", "vlc"]
        self.assertEqual(self.sys.apt_calls, [["update"], install])
        self.assertIn("ผู้ขอ nok", " ".join(self.sys.logs))  # บันทึกว่าใครขอ

    def test_a3_refusals_never_reach_apt(self):
        bad = [
            {"app": "vlc; rm -rf /"},  # นอกรายการ
            {"app": "-o APT::x=y"},
            {"app": "zoom"},  # มีแต่เว็บ ไม่มีแพ็กเกจ
            {"app": 7},
            {},  # ไม่ครบ
        ]
        for req in bad:
            self.assertFalse(ask(self.sys, **req)["ok"], req)
        self.assertEqual(self.sys.apt_calls, [])

    def test_only_from_a_user_session(self):
        for who in ("", "root", "_greetd"):
            self.sys.who = who
            self.assertFalse(ask(self.sys, app="vlc")["ok"], who)
        self.assertEqual(self.sys.apt_calls, [])

    def test_a4_real_reasons(self):
        self.sys.free = 1024**3
        self.assertIn("2 GB", ask(self.sys, app="vlc")["message"])
        self.sys.free = 10 * 1024**3
        self.sys.apt_result["update"] = (100, "Temporary failure resolving 'deb.debian.org'")
        self.assertIn("อินเทอร์เน็ต", ask(self.sys, app="vlc")["message"])
        self.sys.apt_result["update"] = (0, "")
        self.sys.apt_result["install"] = (100, "E: Could not get lock /var/lib/dpkg/lock-frontend")
        self.assertIn("ค้างอยู่", ask(self.sys, app="vlc")["message"])


class CatalogTest(unittest.TestCase):
    def test_builtin_entries_are_all_valid(self):
        raw = json.loads(app_catalog.BUILTIN.read_text(encoding="utf-8"))["apps"]
        loaded = app_catalog.load(admin=Path("/ไม่มีไฟล์นี้"))
        self.assertEqual(set(loaded), set(raw))  # ไม่มีรายการไหนถูกข้ามเพราะรูปผิด
        self.assertTrue(all(e.apt or e.web for e in loaded.values()))

    def test_admin_file_replaces_and_bad_rows_are_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "apps.json"
            f.write_text(json.dumps({"apps": {
                "ok": {"name": "OK", "aliases": ["ok"], "apt": "okpkg"},
                "evil": {"aliases": ["evil"], "apt": "pkg; rm -rf /"},
                "dash": {"aliases": ["dash"], "apt": "-oAPT"},
                "http": {"aliases": ["http"], "web": "http://insecure.example"},
            }}), encoding="utf-8")  # fmt: skip
            self.assertEqual(list(app_catalog.load(admin=f)), ["ok"])
            f.write_text("เสีย", encoding="utf-8")
            self.assertIn("vlc", app_catalog.load(admin=f))  # ไฟล์ผู้ดูแลเสีย = ใช้ของแอป

    def test_exact_alias_only(self):
        apps = app_catalog.load(admin=Path("/ไม่มีไฟล์นี้"))
        self.assertEqual(app_catalog.find("ซูม", apps).key, "zoom")
        self.assertIsNone(app_catalog.find("ซูมภาพ", apps))


if __name__ == "__main__":
    unittest.main()
