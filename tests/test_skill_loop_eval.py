"""ตัววัดวงจรเรียนรู้สกิล (การ์ด 0083) · ไม่ต่อ AI/Claude จริง."""

import unittest
from pathlib import Path
from types import SimpleNamespace

from aipc.skills.forge import Proposal
from aipc.spikes import skill_loop_eval as ev
from aipc.spikes.app_driver import Turn

DATA = Path(__file__).resolve().parent / "data"


class ParseTest(unittest.TestCase):
    def test_parses_blocks_and_skips_comments(self):
        text = ("# คำอธิบาย\n\nข้อ 1\nคำสั่ง: ทำ ก\nผลที่ถูก: ได้ ก\n\n"
                "# อีกบรรทัด\nข้อ 2\nคำสั่ง: ทำ ข\nผลที่ถูก: ได้ ข\n")  # fmt: skip
        self.assertEqual(ev.parse_items(text), [
            {"id": "1", "text": "ทำ ก", "expect": "ได้ ก"},
            {"id": "2", "text": "ทำ ข", "expect": "ได้ ข"},
        ])  # fmt: skip

    def test_empty_command_names_the_item(self):
        text = "ข้อ 1\nคำสั่ง: ทำ ก\nผลที่ถูก: ได้ ก\n\nข้อ 2\nคำสั่ง:\nผลที่ถูก: ได้ ข\n"
        with self.assertRaises(ValueError) as e:
            ev.parse_items(text)
        self.assertIn("ข้อ 2", str(e.exception))

    def test_partly_filled_file_names_the_empty_item(self):
        text = "ข้อ 1\nคำสั่ง: ทำ ก\nผลที่ถูก: ได้ ก\n\nข้อ 2\nคำสั่ง:\nผลที่ถูก:\n"
        with self.assertRaises(ValueError) as e:
            ev.parse_items(text)
        self.assertIn("ข้อ 2", str(e.exception))

    def test_unfilled_template_refuses(self):
        # รูปเดียวกับ skill_loop_test1.txt ตอนยังว่าง · ไม่เปิดไฟล์จริง (ชุดทดสอบของ Pakon · H9)
        text = "# วิธีกรอก\n\n" + "".join(f"ข้อ {n}\nคำสั่ง:\nผลที่ถูก:\n\n" for n in range(1, 21))
        with self.assertRaises(ValueError) as e:
            ev.parse_items(text)
        self.assertIn("ยังไม่ได้กรอก", str(e.exception))

    def test_dev_set_has_ten_items(self):
        items = ev.parse_items((DATA / "skill_loop_dev.txt").read_text(encoding="utf-8"))
        self.assertEqual(len(items), 10)
        self.assertTrue(all(i["text"] and i["expect"] for i in items))


class FakeStore:
    """แทน UserSkills: load_all() → สกิลที่มี (id, name) · current_md(id)."""

    def __init__(self):
        self.skills: dict[str, str] = {}

    def load_all(self):
        return [SimpleNamespace(id=i, name=n) for i, n in self.skills.items()]

    def current_md(self, skill_id):
        return f"---\nid: {skill_id}\n---"


class FakeLedger:
    def __init__(self):
        self.items: list[dict] = []

    def entries(self):
        return list(reversed(self.items))


class FakeDriver:
    """แทน AppDriver: say(text) ทำตามบททีละครั้ง (route · ติดตั้งสกิล · ledger เพิ่ม · plans · cards)."""

    def __init__(self, store, ledger, script):
        self.store, self.ledger, self.script = store, ledger, list(script)

    def say(self, text):
        s = self.script.pop(0)
        if s.get("install"):
            self.store.skills[s["install"]] = s.get("name", s["install"])
        for _ in range(s.get("ledger", 0)):
            self.ledger.items.append({"kind": "skill", "ok": True})
        return Turn(route=s["route"], text=s.get("text", ""), plans=s.get("plans", []),
                    cards=s.get("cards", []))  # fmt: skip


