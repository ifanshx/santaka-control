#!/usr/bin/env python3
"""Santaka Control — panel kendali server untuk STB B860H-V1.

Hanya pustaka standar Python 3. Server-rendered HTML + sedikit JS.
Sasaran memori: <= 35 MB RSS. Nol dependensi, nol build step.

Model keamanan
  * Kata sandi: PBKDF2-SHA256 (200k iterasi), perbandingan waktu konstan.
  * Sesi: cookie HMAC bertanda tangan + penyimpanan server-side (dapat dicabut).
  * Setiap POST wajib menyertakan token CSRF + memeriksa Origin.
  * Setiap route menyatakan izin yang dibutuhkan; role menentukan izin.
  * Semua perintah dijalankan sebagai array argumen (tanpa shell).
  * Galat tidak pernah membocorkan stack trace ke klien.
"""
import json
import os
import secrets
import sys
import time
import traceback
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from lib import (apps_engine, audit, backupops, crypto, dbops, nginxops, perm,
                 ratelimit, session, stats, store, users, validate)
from ui import i18n, layout as uilayout
from ui import pages
from routes import api as api_routes

# Lokasi berkas bisa dipindah lewat env: berguna untuk paket (.deb), container,
# dan pengujian integrasi tanpa menyentuh direktori aplikasi.
CONFIG_PATH = os.environ.get("SANTANTAKA_CONFIG") or os.path.join(BASE, "config.json")
DATA_DIR = os.environ.get("SANTANTAKA_DATA") or os.path.join(BASE, "data")
USERS_PATH = os.path.join(DATA_DIR, "users.json")
SESSIONS_PATH = os.path.join(DATA_DIR, "sessions.json")
AUDIT_PATH = os.path.join(DATA_DIR, "audit.log.jsonl")
STATIC_DIR = os.path.join(BASE, "ui", "static")

DEFAULT_CONFIG = {
    "port": 8081,
    # Hanya loopback secara default: taruh di belakang reverse proxy ber-TLS.
    "bind": "127.0.0.1",
    "hostname": "santaka.local",
    # Prefix mount bila panel dipasang di sub-path (mis. "/control").
    # Proxy mengupas prefix ini; panel memakainya untuk membuat tautan/redirect.
    "base_path": "",
    "secret": "",
    "disk_path": "/",
    # Direktori yang boleh dijelajahi File Explorer.
    "roots": ["/var/www", "/srv", "/opt", "/home"],
    "session_ttl": 12 * 3600,
    "login_attempts": 6,
    "login_window": 300,
    # --- integrasi web server ---
    "web_root": "/var/www",
    "nginx_bin": "",
    "nginx_vhost_dir": "",
    "nginx_conf": "",
    "nginx_log_dir": "/var/log/nginx",
    "caddyfile": "/etc/caddy/Caddyfile",
    "apps_dir": "/opt/santaka-apps",
    "apps_domain": "",
    "apps_lan_domain": "",
    "php_pool_dir": "/etc/php/8.2/fpm/pool.d",
    # --- penyimpanan & status ---
    "data_mount": "/mnt/data",
    "backup_dir": "/var/backups/santaka",
    "state_dir": "/var/lib/santaka-control",
    # --- antarmuka ---
    "phpmyadmin_url": "",
    "terminal_user": "root",
}

MAX_BODY = 64 * 1024 * 1024   # 64 MB (unggahan berkas)

MIME = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}


def load_config():
    cfg = store.read_json(CONFIG_PATH, {}) or {}
    merged = dict(DEFAULT_CONFIG)
    merged.update(cfg)
    if not merged.get("secret"):
        merged["secret"] = crypto.new_secret()
        store.write_json(CONFIG_PATH, merged, mode=0o600)
    return merged


class App:
    """Wadah bersama: config, store, limiter, auditor."""

    def __init__(self):
        self.cfg = load_config()
        uilayout.set_base(self.cfg.get("base_path", ""))
        self.users = users.UserStore(USERS_PATH)
        self.sessions = session.SessionManager(
            SESSIONS_PATH, self.cfg["secret"], ttl=self.cfg.get("session_ttl", 12 * 3600))
        self.audit = audit.Auditor(AUDIT_PATH)
        self.limiter = ratelimit.RateLimiter()
        # Modul yang punya lokasi runtime menerima config yang sudah dimerge.
        for mod in (nginxops, backupops, dbops, apps_engine, stats):
            try:
                mod.configure(self.cfg)
            except Exception as ex:      # konfigurasi buruk tidak boleh mematikan panel
                sys.stderr.write("[sc] konfigurasi %s dilewati: %s\n"
                                 % (mod.__name__, ex))

    def needs_setup(self):
        return self.users.count() == 0


