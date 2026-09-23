import os
import unittest

from aipc.doctor import image_audit as audit
from aipc.doctor.hardware import FAIL, PASS, UNKNOWN, WARN
from tests.test_doctor_hardware import FakeMachine

PASSWD = (
    "root:x:0:0:root:/root:/bin/bash\n"
    "pi:x:1000:1000::/home/pi:/bin/bash\n"
    "usera:x:1010:1010::/home/usera:/bin/bash\n"
    "nobody:x:65534:65534::/nonexistent:/usr/sbin/nologin\n"
)


class SudoTest(unittest.TestCase):
    def test_finds_nopasswd_and_ignores_comments(self):
        text = "# pi ALL=(ALL) NOPASSWD: ALL\npi ALL=(ALL) NOPASSWD: ALL\n%sudo ALL=(ALL:ALL) ALL\n"
        hits = audit.parse_sudoers_nopasswd(text, "/etc/sudoers.d/010_pi-nopasswd")
        self.assertEqual(len(hits), 1)
        self.assertIn(":2 ", hits[0])

    def test_raspberry_pi_os_default_fails(self):
        m = FakeMachine()
        m.write("/etc/sudoers", "%sudo ALL=(ALL:ALL) ALL\n")
        m.write("/etc/sudoers.d/010_pi-nopasswd", "pi ALL=(ALL) NOPASSWD: ALL\n")
        self.assertEqual(audit.check_sudo_nopasswd(m.root).status, FAIL)
        m.close()

    def test_unreadable_sudoers_is_unknown(self):
        m = FakeMachine()
        self.assertEqual(audit.check_sudo_nopasswd(m.root).status, UNKNOWN)
        m.close()


class GroupsTest(unittest.TestCase):
    def test_only_human_users_count(self):
        m = FakeMachine()
        m.write("/etc/passwd", PASSWD)
        m.write("/etc/group", "sudo:x:27:pi\nadm:x:4:syslog,pi\nvideo:x:44:\n")
        c = audit.check_privileged_groups(m.root)
        self.assertEqual(c.status, WARN)
        self.assertIn("sudo: pi", c.detail)
        self.assertNotIn("syslog", c.detail)  # syslog ไม่ใช่บัญชีคน
        m.write("/etc/group", "sudo:x:27:\nadm:x:4:syslog\n")
        self.assertEqual(audit.check_privileged_groups(m.root).status, PASS)
        m.close()


class RemoteServicesTest(unittest.TestCase):
    def test_enabled_ssh_warns(self):
        def run(args):
            if args == ["systemctl", "--version"]:
                return "systemd 257"
            return "enabled" if args[-1] == "ssh.service" else None

        c = audit.check_remote_services(run)
        self.assertEqual(c.status, WARN)
        self.assertIn("ssh.service", c.detail)

    def test_no_systemctl_is_unknown(self):
        self.assertEqual(audit.check_remote_services(lambda a: None).status, UNKNOWN)


class PortsTest(unittest.TestCase):
    HEADER = "  sl  local_address rem_address   st tx_queue rx_queue\n"

    def test_loopback_listeners_are_ignored(self):
        m = FakeMachine()
        m.write(
            "/proc/net/tcp",
            self.HEADER
            + "   0: 0100007F:1F90 00000000:0000 0A 0\n"  # 127.0.0.1:8080 → ไม่นับ
            + "   1: 00000000:0016 00000000:0000 0A 0\n"  # 0.0.0.0:22 → นับ
            + "   2: 0100007F:0035 0100007F:D431 01 0\n",  # ESTABLISHED → ไม่นับ
        )
        m.write(
            "/proc/net/tcp6",
            self.HEADER
            + f"   0: {audit.LOOPBACK6}:0277 {'0' * 32}:0000 0A 0\n"  # ::1:631 → ไม่นับ
            + f"   1: {'0' * 32}:1770 {'0' * 32}:0000 0A 0\n",  # [::]:6000 → นับ
        )
        self.assertEqual(audit.listening_ports(m.root), ["22/tcp", "6000/tcp6"])
        self.assertEqual(audit.check_listening(m.root).status, WARN)
        m.close()


class LogindTest(unittest.TestCase):
    def test_default_is_not_enough(self):
        m = FakeMachine()
        m.write("/etc/systemd/logind.conf", "[Login]\n#KillUserProcesses=no\n")
        self.assertEqual(audit.check_logout_cleanup(m.root).status, WARN)
        m.close()

    def test_dropin_overrides_main_file(self):
        m = FakeMachine()
        m.write("/etc/systemd/logind.conf", "[Login]\nKillUserProcesses=no\n")
        m.write("/etc/systemd/logind.conf.d/50-aipc.conf", "[Login]\nKillUserProcesses=yes\n")
        self.assertEqual(audit.check_logout_cleanup(m.root).status, PASS)
        m.write("/var/lib/systemd/linger/usera", "")
        self.assertEqual(audit.check_logout_cleanup(m.root).status, WARN)
        m.close()


class SwapTest(unittest.TestCase):
    def test_zram_only_passes_disk_swap_warns(self):
        m = FakeMachine()
        head = "Filename Type Size Used Priority\n"
        m.write("/proc/swaps", head + "/dev/zram0 partition 2097148 0 100\n")
        self.assertEqual(audit.check_swap(m.root).status, PASS)
        m.write("/proc/swaps", head + "/var/swap file 524284 0 -2\n")
        self.assertEqual(audit.check_swap(m.root).status, WARN)
        m.close()


@unittest.skipUnless(os.name == "posix", "สิทธิ์ไฟล์แบบ Linux ทดสอบบนวินโดวส์ไม่ได้")
class PermissionTest(unittest.TestCase):
    def test_home_755_fails_700_passes(self):
        m = FakeMachine()
        (m.root / "home" / "a").mkdir(parents=True)
        os.chmod(m.root / "home" / "a", 0o755)
        self.assertEqual(audit.check_home_permissions(m.root).status, FAIL)
        os.chmod(m.root / "home" / "a", 0o700)
        self.assertEqual(audit.check_home_permissions(m.root).status, PASS)
        m.close()

    def test_world_readable_camera_fails(self):
        m = FakeMachine()
        m.write("/dev/video0", "")
        os.chmod(m.root / "dev" / "video0", 0o666)
        self.assertEqual(audit.check_camera_nodes(m.root).status, FAIL)
        m.close()


if __name__ == "__main__":
    unittest.main()
