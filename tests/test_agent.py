"""ผู้ช่วยเว็บที่ AI คิดเอง (การ์ด 0025): ภาษาแผน · ขั้นวางแผน → ดูหน้า → ทำ · Claude สำรอง · อ่านหน้าไว้ก่อน.

AI จริงวัดที่ src/aipc/spikes/agent_eval.py (Pi) · ที่นี่ใช้ AI ปลอมที่ตอบตามบท เพื่อตรวจทางเดินของโค้ด
"""

import json
import time
import unittest
from datetime import date

from aipc.browser import agent, page
from aipc.browser.agent import Agent, Step, parse_steps
from aipc.browser.control import TYPE_JS, Result, site_url
from aipc.cloud.ask import CloudReply


class FakeLlm:
    """ตอบตามบท: plan = รายการคำตอบขั้นวางแผน · look = รายการคำตอบขั้นดูหน้า."""

    def __init__(self, plan=(), look=(), down=False):
        self.plan, self.look, self.down = list(plan), list(look), down
        self.asked, self.prereads, self.warms = [], [], []

    def ask(self, messages, grammar, max_tokens):
        if self.down:
            raise ConnectionError("ไม่มีที่อยู่ของ AI")
        stage = "plan" if messages[0]["content"] == agent.SYSTEM_PLAN else "look"
        self.asked.append((stage, messages[1]["content"]))
        return (self.plan if stage == "plan" else self.look).pop(0), {"prompt_n": 7}

    def preread(self, messages):
        self.warms.append(messages[0]["content"]) if not messages[1]["content"] else \
            self.prereads.append(messages[1]["content"])  # fmt: skip
        return {"prompt_n": 100}

    def abort_preread(self):
        pass


class FakeBrowser:
    def __init__(self, running=True, fail=()):
        self.running, self.fail = running, set(fail)
        self.acts, self.observed = [], 0
        self.obs = {"title": "ราคาทอง", "url": "https://duckduckgo.com/?q=ราคาทอง",
                    "items": [{"n": 1, "kind": "ลิงก์", "label": "สมาคมค้าทองคำ"},
                              {"n": 2, "kind": "ปุ่ม", "label": "ค้นหา"}],
                    "text": "ทองคำแท่ง ขายออก 66,600.00", "atTop": True, "atEnd": False}  # fmt: skip
        self.spot = ("https://duckduckgo.com/?q=ราคาทอง", 0)

    def current(self):
        return {"title": self.obs["title"], "url": self.obs["url"]}

    def observe(self):
        self.observed += 1
        return dict(self.obs)

    def where(self):
        return self.spot

    def tagged(self):
        return True

    def act(self, st):
        self.acts.append(str(st))
        if str(st) in self.fail:
            return Result(False, f"ไม่มีรายการที่ {st.n}")
        self.running = True
        return Result(True, f"ทำ {st} แล้ว")


def make(llm, browser=None, **kw):
    return Agent(
        browser or FakeBrowser(), llm, today=lambda: date(2026, 10, 13), preread=False, **kw
    )


class ParseTest(unittest.TestCase):
    def test_plan_line_to_steps(self):
        self.assertEqual(parse_steps("search ราคา ทอง ; result 1", agent.PLAN_STEPS),
                         [Step("search", 0, "ราคา ทอง"), Step("result", 1)])  # fmt: skip
        self.assertEqual(parse_steps("type 3 สมชาย ใจดี;click 13", agent.LOOK_STEPS),
                         [Step("type", 3, "สมชาย ใจดี"), Step("click", 13)])  # fmt: skip
        self.assertEqual(parse_steps("chat", (*agent.PLAN_STEPS, "chat")), [Step("chat")])

    def test_bad_lines_are_rejected(self):
        for bad in ("", "click", "click x", "result 0", "back 2", "search", "rm -rf ~",
                    "chat ; back", "type สมชาย"):  # fmt: skip
            self.assertIsNone(parse_steps(bad, (*agent.PLAN_STEPS, *agent.LOOK_STEPS, "chat")), bad)
        self.assertIsNone(parse_steps("click 3", agent.PLAN_STEPS), "ขั้นวางแผนคลิกเองไม่ได้")

    def test_look_grammar_only_allows_real_targets(self):
        g = agent.look_grammar({"items": [{"n": 1, "kind": "ช่อง", "label": "ชื่อ"},
                                          {"n": 2, "kind": "ตัวเลือก", "label": "Large"},
                                          {"n": 3, "kind": "ปุ่ม", "label": "ส่ง"}]})  # fmt: skip
        self.assertIn('cnum ::= "2" | "3"', g)
        self.assertIn('fnum ::= "1"', g)
        self.assertIn('"click " cnum', g)
        self.assertIn('"type " fnum " " txt', g)
        g = agent.look_grammar({"items": [{"n": 1, "kind": "ลิงก์", "label": "ข่าว"}]})
        self.assertNotIn('"type "', g, "ไม่มีช่อง = พิมพ์ไม่ได้")
        self.assertNotIn("\\\\n", g)

    def test_grammar_lists_every_step(self):
        for s in agent.PLAN_STEPS:
            self.assertIn(f'"{s}', agent.PLAN_GRAMMAR)
        for s in agent.LOOK_STEPS:
            self.assertIn(f'"{s}', agent.LOOK_GRAMMAR)