APP = App()


class Handler(BaseHTTPRequestHandler):
    server_version = "SantakaControl"
    sys_version = ""          # jangan bocorkan versi Python
    protocol_version = "HTTP/1.1"

    def version_string(self):
        # BaseHTTPRequestHandler menggabungkan server_version + sys_version;
        # tanpa override, header Server memuat "Python/3.x.y".
        return self.server_version

    # Header keamanan yang berlaku untuk semua respons panel. CSP ketat:
    # `script-src 'self'` + nonce per-respons untuk skrip inline halaman.
    # `style-src 'unsafe-inline'` diperlukan karena panel memakai atribut style.
    CSP_TEMPLATE = (
        "default-src 'self'; script-src 'self'{nonce}; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; "
        "connect-src 'self'; object-src 'none'; base-uri 'self'; "
        "form-action 'self'; frame-ancestors 'none'"
    )

    def send_security_headers(self, nonce=None):
        csp = self.CSP_TEMPLATE.format(
            nonce=(" 'nonce-%s'" % nonce) if nonce else "")
        self.send_header("Content-Security-Policy", csp)
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=()")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        if self.is_secure:
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

    # ---------- log ke journal ----------
    def log_message(self, fmt, *args):
        try:
            sys.stderr.write("[sc] %s %s\n" % (self.address_string(), fmt % args))
            sys.stderr.flush()
        except Exception:
            pass

    # ---------- util ----------
    @property
    def ip(self):
        remote = self.client_address[0] if self.client_address else "-"
        # Percayai header proxy hanya jika request berasal dari loopback/trusted proxy
        if remote in ("127.0.0.1", "::1", "localhost"):
            cf_ip = (self.headers.get("CF-Connecting-IP") or "").strip()
            if cf_ip:
                return cf_ip
            xff = (self.headers.get("X-Forwarded-For") or "").strip()
            if xff:
                parts = [p.strip() for p in xff.split(",") if p.strip()]
                if parts:
                    return parts[0]
            x_real = (self.headers.get("X-Real-IP") or "").strip()
            if x_real:
                return x_real
        return remote

    @property
    def is_secure(self):
        proto = (self.headers.get("X-Forwarded-Proto") or "").lower()
        if proto == "https":
            return True
        cf_visitor = self.headers.get("CF-Visitor") or ""
        if '"scheme":"https"' in cf_visitor:
            return True
        if self.headers.get("CF-Connecting-IP") and (self.client_address[0] if self.client_address else "") in ("127.0.0.1", "::1"):
            return True
        return False

    def lang(self):
        raw = self.headers.get("Cookie", "")
        c = SimpleCookie()
        try:
            c.load(raw)
        except Exception:
            pass
        code = (c["sc_lang"].value if "sc_lang" in c else "id") or "id"
        return code if code in i18n.LANGS else "id"

    def theme(self):
        raw = self.headers.get("Cookie", "")
        c = SimpleCookie()
        try:
            c.load(raw)
        except Exception:
            pass
        val = c["sc_theme"].value if "sc_theme" in c else "paper"
        return val if val in ("paper", "night") else "paper"

    def session(self):
        raw = self.headers.get("Cookie", "")
        c = SimpleCookie()
        try:
            c.load(raw)
        except Exception:
            pass
        token = c[APP.sessions.cookie].value if APP.sessions.cookie in c else ""
        if not token:
            return None
        rec = APP.sessions.get(token)
        if not rec:
            return None
        u = APP.users.get(rec.get("u"))
        if not u or u.get("disabled"):
            return None
        return {"username": u["username"], "role": u.get("role", "viewer"),
                "sid": rec.get("sid"), "must_change": u.get("must_change", False),
                "theme": self.theme(), "lang": self.lang()}

    def csrf_token(self, sess):
        """CSRF terikat ke sesi + rahasia server."""
        sid = (sess or {}).get("sid") or "anon"
        return crypto.sign("csrf:" + sid, APP.cfg["secret"])

    def check_csrf(self, form, sess):
        """Verifikasi token CSRF (form) atau header X-CSRF (fetch). Gagal = tolak."""
        got = ""
        if form:
            v = form.get("csrf")
            if isinstance(v, list) and v:
                got = str(v[0] or "")
        if not got:
            got = self.headers.get("X-CSRF", "") or ""
        if not got:
            return False
        sid = (sess or {}).get("sid") or "anon"
        return crypto.verify_sig("csrf:" + sid, got, APP.cfg["secret"])

    def check_origin(self):
        """Blokir POST lintas situs (lapisan kedua setelah CSRF)."""
        origin = self.headers.get("Origin")
        if not origin:
            return True                      # klien non-browser / same-origin lama
        host = (self.headers.get("Host") or "").lower()
        try:
            from urllib.parse import urlparse
            parsed = urlparse(origin)
            return (parsed.netloc or "").lower() == host
        except Exception:
            return False

    # ---------- pengiriman respons ----------
    def send_html(self, html, status=200, cookies=None):
        # Nonce per-respons: skrip inline halaman diberi izin lewat CSP,
        # tanpa perlu melonggarkan `script-src` ke 'unsafe-inline'.
        nonce = secrets.token_urlsafe(16)
        if "<script>" in html:
            html = html.replace("<script>", '<script nonce="%s">' % nonce)
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Cache-Control", "no-store")
        # Panel admin tidak boleh diindeks mesin pencari mana pun.
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_security_headers(nonce)
        for c in (cookies or []):
            self.send_header("Set-Cookie", c)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, data, status=200, cookies=None):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_security_headers()
        for c in (cookies or []):
            self.send_header("Set-Cookie", c)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_static(self, relpath):
        """Sajikan berkas statis dengan pengecekan containment yang portabel."""
        from urllib.parse import unquote
        rel = unquote(relpath or "").replace("\\", "/")
        if not rel or rel.startswith("/") or ".." in rel.split("/"):
            return self.send_json({"error": "terlarang"}, 403)
        root = os.path.realpath(STATIC_DIR)
        full = os.path.realpath(os.path.join(root, *rel.split("/")))
        try:
            inside = os.path.commonpath([root, full]) == root
        except ValueError:
            inside = False
        if not inside or full == root:
            return self.send_json({"error": "terlarang"}, 403)
        if not os.path.isfile(full):
            return self.send_json({"error": "tidak ditemukan"}, 404)
        ext = os.path.splitext(full)[1].lower()
        try:
            st = os.stat(full)
        except OSError:
            return self.send_json({"error": "tidak ditemukan"}, 404)
        # ETag dari mtime+ukuran: cukup unik, tanpa hashing isi berkas.
        etag = '"%x-%x"' % (int(st.st_mtime), st.st_size)
        # Aset direferensikan sebagai /static/x?v=<hash>. Karena query ikut
        # menjadi kunci cache peramban, versi ber-hash aman di-cache selamanya.
        versioned = "v=" in (urlparse(self.path).query or "")
        cache = ("public, max-age=31536000, immutable" if versioned
                 else "public, max-age=86400")

        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", cache)
            self.end_headers()
            return

        try:
            with open(full, "rb") as fh:
                body = fh.read()
        except OSError:
            return self.send_json({"error": "gagal membaca berkas"}, 500)
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", etag)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", cache)
        self.send_security_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def fail(self, code, message_key="st.error", t=None, detail=""):
        t = t or i18n.Translator(self.lang())
        if self.path.startswith("/api/"):
            return self.send_json({"error": t(message_key), "detail": detail}, code)
        msg = {404: "Halaman tidak ditemukan", 403: "Akses ditolak",
               400: "Permintaan tidak valid", 500: "Terjadi galat pada server"}.get(
                   code, "Galat")
        return self.send_html(uilayout.error_page(code, msg, t), code)

    # ---------- pembacaan isi ----------
    def read_form(self):
        """Kembalikan dict field -> list nilai. Batasi ukuran."""
        length = validate.safe_int(self.headers.get("Content-Length"), 0, MAX_BODY, 0)
        if not length:
            return {}
        ctype = (self.headers.get("Content-Type") or "").lower()
        raw = self.rfile.read(length)
        if ctype.startswith("application/json"):
            try:
                data = json.loads(raw.decode("utf-8", "replace") or "{}")
                return {k: [v] if not isinstance(v, list) else v
                        for k, v in (data or {}).items()}
            except ValueError:
                return {}
        if ctype.startswith("multipart/form-data"):
            return {"__multipart__": [raw], "__ctype__": [ctype]}
        try:
            return parse_qs(raw.decode("utf-8", "replace"), keep_blank_values=True)
        except Exception:
            return {}

    @staticmethod
    def fval(form, key, default=""):
        if not isinstance(form, dict):
            return default
        v = form.get(key)
        if isinstance(v, list) and v:
            val = v[0]
            if val is None or val == "" or val == "None" or val == "null":
                return default
            return str(val)
        if v is not None and v != "" and v != "None" and v != "null":
            return str(v)
        return default

    # ---------- GET ----------
    def do_GET(self):
        u = urlparse(self.path)
        path, qs = u.path, parse_qs(u.query)
        t = i18n.Translator(self.lang())

        if path.startswith("/static/"):
            return self.send_static(path[len("/static/"):])

        if path == "/favicon.svg":
            return self.send_static("favicon.svg")

        sess = self.session()

        # ---- setup awal (belum ada pengguna) ----
        if APP.needs_setup():
            if path == "/setup":
                return self.send_html(pages.setup_page(t, self.csrf_token(None),
                                                       self.theme()))
            if path != "/healthz":
                return self.send_html(uilayout.login_page(
                    t, self.csrf_token(None), lang=self.lang(), setup_needed=True))

        if path == "/healthz":
            return self.send_json({"ok": True, "ts": int(time.time()),
                                   "users": APP.users.count()})

        if path in ("/login", "/"):
            if sess:
                return self.redirect("/dash")
            return self.send_html(uilayout.login_page(
                t, self.csrf_token(None), lang=self.lang(),
                username=self.fval(qs, "u")))

        if not sess:
            t = i18n.Translator(self.lang())
            shadow = {"username": "-", "role": ""}
            APP.audit.write(audit.DENIED, shadow, "no-session", target=path,
                            result="denied", ip=self.ip)
            if path.startswith("/api/"):
                return self.send_json({"error": "sesi tidak sah", "login": True}, 401)
            return self.redirect("/login")

        # ---- API ----
        if path.startswith("/api/"):
            return api_routes.dispatch_get(self, APP, sess, path, qs, t)

        # ---- halaman ----
        page_id = path.strip("/") or "dash"
        if path == "/logout":
            tok = self._raw_session_token()
            APP.sessions.destroy(tok)
            APP.audit.write(audit.LOGIN, sess, "logout", result="ok", ip=self.ip)
            return self.redirect("/login",
                                 cookie=APP.sessions.cookie + "=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")

        handler = pages.PAGES.get(page_id)
        if not handler:
            return self.fail(404, t=t)
        needed = pages.PAGE_PERMS.get(page_id, perm.VIEW)
        if not perm.can(sess, needed):
            APP.audit.write(audit.DENIED, sess, "view:" + page_id,
                            result="denied", ip=self.ip)
            return self.fail(403, t=t)

        body = handler(self, APP, sess, qs, t)
        return self.send_html(body)

    # ---------- HEAD ----------
    def do_HEAD(self):
        return self.do_GET()

    # ---------- POST ----------
    def do_POST(self):
        u = urlparse(self.path)
        path = u.path
        t = i18n.Translator(self.lang())

        if not self.check_origin():
            return self.send_json({"error": "asal permintaan tidak sah"}, 403)

        if path.startswith("/api/upload"):
            return self._upload(path, t)

        form = self.read_form()
        sess = self.session()

        # ---- setup awal ----
        if APP.needs_setup():
            if path == "/setup":
                # Tanpa CSRF, siapa pun bisa mengklaim panel yang belum disiapkan.
                if not self.check_csrf(form, None):
                    APP.audit.write(audit.DENIED, {"username": self.fval(form, "username")},
                                    "setup:csrf", result="denied", ip=self.ip)
                    return self.fail(403, t=t)
                return self._do_setup(form, t)
            return self.fail(400, t=t, detail="panel belum disiapkan")

        # ---- login (tanpa sesi) ----
        if path == "/login":
            if not self.check_csrf(form, None):
                APP.audit.write(audit.DENIED, {"username": self.fval(form, "username")},
                                "login:csrf", result="denied", ip=self.ip)
                return self.send_html(uilayout.login_page(
                    t, self.csrf_token(None), error=t("login.errCsrf"),
                    username=self.fval(form, "username"), lang=self.lang()), 403)
            return self._do_login(form, t)
        if path == "/api/login/check":
            if not self.check_csrf(form, None):
                APP.audit.write(audit.DENIED, {"username": self.fval(form, "username")},
                                "login:csrf", result="denied", ip=self.ip)
                return self.send_json({"error": "token CSRF tidak valid"}, 403)
            return self._check_login_password(form, t)
        if not sess:
            return self.send_json({"error": "sesi tidak sah"}, 401)

        if not self.check_csrf(form, sess):
            APP.audit.write(audit.DENIED, sess, "csrf", target=path,
                            result="denied", ip=self.ip)
            return self.send_json({"error": "token CSRF tidak valid"}, 403)

        if path in ("/logout", "/api/logout"):
            APP.sessions.destroy(self._raw_session_token())
            APP.audit.write(audit.LOGIN, sess, "logout", result="ok", ip=self.ip)
            clear = (APP.sessions.cookie + "=; Path=/; Max-Age=0; HttpOnly; "
                     "SameSite=Lax" + ("; Secure" if self.is_secure else ""))
            if path == "/api/logout":
                return self.send_json({"ok": True}, cookies=[clear])
            return self.redirect("/login", cookie=clear)

        if path.startswith("/api/"):
            return api_routes.dispatch_post(self, APP, sess, path, form, t)

        # Form HTML biasa (tanpa JS): jalankan aksi lalu kembali ke halaman
        back = self.fval(form, "back", "/dash")
        return api_routes.dispatch_form(self, APP, sess, path, form, t, back)

    # ---------- upload multipart (streaming) ----------
    def _upload(self, path, t):
        sess = self.session()
        if not sess:
            return self.send_json({"error": "sesi tidak sah"}, 401)
        # Body multipart tidak bisa dibaca ulang, jadi CSRF lewat header saja.
        got = self.headers.get("X-CSRF", "") or ""
        sid = sess.get("sid") or "anon"
        if not got or not crypto.verify_sig("csrf:" + sid, got, APP.cfg["secret"]):
            APP.audit.write(audit.DENIED, sess, "upload:csrf", target=path,
                            result="denied", ip=self.ip)
            return self.send_json({"error": "token CSRF tidak valid"}, 403)
        return api_routes.handle_upload(self, APP, sess, path, t)

    # ---------- auth ----------
    def _do_setup(self, form, t):
        username = self.fval(form, "username").strip().lower()
        password = self.fval(form, "password")
        if not validate.username(username):
            return self.send_html(uilayout.login_page(
                t, self.csrf_token(None), error="Nama pengguna tidak sah (huruf kecil, 3–32 karakter).",
                lang=self.lang(), setup_needed=True), 400)
        if len(password) < 10:
            return self.send_html(uilayout.login_page(
                t, self.csrf_token(None), error="Kata sandi minimal 10 karakter.",
                lang=self.lang(), setup_needed=True), 400)
        APP.users.create(username, password, role=perm.ROLE_ADMIN,
                         display=username, created_by="setup")
        APP.audit.write(audit.LOGIN, {"username": username, "role": "admin"},
                        "setup", target=username, result="ok", ip=self.ip)
        return self.redirect("/login?u=" + username)

    def _check_login_password(self, form, t):
        """Validate credentials before revealing whether this account needs 2FA."""
        username = self.fval(form, "username").strip().lower()
        password = self.fval(form, "password")
        ip_key = "login:ip:" + self.ip
        user_key = "login:user:" + username
        ip_limit = APP.cfg.get("login_attempts", 10)
        window = APP.cfg.get("login_window", 300)
        if (not APP.limiter.allow(ip_key, ip_limit, window)
                or not APP.limiter.allow(user_key, ip_limit, window)):
            APP.audit.write(audit.DENIED, {"username": username}, "login",
                            result="ratelimited", ip=self.ip)
            return self.send_json({"error": t("login.errLock")}, 429)

        user = APP.users.get(username)
        ok_pw = bool(user) and crypto.verify_password(password, user.get("password", ""))
        if user and user.get("disabled"):
            ok_pw = False
        if not ok_pw:
            time.sleep(0.35)
            APP.audit.write(audit.DENIED, {"username": username}, "login",
                            result="badpass", ip=self.ip)
            return self.send_json({"error": t("login.err")}, 401)
        return self.send_json({"requires_2fa": bool(user.get("totp"))})

    def _do_login(self, form, t):
        username = self.fval(form, "username").strip().lower()
        password = self.fval(form, "password")
        code = self.fval(form, "code").strip()

        ip_key = "login:ip:" + self.ip
        user_key = "login:user:" + username.lower()
        ip_limit = APP.cfg.get("login_attempts", 10)
        window = APP.cfg.get("login_window", 300)
        if not APP.limiter.allow(ip_key, ip_limit, window) or not APP.limiter.allow(user_key, ip_limit, window):
            APP.audit.write(audit.DENIED, {"username": username}, "login",
                            result="ratelimited", ip=self.ip)
            return self.send_html(uilayout.login_page(
                t, self.csrf_token(None), error=t("login.errLock"),
                username=username, lang=self.lang()), 429)

        user = APP.users.get(username)
        ok_pw = bool(user) and crypto.verify_password(password, user.get("password", ""))
        if user and user.get("disabled"):
            ok_pw = False

        if not ok_pw:
            time.sleep(0.35)
            APP.audit.write(audit.DENIED, {"username": username}, "login",
                            result="badpass", ip=self.ip)
            return self.send_html(uilayout.login_page(
                t, self.csrf_token(None), error=t("login.err"),
                username=username, lang=self.lang()), 401)

        if user.get("totp"):
            if not APP.users.check_code(user, code):
                time.sleep(0.25)
                APP.audit.write(audit.DENIED, {"username": username}, "login",
                                result="bad2fa", ip=self.ip)
                return self.send_html(uilayout.login_page(
                    t, self.csrf_token(None), error=t("login.errCode"),
                    username=username, lang=self.lang(), show_code=True), 401)

        APP.limiter.reset(ip_key)
        APP.limiter.reset(user_key)
        APP.users.touch_login(username)
        token = APP.sessions.create(user, ip=self.ip,
                                    agent=self.headers.get("User-Agent", ""))
        sec_flag = "; Secure" if self.is_secure else ""
        cookie = "%s=%s; Path=/; HttpOnly; SameSite=Lax%s; Max-Age=%d" % (
            APP.sessions.cookie, token, sec_flag, APP.cfg.get("session_ttl", 12 * 3600))
        APP.audit.write(audit.LOGIN, {"username": username, "role": user.get("role")},
                        "login", result="ok", ip=self.ip)
        return self.redirect("/dash", cookie=cookie)

    # ---------- util redirect & cookie ----------
    def _raw_session_token(self):
        c = SimpleCookie()
        try:
            c.load(self.headers.get("Cookie", ""))
        except Exception:
            pass
        return c[APP.sessions.cookie].value if APP.sessions.cookie in c else ""

    def redirect(self, to, cookie=None):
        """Redirect sadar-prefix: /dash -> /control/dash bila panel di sub-path."""
        target = to
        if to.startswith("/") and not to.startswith(("//", "/api/", "/static/",
                                                     "/favicon")):
            target = uilayout.url(to)
        self.send_response(303)
        self.send_header("Location", target)
        self.send_header("Content-Length", "0")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()


def _warm_caches():
    """Isi cache lambat di latar belakang agar tampilan pertama sudah cepat."""
    import threading

    def work():
        try:
            from lib import svcmgr, stats as st
            st.snapshot(APP.cfg.get("disk_path", "/"))
            svcmgr.list_units()
            svcmgr._unit_files()
            sys.stderr.write("[sc] cache awal siap\n")
        except Exception as ex:
            sys.stderr.write("[sc] pemanasan cache dilewati: %s\n" % ex)

    threading.Thread(target=work, name="warmup", daemon=True).start()


def main():
    bind = APP.cfg.get("bind", "127.0.0.1")
    port = int(APP.cfg.get("port", 8081))
    if len(sys.argv) > 2:
        port = validate.port(sys.argv[2]) or port
    httpd = ThreadingHTTPServer((bind, port), Handler)
    httpd.daemon_threads = True
    sys.stderr.write("[sc] Santaka Control siap di http://%s:%d\n" % (bind, port))
    sys.stderr.flush()
    _warm_caches()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("[sc] berhenti\n")


if __name__ == "__main__":
    main()
