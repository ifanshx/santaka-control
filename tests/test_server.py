"""Uji integrasi HTTP: setup awal, login, CSRF, sesi, dan header keamanan."""
import importlib
import http.client
import json
import os
import re
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer


def _csrf(html):
    m = re.search(r'name="csrf" value="([^"]+)"', html)
    return m.group(1) if m else ""


class ServerFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cfg_path = os.path.join(cls.tmp.name, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump({"secret": "test-secret", "bind": "127.0.0.1",
                       "hostname": "panel.test", "session_ttl": 3600,
                       "login_attempts": 50, "roots": [cls.tmp.name]}, fh)
        os.environ["SANTANTAKA_CONFIG"] = cfg_path
        os.environ["SANTANTAKA_DATA"] = os.path.join(cls.tmp.name, "data")
        import server
        cls.server = importlib.reload(server)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), cls.server.Handler)
        cls.httpd.daemon_threads = True
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()
        os.environ.pop("SANTANTAKA_CONFIG", None)
        os.environ.pop("SANTANTAKA_DATA", None)

    def call(self, method, path, body=None, headers=None, cookie=None):
        h = {"Connection": "close", "Host": "panel.test"}
        h.update(headers or {})
        if cookie:
            h["Cookie"] = cookie
        if body is not None and "Content-Type" not in h:
            h["Content-Type"] = "application/x-www-form-urlencoded"
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        try:
            conn.request(method, path, body=body, headers=h)
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, dict(resp.getheaders()), data.decode("utf-8", "replace")
        finally:
            conn.close()

    def test_flow(self):
        status, headers, html = self.call("GET", "/setup")
        self.assertEqual(status, 200)
        self.assertIn("nosniff", headers.get("X-Content-Type-Options", ""))
        self.assertNotIn("Python/", headers.get("Server", ""))
        self.assertIn("nonce-", headers.get("Content-Security-Policy", ""))

        token = _csrf(html)
        self.assertTrue(token)
        form = "csrf=%s&username=owner&password=AdminPass123" % token
        status, headers, _ = self.call("POST", "/setup", form,
                                       {"Origin": "http://panel.test"})
        self.assertEqual(status, 303, headers)

        # Login tanpa CSRF ditolak.
        status, _, body = self.call("POST", "/login", "username=owner&password=AdminPass123",
                                    {"Origin": "http://panel.test"})
        self.assertEqual(status, 403)
        audit_path = os.path.join(os.environ["SANTANTAKA_DATA"], "audit.log.jsonl")
        with open(audit_path, encoding="utf-8") as fh:
            self.assertIn("login:csrf", fh.read())

        status, _, html = self.call("GET", "/login")
        self.assertEqual(status, 200)
        token = _csrf(html)
        status, headers, _ = self.call(
            "POST", "/login",
            "csrf=%s&username=owner&password=AdminPass123" % token,
            {"Origin": "http://panel.test"})
        self.assertEqual(status, 303, headers)
        cookie = headers.get("Set-Cookie", "")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertNotIn("Secure", cookie)   # panel diakses via HTTP polos

        sid = cookie.split(";", 1)[0]
        status, _, page = self.call("GET", "/dash", cookie=sid)
        self.assertEqual(status, 200)
        self.assertIn("dashboard", page.lower())

        status, headers, body = self.call("GET", "/api/stats", cookie=sid)
        self.assertEqual(status, 200, body[:200])
        self.assertIn("data", json.loads(body))

        status, _, body = self.call("GET", "/api/stats")
        self.assertEqual(status, 401)
        self.assertTrue(json.loads(body).get("login"))

        status, _, body = self.call("POST", "/api/logout", "x=1", cookie=sid)
        self.assertEqual(status, 403)

        status, _, body = self.call("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["users"], 1)

    def test_origin_mismatch_blocked(self):
        status, _, body = self.call(
            "POST", "/login", "username=owner&password=x",
            {"Origin": "http://evil.example"})
        self.assertIn(status, (403, 401))


if __name__ == "__main__":
    unittest.main()
