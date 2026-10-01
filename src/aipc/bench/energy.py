"""พลังงานบนบอร์ด Pi 5 จากชิปจัดการไฟ (PMIC Renesas DA9091) · `vcgencmd pmic_read_adc`.

รูปแบบเอาต์พุต (ราง 12 ราง · กระแสลงท้าย _A · แรงดันลงท้าย _V · คู่กันตามชื่อราง):
    VDD_CORE_A current(7)=10.87674000A
    VDD_CORE_V volt(15)=0.72000000V
แหล่ง: Raspberry Pi Forums t=359249 · github.com/jfikar/RPi5-power
ข้อจำกัด: วัดเฉพาะรางบนบอร์ด ไม่รวมการสูญเสียของอะแดปเตอร์และอุปกรณ์ USB → รายงานเป็น "วัตต์บนบอร์ด" เท่านั้น
(jfikar เสนอสูตรแก้ W_จริง ≈ 1.1451·W + 0.5879 จากมิเตอร์ของเขาเครื่องเดียว · เราไม่ใช้จนกว่าจะเทียบมิเตอร์เอง)
"""

from __future__ import annotations

import re
import subprocess

LINE = re.compile(r"^\s*(\S+)_(A|V)\s+(?:current|volt)\(\d+\)=([0-9.]+)[AV]\s*$")


def parse(text: str) -> dict[str, tuple[float, float]]:
    """ชื่อราง → (แรงดัน V, กระแส A) · รางที่มีแค่ค่าใดค่าหนึ่งไม่นับ."""
    amps: dict[str, float] = {}
    volts: dict[str, float] = {}
    for line in text.splitlines():
        m = LINE.match(line)
        if m:
            (amps if m.group(2) == "A" else volts)[m.group(1)] = float(m.group(3))
    return {r: (volts[r], amps[r]) for r in amps if r in volts}


def board_watts(text: str) -> float:
    return round(sum(v * a for v, a in parse(text).values()), 4)


def read(runner=subprocess.run) -> float | None:
    """วัตต์บนบอร์ดตอนนี้ · ไม่ใช่ Pi 5 / ไม่มี vcgencmd = None (ไม่เดา)."""
    try:
        r = runner(["vcgencmd", "pmic_read_adc"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or not parse(r.stdout):
        return None
    return board_watts(r.stdout)
