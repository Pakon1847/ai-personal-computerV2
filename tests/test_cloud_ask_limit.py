"""การ์ด 0084: บัญชี Claude ใช้ครบ = บอกผู้ใช้ตรง ๆ · ไม่มีเพดานของระบบ (รายวัน/ต่อครั้ง)."""

import json
import unittest

from aipc.cloud import ask
from aipc.cloud.limits import account_limit_message

PREFIX = "บัญชี Claude ใช้ครบโควตาแล้ว · AI ในเครื่องยังใช้ได้ · Claude แจ้งว่า:"


class FakeRunner:
    """แทน claude -p · out = ข้อความที่ส่งกลับทาง stdout · จดคำสั่งที่ถูกเรียก."""

    def __init__(self, out: str, code: int = 0):
        self.out, self.code, self.args = out, code, None

    def __call__(self, args, text, cwd, timeout):
        self.args = args
        return self.code, self.out, ""


def payload(result: str, is_error: bool) -> dict:
    # รูปแบบจากรายงานบั๊ก: is_error true ทั้งที่ subtype success และ exit code 0 (issue 79500)
    return {"type": "result", "subtype": "success", "is_error": is_error, "result": result,
            "total_cost_usd": 0}  # fmt: skip


class AccountLimitTest(unittest.TestCase):
    def test_rate_limit_payload_is_limited(self):
        msg = account_limit_message(payload("API Error: Rate limit reached", True))
        self.assertTrue(msg.startswith(PREFIX), msg)
        self.assertIn("Rate limit reached", msg)

    def test_out_of_usage_and_429_are_limited(self):
        for text in ("You're out of extra usage", "API Error: 429 too many requests"):
            self.assertTrue(account_limit_message(payload(text, True)).startswith(PREFIX), text)

    def test_long_claude_text_is_cut(self):
        msg = account_limit_message(payload("usage limit " + "x" * 500, True))
        # ข้อความ Claude ≤ 200 ตัวอักษร + ช่องว่างและเครื่องหมายคำพูด
        self.assertLessEqual(len(msg) - len(PREFIX), 200 + 4)

    def test_normal_answer_with_word_limit_is_not_limited(self):
        self.assertEqual(account_limit_message(payload("speed limit 90 กม./ชม.", False)), "")

    def test_other_error_is_not_limited(self):
        self.assertEqual(account_limit_message(payload("Invalid model", True)), "")

    def test_call_sets_limited_and_message(self):
        out = json.dumps(payload("API Error: Rate limit reached", True))
        r = ask.ask("ข่าววันนี้", claude="claude", runner=FakeRunner(out))
        self.assertFalse(r.ok)
        self.assertTrue(r.limited)
        self.assertTrue(r.error.startswith(PREFIX), r.error)

    def test_no_internet_is_not_limited(self):
        r = ask.ask("ข่าววันนี้", claude="claude", runner=FakeRunner("rate limit", code=1))
        self.assertFalse(r.limited)
        self.assertIn("ติดต่อ Claude ไม่ได้", r.error)

    def test_no_per_call_budget_flag(self):
        ok = json.dumps(payload("ตอบ", False))
        run = FakeRunner(ok)
        ask.ask("ถาม", claude="claude", runner=run)
        self.assertNotIn("--max-budget-usd", run.args)
        run = FakeRunner(ok)
        ask.ask_plain("ระบบ", "ถาม", claude="claude", runner=run)
        self.assertNotIn("--max-budget-usd", run.args)


if __name__ == "__main__":
    unittest.main()
