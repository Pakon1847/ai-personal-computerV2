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
import threading
import time

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


def summarize(samples: list[tuple[float, float]]) -> dict | None:
    """[(เวลา วิ, วัตต์)] → พลังงานแบบสี่เหลี่ยมคางหมู · ค่าน้อยกว่า 2 ครั้ง = None (ไม่แสดง ไม่เดา)."""
    if len(samples) < 2:
        return None
    joules = sum(
        (b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(samples, samples[1:], strict=False)
    )
    seconds = samples[-1][0] - samples[0][0]
    if seconds <= 0:
        return None
    return {"joules": round(joules, 1), "seconds": round(seconds, 2),
            "mean_w": round(joules / seconds, 2), "samples": len(samples)}  # fmt: skip


class Meter:
    """มิเตอร์พลังงานต่อคำตอบ (Pakon เลือกข้อ ค 2026-10-07 · docs/benchmarks/2026-10-07-energy-meter-pi5).

    อ่านวัตต์บนบอร์ดทุก period วิในเธรดแยก ตั้งแต่ start() ถึง stop() (อ่านซ้ำอีกครั้งตอนจบ) ·
    ใช้ vcgencmd 1 ครั้ง/วิ แทน 4 ครั้ง/วิของตัววัดเดิม เพื่อไม่แย่ง CPU กับ AI ในเครื่อง
    """

    def __init__(self, period: float = 1.0, reader=None, clock=time.monotonic):
        self.period = period
        self._read = reader or read
        self._clock = clock
        self._samples: list[tuple[float, float]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _sample(self) -> None:
        w = self._read()
        if w is not None:
            self._samples.append((self._clock(), w))

    def _run(self) -> None:
        while True:
            self._sample()
            if self._stop.wait(self.period):
                self._sample()  # ค่าตอนจบ
                return

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> dict | None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        return summarize(list(self._samples))


def meter_factory(runner=subprocess.run):
    """อ่าน PMIC ได้ (Pi 5) = สร้างมิเตอร์ใหม่ทุกคำตอบ · อ่านไม่ได้ (วินโดวส์ · Pi รุ่นอื่น) = ไม่มีมิเตอร์."""
    if read(runner) is None:
        return lambda: None
    return lambda: Meter()