class AgentTest(unittest.TestCase):
    def test_not_web_goes_to_chat_without_touching_browser(self):
        b = FakeBrowser()
        out = make(FakeLlm(plan=["chat"]), b).run("พรุ่งนี้มีนัดอะไร")
        self.assertFalse(out.handled)
        self.assertEqual(b.acts, [])

    def test_ai_not_ready_goes_to_chat(self):
        out = make(FakeLlm(down=True)).run("ตอนนี้กี่โมง")
        self.assertFalse(out.handled)

    def test_page_steps_without_browser_are_app_commands(self):
        b = FakeBrowser(running=False)
        out = make(FakeLlm(plan=["back"]), b).run("ย้อนกลับ")
        self.assertFalse(out.handled)
        self.assertEqual(b.acts, [])

    def test_plan_runs_in_order_and_says_what_was_done(self):
        b = FakeBrowser(running=False)
        out = make(FakeLlm(plan=["search ราคาทอง ; result 1"]), b).run("ค้นหาราคาทองแล้วเข้าลิงก์แรก")
        self.assertEqual(b.acts, ["search ราคาทอง", "result 1"])
        self.assertTrue(out.ok)
        self.assertEqual(out.say, "ทำ search ราคาทอง แล้ว · ทำ result 1 แล้ว")

    def test_look_sees_page_then_clicks(self):
        llm = FakeLlm(plan=["look เข้าเว็บสมาคมค้าทองคำ"], look=["click 1"])
        b = FakeBrowser()
        out = make(llm, b).run("เข้าเว็บสมาคมค้าทองคำ")
        self.assertEqual(b.acts, ["click 1"])
        seen = llm.asked[1][1]
        self.assertIn("[1] ลิงก์: สมาคมค้าทองคำ", seen)
        self.assertTrue(seen.endswith("คำขอ: เข้าเว็บสมาคมค้าทองคำ"))
        self.assertIn("วันอังคารที่ 13 ตุลาคม 2569", seen)
        self.assertTrue(out.ok)

    def test_answer_is_spoken_not_clicked(self):
        b = FakeBrowser()
        out = make(FakeLlm(plan=["look ทองขายออกเท่าไหร่"], look=["answer ทองแท่งขายออก 66,600 บาท"]),
                   b).run("ทองขายออกเท่าไหร่")  # fmt: skip
        self.assertEqual((b.acts, out.say), ([], "ทองแท่งขายออก 66,600 บาท"))

    def test_scroll_then_look_again(self):
        b = FakeBrowser()
        llm = FakeLlm(plan=["look หาปุ่มสมัคร"], look=["down", "click 2"])
        out = make(llm, b).run("กดสมัคร")
        self.assertEqual(b.acts, ["down", "click 2"])
        self.assertEqual(b.observed, 2)
        self.assertIn("ทำไปแล้ว: ทำ down แล้ว", llm.asked[2][1])
        self.assertTrue(out.ok)

    def test_look_can_hand_over_to_chat(self):
        b = FakeBrowser()
        out = make(FakeLlm(plan=["look วันนี้มีนัดอะไร"], look=["chat"]), b).run("วันนี้มีนัดอะไร")
        self.assertFalse(out.handled)
        self.assertEqual(b.acts, [])
        out = make(FakeLlm(plan=["search ข่าว ; look วันนี้มีนัดอะไร"], look=["chat"]),
                   FakeBrowser()).run("ค้นข่าวแล้วบอกว่าวันนี้มีนัดอะไร")  # fmt: skip
        self.assertTrue(out.handled)
        self.assertFalse(out.ok, "แผนหลายขั้น = ทำไม่สำเร็จ ไม่ย้อนไปแชท (ค้นไปแล้ว)")

    def test_not_found_without_claude_says_so(self):
        out = make(FakeLlm(plan=["look หาปุ่มสมัคร"], look=["none"])).run("กดสมัคร")
        self.assertFalse(out.ok)
        self.assertIn("หาไม่เจอ", out.say)
        self.assertFalse(out.cloud)

    def test_claude_takes_over_when_local_fails(self):
        sent = []

        def cloud(system, prompt):
            sent.append((system, prompt))
            return CloudReply(True, "ขอเลือกลิงก์นี้\nclick 1")

        b = FakeBrowser(fail={"result 9"})
        out = make(FakeLlm(plan=["result 9"]), b, cloud=cloud).run("เข้าลิงก์ที่เก้า")
        self.assertEqual(b.acts, ["result 9", "click 1"])
        self.assertTrue(out.ok and out.cloud)
        system, prompt = sent[0]
        self.assertEqual(system, agent.CLOUD_SYSTEM)
        self.assertIn("คำสั่งของผู้ใช้: เข้าลิงก์ที่เก้า", prompt)
        self.assertIn("ปัญหา: ไม่มีรายการที่ 9", prompt)
        self.assertIn("[1] ลิงก์: สมาคมค้าทองคำ", prompt)

    def test_claude_switched_off_sends_nothing(self):
        sent = []
        b = FakeBrowser(fail={"result 9"})
        out = make(FakeLlm(plan=["result 9"]), b, cloud=lambda s, p: sent.append(p),
                   cloud_ready=lambda: False).run("เข้าลิงก์ที่เก้า")  # fmt: skip
        self.assertEqual(sent, [])
        self.assertFalse(out.ok or out.cloud)

    def test_claude_reply_that_is_not_a_plan_is_not_run(self):
        b = FakeBrowser(fail={"result 9"})
        cloud = lambda s, p: CloudReply(True, "ลองรันคำสั่ง rm -rf ~ ดูครับ")  # noqa: E731
        out = make(FakeLlm(plan=["result 9"]), b, cloud=cloud).run("เข้าลิงก์ที่เก้า")
        self.assertEqual(b.acts, ["result 9"])
        self.assertFalse(out.ok)


