"""scripts/pi/install-browser.sh (Pakon เลือกทาง ข 2026-10-06): Chromium ไม่ใช้ keyring · ดูก่อนเป็นค่าเริ่มต้น."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pi" / "install-browser.sh"
BASH = shutil.which("bash")


@unittest.skipIf(BASH is None or os.name == "nt", "ต้องใช้ bash บน Linux")
class InstallBrowserTest(unittest.TestCase):
    def run_script(self, d, *args):
        env = dict(os.environ, AIPC_CHROMIUM_D=str(d))
        return subprocess.run([BASH, str(SCRIPT), *args], env=env, capture_output=True, text=True, check=False)

    def test_dry_run_then_apply_then_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "aipc-password-store"
            r = self.run_script(d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("โหมดดูก่อน", r.stdout)
            self.assertFalse(f.exists())
            self.assertEqual(self.run_script(d, "--apply").returncode, 0)
            self.assertIn("--password-store=basic", f.read_text(encoding="utf-8"))
            # ตัวเปิด chromium source ไฟล์นี้ใน sh → ต้องต่อท้ายค่าเดิม ไม่ทับแฟล็กอื่น
            out = subprocess.run(["sh", "-c", f'CHROMIUM_FLAGS="--a"; . "{f}"; echo "$CHROMIUM_FLAGS"'],
                                 capture_output=True, text=True, check=True).stdout.strip()  # fmt: skip
            self.assertEqual(out, "--a --password-store=basic")
            self.assertEqual(self.run_script(d, "--rollback").returncode, 0)
            self.assertFalse(f.exists())

    def test_missing_dir_stops(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_script(Path(d) / "nope", "--apply")
            self.assertNotEqual(r.returncode, 0)
