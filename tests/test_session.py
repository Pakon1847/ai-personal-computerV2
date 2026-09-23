"""เซสชันของ V2 หลัง login (การ์ด 0004): ปุ่มออก และสคริปต์เปิดหน้าจอใหม่เมื่อล่ม."""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LOOP = Path(__file__).resolve().parents[1] / "scripts" / "pi" / "session" / "aipc-shell-loop"

try:
    from aipc.ui.backend import SessionController
except ImportError:  # pragma: no cover
    SessionController = None


@unittest.skipIf(SessionController is None, "ไม่มี PySide6")
class LogoutTest(unittest.TestCase):
    def test_real_session_runs_labwc_exit(self):
        calls = []
        s = SessionController(True, runner=lambda args: calls.append(args) or 0)
        self.assertTrue(s.logout())
        self.assertEqual(calls, [["labwc", "--exit"]])
        self.assertEqual(s.error, "")

    def test_failed_exit_is_reported_not_silent(self):
        s = SessionController(True, runner=lambda args: 127)
        self.assertFalse(s.logout())
        self.assertIn("ไม่สำเร็จ", s.error)

    def test_dev_window_never_runs_anything(self):
        calls = []
        s = SessionController(False, runner=lambda args: calls.append(args) or 0)
        self.assertFalse(s.logout())
        self.assertEqual(calls, [])


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("bash"), "รันบน Linux")
class ShellLoopTest(unittest.TestCase):
    """รันสคริปต์จริงด้วยคำสั่งปลอมแทนหน้าจอ V2 · นับว่าถูกเปิดกี่ครั้ง."""

    def run_loop(self, fake_body: str, **env):
        with tempfile.TemporaryDirectory() as tmp:
            count = Path(tmp) / "count"
            fake = Path(tmp) / "fake-ui"
            fake.write_text(f"#!/bin/sh\necho x >> {count}\n{fake_body}\n", encoding="utf-8")
            fake.chmod(0o755)
            e = {k: v for k, v in os.environ.items() if k != "LABWC_PID"}
            e.update(AIPC_SHELL_CMD=str(fake), **env)
            p = subprocess.run(
                ["bash", str(LOOP)], env=e, capture_output=True, text=True, timeout=30
            )
            runs = len(count.read_text().split()) if count.exists() else 0
            return p.returncode, runs, p.stderr

    def test_gives_up_after_three_quick_crashes(self):
        code, runs, err = self.run_loop("exit 1", AIPC_MAX_CRASHES="3", AIPC_CRASH_WINDOW="60")
        self.assertEqual((code, runs), (1, 3))
        self.assertIn("จบเซสชัน", err)

    def test_restarts_when_crashes_are_far_apart(self):
        # หน้าต่างเวลา 0 วินาที = ไม่มีการล่มไหนนับว่า "ติดกัน" → เปิดใหม่เรื่อย ๆ จน labwc จบ
        with tempfile.TemporaryDirectory() as tmp:
            sleeper = subprocess.Popen(["sleep", "30"])
            try:
                stop = f'[ "$(wc -l < {tmp}/c)" -ge 4 ] && kill {sleeper.pid}; exit 1'
                body = f"echo x >> {tmp}/c; {stop}"
                code, runs, _ = self.run_loop(
                    body, AIPC_MAX_CRASHES="2", AIPC_CRASH_WINDOW="0", LABWC_PID=str(sleeper.pid)
                )
            finally:
                sleeper.kill()
                sleeper.wait()
        self.assertEqual((code, runs), (0, 4))

    def test_stops_when_labwc_is_gone(self):
        # ผู้ใช้กด "ออก" → labwc จบ → ห้ามเปิดหน้าจอใหม่
        sleeper = subprocess.Popen(["sleep", "30"])
        try:
            code, runs, _ = self.run_loop(f"kill {sleeper.pid}; exit 0", LABWC_PID=str(sleeper.pid))
        finally:
            sleeper.kill()
            sleeper.wait()
        self.assertEqual((code, runs), (0, 1))


def _xkb():
    import ctypes
    import ctypes.util

    name = ctypes.util.find_library("xkbcommon")
    return ctypes.CDLL(name) if name else None


