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

from aipc.skills import manifest, userskills
from aipc.spikes import skill_select

REPO = Path(__file__).resolve().parents[1]
TEMPLATES = REPO / "scripts" / "pi" / "chat-templates"


# สกิลผู้ใช้จำลองสำหรับเทสต์ (หัวข้อไม่ชนกันและไม่ชนสกิลในตัว) · มากกว่า 5 ตัว = ต้องผ่านตัวค้นของการ์ด 0018
USER_SKILLS = [
    (
        "plant-care",
        "ดูแลต้นไม้",
        "แนะนำวิธีรดน้ำ ใส่ปุ๋ย และดูแลต้นไม้ในบ้าน",
        ["รดน้ำต้นกระบองเพชรบ่อยแค่ไหน", "ต้นไม้ในห้องใบเหลืองทำยังไงดี", "ใส่ปุ๋ยมอนสเตอร่าตอนไหน"],
    ),
    (
        "cat-care",
        "เลี้ยงแมว",
        "แนะนำการเลี้ยงแมว อาหาร การฝึกกระบะทราย",
        ["แมวไม่ยอมกินข้าว", "ฝึกลูกแมวใช้กระบะทราย", "แมวอายุสามเดือนกินอะไรได้บ้าง"],
    ),
    (
        "running-plan",
        "ตารางวิ่ง",
        "จัดตารางฝึกวิ่งสำหรับมือใหม่ถึงฮาล์ฟมาราธอน",
        ["อยากวิ่งห้ากิโลให้ได้ในเดือนเดียว", "ตารางซ้อมวิ่งฮาล์ฟมาราธอน", "มือใหม่วิ่งสัปดาห์ละกี่วันดี"],
    ),
    (
        "guitar-chords",
        "คอร์ดกีตาร์",
        "อธิบายวิธีจับคอร์ดกีตาร์และลำดับคอร์ดง่าย ๆ",
        ["จับคอร์ด F ยังไงไม่ให้บอด", "คอร์ดง่าย ๆ สำหรับเพลงช้า", "เปลี่ยนคอร์ด G ไป C ให้เร็วขึ้น"],
    ),
    (
        "coffee-brew",
        "ชงกาแฟ",
        "สอนชงกาแฟดริป สัดส่วนผงต่อน้ำ อุณหภูมิน้ำ",
        ["ชงกาแฟดริปใช้ผงกี่กรัม", "น้ำร้อนกี่องศาถึงจะดีสำหรับดริป", "กาแฟเปรี้ยวเกินไปแก้ยังไง"],
    ),
    (
        "trip-budget",
        "งบเที่ยว",
        "ประมาณค่าใช้จ่ายทริปเที่ยวในประเทศแบบประหยัด",
        ["ไปเชียงใหม่สามวันใช้เงินเท่าไร", "เที่ยวทะเลแบบประหยัดต้องเตรียมงบเท่าไร", "แบ่งงบค่าที่พักกับค่ากิน"],
    ),
    (
        "origami",
        "พับกระดาษ",
        "สอนพับกระดาษเป็นรูปสัตว์และดอกไม้ทีละขั้น",
        ["พับนกกระเรียนกระดาษยังไง", "สอนพับดอกกุหลาบกระดาษ", "พับกบกระโดดได้ให้ลูกเล่น"],
    ),
]


