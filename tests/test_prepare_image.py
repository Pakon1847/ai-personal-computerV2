"""ล้างข้อมูลก่อนทำ image สำหรับแจก (การ์ด 0077 หัวข้อ 3 ข้อ 3 · เกณฑ์ I2) · รันสคริปต์จริงด้วย bash บนรากปลอม.

สคริปต์ทำงานกับโฟลเดอร์ราก (--root) · เทสต์สร้างรากปลอมที่มีข้อมูลผู้ใช้ทุกชนิด แล้วตรวจว่า
โหมดตรวจไม่ลบอะไรและบอกครบ · โหมด --apply ลบครบแล้วตรวจซ้ำได้ 0 · ของระบบที่ต้องอยู่ไม่ถูกแตะ
userdel / id เป็นของปลอมใน PATH · ของจริงต้องรันบนการ์ดที่จะทำ image เท่านั้น (ถาม Pakon ก่อน)
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "pi" / "prepare-image.sh"
BASH = shutil.which("bash")

PASSWD = """root:x:0:0:root:/root:/bin/bash
_greetd:x:109:109::/var/lib/greetd:/usr/sbin/nologin
aipc2030:x:1000:1000:,,,:/home/aipc2030:/bin/bash
pakon:x:1001:1001:Pakon:/home/pakon:/bin/bash
nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin
"""

# ของผู้ใช้ที่ต้องหายจาก image (I2) · path ใต้ราก
PRIVATE = [
    "home/pakon/.local/share/aipc/chats/a.json",
    "home/pakon/.claude/.credentials.json",
    "home/aipc2030/.ssh/authorized_keys",
    "root/.bash_history",
    "root/.ssh/authorized_keys",
    "var/lib/aipc/recovery/pakon.json",
    "var/lib/aipc/password-checks/pakon.json",
    "var/lib/aipc/greeter-user.json",
    "var/lib/aipc-vision/face-login/pakon.json",
    "var/spool/cron/crontabs/pakon",
    "var/mail/pakon",
    "var/lib/systemd/linger/pakon",
    "etc/NetworkManager/system-connections/Home.nmconnection",
    "etc/ssh/ssh_host_ed25519_key",
    "var/log/journal/abc/system.journal",
]
# ของระบบที่ต้องอยู่ครบ
KEEP = [
    "etc/aipc/llm.conf",
    "var/lib/aipc/install-all.done",
    "opt/aipc-models/gemma.gguf",
    "etc/ssh/sshd_config",
]


@unittest.skipUnless(BASH, "ต้องมี bash")
class PrepareImageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "root"
        for rel in PRIVATE + KEEP:
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x", encoding="utf-8")
        (self.root / "etc" / "passwd").write_text(PASSWD, encoding="utf-8", newline="\n")
        (self.root / "etc" / "machine-id").write_text("0123456789abcdef\n", encoding="utf-8")
        self.fake = base / "bin"
        self.fake.mkdir()
        self.log = base / "calls.log"
        log = self.log.as_posix()
        self.write(self.fake / "id", "echo 0\n")
        # userdel ปลอม: จดว่าเรียก + ลบบรรทัดของบัญชีออกจาก passwd ของรากที่ส่งมา (--root)
        self.write(self.fake / "userdel",
                   f'echo "userdel $*" >> "{log}"\n'
                   'root=/; while [ $# -gt 1 ]; do case "$1" in --root) root="$2"; shift 2;; '
                   '*) shift;; esac; done\n'
                   'sed -i "/^$1:/d" "$root/etc/passwd"\n')  # fmt: skip

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def write(path: Path, body: str) -> None:
        path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8", newline="\n")
        path.chmod(0o755)

    def run_it(self, *args):
        cmd = (f'PATH="{self.fake.as_posix()}:$PATH" bash "{SCRIPT.as_posix()}" '
               f'--root "{self.root.as_posix()}" {" ".join(args)}')  # fmt: skip
        env = dict(os.environ)
        env["PATH"] = self.fake.as_posix() + os.pathsep + env["PATH"]  # วินโดวส์: "C:/…" มี : แยกผิดที่
        return subprocess.run([BASH, "-c", cmd], env=env, capture_output=True, text=True,
                              encoding="utf-8")  # fmt: skip

    def exists(self, rel: str) -> bool:
        return (self.root / rel).exists()

    def test_check_mode_changes_nothing_and_lists_everything(self):
        r = self.run_it()
        self.assertEqual(r.returncode, 1, "มีข้อมูลผู้ใช้ = ไม่ผ่าน I2")
        self.assertTrue(all(self.exists(rel) for rel in PRIVATE + KEEP), "โหมดตรวจห้ามลบ")
        self.assertFalse(self.log.exists(), "โหมดตรวจห้ามเรียก userdel")
        for name in ("aipc2030", "pakon", "home/pakon", "recovery", "face-login",
                     "system-connections", "ssh_host_ed25519_key", "machine-id"):  # fmt: skip
            self.assertIn(name, r.stdout, name)
        self.assertNotIn("nobody", r.stdout, "บัญชีระบบไม่ใช่ข้อมูลผู้ใช้")

    def test_apply_needs_the_second_flag(self):
        r = self.run_it("--apply")
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(all(self.exists(rel) for rel in PRIVATE))
        self.assertIn("--yes-wipe-users", r.stdout + r.stderr)

    def test_apply_wipes_user_data_then_check_is_clean(self):
        r = self.run_it("--apply", "--yes-wipe-users")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([rel for rel in PRIVATE if self.exists(rel)], [])
        self.assertEqual([rel for rel in KEEP if not self.exists(rel)], [], "ของระบบต้องอยู่")
        passwd = (self.root / "etc" / "passwd").read_text(encoding="utf-8")
        self.assertNotIn("pakon:", passwd)
        self.assertIn("nobody:", passwd)
        self.assertEqual((self.root / "etc" / "machine-id").read_text(encoding="utf-8"), "",
                         "machine-id ว่าง = เครื่องที่แฟลชแล้วสร้างใหม่ตอนบูตครั้งแรก")  # fmt: skip
        again = self.run_it()
        self.assertEqual(again.returncode, 0, again.stdout)

    def test_refuses_without_root(self):
        self.write(self.fake / "id", "echo 1000\n")
        r = self.run_it("--apply", "--yes-wipe-users")
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(self.exists("home/pakon/.claude/.credentials.json"))


if __name__ == "__main__":
    unittest.main()
