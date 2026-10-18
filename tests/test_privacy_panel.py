"""แผงความเป็นส่วนตัวแบบสด + สวิตช์อากาศ (Pakon เลือกข้อ ข 2026-10-07).

เกณฑ์: docs/benchmarks/2026-10-07-privacy-panel (ข้อ 2–5 วัดด้วยเทสต์นี้ · ข้อ 1 วัดบน Pi)
"""

import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from aipc.cloud.ledger import Ledger
from aipc.skills.weather import Weather
from aipc.ui import privacy, settings
from tests.test_weather import FC, GEO

try:
    from aipc.ui.backend import PrivacyStatus, SkillsController
except ImportError:  # ไม่มี PySide6
    PrivacyStatus = SkillsController = None


class SandboxStateTest(unittest.TestCase):
    def proc(self, status: str | None) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        if status is not None:
            (root / "123").mkdir()
            (root / "123" / "status").write_text(status, encoding="utf-8")
        return root

    def links(self, llm: str, me: str):
        return lambda p: llm if "123" in p else me

    def test_locked_needs_seccomp_and_own_namespace(self):
        root = self.proc("Name:\tllama-server\nSeccomp:\t2\nSeccomp_filters:\t1\n")
        state = privacy.sandbox_state(123, root, self.links("net:[1]", "net:[2]"))
        self.assertEqual(state, "locked")

    def test_open_when_any_layer_missing(self):
        root = self.proc("Seccomp:\t0\n")
        self.assertEqual(privacy.sandbox_state(123, root, self.links("net:[1]", "net:[2]")), "open")
        root = self.proc("Seccomp:\t2\n")
        self.assertEqual(privacy.sandbox_state(123, root, self.links("net:[1]", "net:[1]")), "open")

    def test_unknown_never_guesses(self):
        self.assertEqual(privacy.sandbox_state(None), "unknown")
        root = self.proc(None)  # โปรเซสหายไปแล้ว
        self.assertEqual(privacy.sandbox_state(123, root, self.links("a", "b")), "unknown")

    def test_llm_pid_from_systemctl(self):
        def run(out, rc=0):
            return lambda *a, **k: SimpleNamespace(stdout=out, returncode=rc)

        self.assertEqual(privacy.llm_pid(run("229779\n")), 229779)
        self.assertIsNone(privacy.llm_pid(run("0\n")))  # service ไม่ได้รัน
        self.assertIsNone(privacy.llm_pid(run("", 1)))

        def missing(*a, **k):
            raise OSError("no systemctl")  # วินโดวส์

        self.assertIsNone(privacy.llm_pid(missing))


class CountsTest(unittest.TestCase):
    def test_counts_only_today(self):
        entries = [
            {"time": "2026-10-07T09:00:00", "kind": "ask"},
            {"time": "2026-10-07T09:05:00", "kind": "weather"},
            {"time": "2026-10-06T23:59:00", "kind": "ask"},
            {"time": "เสีย", "kind": "ask"},
        ]
        self.assertEqual(privacy.today_counts(entries, date(2026, 10, 7)), {"ask": 1, "weather": 1})


