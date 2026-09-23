import tempfile
import unittest
from pathlib import Path

from aipc.doctor import hardware as hw


class FakeMachine:
    """สร้างโฟลเดอร์ปลอมที่หน้าตาเหมือน / ของ Pi เพื่อทดสอบโดยไม่ต้องมีเครื่องจริง."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def write(self, path: str, content: str | bytes):
        p = self.root / path.lstrip("/")
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8")

    def close(self):
        self.tmp.cleanup()


def throttled(value):
    return lambda args: f"throttled={value:#x}" if args[:1] == ["vcgencmd"] else None


class HardwareTest(unittest.TestCase):
    def setUp(self):
        self.m = FakeMachine()

    def tearDown(self):
        self.m.close()

    def test_pi5_board_passes_pi4_warns(self):
        self.m.write("/proc/device-tree/model", "Raspberry Pi 5 Model B Rev 1.0\x00")
        self.assertEqual(hw.check_board(self.m.root).status, hw.PASS)
        self.m.write("/proc/device-tree/model", "Raspberry Pi 4 Model B Rev 1.4\x00")
        self.assertEqual(hw.check_board(self.m.root).status, hw.WARN)

    def test_ram_threshold(self):
        self.m.write("/proc/meminfo", "MemTotal: 8245680 kB\n")
        self.assertEqual(hw.check_ram(self.m.root).status, hw.PASS)
        self.m.write("/proc/meminfo", "MemTotal: 3884000 kB\n")
        self.assertEqual(hw.check_ram(self.m.root).status, hw.WARN)

    def test_power_5a_and_no_undervoltage_passes(self):
        self.m.write("/proc/device-tree/chosen/power/max_current", (5000).to_bytes(4, "big"))
        self.assertEqual(hw.check_power(self.m.root, throttled(0)).status, hw.PASS)

    def test_power_3a_supply_warns(self):
        self.m.write("/proc/device-tree/chosen/power/max_current", (3000).to_bytes(4, "big"))
        self.assertEqual(hw.check_power(self.m.root, throttled(0)).status, hw.WARN)

    def test_undervoltage_since_boot_fails_even_with_5a(self):
        self.m.write("/proc/device-tree/chosen/power/max_current", (5000).to_bytes(4, "big"))
        self.assertEqual(hw.check_power(self.m.root, throttled(0x50000)).status, hw.FAIL)

    def test_power_unreadable_is_unknown_not_pass(self):
        self.assertEqual(hw.check_power(self.m.root, lambda a: None).status, hw.UNKNOWN)

    def test_fan_spinning_passes_fan_idle_unknown(self):
        self.m.write("/sys/class/hwmon/hwmon2/name", "pwmfan\n")
        self.m.write("/sys/class/hwmon/hwmon2/fan1_input", "2800\n")
        self.assertEqual(hw.check_cooling(self.m.root).status, hw.PASS)
        self.m.write("/sys/class/hwmon/hwmon2/fan1_input", "0\n")
        self.assertEqual(hw.check_cooling(self.m.root).status, hw.UNKNOWN)

    def test_rtc_charging(self):
        self.m.write("/sys/class/rtc/rtc0/charging_voltage", "3000000\n")
        self.assertEqual(hw.check_rtc(self.m.root).status, hw.PASS)
        self.m.write("/sys/class/rtc/rtc0/charging_voltage", "0\n")
        c = hw.check_rtc(self.m.root)
        self.assertEqual(c.status, hw.WARN)
        self.assertIn("rtc_bbat_vchg", c.fix)  # บอกวิธีแก้ แต่ไม่แก้เอง

    def test_os_requires_trixie(self):
        self.m.write("/etc/os-release", 'PRETTY_NAME="Debian 12"\nVERSION_CODENAME=bookworm\n')
        self.assertEqual(hw.check_os(self.m.root).status, hw.FAIL)

    def test_storage_kind_from_mounts(self):
        self.m.write("/proc/mounts", "/dev/mmcblk0p2 / ext4 rw 0 0\n")
        self.assertEqual(hw.root_device(self.m.root), "/dev/mmcblk0p2")
        self.assertIn("microSD", hw.check_storage(self.m.root, self.m.root).detail)
        self.m.write("/proc/mounts", "/dev/nvme0n1p2 / ext4 rw 0 0\n")
        self.assertIn("NVMe", hw.check_storage(self.m.root, self.m.root).detail)

    def test_nothing_readable_never_passes(self):
        # เครื่องที่อ่านอะไรไม่ได้เลย (เช่นวินโดวส์) ต้องไม่มีข้อไหนแอบผ่าน
        # ยกเว้นพื้นที่ดิสก์ ซึ่งอ่านได้ทุกระบบ
        checks = hw.run_all(self.m.root, lambda a: None, self.m.root)
        passed = [c.id for c in checks if c.status == hw.PASS]
        self.assertTrue(set(passed) <= {"storage", "glibc"}, passed)


# โหนดวิดีโอของ Pi 4 ที่ไม่ได้ต่อกล้อง (คัดจาก /sys/class/video4linux บนเครื่องจริง 2026-09-24)
PI4_SOC_NODES = {
    "video10": "bcm2835-codec-decode", "video11": "bcm2835-codec-encode",
    "video12": "bcm2835-codec-isp", "video13": "bcm2835-isp-output0",
    "video14": "bcm2835-isp-capture0", "video15": "bcm2835-isp-capture1",
    "video16": "bcm2835-isp-stats2", "video18": "bcm2835-codec-image_fx",
    "video19": "rpi-hevc-dec", "video20": "bcm2835-isp-output0",
    "video21": "bcm2835-isp-capture0", "video22": "bcm2835-isp-capture1",
    "video23": "bcm2835-isp-stats2", "video31": "bcm2835-codec-encode_image",
}


class CameraTest(unittest.TestCase):
    """บั๊กที่เจอบน Pi 4: นับโหนดของชิปเป็นกล้อง ทำให้ไฟกล้องบอก "กล้องพร้อม" ทั้งที่ไม่มีกล้อง."""

    def setUp(self):
        self.m = FakeMachine()

    def tearDown(self):
        self.m.close()

    def node(self, dev: str, name: str | None):
        self.m.write(f"/dev/{dev}", "")
        if name is not None:
            self.m.write(f"/sys/class/video4linux/{dev}/name", name + "\n")

    def test_pi4_without_camera_is_not_a_camera(self):
        for dev, name in PI4_SOC_NODES.items():
            self.node(dev, name)
        c = hw.check_camera(self.m.root)
        self.assertEqual(c.status, hw.WARN)
        self.assertIn("ไม่พบกล้อง", c.detail)
        self.assertIn("14", c.detail)

    def test_csi_camera_among_soc_nodes_passes(self):
        for dev, name in PI4_SOC_NODES.items():
            self.node(dev, name)
        self.node("video0", "unicam-image")
        c = hw.check_camera(self.m.root)
        self.assertEqual(c.status, hw.PASS)
        self.assertIn("video0 (unicam-image)", c.detail)
        self.assertNotIn("bcm2835", c.detail)

    def test_usb_webcam_passes(self):
        self.node("video0", "HD Webcam C270")
        self.assertEqual(hw.check_camera(self.m.root).status, hw.PASS)

    def test_pi5_isp_is_not_a_camera(self):
        self.node("video20", "pispbe-input")
        self.node("video19", "rpi-hevc-dec")
        self.assertEqual(hw.check_camera(self.m.root).status, hw.WARN)

    def test_unreadable_name_is_unknown_not_camera(self):
        self.node("video0", None)
        c = hw.check_camera(self.m.root)
        self.assertEqual(c.status, hw.UNKNOWN)
        self.assertIn("อ่านชื่อ", c.detail)

    def test_no_video_nodes_is_unknown(self):
        self.assertEqual(hw.check_camera(self.m.root).status, hw.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
