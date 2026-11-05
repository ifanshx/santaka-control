"""Sesi: cookie HMAC bertanda tangan + penyimpanan server-side (dapat dicabut)."""
import json
import os
import time

from . import crypto, store

COOKIE_NAME = "sc_session"
SESSION_TTL = 12 * 3600
RENEW_AFTER = 2 * 3600


class SessionManager:
    def __init__(self, path, secret, cookie=COOKIE_NAME, ttl=SESSION_TTL):
        self.path = path
        self.secret = secret
        self.cookie = cookie
        self.ttl = ttl

    # ---------- internal ----------

    def _load(self):
        return store.read_json(self.path, {}) or {}

    def _save(self, data):
        store.write_json(self.path, data)

    @staticmethod
    def _purge(data):
        now = int(time.time())
        return {k: v for k, v in data.items()
                if isinstance(v, dict) and v.get("exp", 0) > now}

    # ---------- publik ----------

    def create(self, user, ip="", agent=""):
        data = self._purge(self._load())
        sid = crypto.new_token(24)
        data[sid] = {
            "u": user["username"],
            "role": user.get("role", "viewer"),
            "exp": int(time.time()) + self.ttl,
            "ip": ip,
            "agent": agent[:120],
            "created": int(time.time()),
        }
        self._save(data)
        return self._token(sid)

    def _token(self, sid):
        return "%s.%s" % (sid, crypto.sign(sid, self.secret))

    def _sid(self, token):
        if not token or "." not in token:
            return None
        sid, sig = token.rsplit(".", 1)
        if not crypto.verify_sig(sid, sig, self.secret):
            return None
        return sid

    def get(self, token):
        """Kembalikan dict sesi atau None. Perpanjang bila hampir kedaluwarsa."""
        sid = self._sid(token)
        if not sid:
            return None
        data = self._load()
        rec = data.get(sid)
        if not rec or rec.get("exp", 0) <= time.time():
            if rec:
                data.pop(sid, None)
                self._save(data)
            return None
        if rec["exp"] - time.time() < (self.ttl - RENEW_AFTER):
            rec["exp"] = int(time.time()) + self.ttl
            data[sid] = rec
            self._save(data)
        rec["sid"] = sid
        return rec

    def destroy(self, token):
        sid = self._sid(token)
        if not sid:
            return False
        data = self._load()
        if sid in data:
            data.pop(sid)
            self._save(data)
            return True
        return False

    def destroy_user(self, username, keep_sid=None):
        """Cabut semua sesi milik user (dipakai saat ganti password / hapus akun)."""
        data = self._purge(self._load())
        removed = 0
        for sid, rec in list(data.items()):
            if rec.get("u") == username and sid != keep_sid:
                data.pop(sid)
                removed += 1
        self._save(data)
        return removed

    def list(self):
        """Daftar sesi aktif (terbaru dulu), tanpa token."""
        data = self._purge(self._load())
        rows = []
        for sid, rec in data.items():
            rows.append({
                "sid": sid[:10] + "…",
                "sid_full": sid,
                "user": rec.get("u"),
                "role": rec.get("role"),
                "ip": rec.get("ip", ""),
                "created": rec.get("created", 0),
                "exp": rec.get("exp", 0),
            })
        rows.sort(key=lambda r: r.get("created", 0), reverse=True)
        return rows


def csrf_for(sid, secret):
    """Token CSRF terikat ke sesi (HMAC dari sid). Deterministik per sesi."""
    return crypto.sign("csrf:" + (sid or "anon"), secret)
