"""คู่มือเชื่อมต่อ Claude ในแอป (การ์ด 0021 · เกณฑ์ข้อ 1–2)."""

import unittest
from types import SimpleNamespace

from aipc.cloud import setup_guide


def run(out, rc=0):
    return lambda *a, **k: SimpleNamespace(stdout=out, returncode=rc)


class AddressesTest(unittest.TestCase):
    def test_ipv4_without_loopback(self):
        out = "172.20.10.3 127.0.1.1 fe80::1 192.168.1.35 \n"
        self.assertEqual(setup_guide.addresses(run(out)), ["172.20.10.3", "192.168.1.35"])

    def test_unreadable_is_empty(self):
        self.assertEqual(setup_guide.addresses(run("", 1)), [])

        def missing(*a, **k):
            raise OSError("no hostname")  # วินโดวส์

        self.assertEqual(setup_guide.addresses(missing), [])


class StepsTest(unittest.TestCase):
    def ssh_step(self, steps):
        return next(s for s in steps if "SSH" in s["title"] or "ssh" in s["command"])

    def test_ssh_command_has_account_and_every_address(self):
        steps = setup_guide.steps("pakon", ["172.20.10.3", "192.168.1.35"])
        ssh = self.ssh_step(steps)
        self.assertIn("ssh pakon@172.20.10.3", ssh["command"])
        self.assertIn("192.168.1.35", ssh["command"] + ssh["detail"])

    def test_no_address_says_connect_first_and_shows_no_broken_command(self):
        steps = setup_guide.steps("pakon", [])
        for s in steps:
            self.assertNotIn("@\n", s["command"] + "\n")
            self.assertFalse(s["command"].rstrip().endswith("@"))
        self.assertTrue(any("ต่อเน็ต" in s["detail"] for s in steps))

    def test_install_and_login_match_find_claude(self):
        commands = [s["command"] for s in setup_guide.steps("pakon", ["10.0.0.2"])]
        self.assertIn("curl -fsSL https://claude.ai/install.sh | bash", commands)
        self.assertIn("~/.local/bin/claude", commands)  # ที่ find_claude หาเมื่อ PATH ไม่มี

    def test_last_step_is_log_out_and_back_in(self):
        last = setup_guide.steps("pakon", ["10.0.0.2"])[-1]
        self.assertIn("ออกจากระบบ", last["title"] + last["detail"])
        self.assertEqual(last["command"], "")

    def test_every_step_has_text(self):
        for s in setup_guide.steps("pakon", ["10.0.0.2"]):
            self.assertTrue(s["title"] and s["detail"])
            self.assertEqual(set(s), {"title", "detail", "command"})


class ConnectTest(unittest.TestCase):
    """เกณฑ์ข้อ 8: python -m aipc.cloud.connect (คำสั่งปลอมทั้งหมด)."""

    def go(self, finds, install_rc=0):
        from aipc.cloud import connect

        finds, calls, lines = list(finds), [], []

        def run(cmd, **k):
            calls.append(cmd)
            return SimpleNamespace(returncode=install_rc if cmd[0] == "bash" else 0)

        rc = connect.main(find=lambda: finds.pop(0) if len(finds) > 1 else finds[0],
                          run=run, out=lines.append, ask=lambda p: "")  # fmt: skip
        return rc, calls, "\n".join(lines)

    def test_already_installed_skips_installer(self):
        rc, calls, text = self.go(["/home/p/.local/bin/claude"])
        self.assertEqual(rc, 0)
        self.assertEqual(calls, [["/home/p/.local/bin/claude"]])
        self.assertIn("ออกจากระบบแล้วเข้าใหม่", text)

    def test_installs_then_logs_in(self):
        rc, calls, _ = self.go([None, "/home/p/.local/bin/claude"])
        self.assertEqual(rc, 0)
        self.assertEqual(calls[0][:2], ["bash", "-c"])
        self.assertIn("pipefail", calls[0][2])
        self.assertIn(setup_guide.INSTALL, calls[0][2])
        self.assertEqual(calls[1], ["/home/p/.local/bin/claude"])

    def test_failed_install_never_runs_claude(self):
        rc, calls, text = self.go([None, None], install_rc=1)
        self.assertEqual(rc, 1)
        self.assertEqual(len(calls), 1)
        self.assertIn("ไม่สำเร็จ", text)
        rc, calls, _ = self.go([None, None], install_rc=0)  # รหัส 0 แต่ไม่มีไฟล์ = ไม่สำเร็จ
        self.assertEqual((rc, len(calls)), (1, 1))


if __name__ == "__main__":
    unittest.main()
