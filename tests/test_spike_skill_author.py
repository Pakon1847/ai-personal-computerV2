"""ตัววัด 'ใครเขียนสกิลได้' (spikes.skill_author) · AI ปลอม ไม่ต่อเน็ต."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from aipc.skills import forge, manifest
from aipc.spikes import skill_author

STEPS_MD = """---
id: video-mode
name: โหมดดูวิดีโอ
description: เปิด YouTube และปรับเสียงสำหรับดูวิดีโอ
keywords: โหมดดูวิดีโอ
examples:
  - เข้าโหมดดูวิดีโอ
  - ขอโหมดดูวิดีโอ
  - โหมดดูวิดีโอหน่อย
permissions: run_actions
---
## ขั้นตอน
1. บอก: เตรียมดูวิดีโอ
2. เปิดเว็บ youtube
3. ปรับเสียง 70
"""
LLM_MD = """---
id: kid-words
name: อธิบายศัพท์ให้เด็ก
description: อธิบายคำศัพท์ภาษาอังกฤษให้เด็กประถมพร้อมตัวอย่าง
keywords: อธิบายคำศัพท์
examples:
  - อธิบายคำศัพท์ brave
  - อธิบายคำศัพท์ curious
  - อธิบายคำศัพท์ happy
worker: llm
needs: llm
---
## คำสั่งให้ AI
อธิบายคำศัพท์ภาษาอังกฤษให้เด็กประถมเข้าใจ ตอบภาษาไทย ยกตัวอย่างประโยค 1 ประโยค
"""
ITEM_STEPS = {
    "id": "s1",
    "kind": "steps",
    "request": "โหมดดูวิดีโอ",
    "actions": [
        {"action": "open_url", "params": {"site": "youtube"}},
        {"action": "set_volume", "params": {"percent": 70}},
    ],
    "should": ["เข้าโหมดดูวิดีโอ"],
    "should_not": ["วิดีโอกินเน็ตไหม"],
}
ITEM_LLM = {
    "id": "l1",
    "kind": "llm",
    "request": "อธิบายศัพท์ให้เด็ก",
    "should": ["อธิบายคำว่า brave ให้เด็ก"],
    "should_not": ["เด็กควรนอนกี่ชั่วโมง"],
}


class DatasetTest(unittest.TestCase):
    def test_dataset_is_well_formed(self):
        data = json.loads(skill_author.DATASET.read_text(encoding="utf-8"))
        items = data["items"]
        self.assertEqual(len(items), 10)
        self.assertEqual(len({i["id"] for i in items}), 10)
        for it in items:
            self.assertIn(it["kind"], ("steps", "llm"))
            self.assertEqual(len(it["should"]), 3, it["id"])
            self.assertEqual(len(it["should_not"]), 3, it["id"])
            if it["kind"] == "steps":
                self.assertTrue(it["actions"], it["id"])


class StructureTest(unittest.TestCase):
    def test_steps_must_match_actions_exactly_but_say_steps_are_fine(self):
        self.assertEqual(skill_author.structure(STEPS_MD, ITEM_STEPS), (True, ""))
        wrong = STEPS_MD.replace("ปรับเสียง 70", "ปรับเสียง 50")
        self.assertFalse(skill_author.structure(wrong, ITEM_STEPS)[0])
        extra = STEPS_MD.replace("3. ปรับเสียง 70", "3. ปรับเสียง 70\n4. เปิดเว็บ gmail")
        self.assertFalse(skill_author.structure(extra, ITEM_STEPS)[0], "ขั้นสั่งเครื่องเกิน = ผิด")

    def test_llm_skill_must_not_touch_the_machine(self):
        self.assertTrue(skill_author.structure(LLM_MD, ITEM_LLM)[0])
        self.assertFalse(skill_author.structure(STEPS_MD, ITEM_LLM)[0])

    def test_invalid_file_is_reported(self):
        ok, why = skill_author.structure("ไม่ใช่ไฟล์สกิล", ITEM_LLM)
        self.assertFalse(ok)
        self.assertIn("ไม่ผ่านตัวตรวจ", why)


def fake_server(contents):
    """llama-server ปลอม: ตอบข้อความใน contents ตามลำดับ · เก็บ body ที่ส่งมา."""
    sent = []

    def opener(req, timeout=None):
        sent.append(json.loads(req.data))
        body = {
            "choices": [{"message": {"content": contents.pop(0)}, "finish_reason": "stop"}],
            "timings": {"predicted_per_second": 4.5},
        }
        return contextlib.nullcontext(io.BytesIO(json.dumps(body).encode()))

    return opener, sent


class LocalRunnerTest(unittest.TestCase):
    def test_local_answer_goes_through_the_same_forge_checks(self):
        reply = json.dumps(
            {"skill_md": LLM_MD, "should_trigger": [], "should_not_trigger": [], "note": ""},
            ensure_ascii=False,
        )
        opener, sent = fake_server([reply])
        calls = []
        run = skill_author.local_runner("http://x", "fake", calls, opener=opener)
        p = forge.forge("อธิบายศัพท์ให้เด็ก", skills=manifest.load_builtin(), runner=run)
        self.assertEqual(p.skill_id, "kid-words")
        self.assertTrue(p.skill_md)
        self.assertEqual(sent[0]["response_format"]["type"], "json_schema", "บังคับรูป JSON")
        self.assertIn("## คำขอ", sent[0]["messages"][0]["content"], "แม่แบบคำขอเดียวกับ Claude")
        self.assertEqual(calls[0]["finish"], "stop")
        self.assertIn("kid-words", calls[0]["text"], "เก็บคำตอบดิบไว้ตรวจ")

    def test_broken_answer_gets_a_second_try_with_the_errors(self):
        bad = json.dumps(
            {"skill_md": "ผิดรูป", "should_trigger": [], "should_not_trigger": [], "note": ""}
        )
        good = json.dumps(
            {"skill_md": LLM_MD, "should_trigger": [], "should_not_trigger": [], "note": ""},
            ensure_ascii=False,
        )
        opener, sent = fake_server([bad, good])
        run = skill_author.local_runner("http://x", "fake", [], opener=opener)
        p = forge.forge("x", skills=manifest.load_builtin(), runner=run)
        self.assertEqual(p.attempts, 2)
        self.assertTrue(p.skill_md)
        self.assertIn("รอบก่อนไม่ผ่านตัวตรวจ", sent[1]["messages"][0]["content"])


class RouteTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        (self.dir / "l1.md").write_text(LLM_MD, encoding="utf-8")

    def test_new_skill_is_judged_by_the_app_picker(self):
        def ai(text, tools):
            self.assertIn("kid-words", [t["function"]["name"] for t in tools])
            return {"tool": "kid-words" if "brave" in text else "", "seconds": 0, "timings": {}}

        res = skill_author.route(self.dir, [ITEM_LLM], ai, manifest.load_builtin())
        self.assertEqual((res["should_hit"], res["should_total"]), (1, 1))
        self.assertEqual((res["should_not_false"], res["should_not_total"]), (0, 1))

    def test_missing_skill_misses_every_should_sentence(self):
        res = skill_author.route(
            self.dir, [ITEM_STEPS], lambda t, tools: {"tool": ""}, manifest.load_builtin()
        )
        self.assertEqual(res["should_hit"], 0)
        self.assertEqual(res["should_not_false"], 0)

    def test_verdict_counts_lost_regression_items(self):
        a = {"n": 10, "valid": 10, "structure": 9}
        r = {"should_hit": 24, "should_total": 30, "should_not_false": 3, "should_not_total": 30}
        base = {
            "rows": [
                {"text": "x", "ok": True},
                {"text": "y", "ok": True},
                {"text": "z", "ok": False},
            ]
        }
        reg = {
            "rows": [
                {"text": "x", "ok": False},
                {"text": "y", "ok": True},
                {"text": "z", "ok": True},
            ]
        }
        crit = json.loads(skill_author.DATASET.read_text(encoding="utf-8"))["criteria"]
        v = skill_author.verdict(a, r, reg, base, crit)
        self.assertEqual(v["regression_lost"], ["x"])
        self.assertTrue(v["pass"])
        r["should_not_false"] = 4
        self.assertFalse(skill_author.verdict(a, r, reg, base, crit)["pass"])


if __name__ == "__main__":
    unittest.main()
