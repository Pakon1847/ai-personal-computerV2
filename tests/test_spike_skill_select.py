"""ตัววัดการเลือกสกิล (spikes.skill_select) · AI ปลอม ไม่ต่อเน็ต."""

import contextlib
import hashlib
import io
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aipc.skills import manifest
from aipc.spikes import skill_select

REPO = Path(__file__).resolve().parents[1]
TEMPLATES = REPO / "scripts" / "pi" / "chat-templates"


def fake_urlopen(props):
    def opener(url, timeout=None):
        return contextlib.nullcontext(io.BytesIO(json.dumps(props).encode()))

    return opener


class ChatTemplateFilesTest(unittest.TestCase):
    """template ต้นฉบับที่ใช้แทนตัวใน GGUF (scripts/pi/chat-templates) ต้องรับเครื่องมือ และตรงกับที่มาที่จดไว้."""

    def test_each_template_supports_tools_and_matches_recorded_sha256(self):
        readme = (TEMPLATES / "README.md").read_text(encoding="utf-8")
        files = sorted(TEMPLATES.glob("*.jinja"))
        self.assertTrue(files)
        for f in files:
            text = f.read_text(encoding="utf-8")
            self.assertIn("tools", text, f.name)
            self.assertIn("<tool_call>", text, f.name)
            row = next(line for line in readme.splitlines() if f"`{f.name}`" in line)
            digest = re.findall(r"`([0-9a-f]{64})`", row)
            self.assertEqual(digest, [hashlib.sha256(f.read_bytes()).hexdigest()])

    def test_scripts_pass_template_to_llama_server(self):
        start = (REPO / "scripts" / "pi" / "session" / "aipc-llm-start").read_text(encoding="utf-8")
        self.assertIn('--chat-template-file "$TEMPLATE"', start)
        self.assertEqual(start.count('-fa "${FLASH_ATTN:-off}"'), 2, "flash attention ช้าบน Pi 5")
        self.assertEqual(start.count('-cram "${CACHE_RAM:-512}"'), 2, "แคชเริ่มต้น 8 GB = OOM")
        measure = (REPO / "scripts" / "pi" / "measure-llm.sh").read_text(encoding="utf-8")
        self.assertIn('--chat-template-file "$TPL"', measure)
        self.assertEqual(measure.count("-fa off --no-webui"), 2, "วัดด้วยค่าเดียวกับแอป")
        install = (REPO / "scripts" / "pi" / "install-llm.sh").read_text(encoding="utf-8")
        self.assertIn("chat-templates/${NAME%.gguf}.jinja", install)

    def test_shell_syntax(self):
        sh = next((p for p in ("/bin/sh", "/usr/bin/sh") if Path(p).exists()), None)
        if sh is None:
            self.skipTest("ไม่มี sh")
        for name in ("measure-llm.sh", "session/aipc-llm-start"):
            subprocess.run([sh, "-n", str(REPO / "scripts" / "pi" / name)], check=True)


class SkillSelectTest(unittest.TestCase):
    def setUp(self):
        self.skills = manifest.load_builtin()
        self.asked = []

    def ai(self, answers):
        def fake(text, tools):
            self.asked.append((text, {t["function"]["name"] for t in tools}))
            return {"tool": answers.get(text, ""), "seconds": 1.0, "timings": {}}

        return fake

    def test_rules_first_then_ai_only_when_rules_find_nothing(self):
        items = [{"text": "เปิดยูทูบ", "expect": "system-command", "kind": "direct"},
                 {"text": "คอมหน่วงมาก", "expect": "machine-status", "kind": "paraphrase"},
                 {"text": "เล่ามุกหน่อย", "expect": "none", "kind": "general"},
                 {"text": "ขอแบบกระชับของเนื้อหานี้", "expect": "summarize-text",
                  "kind": "paraphrase"}]  # fmt: skip
        res = skill_select.evaluate(
            items,
            self.skills,
            self.ai(
                {
                    "คอมหน่วงมาก": "machine-status",
                    "เล่ามุกหน่อย": "rm-rf",
                    "ขอแบบกระชับของเนื้อหานี้": "summarize-text",
                }
            ),
        )
        self.assertEqual(
            [t for t, _ in self.asked], ["คอมหน่วงมาก", "เล่ามุกหน่อย", "ขอแบบกระชับของเนื้อหานี้"]
        )
        self.assertNotIn("system-command", self.asked[0][1], "AI ไม่มีเครื่องมือสั่งเครื่อง")
        self.assertEqual(res["correct"], 4, "ชื่อที่ไม่มีในรายการ (rm-rf) = คุยทั่วไป ถูกต้องตามแอปจริง")
        self.assertEqual(res["false_calls"], 0)
        self.assertEqual(res["ai_asked"], 3)

    def test_ai_first_asks_ai_for_everything_except_machine_commands(self):
        items = [
            {"text": "เปิดยูทูบ", "expect": "system-command", "kind": "direct"},
            {"text": "เครื่องบินลำแรกของโลกบินได้เมื่อไร", "expect": "none", "kind": "trap"},
            {"text": "เตือนส่งรายงานวันศุกร์บ่ายสอง", "expect": "reminder", "kind": "direct"},
        ]
        res = skill_select.evaluate(
            items, self.skills, self.ai({"เตือนส่งรายงานวันศุกร์บ่ายสอง": "reminder"}), "ai-first"
        )
        self.assertEqual([t for t, _ in self.asked], [items[1]["text"], items[2]["text"]])
        self.assertEqual(res["correct"], 3, "ประโยคหลอกที่กฎเลือกผิด (machine-status) ถึงมือ AI")
        self.assertEqual(res["mode"], "ai-first")
        self.assertEqual(res["ai_seconds_first"], 1.0)

    def test_ai_first_without_ai_falls_back_to_rules(self):
        items = [{"text": "เครื่องบินลำแรกของโลกบินได้เมื่อไร", "expect": "none", "kind": "trap"}]
        res = skill_select.evaluate(items, self.skills, None, "ai-first")
        self.assertEqual(res["rows"][0]["got"], "machine-status", "ไม่มี AI = ผลเท่ากฎอย่างเดียว")

    def test_refuses_server_whose_template_drops_tools(self):
        stripped = {"chat_template": "{%- for message in messages -%}...", "chat_template_caps":
                    {"supports_tools": False}}  # fmt: skip
        with mock.patch.object(skill_select.urllib.request, "urlopen", fake_urlopen(stripped)):
            info = skill_select.server_info("http://x")
            self.assertFalse(info["supports_tools"])
            with (
                tempfile.TemporaryDirectory() as d,
                contextlib.redirect_stderr(io.StringIO()) as err,
            ):
                out = Path(d) / "r.json"
                code = skill_select.main(
                    ["--label", "t", "--server", "http://x", "--out", str(out)]
                )
                self.assertEqual(code, 2)
                self.assertFalse(out.exists(), "ไม่เขียนผลที่ใช้ไม่ได้")
            self.assertIn("chat-template-file", err.getvalue())

    def test_dataset_is_well_formed(self):
        data = json.loads(skill_select.DATASET.read_text(encoding="utf-8"))
        ids = {s.id for s in self.skills} | {"none"}
        kinds = {"direct", "paraphrase", "general", "trap"}
        for it in data["items"]:
            self.assertIn(it["expect"], ids, it["text"])
            self.assertIn(it["kind"], kinds, it["text"])
        self.assertEqual(len({it["text"] for it in data["items"]}), len(data["items"]), "ประโยคซ้ำ")
        self.assertEqual(data["criteria"]["correct_min"], 0.8)


if __name__ == "__main__":
    unittest.main()
