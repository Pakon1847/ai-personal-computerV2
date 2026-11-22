"""รันเทสต์ของ server/share-worker (JavaScript) ด้วย Node · บน Pi ไม่มี Node = ถูกข้าม."""

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("node"), "เครื่องนี้ไม่มี Node.js")
class ShareWorkerTest(unittest.TestCase):
    def test_worker(self):
        done = subprocess.run(
            ["node", "--test", "server/share-worker/worker.test.mjs"],
            cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=120,
        )  # fmt: skip
        self.assertEqual(done.returncode, 0, done.stdout[-2000:])
