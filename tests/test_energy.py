"""วัตต์บนบอร์ด Pi 5 จาก `vcgencmd pmic_read_adc` (aipc.bench.energy) · ไม่ต้องมี Pi."""

import subprocess
import unittest

from aipc.bench import energy

# บรรทัดกระแสจาก README ของ jfikar/RPi5-power · บรรทัดแรงดันตามรูปแบบเดียวกัน (ค่าสมมติสำหรับเทสต์)
SAMPLE = """\
 3V3_SYS_A current(1)=0.06245952A
 VDD_CORE_A current(7)=10.87674000A
 HDMI_A current(22)=0.01367520A
 3V3_SYS_V volt(9)=3.30000000V
 VDD_CORE_V volt(15)=0.72000000V
 HDMI_V volt(23)=5.00000000V
 EXT5V_V volt(24)=5.10000000V
 BATT_V volt(25)=0.00000000V
"""


class EnergyTest(unittest.TestCase):
    def test_pairs_rails_by_name(self):
        rails = energy.parse(SAMPLE)
        self.assertEqual(set(rails), {"3V3_SYS", "VDD_CORE", "HDMI"})  # EXT5V มีแต่แรงดัน = ไม่นับ
        self.assertEqual(rails["VDD_CORE"], (0.72, 10.87674))

    def test_board_watts(self):
        want = 3.3 * 0.06245952 + 0.72 * 10.87674 + 5.0 * 0.0136752
        self.assertAlmostEqual(energy.board_watts(SAMPLE), round(want, 4))

    def test_read_without_vcgencmd_is_none(self):
        def missing(*a, **k):
            raise FileNotFoundError

        self.assertIsNone(energy.read(missing))
        bad = subprocess.CompletedProcess([], 1, "", "error")
        self.assertIsNone(energy.read(lambda *a, **k: bad))


if __name__ == "__main__":
    unittest.main()
