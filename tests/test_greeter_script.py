"""ตัวเปิดหน้า Login (scripts/pi/session/aipc-greeter) · พบ 2026-09-29: หน้า Login ไม่มีผังแป้นไทย.

greetd เรียก aipc-greeter → cage + หน้าจอ V2 แบบ greeter
ผังแป้นต้องเป็นชุดเดียวกับเซสชัน (labwc/environment)
เทสต์นี้กันไม่ให้ค่าสองที่เพี้ยนกัน และกันไม่ให้สคริปต์ติดตั้ง/อัปเดตกลับไปเรียก cage ตรง ๆ
"""

import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SESSION = ROOT / "scripts" / "pi" / "session"
GREETER = SESSION / "aipc-greeter"
XKB_VARS = ("XKB_DEFAULT_MODEL", "XKB_DEFAULT_LAYOUT", "XKB_DEFAULT_OPTIONS")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class GreeterScriptTest(unittest.TestCase):
    def test_session_layout_has_thai_and_our_toggle(self):
        env = read(SESSION / "labwc" / "environment")
        self.assertIn("XKB_DEFAULT_LAYOUT=us,th", env)
        self.assertIn("aipc:grave_toggle", env)
        self.assertTrue((SESSION / "xkb" / "rules" / "evdev").is_file())
        self.assertTrue((SESSION / "xkb" / "symbols" / "aipc").is_file())

    def test_greeter_reads_the_same_layout_as_the_session(self):
        text = read(GREETER)
        self.assertIn("labwc/environment", text, "ต้องอ่านค่าจากไฟล์เดียวกับเซสชัน ไม่เขียนซ้ำ")
        for var in XKB_VARS:
            self.assertIn(var, text)
        self.assertIn('XKB_CONFIG_EXTRA_PATH="$HERE/xkb"', text)
        self.assertIn('--greeter "$1"', text)
        self.assertTrue(text.startswith("#!/bin/sh\n"))

    def test_install_and_update_use_the_greeter(self):
        install = read(ROOT / "scripts" / "pi" / "install-greeter.sh")
        self.assertIn("CMD=\"$GREETER '$SESSION'\"", install)
        self.assertNotIn('CMD="cage', install, "ห้ามกลับไปเรียก cage ตรง ๆ (ไม่มีผังแป้นไทย)")
        self.assertIn("--config-only", install)
        update = read(ROOT / "scripts" / "pi" / "update-app.sh")
        self.assertIn('sh -n "$G/aipc-greeter"', update, "ต้องตรวจตัวเปิดหน้า Login ก่อนสลับรุ่น")

    @unittest.skipUnless(shutil.which("git"), "ไม่มี git")
    def test_greeter_is_executable_in_git(self):
        out = subprocess.run(["git", "ls-files", "-s", str(GREETER.relative_to(ROOT))], cwd=ROOT,
                             capture_output=True, text=True, check=False).stdout  # fmt: skip
        if not out:
            self.skipTest("ไฟล์ยังไม่อยู่ใน git index")
        self.assertTrue(out.startswith("100755"), out)

    @unittest.skipUnless(shutil.which("sh") and os.name == "posix", "ต้องมี sh (Linux)")
    def test_greeter_exports_the_session_layout(self):
        subprocess.run(["sh", "-n", str(GREETER)], check=True)
        # รันส่วนที่อ่านผังแป้นจริง (ตัดบรรทัด exec cage ออก) แล้วดูค่าที่ export
        body = read(GREETER).replace("exec cage", "env | grep ^XKB_ #")
        cmd = ["sh", "-c", body, str(GREETER)]
        # AIPC_JOURNALED=1: ข้ามขั้นส่งข้อความไป journal · ขั้นนั้นรันไฟล์จริงซ้ำ = เปิด cage จริง
        # (เทสต์ค้างบน Pi 2026-10-24)
        run_env = {**os.environ, "AIPC_JOURNALED": "1"}
        out = subprocess.run(cmd, capture_output=True, text=True, check=True, env=run_env,
                             timeout=30).stdout  # fmt: skip
        env = dict(line.split("=", 1) for line in out.splitlines())
        for line in read(SESSION / "labwc" / "environment").splitlines():
            key = line.split("=", 1)[0]
            if key in XKB_VARS:
                self.assertEqual(f"{key}={env[key]}", line)
        self.assertEqual(Path(env["XKB_CONFIG_EXTRA_PATH"]), SESSION / "xkb")


if __name__ == "__main__":
    unittest.main()
