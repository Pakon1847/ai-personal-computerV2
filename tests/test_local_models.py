"""เลือก AI ในเครื่อง 3 ตัว (การ์ด 0076) · เกณฑ์ M1 M2."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from aipc.chat import localmodels as lm
from aipc.ui.backend import LocalModels

REPO = Path(__file__).resolve().parents[1]
START = REPO / "scripts" / "pi" / "session" / "aipc-llm-start"


class ListTest(unittest.TestCase):
    def test_list_has_three_models_with_screen_text(self):
        models = lm.load()
        self.assertEqual([m.key for m in models], ["gemma4-e2b", "qwen3.5-2b", "qwen3.5-4b"])
        self.assertEqual(set(lm.INFO), {m.key for m in models}, "ทุกตัวในรายการต้องมีคำบรรยายบนหน้าจอ")

    def test_missing_or_broken_list(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(lm.load(Path(d) / "none.conf"), [])
            p = Path(d) / "x.conf"
            p.write_text("# หมายเหตุ\n\nonlyname\nok|ok.gguf|\n", encoding="utf-8")
            self.assertEqual(lm.load(p), [lm.Model("ok", "ok.gguf", "")])


class ChoiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.models = [lm.Model("a", "a.gguf"), lm.Model("b", "b.gguf", "b.jinja")]
        self.dir = self.root / "models"
        self.dir.mkdir()
        (self.dir / "a.gguf").write_bytes(b"x")
        (self.dir / "b.gguf").write_bytes(b"x")

    def tearDown(self):
        self.tmp.cleanup()

    def test_m1_bad_choice_uses_machine_model(self):
        for choice in ("", "zzz", "../a", "/opt/aipc-models/a.gguf"):
            self.assertEqual(
                lm.effective(self.models, choice, "machine.gguf", self.dir), "machine.gguf", choice
            )
        (self.dir / "b.gguf").unlink()  # ในรายการ แต่ไฟล์ไม่มีจริง
        self.assertEqual(lm.effective(self.models, "b", "machine.gguf", self.dir), "machine.gguf")
        self.assertEqual(lm.effective(self.models, "a", "machine.gguf", self.dir), "a.gguf")

    def test_m2_saved_per_account(self):
        alice, bob = self.root / "alice" / "llm-model", self.root / "bob" / "llm-model"
        self.assertTrue(lm.save("b", self.models, alice))
        self.assertEqual(lm.chosen(alice), "b")
        self.assertEqual(lm.chosen(bob), "", "บัญชีอื่นไม่เปลี่ยน")
        self.assertFalse(lm.save("../etc", self.models, alice))
        self.assertEqual(lm.chosen(alice), "b")

    def _ctl(self, active=True, restart=lambda: True, switched=None):
        return LocalModels(active, models=self.models, models_dir=self.dir,
                           choice=self.root / "c" / "llm-model", machine="a.gguf",
                           restart=restart, on_switch=switched)  # fmt: skip

    def test_controller_pick_and_current(self):
        names = []
        ctl = self._ctl(switched=names.append)
        self.assertEqual([m["current"] for m in ctl.models], [True, False])
        self.assertTrue(ctl.pick("b"))
        self.assertEqual([m["current"] for m in ctl.models], [False, True])
        self.assertEqual(names, ["b"])
        self.assertEqual(ctl.error, "")

    def test_controller_refuses_uninstalled_and_outside_session(self):
        (self.dir / "b.gguf").unlink()
        ctl = self._ctl()
        self.assertFalse(ctl.models[1]["installed"])
        self.assertFalse(ctl.pick("b"))
        self.assertIn("ยังไม่ได้ติดตั้ง", ctl.error)
        self.assertFalse(self._ctl(active=False).pick("a"))

    def test_restart_failure_is_reported(self):
        ctl = self._ctl(restart=lambda: False)
        self.assertFalse(ctl.pick("b"))
        self.assertIn("ออกจากระบบแล้วเข้าใหม่", ctl.error)  # H2: ไม่เงียบ


@unittest.skipUnless(shutil.which("sh") and shutil.which("awk"), "ต้องมี sh + awk")
class StartScriptTest(unittest.TestCase):
    """รัน aipc-llm-start จริงโดยแทน path ของเครื่องด้วยโฟลเดอร์ชั่วคราว และแทน llama-server ด้วย echo."""

    def run_start(self, choice: str | None, files=("Qwen3.5-2B-Q4_K_M.gguf",)) -> str:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "models").mkdir()
            for f in files:
                (root / "models" / f).write_bytes(b"x")
            (root / "llm.conf").write_text(
                "MODEL=/m/machine.gguf\nTHREADS=3\nCTX=4096\nTEMPLATE=\n", encoding="utf-8"
            )
            text = START.read_text(encoding="utf-8")
            text = text.replace("/etc/aipc/llm.conf", (root / "llm.conf").as_posix())
            text = text.replace("/opt/aipc-models", (root / "models").as_posix())
            text = text.replace("exec /opt/aipc-llm/bin/llama-server", "echo")
            (root / "bin").mkdir()
            script = root / "bin" / "aipc-llm-start"
            script.write_text(text, encoding="utf-8", newline="\n")
            shutil.copy(START.parent / "llm-models.conf", root / "bin" / "llm-models.conf")
            cfg = root / "cfg"
            if choice is not None:
                (cfg / "aipc").mkdir(parents=True)
                (cfg / "aipc" / "llm-model").write_text(choice, encoding="utf-8")
            env = dict(os.environ, XDG_CONFIG_HOME=cfg.as_posix(),
                       XDG_RUNTIME_DIR=(root / "run").as_posix(),
                       XDG_CACHE_HOME=(root / "cache").as_posix(),
                       HOME=root.as_posix())  # fmt: skip
            out = subprocess.run([shutil.which("sh"), script.as_posix()], env=env,
                                 capture_output=True, text=True, check=True).stdout  # fmt: skip
            return out.split("-m ", 1)[1].split(" ", 1)[0]

    def test_choice_in_list_and_installed(self):
        self.assertTrue(self.run_start("qwen3.5-2b\n").endswith("/models/Qwen3.5-2B-Q4_K_M.gguf"))

    def test_m1_falls_back_to_machine(self):
        self.assertEqual(self.run_start(None), "/m/machine.gguf")
        self.assertEqual(self.run_start("qwen3.5-4b"), "/m/machine.gguf", "ไฟล์ไม่มีจริง")
        self.assertEqual(self.run_start("/etc/passwd"), "/m/machine.gguf")
        self.assertEqual(self.run_start(""), "/m/machine.gguf")


if __name__ == "__main__":
    unittest.main()
