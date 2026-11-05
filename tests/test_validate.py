"""Validator input: setiap batas sistem harus menolak data berbahaya."""
import unittest

from lib import validate


class PortTest(unittest.TestCase):
    def test_accepts_range(self):
        self.assertEqual(validate.port("1"), 1)
        self.assertEqual(validate.port(65535), 65535)

    def test_rejects_out_of_range_and_junk(self):
        for bad in ("0", "65536", "-1", "abc", None, ""):
            self.assertIsNone(validate.port(bad))


class NameTest(unittest.TestCase):
    def test_unit(self):
        self.assertTrue(validate.unit("nginx.service"))
        self.assertTrue(validate.unit("php8.2-fpm.service"))
        self.assertFalse(validate.unit("nginx && rm -rf /"))
        self.assertFalse(validate.unit("../etc/passwd"))

    def test_domain(self):
        self.assertTrue(validate.domain("panel.example.com"))
        self.assertTrue(validate.domain("a-b.co"))
        self.assertFalse(validate.domain("localhost"))
        self.assertFalse(validate.domain("-bad.com"))
        self.assertFalse(validate.domain("bad..com"))
        self.assertFalse(validate.domain("x" * 254 + ".com"))

    def test_filename_blocks_traversal(self):
        self.assertTrue(validate.filename("catatan.txt"))
        for bad in ("..", ".", "a/b", "a\\b", "x\x00y", "", None):
            self.assertFalse(validate.filename(bad), repr(bad))

    def test_username_and_slug(self):
        self.assertTrue(validate.username("ops_1"))
        self.assertFalse(validate.username("Ops"))
        self.assertFalse(validate.username("ab"))
        self.assertTrue(validate.slug("my-app"))
        self.assertFalse(validate.slug("my app"))

    def test_sql_name_blocks_quotes(self):
        self.assertTrue(validate.sql_name("app_db"))
        self.assertFalse(validate.sql_name("a`; DROP TABLE x; --"))

    def test_safe_int_clamps(self):
        self.assertEqual(validate.safe_int("7", 1, 10), 7)
        self.assertEqual(validate.safe_int("100", 1, 10, default=3), 3)
        self.assertEqual(validate.safe_int("nope", 1, 10), None)

    def test_one_of(self):
        self.assertEqual(validate.one_of("b", ("a", "b"), "a"), "b")
        self.assertEqual(validate.one_of("z", ("a", "b"), "a"), "a")


if __name__ == "__main__":
    unittest.main()
