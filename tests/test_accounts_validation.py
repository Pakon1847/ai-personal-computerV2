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


class PinTest(unittest.TestCase):
    def test_good_pins(self):
        for pin in ("482917", "๔๘๒๙๑๗", "4829 17", "730519204816"):
            self.assertTrue(v.check_pin(pin, pin).ok, pin)

    def test_length_and_digits_only(self):
        for pin in ("", "48291", "4829173051924", "48291a", "４８２９１７", "48-291"):
            self.assertFalse(v.check_pin(pin, pin).ok, pin)

    def test_easy_pins_rejected(self):
        for pin in ("000000", "111111", "123456", "654321", "890123", "121212", "123123",
                    "12341234", "112233", "147258"):  # fmt: skip
            self.assertFalse(v.check_pin(pin, pin).ok, pin)

    def test_confirm_must_match(self):
        self.assertFalse(v.check_pin("482917", "482918").ok)
        self.assertTrue(v.check_pin("482917", "๔๘๒๙๑๗").ok)  # เลขไทย = เลขอารบิก

    def test_normalize(self):
        self.assertEqual(v.normalize_pin(" ๔๘๒ ๙๑๗ "), "482917")


if __name__ == "__main__":
    unittest.main()
