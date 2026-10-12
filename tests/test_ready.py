"""ตรวจความพร้อมก่อนสาธิต (aipc.doctor.ready) · ค่าปลอม ไม่ต้องมี Pi."""

import tempfile
import unittest
from pathlib import Path

from aipc.doctor import ready
from aipc.doctor.hardware import FAIL, PASS, UNKNOWN, WARN


def runner(outputs: dict):
    return lambda cmd: outputs.get(cmd[0] + " " + cmd[1])


class ReadyTest(unittest.TestCase):
    def test_clock_not_synced_warns_about_reminders(self):
        c = ready.check_clock(runner({"timedatectl show": "no"}))
        self.assertEqual(c.status, WARN)
        self.assertIn("นัด", c.detail)
        self.assertEqual(ready.check_clock(runner({"timedatectl show": "yes"})).status, PASS)
        self.assertEqual(ready.check_clock(runner({})).status, UNKNOWN)

    def test_power_and_heat(self):
        ok = ready.check_power_and_heat(
            runner(
                {"vcgencmd measure_temp": "temp=55.0'C", "vcgencmd get_throttled": "throttled=0x0"}
            )
        )
        self.assertEqual([c.status for c in ok], [PASS, PASS])
        past = ready.check_power_and_heat(
            runner(
                {
                    "vcgencmd measure_temp": "temp=87.3'C",
                    "vcgencmd get_throttled": "throttled=0x50000",
                }
            )
        )
        self.assertEqual([c.status for c in past], [FAIL, WARN])  # ร้อนเกิน 85 · ไฟเคยตก
        self.assertIn("ปลั๊ก", past[1].fix)
        now = ready.check_power_and_heat(runner({"vcgencmd get_throttled": "throttled=0x50005"}))
        self.assertEqual([c.status for c in now], [UNKNOWN, FAIL])  # ไฟตกอยู่ตอนนี้

    def test_network(self):
        class Conn:
            def close(self):
                pass

        self.assertEqual(ready.check_network(lambda *a, **k: Conn()).status, PASS)

        def down(*a, **k):
            raise OSError

        self.assertEqual(ready.check_network(down).status, WARN)

    def test_camera_ignores_the_pi_chips_own_video_nodes(self):
        # พบบน Pi 5 2026-10-12: ถอดกล้องแล้วยังขึ้น "พบกล้อง" (นับ /dev/video* ของชิปด้วย)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "dev").mkdir()

            def node(n, name):
                (root / "dev" / f"video{n}").touch()
                sysfs = root / "sys/class/video4linux" / f"video{n}"
                sysfs.mkdir(parents=True)
                (sysfs / "name").write_text(name, encoding="utf-8")

            node(19, "rpi-hevc-dec")
            node(20, "pispbe-input")
            cam = ready.check_devices(root, True, True, "claude")[0]
            self.assertEqual((cam.id, cam.status), ("camera", WARN))
            node(0, "USB Camera: USB Camera")
            self.assertEqual(ready.check_devices(root, True, True, "claude")[0].status, PASS)

    def test_run_all_lists_everything(self):
        with tempfile.TemporaryDirectory() as d:
            checks = ready.run_all(
                ai_ready=False,
                home=Path(d),
                voice_available=True,
                mic_available=False,
                claude=None,
                root=Path(d),
                run=runner({}),
                connect=lambda *a, **k: (_ for _ in ()).throw(OSError()),
            )
        ids = [c.id for c in checks]
        self.assertEqual(
            ids, ["ai", "net", "clock", "heat", "power", "disk", "camera", "speak", "mic", "claude"]
        )
        self.assertEqual(checks[0].status, FAIL)
        self.assertTrue(all(c.fix for c in checks if c.status in (WARN, FAIL)))  # ทุกข้อที่ไม่ผ่านมีวิธีแก้


if __name__ == "__main__":
    unittest.main()
