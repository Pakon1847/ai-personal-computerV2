"""ตัวติดตั้งรวม (การ์ด 0077 · I3 ส่วนที่ทดสอบบนวินโดวส์ได้) · รันสคริปต์จริงด้วย bash แต่แทนคำสั่งที่แตะเครื่อง.

ของปลอมใน PATH: uname (aarch64) · id (root) · apt-get git cmake curl sha256sum ·
สคริปต์ install-*.sh ปลอมจดว่าถูกเรียก
ของจริงต้องทดสอบบน Raspberry Pi OS ที่ลงใหม่ (I3 · ถาม Pakon ก่อน)
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "pi" / "install-all.sh"
BASH = shutil.which("bash")
SUBS = ("install-greeter", "update-app", "install-accounts", "install-llm", "install-voice",
        "install-visiond", "install-lockscreen", "install-browser", "install-wifi-access",
        "install-apps")  # fmt: skip
SHA = re.search(r"MODEL_SHA256=(\w+)", SCRIPT.read_text(encoding="utf-8")).group(1)


@unittest.skipUnless(BASH and os.name != "nt" or shutil.which("bash"), "ต้องมี bash")
class InstallAllTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root
        pi = root / "repo" / "scripts" / "pi"
        pi.mkdir(parents=True)
        (root / "repo" / "pyproject.toml").write_text("", encoding="utf-8")
        shutil.copy(SCRIPT, pi / "install-all.sh")
        self.log = root / "calls.log"
        for name in SUBS:  # ล้มเมื่อชื่อตรงกับ FAIL_AT
            self.write(pi / f"{name}.sh",
                       f'echo "{name} $*" >> "{self.log.as_posix()}"\n'
                       f'[ "${{FAIL_AT:-}}" = "{name}" ] && exit 3\nexit 0\n')  # fmt: skip
        fake = root / "bin"
        fake.mkdir()
        log = self.log.as_posix()
        self.write(fake / "uname", "echo aarch64\n")
        self.write(fake / "id", "echo 0\n")
        for tool in ("apt-get", "git"):
            self.write(fake / tool, f'echo "{tool} $*" >> "{log}"\n')
        # cmake --build = สร้างไฟล์ llama-server ปลอม
        # (วินโดวส์นับว่าไฟล์รันได้เมื่อขึ้นต้นด้วย #!)
        server = '"$2/bin/llama-server"'
        self.write(fake / "cmake", f'echo "cmake $*" >> "{log}"\n'
                   f'if [ "$1" = "--build" ]; then mkdir -p "$2/bin"; echo "#!/bin/sh" > {server}; '
                   f'chmod +x {server}; fi\n')  # fmt: skip
        self.write(fake / "curl", f'echo "curl" >> "{log}"\n'
                   'while [ "$1" != "-o" ]; do shift; done\necho model > "$2"\n')  # fmt: skip
        self.write(fake / "sha256sum", f'echo "${{FAKE_SHA:-{SHA}}}  $1"\n')
        self.fake = fake

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def write(path: Path, body: str) -> None:
        path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8", newline="\n")
        path.chmod(0o755)

    def run_it(self, *args, **env):
        e = dict(os.environ, AIPC_STATE_DIR=(self.root / "state").as_posix(),
                 AIPC_BUILD_DIR=(self.root / "build").as_posix(), **env)  # fmt: skip
        e["PATH"] = self.fake.as_posix() + os.pathsep + e["PATH"]
        script = self.root / "repo" / "scripts" / "pi" / "install-all.sh"
        cmd = f'PATH="{self.fake.as_posix()}:$PATH" bash "{script.as_posix()}" {" ".join(args)}'
        return subprocess.run([BASH, "-c", cmd], env=e, capture_output=True, text=True,
                              encoding="utf-8")  # fmt: skip

    def calls(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def test_dry_run_changes_nothing(self):
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ถ้าถูกต้อง", r.stdout)
        self.assertEqual(self.calls(), [], "โหมดดูก่อนต้องไม่เรียกอะไรเลย")
        self.assertFalse((self.root / "state").exists())

    def test_apply_runs_every_step_in_order(self):
        r = self.run_it("--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        subs = [c.split()[0] for c in self.calls() if c.split()[0] in SUBS]
        self.assertEqual(subs, list(SUBS))
        self.assertIn("install-greeter --apply --session v2", self.calls())
        llm = next(c for c in self.calls() if c.startswith("install-llm"))
        self.assertIn("gemma-4-E2B-it-Q4_K_M.gguf", llm)
        self.assertIn("เสร็จครบ 12 ขั้น", r.stdout)

    def test_stops_at_failed_step_and_resumes_there(self):
        r = self.run_it("--apply", FAIL_AT="install-voice")
        self.assertEqual(r.returncode, 1)
        self.assertIn("หยุดที่ขั้น 7 (voice)", r.stdout)
        self.assertNotIn("install-visiond --apply", self.calls(), "ขั้นหลังจากที่พังต้องไม่ทำ")
        self.log.unlink()
        r = self.run_it("--apply")
        self.assertEqual(r.returncode, 0, r.stdout)
        subs = [c.split()[0] for c in self.calls() if c.split()[0] in SUBS]
        self.assertEqual(subs[0], "install-voice", "ทำต่อจากขั้นที่หยุด ไม่ทำขั้นที่เสร็จแล้วซ้ำ")
        self.assertNotIn("apt-get install -y git cmake build-essential libcurl4-openssl-dev",
                         self.calls())  # fmt: skip

    def test_bad_model_checksum_stops_and_deletes_the_file(self):
        r = self.run_it("--apply", FAKE_SHA="0" * 64)
        self.assertEqual(r.returncode, 1)
        self.assertIn("sha256 ไม่ตรง", r.stdout)
        self.assertFalse((self.root / "build" / "models" / "gemma-4-E2B-it-Q4_K_M.gguf").exists())
        self.assertFalse(any(c.startswith("install-") for c in self.calls()))

    def test_wrong_machine_is_refused_before_changing_anything(self):
        self.write(self.fake / "uname", "echo x86_64\n")
        r = self.run_it("--apply")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ARM 64", r.stdout)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
