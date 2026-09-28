import re
import unittest

from aipc.accounts import validation as v


class UsernameTest(unittest.TestCase):
    def test_valid(self):
        for name in ("namfon", "pakon2", "lab-user"):
            self.assertTrue(v.check_username(name).ok, name)

    def test_rules(self):
        self.assertFalse(v.check_username("").ok)
        self.assertFalse(v.check_username("Namfon").ok)  # ตัวใหญ่
        self.assertFalse(v.check_username("2fast").ok)  # ขึ้นต้นด้วยตัวเลข
        self.assertFalse(v.check_username("ab").ok)  # สั้นไป
        self.assertFalse(v.check_username("a" * 33).ok)  # ยาวเกินที่ useradd รับ
        self.assertFalse(v.check_username("na mfon").ok)
        self.assertFalse(v.check_username("น้ำฝน").ok)  # ชื่อ Linux user เป็นภาษาไทยไม่ได้

    def test_reserved_names_rejected(self):
        self.assertFalse(v.check_username("root").ok)
        self.assertFalse(v.check_username("postgres").ok)

    def test_trailing_newline_rejected(self):
        """พบ 2026-09-28: re.match + $ ยอมให้มีขึ้นบรรทัดท้าย → "root\\n" หลุดทั้งกฎและรายชื่อสงวน
        ชื่อนี้จะถูกส่งให้ useradd ตอนสร้างบัญชีจริง (การ์ด 0012) จึงต้องตรวจทั้งสตริง."""
        for name in ("root\n", "namfon\n", "pakon2\r\n"):
            self.assertFalse(v.check_username(name).ok, repr(name))


class PasswordTest(unittest.TestCase):
    def test_short_passwords_score_low(self):
        self.assertEqual(v.password_strength(""), 0)
        self.assertEqual(v.password_strength("abc123"), 1)

    def test_mixed_and_long_scores_high(self):
        self.assertEqual(v.password_strength("abcdefghij"), 2)
        self.assertEqual(v.password_strength("Abcdefgh12"), 3)
        self.assertEqual(v.password_strength("Abcdefgh12!xyz"), 4)

    def test_labels_cover_every_score(self):
        self.assertEqual(len(v.STRENGTH_LABELS), 5)

    def test_check_password(self):
        self.assertFalse(v.check_password("short", "short").ok)
        self.assertFalse(v.check_password("longenough1", "different1").ok)
        self.assertTrue(v.check_password("longenough1", "longenough1").ok)


class RecoveryCodeTest(unittest.TestCase):
    def test_format(self):
        code = v.new_recovery_code()
        self.assertRegex(code, r"^([0-9A-Z]{4}-){5}[0-9A-Z]{4}$")

    def test_no_confusable_letters(self):
        code = v.new_recovery_code()
        self.assertIsNone(re.search(r"[ILOU]", code))

    def test_codes_differ(self):
        self.assertEqual(len({v.new_recovery_code() for _ in range(50)}), 50)


if __name__ == "__main__":
    unittest.main()