def wait_for(cond, secs=3.0):
    deadline = time.monotonic() + secs
    while time.monotonic() < deadline and not cond():
        time.sleep(0.02)
    return cond()


class PreReadTest(unittest.TestCase):
    def test_warms_both_system_prompts_in_chunks_when_idle(self):
        llm, idle = FakeLlm(), {"v": False}
        a = Agent(FakeBrowser(running=False), llm, idle=lambda: idle["v"])
        a.pre.warm()
        time.sleep(0.1)
        self.assertEqual(llm.warms, [], "แชทกำลังใช้ AI = ยังไม่อุ่น")
        idle["v"] = True
        self.assertTrue(wait_for(lambda: a.pre.warmed))
        plan = [w for w in llm.warms if agent.SYSTEM_PLAN.startswith(w)]
        look = [w for w in llm.warms if agent.SYSTEM_LOOK.startswith(w)]
        self.assertGreater(len(plan), 2, "อ่านเป็นช่วง ๆ (แชทแทรกได้ไม่ต้องรอนาน)")
        self.assertEqual((plan[-1], look[-1]), (agent.SYSTEM_PLAN, agent.SYSTEM_LOOK))
        self.assertEqual(len(plan) + len(look), len(llm.warms))

    def test_command_pauses_warming_and_it_resumes_after(self):
        llm = FakeLlm(plan=["chat"])
        a = Agent(FakeBrowser(running=False), llm, today=lambda: date(2026, 10, 13))
        a.run("สวัสดี")  # ยังไม่อุ่น → หลังทำคำสั่งเริ่มอุ่น
        self.assertTrue(wait_for(lambda: a.pre.warmed))

    def test_reads_page_ahead_in_chunks_and_reuses_it(self):
        b = FakeBrowser()
        b.obs["text"] = "ข้อความยาว " * 120
        llm = FakeLlm(plan=["look ราคาเท่าไหร่"], look=["answer 66,600 บาท"])
        a = Agent(b, llm, today=lambda: date(2026, 10, 13))
        a.pre.settle = 0
        a.pre.schedule()
        full = page.page_text(b.obs)
        self.assertTrue(wait_for(lambda: a.pre.done_chars >= len(full)))
        self.assertGreater(len(llm.prereads), 1, "อ่านเป็นช่วง ๆ ผู้ใช้พูดแทรกได้")
        self.assertEqual(llm.prereads[-1], full)
        self.assertTrue(all(full.startswith(x) for x in llm.prereads))
        out = a.run("ราคาเท่าไหร่")
        self.assertTrue(out.trace[-1]["preread"], "ใช้หน้าที่อ่านไว้แล้ว ไม่อ่านใหม่")
        self.assertTrue(llm.asked[-1][1].startswith(full), "ส่วนหน้าของคำขอตรงกับที่อ่านไว้ = ใช้แคชได้")
        self.assertEqual(out.say, "66,600 บาท")

    def test_page_changed_means_read_again(self):
        b = FakeBrowser()
        a = Agent(b, FakeLlm(), today=lambda: date(2026, 10, 13))
        a.pre.settle = 0
        a.pre.schedule()
        self.assertTrue(wait_for(lambda: a.pre.take() is not None))
        b.spot = ("https://duckduckgo.com/?q=ราคาทอง", 720)  # เลื่อนแล้ว
        self.assertIsNone(a.pre.take())


