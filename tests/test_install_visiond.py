"""สคริปต์ติดตั้ง visiond (การ์ด 0015) · ตรวจเนื้อสคริปต์ ไม่ได้รันจริง."""

import shutil
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pi" / "install-visiond.sh"


class InstallVisiondTest(unittest.TestCase):
    def setUp(self):
        self.text = SCRIPT.read_text(encoding="utf-8")

    def test_only_greetd_pam_gets_the_face_line(self):
        self.assertIn("PAMGREETD=/etc/pam.d/greetd", self.text)
        for other in ("/etc/pam.d/sudo", "/etc/pam.d/sshd", "/etc/pam.d/login", "common-auth"):
            self.assertNotIn(other, self.text, f"ใบหน้าต้องไม่ไปอยู่ใน {other}")

    def test_face_line_falls_back_to_password(self):
        self.assertIn("[success=done default=ignore] pam_exec.so quiet", self.text)
        self.assertNotIn("sufficient", self.text)

    def test_sudoers_checked_and_single_command(self):
        self.assertIn("visudo -cf", self.text)
        self.assertIn('NOPASSWD: /usr/local/sbin/aipc-accounts \\"\\"', self.text)

    def test_dry_run_is_default_and_rollback_restores_backup(self):
        self.assertIn('MODE="dry-run"', self.text)
        self.assertIn('install -o root -g root -m 0644 "$BACKUP" "$PAMGREETD"', self.text)

    def test_bash_syntax(self):
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("ไม่มี bash")
        subprocess.run([bash, "-n", str(SCRIPT)], check=True)


if __name__ == "__main__":
    unittest.main()