ITEM = {"id": "1", "text": "โหมดดูหนัง", "expect": "เปิด Netflix"}


class RunItemTest(unittest.TestCase):
    def setUp(self):
        self.store, self.ledger, self.records = FakeStore(), FakeLedger(), []

    def run_with(self, script):
        drv = FakeDriver(self.store, self.ledger, script)
        return ev.run_item(drv, self.store, self.ledger, self.records, ITEM)

    def test_full_loop_counts_ok(self):
        row = self.run_with([
            {"route": "create", "install": "s1", "ledger": 1, "cards": [{"kind": "forging"}]},
            {"route": "skill:s1", "ledger": 0},
        ])  # fmt: skip
        self.assertTrue(row["asked_create"])
        self.assertTrue(row["installed"])
        self.assertEqual(row["skill_id"], "s1")
        self.assertTrue(row["again_new_skill"])
        self.assertEqual(row["again_ledger_added"], 0)

    def test_rule_route_by_skill_name_counts_as_new_skill(self):
        row = self.run_with([
            {"route": "create", "install": "s1", "name": "โหมดดูหนัง", "ledger": 1},
            {"route": "rule:steps:โหมดดูหนัง"},
        ])  # fmt: skip
        self.assertTrue(row["again_new_skill"])

    def test_second_time_calling_claude_is_counted(self):
        row = self.run_with([
            {"route": "create", "install": "s1", "ledger": 1},
            {"route": "cloud", "ledger": 1},
        ])  # fmt: skip
        self.assertEqual(row["again_ledger_added"], 1)
        self.assertFalse(row["again_new_skill"])

    def test_cloud_answer_is_not_create(self):
        row = self.run_with([{"route": "cloud", "ledger": 1}])
        self.assertFalse(row["asked_create"])
        self.assertFalse(row["installed"])
        self.assertNotIn("again_route", row)

    def test_failed_forge_keeps_md_and_trial(self):
        def forge(request, **kw):
            return Proposal(False, request, skill_md="---\nid: x\n---", trial={"hit": False},
                            errors=["ทดลองเส้นทางไม่ผ่าน"])  # fmt: skip

        wrapped, records = ev.recording_forge(forge)
        wrapped("โหมดดูหนัง")
        self.assertEqual(records[0]["skill_md"], "---\nid: x\n---")
        self.assertEqual(records[0]["trial"], {"hit": False})
        self.records = records

        class ForgeDriver(FakeDriver):
            def say(inner, text):
                return Turn(route="create", cards=[{"kind": "forging"}])

        row = ev.run_item(ForgeDriver(self.store, self.ledger, []), self.store, self.ledger,
                          self.records, ITEM)  # fmt: skip
        self.assertFalse(row["installed"])
        self.assertEqual(row["forge"], [])  # บันทึกก่อนข้อนี้ไม่นับเป็นของข้อนี้

    def test_unconfirmed_machine_action_is_counted(self):
        plan = [["volume", {"level": 60}]]
        row = self.run_with([
            {"route": "create", "install": "s1", "ledger": 1, "plans": plan},
            {"route": "skill:s1", "plans": plan},
        ])  # fmt: skip
        self.assertEqual(row["unconfirmed"], 2)
        self.store.skills.clear()
        confirmed = [{"kind": "steps", "confirmToken": "c1"}]
        row = self.run_with([
            {"route": "create", "install": "s1", "ledger": 1, "plans": plan, "cards": confirmed},
            {"route": "skill:s1", "plans": plan, "cards": confirmed},
        ])  # fmt: skip
        self.assertEqual(row["unconfirmed"], 0)


def row(i, asked=True, installed=True, new_skill=True, ledger=0, unconfirmed=0):
    r = {"id": str(i), "text": f"คำสั่ง {i}", "expect": f"ผล {i}", "asked_create": asked,
         "installed": installed, "unconfirmed": unconfirmed}  # fmt: skip
    if installed:
        r.update(again_route="skill:s", again_plans=[], again_text="ทำแล้ว",
                 again_new_skill=new_skill, again_ledger_added=ledger)  # fmt: skip
    return r


