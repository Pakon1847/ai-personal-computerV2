"""สถานะเครือข่ายบนแถบสถานะ (BRIEF 5.7 ข้อ 3) · อ่านตาราง route อย่างเดียว ไม่ส่งข้อมูลออก."""

import tempfile
import unittest
from pathlib import Path

from aipc.skills import machine

HEAD = "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"


def route(body: str):
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "proc/net").mkdir(parents=True)
        (Path(tmp) / "proc/net/route").write_text(HEAD + body, encoding="utf-8")
        return machine.has_default_route(Path(tmp))


class DefaultRouteTest(unittest.TestCase):
    def test_default_route_up(self):
        self.assertTrue(route("wlan0\t00000000\t0101A8C0\t0003\t0\t0\t600\t00000000\t0\t0\t0\n"))

    def test_only_local_network(self):
        self.assertFalse(route("wlan0\t0001A8C0\t00000000\t0001\t0\t0\t600\t00FFFFFF\t0\t0\t0\n"))

    def test_default_route_but_interface_down(self):
        self.assertFalse(route("eth0\t00000000\t0101A8C0\t0002\t0\t0\t100\t00000000\t0\t0\t0\n"))

    def test_no_routes(self):
        self.assertFalse(route(""))

    def test_unreadable_is_unknown(self):
        self.assertIsNone(machine.has_default_route(Path("/nonexistent-root")))


if __name__ == "__main__":
    unittest.main()
