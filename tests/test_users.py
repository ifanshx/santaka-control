"""Penyimpanan pengguna: kripto sandi, proteksi admin terakhir, kode 2FA."""
import os
import tempfile
import unittest

from lib import crypto, perm, users


class UserStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "users.json")
        self.store = users.UserStore(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_and_authenticate(self):
        self.store.create("owner", "Rahasia#1", perm.ROLE_ADMIN, "Owner", "test")
        user = self.store.get("owner")
        self.assertEqual(user["role"], perm.ROLE_ADMIN)
        self.assertTrue(crypto.verify_password("Rahasia#1", user["password"]))
        self.assertFalse(crypto.verify_password("salah", user["password"]))
        self.assertTrue(self.store.is_last_admin("owner"))

    def test_duplicate_rejected(self):
        self.store.create("owner", "pw", perm.ROLE_ADMIN)
        with self.assertRaises(ValueError):
            self.store.create("owner", "pw2", perm.ROLE_VIEWER)

    def test_last_admin_protected(self):
        self.store.create("owner", "pw", perm.ROLE_ADMIN)
        with self.assertRaises(ValueError):
            self.store.set_role("owner", perm.ROLE_VIEWER)
        with self.assertRaises(ValueError):
            self.store.disable("owner")
        with self.assertRaises(ValueError):
            self.store.delete("owner")

    def test_second_admin_allows_change(self):
        self.store.create("a", "pw", perm.ROLE_ADMIN)
        self.store.create("b", "pw", perm.ROLE_ADMIN)
        self.store.set_role("a", perm.ROLE_OPERATOR)
        self.assertEqual(self.store.get("a")["role"], perm.ROLE_OPERATOR)

    def test_totp_activation_and_recovery_code(self):
        self.store.create("owner", "pw", perm.ROLE_ADMIN)
        secret, uri = self.store.start_totp("owner")
        self.assertIn("otpauth://totp/", uri)
        codes = self.store.verify_totp("owner", crypto.totp_now(secret))
        self.assertEqual(len(codes), users.RECOVERY_COUNT)
        user = self.store.get("owner")
        self.assertEqual(user["totp"], secret)
        self.assertIsNone(user["totp_pending"])
        self.assertTrue(self.store.check_code(user, codes[0]))
        self.assertFalse(self.store.check_code(self.store.get("owner"), codes[0]))
        self.assertEqual(self.store.recovery_left("owner"), users.RECOVERY_COUNT - 1)


class PermTest(unittest.TestCase):
    def test_roles(self):
        viewer = {"role": perm.ROLE_VIEWER}
        operator = {"role": perm.ROLE_OPERATOR}
        admin = {"role": perm.ROLE_ADMIN}
        self.assertTrue(perm.can(viewer, perm.VIEW))
        self.assertFalse(perm.can(viewer, perm.SERVICE))
        self.assertTrue(perm.can(operator, perm.SERVICE))
        self.assertFalse(perm.can(operator, perm.USER_MANAGE))
        self.assertTrue(perm.can(admin, perm.USER_MANAGE))
        self.assertFalse(perm.can(None, perm.VIEW))
        self.assertTrue(perm.can_any(operator, (perm.USER_MANAGE, perm.FILE_WRITE)))

    def test_manage_roles(self):
        admin = {"role": perm.ROLE_ADMIN}
        operator = {"role": perm.ROLE_OPERATOR}
        self.assertEqual(perm.manageable_roles(admin), perm.ROLE_ORDER)
        self.assertEqual(perm.manageable_roles(operator), [perm.ROLE_VIEWER])
        self.assertTrue(perm.can_manage_user(admin, perm.ROLE_OPERATOR))
        self.assertFalse(perm.can_manage_user(operator, perm.ROLE_ADMIN))


if __name__ == "__main__":
    unittest.main()