class PageTest(unittest.TestCase):
    def test_page_text_is_short_and_readable(self):
        text = page.page_text({"title": "ข่าว", "url": "https://x.com/?q=%E0%B8%97%E0%B8%AD%E0%B8%87",
                               "items": [{"n": 1, "kind": "ช่อง", "label": "ชื่อ"}], "text": "สวัสดี",
                               "atTop": True})  # fmt: skip
        self.assertIn("https://x.com/?q=ทอง", text)  # %E0… เปลือง token หลายเท่า
        self.assertIn("[1] ช่อง: ชื่อ", text)
        self.assertIn("ตำแหน่ง: บนสุด", text)
        self.assertEqual(page.page_text({}), "หน้าเว็บ: (ยังไม่ได้เปิดเบราว์เซอร์)")

    def test_password_fields_never_reach_the_ai(self):
        self.assertIn("input:not([type=hidden]):not([type=password])", page.OBSERVE_JS)
        self.assertIn("type === 'password'", TYPE_JS)

    def test_site_names(self):
        self.assertEqual(site_url("youtube.com"), "https://youtube.com")
        self.assertEqual(site_url("ยูทูบ"), "https://www.youtube.com")
        self.assertEqual(site_url("เว็บพันทิป"), "https://pantip.com")
        self.assertEqual(site_url("https://th.wikipedia.org/wiki/ช้าง"),
                         "https://th.wikipedia.org/wiki/ช้าง")  # fmt: skip
        self.assertIsNone(site_url("ร้านป้าแดง"))


class LlmTest(unittest.TestCase):
    def test_request_is_deterministic_and_grammar_bound(self):
        sent = {}

        class Conn:
            sock = None

            def request(self, method, path, body, headers):
                sent.update(json.loads(body), path=path)

            def getresponse(self):
                class R:
                    status = 200

                    def read(self):
                        return json.dumps({"choices": [{"message": {"content": "back"}}],
                                           "timings": {"prompt_n": 3}}).encode()  # fmt: skip

                return R()

            def close(self):
                pass

        class T:
            def connect(self, timeout):
                return Conn()

        text, timings = agent.Llm(T()).ask(
            [{"role": "user", "content": "x"}], agent.PLAN_GRAMMAR, 60
        )
        self.assertEqual((text, timings), ("back", {"prompt_n": 3}))
        self.assertEqual(sent["temperature"], 0)
        self.assertEqual(sent["grammar"], agent.PLAN_GRAMMAR)
        self.assertTrue(sent["cache_prompt"])
        self.assertFalse(sent["chat_template_kwargs"]["enable_thinking"])


if __name__ == "__main__":
    unittest.main()