def user_skill(sid, name, desc, examples, md=False):
    text = "\n".join(["---", f"id: {sid}", f"name: {name}", f"description: {desc}", "worker: llm",
                      "needs: llm", "examples:", *[f"  - {e}" for e in examples], "---",
                      "## คำสั่งให้ AI", f"{desc} ตอบสั้น ๆ เป็นข้อ ๆ"])  # fmt: skip
    if md:
        return text
    m, errors = userskills.check_md(text)
    assert m is not None, errors
    return m


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
        self.choices = []

    def ai(self, answers):
        def fake(text, tools, choice="auto"):
            self.asked.append((text, {t["function"]["name"] for t in tools}))
            self.choices.append(choice)
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
            # ไม่ใช่ตัวอย่างของสกิลเป๊ะ ๆ (ตรงตัวอย่างเป๊ะ = กฎเลือกเลย · router.repeat_of การ์ด 0017)
            {"text": "เตือนส่งรายงานวันศุกร์บ่ายสามโมง", "expect": "reminder", "kind": "direct"},
        ]
        res = skill_select.evaluate(
            items, self.skills, self.ai({"เตือนส่งรายงานวันศุกร์บ่ายสามโมง": "reminder"}), "ai-first"
        )
        self.assertEqual([t for t, _ in self.asked], [items[1]["text"], items[2]["text"]])
        self.assertEqual(res["correct"], 3, "ประโยคหลอกที่กฎเลือกผิด (machine-status) ถึงมือ AI")
        self.assertEqual(res["mode"], "ai-first")
        self.assertEqual(res["ai_seconds_first"], 1.0)

    def test_ai_first_without_ai_falls_back_to_rules(self):
        items = [{"text": "เครื่องบินลำแรกของโลกบินได้เมื่อไร", "expect": "none", "kind": "trap"}]
        res = skill_select.evaluate(items, self.skills, None, "ai-first")
        rules = skill_select.evaluate(items, self.skills, None, "rules-first")
        self.assertEqual(res["rows"][0]["got"], rules["rows"][0]["got"], "ไม่มี AI = ผลเท่ากฎอย่างเดียว")

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

    def test_without_user_skills_ai_sees_the_same_tools_as_before(self):
        items = [{"text": "เล่ามุกหน่อย", "expect": "none", "kind": "general"}]
        skill_select.evaluate(items, self.skills, self.ai({}))
        before = {t["function"]["name"] for t in skill_select.catalog.tools(self.skills, {"llm"})}
        self.assertEqual(self.asked[0][1], before, "ชุดเดิม (การ์ด 0074 ไม่เปลี่ยนผลเก่า)")

    def test_user_skills_reach_rules_and_ai_like_the_app(self):
        pool = [user_skill(*t) for t in USER_SKILLS]
        items = [{"text": "ใบมอนสเตอร่าเหลืองเป็นจุด ๆ", "expect": "plant-care", "kind": "paraphrase"},
                 {"text": "รดน้ำต้นกระบองเพชรบ่อยแค่ไหน", "expect": "plant-care",
                  "kind": "direct"}]  # fmt: skip
        res = skill_select.evaluate(
            items, self.skills, self.ai({"ใบมอนสเตอร่าเหลืองเป็นจุด ๆ": "plant-care"}), "ai-first",
            user=pool,
        )  # fmt: skip
        text, names = self.asked[0]
        # ai-first = ทางของแอปเมื่อ AI พร้อม (backend._handle)
        # ตรงตัวอย่างเป๊ะ = router.repeat_of เลือกเอง
        self.assertEqual(len(self.asked), 1, "ประโยคที่ตรงตัวอย่างเป๊ะ = กฎเลือกสกิลผู้ใช้เอง ไม่ถาม AI")
        self.assertIn("plant-care", names)
        n = len(names & {s.id for s in pool})
        self.assertTrue(1 <= n <= 5, "สกิลผู้ใช้ส่งให้ AI เฉพาะตัวที่ใกล้ข้อความ ≤ 5 ตัว (การ์ด 0018 · 0074)")
        self.assertEqual(self.choices[0], "required", "มีสกิลผู้ใช้ใกล้ข้อความ = บังคับให้ AI เลือก")
        self.assertIn(skill_select.catalog.ANSWER, names)
        self.assertTrue({"translate", "summarize-text"} <= names, "สกิลในตัวส่งทุกครั้ง")
        self.assertEqual(res["correct"], 2)

    def test_answer_directly_asks_again_with_builtin_tools_like_the_app(self):
        """การ์ด 0074 หัวข้อ 14: บังคับเลือก → "ตอบเอง" → ถามรอบ 2 ด้วยสกิลในตัวอย่างเดียว · เวลารวม 2 รอบ."""
        pool = [user_skill(*t) for t in USER_SKILLS]
        text = "ใบมอนสเตอร่าเหลืองเป็นจุด ๆ ทำไงดี"
        answers = iter([skill_select.catalog.ANSWER, ""])

        def fake(t, tools, choice="auto"):
            self.asked.append((t, {x["function"]["name"] for x in tools}))
            self.choices.append(choice)
            return {"tool": next(answers), "seconds": 1.0, "timings": {}}

        items = [{"text": text, "expect": "plant-care", "kind": "paraphrase"}]
        res = skill_select.evaluate(items, self.skills, fake, "ai-first", user=pool)
        self.assertEqual(self.choices, ["required", "auto"])
        self.assertFalse(self.asked[1][1] & {s.id for s in pool}, "รอบ 2 ไม่มีสกิลผู้ใช้")
        row = res["rows"][0]
        self.assertEqual((row["got"], row["seconds"], row["forced"]), ("none", 2.0, True))

    def test_load_pool_keeps_order_and_skips_what_the_import_gate_rejects(self):
        items = [{"id": "p1", "md": user_skill(*USER_SKILLS[0], md=True)},
                 {"id": "p2", "md": user_skill(*USER_SKILLS[0], md=True)},  # id ซ้ำตัวก่อน
                 {"id": "p3", "md": "ไม่ใช่ไฟล์สกิล"},
                 {"id": "p4", "md": user_skill(*USER_SKILLS[1], md=True)}]  # fmt: skip
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "pool.json"
            path.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
            ok, rejected = skill_select.load_pool(path, self.skills)
        self.assertEqual([s.id for s in ok], ["plant-care", "cat-care"])
        self.assertEqual([r["id"] for r in rejected], ["p2", "p3"])

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
