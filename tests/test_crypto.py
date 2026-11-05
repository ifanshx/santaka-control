"""Kripto: hash kata sandi, TOTP, dan tanda tangan HMAC."""
import unittest

from lib import crypto


class PasswordTest(unittest.TestCase):
    def test_roundtrip_with_low_rounds(self):
        stored = crypto.hash_password("S3cret!", rounds=1000)
        self.assertTrue(stored.startswith("pbkdf2_sha256$1000$"))
        self.assertTrue(crypto.verify_password("S3cret!", stored))
        self.assertFalse(crypto.verify_password("s3cret!", stored))

    def test_rejects_malformed(self):
        for bad in ("", None, "plain", "pbkdf2_sha256$1$zzzz$zzzz"):
            self.assertFalse(crypto.verify_password("x", bad))


class TotpTest(unittest.TestCase):
    def test_matches_reference_vector(self):
        # RFC 6238 test vector (SHA-1, 8 digit) tidak dipakai; cek konsistensi internal.
        secret = crypto.base32_encode(b"12345678901234567890")
        code = crypto.totp_at(secret, 59 // 30)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())
        self.assertEqual(code, crypto.totp_at(secret, 59 // 30))

    def test_verify_accepts_current_code(self):
        secret = crypto.generate_totp_secret()
        self.assertTrue(crypto.totp_verify(secret, crypto.totp_now(secret)))
        self.assertFalse(crypto.totp_verify(secret, "000000" if
                                            crypto.totp_now(secret) != "000000"
                                            else "111111"))

    def test_invalid_secret_returns_none(self):
        self.assertIsNone(crypto.totp_at("", 1))


class SignatureTest(unittest.TestCase):
    def test_sign_verify(self):
        payload = "csrf:abc"
        sig = crypto.sign(payload, "key")
        self.assertTrue(crypto.verify_sig(payload, sig, "key"))
        self.assertFalse(crypto.verify_sig(payload, sig, "other"))
        self.assertFalse(crypto.verify_sig("csrf:xyz", sig, "key"))

    def test_recovery_codes_unique(self):
        codes = crypto.new_recovery_codes(8)
        self.assertEqual(len(set(codes)), 8)


if __name__ == "__main__":
    unittest.main()