class SummaryTest(unittest.TestCase):
    ROWS = [row(1), row(2), row(3, new_skill=False), row(4, ledger=1),
            row(5, asked=False, installed=False)]  # fmt: skip

    def test_summary_l1_l2_l4(self):
        s = ev.summarize(self.ROWS, {"1": True, "2": False, "3": True, "4": True})
        self.assertEqual(s["L1"], [4, 5])
        self.assertEqual(s["steps"], {"asked_create": 4, "installed": 4})
        self.assertEqual(s["L2"], [1, 4])  # ข้อ 1 เท่านั้น: 2 Pakon ว่าไม่ถูก · 3 ไปสกิลอื่น · 4 เรียก Claude
        self.assertEqual(s["L4"], 0)
        self.assertEqual(s["pass"], {"L1": True, "L2": False, "L4": True})

    def test_l2_waits_for_pakon(self):
        s = ev.summarize(self.ROWS, None)
        self.assertIsNone(s["L2"])
        self.assertEqual(s["L2_route_ledger"], [2, 4])
        self.assertIsNone(s["pass"]["L2"])

    def test_sheet_round_trip(self):
        sheet = ev.review_sheet(self.ROWS)
        self.assertIn("คำสั่ง 1", sheet)
        self.assertNotIn("คำสั่ง 5", sheet)  # ติดตั้งไม่ได้ = ไม่มีครั้งที่สองให้ตรวจ
        filled = sheet.replace("- ตัดสิน: \n", "- ตัดสิน: ถูก\n", 2).replace(
            "- ตัดสิน: \n", "- ตัดสิน: ไม่ถูก\n", 1
        )
        self.assertEqual(ev.read_sheet(filled), {"1": True, "2": True, "3": False})


class HRouteTest(unittest.TestCase):
    ITEMS = [{"id": "h1", "text": "เปิดยูทูบ", "expect": [{"kind": "site"}]},
             {"id": "h2", "text": "สวัสดี", "expect": []}]  # fmt: skip

    def test_h_route_change_is_counted(self):
        before = {"h1": "browser", "h2": "unknown"}
        after = {"h1": "skill", "h2": "skill"}
        # h2 ไม่ใช่คำสั่ง → ไม่นับใน L3
        self.assertEqual(ev.l3_changes(before, after, self.ITEMS), ["h1"])

    def test_routes_use_skill_matchers(self):
        class Skills:
            def voiceSkill(self, text):  # noqa: N802
                return "s1" if text == "สวัสดี" else ""

            def voiceIntent(self, text):  # noqa: N802
                return ""

        got = ev.h_routes(Skills(), self.ITEMS)
        self.assertEqual(got["h2"], "skill")
        self.assertNotEqual(got["h1"], "skill")


class FakeClaudeTest(unittest.TestCase):
    def test_fake_claude_skill_passes_the_gate(self):
        from aipc.skills import manifest

        make = ev.fake_forge()
        p = make("โหมดดูหนังให้หน่อย", skills=manifest.load_builtin())
        self.assertTrue(p.skill_md, p.errors)
        self.assertFalse(p.errors, p.errors)


class CliTest(unittest.TestCase):
    def test_empty_test_file_stops_cli(self):
        import io
        import tempfile
        from contextlib import redirect_stderr

        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "empty.txt"
            f.write_text("ข้อ 1\nคำสั่ง:\nผลที่ถูก:\n", encoding="utf-8")
            err = io.StringIO()
            with redirect_stderr(err):
                rc = ev.main(["--server", "http://127.0.0.1:9", "--data", str(f),
                              "--out", str(Path(d) / "out.json")])  # fmt: skip
        self.assertEqual(rc, 2)
        self.assertIn("ยังไม่ได้กรอก", err.getvalue())


if __name__ == "__main__":
    unittest.main()
