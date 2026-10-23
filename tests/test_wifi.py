"""เลือก Wi-Fi (การ์ด 0063) · nmcli จำลอง ไม่แตะเครือข่ายจริง · เกณฑ์ W3: รหัสไม่อยู่ใน argv."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from aipc.ui import wifi

PW = "correct-horse-42"


class FakeNmcli:
    """จำลอง nmcli: โปรไฟล์ที่จำไว้ · ผลค้นหา · รหัสที่ถูก · จดทุกคำสั่งและเนื้อไฟล์รหัสตอนที่ถูกอ่าน."""

    def __init__(self, profiles=None, listing="", good=PW):
        self.profiles = dict(profiles or {})  # ชื่อโปรไฟล์ → SSID
        self.listing, self.good = listing, good
        self.calls, self.files = [], []

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        a = argv[1:]
        ok = lambda out="": subprocess.CompletedProcess(argv, 0, out, "")  # noqa: E731
        bad = lambda err: subprocess.CompletedProcess(argv, 4, "", err)  # noqa: E731
        if a[:4] == ["-t", "-f", "NAME,TYPE", "connection"]:
            rows = "".join(f"{n}:802-11-wireless\n" for n in self.profiles)
            return ok(rows + "Wired connection 1:802-3-ethernet\n")
        if a[:2] == ["-g", "802-11-wireless.ssid"]:
            return ok(self.profiles.get(a[-1], "") + "\n")
        if "wifi" in a and "list" in a:
            return ok(self.listing)
        if a[:2] == ["connection", "add"]:
            self.profiles[a[a.index("con-name") + 1]] = a[a.index("ssid") + 1]
            return ok()
        if a[:2] == ["connection", "delete"]:
            self.profiles.pop(a[-1], None)
            return ok()
        if "up" in a:
            if "passwd-file" in a:
                path = Path(a[a.index("passwd-file") + 1])
                self.files.append((path, path.read_text(encoding="utf-8")))
                pw = self.files[-1][1].split(":", 1)[1].strip()
                if pw != self.good:
                    return bad(
                        "Error: Connection activation failed: "
                        "Secrets were required, but not provided."
                    )
            return ok()
        return bad("unknown")


LISTING = (
    "*:Home\\:5G:80:WPA2\n"  # ':' ในชื่อ → nmcli เขียน '\:'
    " :Cafe:40:WPA2\n"
    " :Cafe:65:WPA2\n"  # ชื่อซ้ำ → เก็บอันแรงกว่า
    " ::90:WPA2\n"  # ไม่มีชื่อ (ซ่อน) → ข้าม
    " :Free:30:--\n"
)


class WifiTest(unittest.TestCase):
    def test_scan_parses_sorts_and_marks(self):
        nm = FakeNmcli(profiles={"preconfigured": "Home:5G"}, listing=LISTING)
        nets, err = wifi.scan(run=nm)
        self.assertEqual(err, "")
        self.assertEqual([n["ssid"] for n in nets], ["Home:5G", "Cafe", "Free"])
        home, cafe, free = nets
        # โปรไฟล์ชื่อไม่ตรง SSID ก็รู้ว่าเคยต่อ
        self.assertTrue(home["active"] and home["known"] and home["secure"])
        self.assertEqual(cafe["signal"], 65)
        self.assertFalse(free["secure"])

    def test_password_never_in_argv_and_file_removed(self):  # W3
        nm = FakeNmcli()
        with tempfile.TemporaryDirectory() as d:
            ok, msg = wifi.connect("Cafe", PW, run=nm, tmpdir=d)
            self.assertTrue(ok, msg)
            self.assertEqual(os.listdir(d), [], "ไฟล์รหัสต้องถูกลบทันที")
        self.assertTrue(all(PW not in arg for argv in nm.calls for arg in argv))
        self.assertEqual(nm.files[0][1], f"802-11-wireless-security.psk:{PW}\n")
        self.assertEqual(nm.profiles, {"Cafe": "Cafe"})

    def test_wrong_password_says_so_and_forgets_profile(self):  # W2
        nm = FakeNmcli()
        with tempfile.TemporaryDirectory() as d:
            ok, msg = wifi.connect("Cafe", "wrong-pass-99", run=nm, tmpdir=d)
            self.assertEqual(os.listdir(d), [])
        self.assertFalse(ok)
        self.assertEqual(msg, "รหัสไม่ถูก")
        self.assertEqual(nm.profiles, {}, "ไม่จำรหัสผิดไว้")

    def test_known_network_connects_without_password(self):
        nm = FakeNmcli(profiles={"preconfigured": "Home"})
        ok, _ = wifi.connect("Home", "", run=nm)
        self.assertTrue(ok)
        up = ["nmcli", "--wait", "30", "connection", "up", "id", "preconfigured"]
        self.assertIn(up, nm.calls)
        self.assertFalse(any("add" in c for c in nm.calls))

    def test_short_password_refused_before_nmcli(self):
        nm = FakeNmcli()
        ok, msg = wifi.connect("Cafe", "1234", run=nm)
        self.assertFalse(ok)
        self.assertIn("8–63", msg)
        self.assertEqual(nm.calls, [])

    def test_forget_deletes_profile(self):
        nm = FakeNmcli(profiles={"preconfigured": "Home"})
        self.assertTrue(wifi.forget("Home", run=nm)[0])
        self.assertEqual(nm.profiles, {})
        self.assertFalse(wifi.forget("Home", run=nm)[0])

    def test_no_nmcli_is_reported(self):
        def missing(argv, **kw):
            raise FileNotFoundError

        nets, err = wifi.scan(run=missing)
        self.assertEqual(nets, [])
        self.assertIn("nmcli", err)


if __name__ == "__main__":
    unittest.main()