@unittest.skipUnless(sys.platform.startswith("linux") and _xkb(), "ต้องมี libxkbcommon (Linux)")
class KeymapTest(unittest.TestCase):
    """คอมไพล์ผังแป้นจริงด้วย libxkbcommon ตัวเดียวกับที่ labwc ใช้ · ผิดตรงนี้ = labwc ใช้แป้นผิด."""

    TLDE, AC01 = 49, 38  # keycode ของปุ่ม ` และปุ่ม a (evdev + 8)
    ISO_NEXT_GROUP, THAI_FOFAN = 0xFE08, 0x0DBF

    FIELDS = ("rules", "model", "layout", "variant", "options")

    def env(self) -> dict[str, str]:
        text = (LOOP.parent / "labwc" / "environment").read_text(encoding="utf-8")
        pairs = (ln.partition("=") for ln in text.splitlines() if ln and ln[0] != "#")
        return {k: v for k, _, v in pairs}

    def keysym(self, key: int, group: int, level: int = 0) -> int | None:
        import ctypes as c

        os.environ["XKB_CONFIG_EXTRA_PATH"] = str(LOOP.parent / "xkb")  # เหมือน aipc-session
        x, conf = _xkb(), self.env()

        class Names(c.Structure):
            _fields_ = [(n, c.c_char_p) for n in self.FIELDS]

        x.xkb_context_new.restype = c.c_void_p
        x.xkb_keymap_new_from_names.restype = c.c_void_p
        x.xkb_keymap_new_from_names.argtypes = [c.c_void_p, c.POINTER(Names), c.c_int]
        x.xkb_keymap_key_get_syms_by_level.argtypes = [
            c.c_void_p, c.c_uint32, c.c_uint32, c.c_uint32, c.POINTER(c.POINTER(c.c_uint32)),
        ]  # fmt: skip
        values = ["evdev", conf["XKB_DEFAULT_MODEL"], conf["XKB_DEFAULT_LAYOUT"], "",
                  conf["XKB_DEFAULT_OPTIONS"]]  # fmt: skip
        names = Names(*(v.encode() for v in values))
        km = x.xkb_keymap_new_from_names(x.xkb_context_new(0), c.byref(names), 0)
        self.assertTrue(km, "คอมไพล์ผังแป้นไม่ผ่าน → labwc จะใช้แป้นผิด")
        syms = c.POINTER(c.c_uint32)()
        n = x.xkb_keymap_key_get_syms_by_level(km, key, group, level, c.byref(syms))
        return syms[0] if n else None

    def test_grave_switches_language_in_both_layouts(self):
        self.assertEqual(self.keysym(self.TLDE, 0), self.ISO_NEXT_GROUP, "อังกฤษ → ไทย")
        self.assertEqual(self.keysym(self.TLDE, 1), self.ISO_NEXT_GROUP, "ไทย → อังกฤษ")
        self.assertEqual(self.keysym(self.TLDE, 0, level=1), ord("~"), "Shift+` = ~")
        self.assertEqual(self.keysym(self.TLDE, 1, level=1), ord("%"), "ไทย Shift+` = %")

    def test_thai_layout_still_types_thai(self):
        self.assertEqual(self.keysym(self.AC01, 1), self.THAI_FOFAN, "ปุ่ม a ฝั่งไทย = ฟ")
        self.assertEqual(self.keysym(self.AC01, 0), ord("a"))


class SessionConfigTest(unittest.TestCase):
    """ค่าตั้ง labwc ของเซสชันต้องไม่มีทางหลุดไปเดสก์ท็อป/terminal ของ Pi."""

    DIR = LOOP.parent / "labwc"

    @staticmethod
    def code_only(path: Path) -> str:
        """ตัดคำอธิบาย (comment) ออก ตรวจเฉพาะค่าที่มีผลจริง."""
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".xml":
            return re.sub(r"<!--.*?-->", "", text, flags=re.S)
        return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))

    def test_no_default_keybinds_or_terminal(self):
        rc = self.code_only(self.DIR / "rc.xml")
        self.assertIn('key="A-Tab"', rc)
        for bad in ("<default", "terminal", "Execute", "Exit", "wfpanelctl", "pishutdown"):
            self.assertNotIn(bad, rc, bad)

    def test_menu_is_empty(self):
        menu = self.code_only(self.DIR / "menu.xml")
        self.assertNotIn("<item", menu)

    def test_session_does_not_start_pi_desktop(self):
        text = self.code_only(LOOP.parent / "aipc-session")
        self.assertIn('labwc -C "$HERE/labwc" -S', text)
        for bad in ("labwc-pi", "wf-panel", "pcmanfm", " -m"):
            self.assertNotIn(bad, text)


if __name__ == "__main__":
    unittest.main()
