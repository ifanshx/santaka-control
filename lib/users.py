"""Manajemen pengguna panel: multi-user dengan role, hash PBKDF2, 2FA per-user."""
import os
import time

from . import crypto, perm, store

RECOVERY_COUNT = 8


def _hostname():
    try:
        return os.uname().nodename
    except AttributeError:
        import platform
        return platform.node() or "santaka"


class UserStore:
    def __init__(self, path):
        self.path = path

    # ---------- baca ----------

    def all(self):
        data = store.read_json(self.path, None)
        if data is None:
            return {}
        if "users" in data:
            return data["users"]
        return data  # kompatibilitas format lama

    def get(self, username):
        if not username:
            return None
        return self.all().get(username)

    def count(self):
        return len(self.all())

    def count_admins(self):
        return len([u for u in self.all().values()
                    if u.get("role") == perm.ROLE_ADMIN])

    def is_last_admin(self, username):
        u = self.get(username)
        return bool(u and u.get("role") == perm.ROLE_ADMIN
                    and self.count_admins() <= 1)

    # ---------- tulis ----------

    def save_all(self, users):
        store.write_json(self.path, {"users": users}, mode=0o600)

    def create(self, username, password, role=perm.ROLE_VIEWER,
               display="", created_by=""):
        users = self.all()
        if username in users:
            raise ValueError("username sudah dipakai")
        users[username] = self._blank(username, display or username, role,
                                      password, created_by)
        self.save_all(users)
        return users[username]

    def _blank(self, username, display, role, password, created_by):
        now = int(time.time())
        return {
            "username": username,
            "display": display,
            "role": role,
            "password": crypto.hash_password(password),
            "totp": None,
            "recovery": [],
            "created": now,
            "created_by": created_by,
            "updated": now,
            "last_login": 0,
            "disabled": False,
        }

    def update(self, username, **fields):
        users = self.all()
        if username not in users:
            raise ValueError("user tidak ditemukan")
        users[username].update(fields)
        users[username]["updated"] = int(time.time())
        self.save_all(users)
        return users[username]

    def set_password(self, username, password):
        return self.update(username, password=crypto.hash_password(password))

    def set_role(self, username, role):
        if role not in perm.ROLE_ORDER:
            raise ValueError("role tidak dikenal: %s" % role)
        if self.is_last_admin(username) and role != perm.ROLE_ADMIN:
            raise ValueError("tidak bisa menurunkan administrator terakhir")
        return self.update(username, role=role)

    def disable(self, username, disabled=True):
        if disabled and self.is_last_admin(username):
            raise ValueError("tidak bisa menonaktifkan administrator terakhir")
        return self.update(username, disabled=bool(disabled))

    def delete(self, username, actor=""):
        if self.is_last_admin(username):
            raise ValueError("tidak bisa menghapus administrator terakhir")
        users = self.all()
        if username not in users:
            raise ValueError("user tidak ditemukan")
        users.pop(username)
        self.save_all(users)
        return True

    # ---------- 2FA ----------

    def start_totp(self, username):
        """Buat secret baru; BELUM aktif sampai verify_totp dipanggil."""
        secret = crypto.generate_totp_secret()
        self.update(username, totp_pending=secret)
        label = "%s@%s" % (username, _hostname())
        return secret, crypto.otpauth_uri(secret, label)

    def verify_totp(self, username, code):
        """Aktifkan 2FA setelah kode pertama terverifikasi; hasilkan recovery codes."""
        u = self.get(username)
        if not u:
            return None
        secret = u.get("totp_pending") or u.get("totp")
        if not secret or not crypto.totp_verify(secret, code):
            return None
        codes = crypto.new_recovery_codes(RECOVERY_COUNT)
        self.update(
            username,
            totp=secret,
            totp_pending=None,
            recovery=[crypto.sha256_hex(c) for c in codes],
        )
        return codes

    def disable_totp(self, username):
        return self.update(username, totp=None, totp_pending=None, recovery=[])

    def check_code(self, user, code):
        """Terima kode TOTP atau kode recovery sekali-pakai."""
        if not code:
            return False
        code = str(code).strip().lower()
        secret = user.get("totp")
        if secret and crypto.totp_verify(secret, code):
            return True
        if secret and code:
            hashed = crypto.sha256_hex(code)
            left = [h for h in (user.get("recovery") or []) if h != hashed]
            if len(left) != len(user.get("recovery") or []):
                self.update(user["username"], recovery=left)
                return True
        return False

    def recovery_left(self, username):
        u = self.get(username) or {}
        return len(u.get("recovery") or [])

    def touch_login(self, username):
        try:
            self.update(username, last_login=int(time.time()))
        except ValueError:
            pass

    # ---------- kompatibilitas panel lama ----------

    def import_legacy(self, username, password_hash, totp_secret,
                      recovery_hashes=None, role=perm.ROLE_ADMIN):
        """Impor satu akun dari format panel lama (config.json)."""
        users = self.all()
        if username in users:
            return False
        users[username] = {
            "username": username,
            "display": username,
            "role": role,
            "password": password_hash,
            "totp": totp_secret or None,
            "recovery": list(recovery_hashes or []),
            "created": int(time.time()),
            "created_by": "import",
            "updated": int(time.time()),
            "last_login": 0,
            "disabled": False,
        }
        self.save_all(users)
        return True
