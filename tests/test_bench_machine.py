import tempfile
import unittest
from pathlib import Path

from aipc.bench import machine


def fake_root(files: dict[str, str]) -> tempfile.TemporaryDirectory:
    tmp = tempfile.TemporaryDirectory()
    for path, text in files.items():
        p = Path(tmp.name) / path.lstrip("/")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp


PI5_FILES = {
    "/proc/device-tree/model": "Raspberry Pi 5 Model B Rev 1.0\x00",
    "/proc/meminfo": "MemTotal:        8245680 kB\nMemFree: 1 kB\n",
    "/etc/os-release": 'PRETTY_NAME="Debian GNU/Linux 13 (trixie)"\nID=debian\n',
    "/sys/class/thermal/thermal_zone0/temp": "52350\n",
}


class BoardTest(unittest.TestCase):
    def test_reads_pi5_files(self):
        with fake_root(PI5_FILES) as root:
            r = Path(root)
            self.assertEqual(machine.board_model(r), "Raspberry Pi 5 Model B Rev 1.0")
            self.assertEqual(machine.ram_total_mb(r), 8052)
            self.assertEqual(machine.os_pretty_name(r), "Debian GNU/Linux 13 (trixie)")
            self.assertAlmostEqual(machine.cpu_temp_c(r), 52.35)

    def test_board_class(self):
        self.assertEqual(machine.board_class("Raspberry Pi 5 Model B Rev 1.0"), "pi5")
        self.assertEqual(machine.board_class("Raspberry Pi 4 Model B Rev 1.4"), "pi4")
        self.assertEqual(machine.board_class(None), "other")

    def test_missing_files_give_none_not_crash(self):
        with fake_root({}) as root:
            r = Path(root)
            self.assertIsNone(machine.board_model(r))
            self.assertIsNone(machine.ram_total_mb(r))
            self.assertIsNone(machine.cpu_temp_c(r))


class ThrottledTest(unittest.TestCase):
    def test_parses_vcgencmd_output(self):
        self.assertEqual(machine.throttled_raw(lambda args: "throttled=0x50005"), 0x50005)
        self.assertIsNone(machine.throttled_raw(lambda args: None))
        self.assertIsNone(machine.throttled_raw(lambda args: "garbage"))

    def test_decode_zero_means_no_problem(self):
        self.assertEqual(machine.decode_throttled(0), [])

    def test_decode_undervoltage_now_and_since_boot(self):
        problems = machine.decode_throttled(0x10001)
        self.assertEqual(len(problems), 2)
        self.assertIn("ไฟตก (under-voltage) ตอนนี้", problems)


class CollectTest(unittest.TestCase):
    def test_collect_with_fake_machine(self):
        answers = {
            ("vcgencmd", "get_throttled"): "throttled=0x0",
            ("git", "-C", "repo", "rev-parse", "HEAD"): "abc123",
            ("git", "-C", "repo", "status", "--porcelain"): "",
        }
        with fake_root(PI5_FILES) as root:
            info = machine.collect(Path("repo"), Path(root), lambda a: answers.get(tuple(a)))
        self.assertEqual(info.board_class, "pi5")
        self.assertEqual(info.throttled, 0)
        self.assertEqual(info.git_commit, "abc123")
        self.assertIs(info.git_dirty, False)


if __name__ == "__main__":
    unittest.main()