@unittest.skipIf(PrivacyStatus is None, "ไม่มี PySide6")
class PanelTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.t = 100.0
        self.ledger = Ledger(
            Path(tmp.name) / "outbound.json", now=lambda: datetime(2026, 10, 7, 9, 0)
        )
        self.claude, self.weather, self.llm = True, True, "locked"

    def panel(self) -> "PrivacyStatus":
        p = PrivacyStatus(
            ledger=self.ledger,
            claude_on=lambda: self.claude,
            weather_on=lambda: self.weather,
            active=False,
            clock=lambda: self.t,
            today=lambda: date(2026, 10, 7),
            llm_state=lambda: self.llm,
        )
        p.refreshLlm()
        p.refresh()
        return p

    def test_every_kind_counts_and_flashes_within_3_seconds(self):
        """เกณฑ์ข้อ 2: ถาม Claude · สร้างสกิล · อากาศ → ตัวนับเพิ่มและเปลี่ยนสีทันทีที่อ่านรอบถัดไป (ทุก 2 วิ)."""
        p = self.panel()
        self.assertEqual((p.sentToday, p.flash, p.kind), (0, False, "ok"))  # เปิดแอปไม่เปลี่ยนสี
        for n, kind in enumerate(("ask", "skill", "weather"), start=1):
            self.ledger.record(kind, f"ข้อความที่ {n} " + "x" * n)
            self.t += 2.0
            p.refresh()
            self.assertEqual(p.sentToday, n)
            self.assertTrue(p.flash)
            self.assertEqual(p.kind, "accent")
            self.t += 3.1
            p.refresh()
            self.assertFalse(p.flash)
        self.assertEqual(p.text, "AI ในเครื่อง: ต่อเน็ตไม่ได้ · ส่งออกวันนี้ 3 ครั้ง")

    def test_clearing_ledger_is_not_an_outbound_event(self):
        self.ledger.record("ask", "ข่าววันนี้")
        p = self.panel()
        self.ledger.clear()
        self.t += 2
        p.refresh()
        self.assertFalse(p.flash)
        self.assertEqual(p.sentToday, 0)

    def test_all_off_badge(self):
        """เกณฑ์ข้อ 4."""
        self.claude = self.weather = False
        p = self.panel()
        self.assertTrue(p.allOff)
        # ค้นเว็บด้วยเสียงยังส่งได้เมื่อสั่ง → ห้ามอ้างว่า "ปิดทั้งหมด" (ตรวจทั้งระบบ 2.6)
        self.assertEqual(p.text, "AI ในเครื่อง: ต่อเน็ตไม่ได้ · Claude/อากาศ: ปิด · ส่งออกวันนี้ 0 ครั้ง")
        self.ledger.record("web", "ค้นเว็บ: ราคาทอง")
        p.refresh()
        self.assertIn("ส่งออกวันนี้ 1 ครั้ง", p.text)
        self.weather = True
        p.refresh()
        self.assertFalse(p.allOff)

    def test_llm_states(self):
        self.llm = "open"
        p = self.panel()
        self.assertEqual((p.kind, p.text), ("warn", "AI ในเครื่อง: ไม่ได้ล็อกเน็ต · ส่งออกวันนี้ 0 ครั้ง"))
        self.llm = "unknown"  # วินโดวส์ / อ่านไม่ได้ → ไม่พูดถึง AI ในเครื่อง (ไม่เดา)
        p.refreshLlm()
        self.assertEqual((p.kind, p.text), ("neutral", "ส่งออกวันนี้ 0 ครั้ง"))

    def test_login_screen_has_no_panel(self):
        """เกณฑ์ข้อ 5: หน้า Login ไม่มีเจ้าของข้อมูล."""
        p = PrivacyStatus(active=False)
        self.assertFalse(p.visible)


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class WeatherSwitchTest(unittest.TestCase):
    """เกณฑ์ข้อ 3: ปิดสวิตช์อากาศ = เรียก Open-Meteo 0 ครั้ง และไม่มีรายการในบันทึกส่งออก."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.calls, self.on = [], False
        self.ledger = Ledger(Path(tmp.name) / "outbound.json")

        def get(url, params, timeout=10):
            self.calls.append(url)
            return GEO if "geocoding" in url else FC

        weather = Weather(get=get, record=lambda sent: self.ledger.record("weather", sent))
        self.s = SkillsController(reminders_path=Path(tmp.name) / "r.json", run_timer=False,
                                  weather=weather, weather_on=lambda: self.on)  # fmt: skip

    def why(self, card):
        return {r["k"]: r["v"] for r in card.get("why", [])}

    def test_off_sends_nothing(self):
        for q in ("พรุ่งนี้เชียงใหม่ฝนตกไหม", "อากาศวันนี้เป็นยังไง"):
            card = self.s.handle(q)
            self.assertEqual(card["kind"], "weather-off")
            self.assertIn("ปิด", card["title"])
            self.assertEqual(self.why(card)["ข้อมูลออกนอกเครื่อง"], "ไม่มี · ปิดสวิตช์อากาศอยู่")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.ledger.entries(), [])

    def test_switched_off_while_waiting_for_city(self):
        self.on = True
        self.assertIn("เมืองไหน", self.s.handle("อากาศวันนี้เป็นยังไง")["title"])
        self.on = False
        self.assertEqual(self.s.handle("เชียงใหม่")["kind"], "weather-off")
        self.assertEqual(self.calls, [])

    def test_on_still_works(self):
        self.on = True
        self.assertEqual(self.s.handle("พรุ่งนี้เชียงใหม่ฝนตกไหม")["kind"], "weather")
        self.assertTrue(self.calls)
        self.assertEqual({e["kind"] for e in self.ledger.entries()}, {"weather"})


class SettingTest(unittest.TestCase):
    def test_default_on_and_saved(self):
        self.assertTrue(settings.UiPrefs().use_weather)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ui.json"
            path.write_text(json.dumps({"use_weather": False}), encoding="utf-8")
            self.assertFalse(settings.load(path).use_weather)
            path.write_text(json.dumps({"use_weather": "แปลก"}), encoding="utf-8")
            self.assertTrue(settings.load(path).use_weather)  # ค่าแปลก = ค่าเริ่มต้น (เปิด)


if __name__ == "__main__":
    unittest.main()
