"""รายการอุปกรณ์ที่ต่อกับเครื่อง (การ์ด 0051 ข้อ 4.4) · ไฟล์ระบบปลอม ไม่แตะเครื่องจริง."""

import os
import tempfile
import unittest
from pathlib import Path

from aipc.doctor import devices

# รูปแบบจาก wpctl status (PipeWire) · ตัวที่มี * คือตัวที่ใช้อยู่
WPCTL = """PipeWire 'pipewire-0' [1.2.7, aipc@ai-pc, cookie:1]
 └─ Clients:
        33. pipewire                            [1.2.7, aipc@ai-pc, pid:900]

Audio
 ├─ Devices:
 │      50. Built-in Audio                      [alsa]
 │      51. USB PnP Sound Device                [alsa]
 ├─ Sinks:
 │      56. Built-in Audio Digital Stereo (HDMI) [vol: 0.40]
 │  *   58. USB PnP Sound Device Analog Stereo  [vol: 1.00]
 ├─ Sources:
 │  *   59. USB PnP Sound Device Mono           [vol: 0.80]
 ├─ Filters:
 └─ Streams:

Video
 ├─ Devices:
 │      70. USB Camera                          [v4l2]
 ├─ Sinks:
 ├─ Sources:
 │  *   72. USB Camera (V4L2)

Settings
 └─ Default Configured Devices:
"""

BT = "Device 41:42:AA:BB:CC:DD Galaxy Buds2\nDevice 11:22:33:44:55:66 MX Keys\n"


class FakeRoot:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def put(self, rel, text):
        f = self.root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")

    def close(self):
        self._tmp.cleanup()


class DevicesTest(unittest.TestCase):
    def setUp(self):
        self.fs = FakeRoot()
        self.addCleanup(self.fs.close)
        put = self.fs.put
        put("sys/bus/usb/devices/usb1/bDeviceClass", "09")  # ฮับในบอร์ด
        put("sys/bus/usb/devices/usb1/product", "xHCI Host Controller")
        put("sys/bus/usb/devices/1-1/bDeviceClass", "00")
        put("sys/bus/usb/devices/1-1/product", "USB Optical Mouse")
        put("sys/bus/usb/devices/1-1/manufacturer", "Logitech")
        if os.name != "nt":  # วินโดวส์ตั้งชื่อโฟลเดอร์ที่มี ":" ไม่ได้
            put("sys/bus/usb/devices/1-1:1.0/product", "ไม่ใช่อุปกรณ์ (interface)")
        put("sys/bus/usb/devices/1-2/bDeviceClass", "00")
        put("sys/bus/usb/devices/1-2/product", "USB PnP Sound Device")
        put("sys/class/video4linux/video0/name", "USB Camera: USB Camera")
        put("sys/class/video4linux/video1/name", "USB Camera: USB Camera")
        put("sys/class/video4linux/video19/name", "pispbe-input")  # ของชิป Pi 5
        put("sys/class/drm/card1-HDMI-A-1/status", "connected")
        put("sys/class/drm/card1-HDMI-A-2/status", "disconnected")

    def run_cmd(self, args):
        return {"wpctl": WPCTL, "bluetoothctl": BT}.get(args[0])

    def test_scan_lists_what_is_plugged_in(self):
        got = devices.scan(self.fs.root, self.run_cmd)
        self.assertEqual(got["usb"], ["USB Optical Mouse (Logitech)", "USB PnP Sound Device"])
        self.assertEqual(got["camera"], ["USB Camera: USB Camera"])  # 2 โหนดชื่อเดียวกัน = 1 ตัว
        self.assertEqual(got["display"], ["HDMI-A-1"])
        self.assertEqual(got["audio_out"], ["USB PnP Sound Device Analog Stereo · ใช้อยู่",
                                            "Built-in Audio Digital Stereo (HDMI)"])  # fmt: skip
        self.assertEqual(got["audio_in"], ["USB PnP Sound Device Mono · ใช้อยู่"])  # ไม่ปนกล้อง
        self.assertEqual(got["bluetooth"], ["Galaxy Buds2", "MX Keys"])

    def test_cannot_check_is_not_the_same_as_none(self):
        empty = FakeRoot()
        self.addCleanup(empty.close)
        got = devices.scan(empty.root, lambda args: None)
        self.assertTrue(all(v is None for v in got.values()))
        lines = devices.summary(got)
        self.assertIn("Bluetooth: ตรวจไม่ได้", lines)
        got = devices.scan(self.fs.root, lambda args: "" if args[0] == "bluetoothctl" else None)
        self.assertIn("Bluetooth: ไม่มี", devices.summary(got))

    def test_summary_one_line_per_kind(self):
        lines = devices.summary(devices.scan(self.fs.root, self.run_cmd))
        self.assertEqual(len(lines), len(devices.KINDS))
        self.assertIn("ไมค์: USB PnP Sound Device Mono · ใช้อยู่", lines)


if __name__ == "__main__":
    unittest.main()
