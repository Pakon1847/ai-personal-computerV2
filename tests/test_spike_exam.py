"""ตัววัดชุดสอบจบ (spikes.exam) + system prompt ใหม่ + ask-cloud · AI และ Claude ปลอม."""

import json
import unittest
from datetime import date, datetime

from aipc.cloud import ask
from aipc.skills import catalog, manifest
from aipc.spikes import exam

DATA = json.loads(exam.DATASET.read_text(encoding="utf-8"))
ITEMS = {i["id"]: i for i in DATA["items"]}
PH = exam.placeholders(datetime(2026, 9, 30, 11, 0))
SKILLS = manifest.load_builtin()


def local_says(text="", tool=""):
    return lambda system, q, tools: {"text": text, "tool": tool, "ttft": 1.0, "seconds": 2.0}


class DatasetTest(unittest.TestCase):
    def test_100_items_8_groups_unique_ids(self):
        self.assertEqual(len(DATA["items"]), 100)
        self.assertEqual(len(ITEMS), 100)
        self.assertEqual(set(DATA["categories"]), {i["cat"] for i in DATA["items"]})

    def test_placeholders_from_the_clock(self):
        self.assertEqual(PH["weekday"], "พุธ")
        self.assertEqual(PH["tomorrow_weekday"], "พฤหัสบดี")
        self.assertEqual(PH["be_year"], "2569")
        self.assertEqual(PH["next_month"], "ตุลาคม")
        self.assertEqual(PH["days_to_newyear"], "93")


class PromptTest(unittest.TestCase):
    def test_prompt_has_date_rules_and_about(self):
        p = catalog.system_prompt(date(2026, 9, 30), cloud=True, model="Typhoon2.5 4B")
        for part in ("วันพุธที่ 30 กันยายน พ.ศ. 2569", "ข้อมูลสด", "ห้ามเดาตัวเลขของเครื่อง", "PIN",
                     catalog.ASK_CLOUD, "Typhoon2.5 4B"):  # fmt: skip
            self.assertIn(part, p)
        self.assertNotIn(catalog.ASK_CLOUD, catalog.system_prompt(date(2026, 9, 30)))

    def test_ask_cloud_tool_only_when_hybrid_and_first(self):
        names = [t["function"]["name"] for t in catalog.tools(SKILLS, {"llm"}, cloud=True)]
        self.assertEqual(names[0], catalog.ASK_CLOUD)
        plain = [t["function"]["name"] for t in catalog.tools(SKILLS, {"llm"})]
        self.assertNotIn(catalog.ASK_CLOUD, plain)


class JudgeTest(unittest.TestCase):
    def run1(self, qid, local, cloud=None):
        return exam.run_item(ITEMS[qid], SKILLS, "sys", [], local, cloud, PH)

    def test_command_goes_by_rule(self):
        r = self.run1("D01", local_says("x"))
        self.assertEqual((r["by"], r["route"], r["auto"]), ("rule", "system-command", "ok"))

    def test_skill_route_and_wrong_route(self):
        self.assertEqual(self.run1("D06", local_says(tool="machine-status"))["auto"], "ok")
        self.assertEqual(self.run1("D06", local_says("เครื่องปกติดี"))["auto"], "wrong-route")
        self.assertEqual(self.run1("A01", local_says(tool="translate"))["auto"], "wrong-route")

    def test_answer_keywords_and_date_placeholders(self):
        self.assertEqual(self.run1("A05", local_says("น้ำคือ H2O"))["auto"], "ok")
        self.assertEqual(self.run1("A05", local_says("ไม่แน่ใจ"))["auto"], "check")
        self.assertEqual(self.run1("C02", local_says("วันนี้วันพุธ"))["auto"], "ok")
        self.assertEqual(self.run1("C02", local_says("วันนี้วันศุกร์"))["auto"], "check")

    def test_live_data_must_be_honest_not_made_up(self):
        honest = self.run1("B01", local_says("ขออภัย ผมไม่มีข้อมูลสดเรื่องอากาศ"))
        self.assertEqual((honest["auto"], honest["fabricated"]), ("ok", False))
        made_up = self.run1("B01", local_says("วันนี้อากาศดี 32 องศา"))
        self.assertEqual((made_up["auto"], made_up["fabricated"]), ("fabricated", True))

    def test_hybrid_sends_to_claude_and_skips_made_up_check(self):
        def cloud(q):
            return ask.CloudReply(True, "กรุงเทพ 25–35 องศา ฝน 30%", seconds=15.0)

        r = self.run1("B01", local_says(tool=catalog.ASK_CLOUD), cloud)
        self.assertEqual((r["by"], r["auto"], r["fabricated"]), ("cloud", "cloud-answered", False))
        self.assertEqual(r["seconds"], 17.0)

        def offline(q):
            return ask.CloudReply(False, error="ไม่มีเน็ต")

        self.assertEqual(self.run1("B01", local_says(tool=catalog.ASK_CLOUD), offline)["auto"],
                         "cloud-failed")  # fmt: skip

    def test_summary_checks(self):
        rows = [
            self.run1("B01", local_says("ไม่มีข้อมูลสด")),
            self.run1("D06", local_says(tool="machine-status")),
        ]
        s = exam.summarize(rows, DATA["criteria"])
        self.assertEqual((s["honest"], s["route"], s["fabricated"]), ((1, 1), (1, 1), 0))
        self.assertTrue(all(s["checks"].values()))


class CloudTest(unittest.TestCase):
    def test_only_websearch_and_question_with_short_context(self):
        seen = {}

        def runner(args, prompt, cwd, timeout):
            seen.update(args=args, prompt=prompt)
            reply = {"result": "ตอบแล้ว", "is_error": False, "total_cost_usd": 0.05}
            return 0, json.dumps(reply), ""

        history = [{"role": "user", "content": f"ข้อความ {i}"} for i in range(10)]
        r = ask.ask("วันนี้อากาศเป็นไง", history, claude="claude", runner=runner,
                    today=date(2026, 9, 30))  # fmt: skip
        self.assertTrue(r.ok)
        args = seen["args"]
        self.assertEqual(args[args.index("--tools") + 1], "WebSearch")
        self.assertEqual(args[args.index("--allowedTools") + 1], "WebSearch")
        self.assertIn("--no-session-persistence", args)
        self.assertNotIn("ข้อความ 5", seen["prompt"], "ส่งบริบทแค่ 4 ข้อความล่าสุด")
        self.assertIn("ข้อความ 9", seen["prompt"])

    def test_offline_is_reported(self):
        r = ask.ask("x", claude="claude", runner=lambda *a: (1, "", "network error"))
        self.assertFalse(r.ok)
        self.assertIn("ไม่มีอินเทอร์เน็ต", r.error)


if __name__ == "__main__":
    unittest.main()
