"""Regresi daftar vhost: potongan konfigurasi dan endpoint status bukan situs."""
import os
import tempfile
import unittest

from lib import nginxops


class ListVhostsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self._old_dir = nginxops.VHOST_DIR
        nginxops.VHOST_DIR = self.dir.name
        self.addCleanup(setattr, nginxops, "VHOST_DIR", self._old_dir)

    def _write(self, name, body):
        with open(os.path.join(self.dir.name, name), "w", encoding="utf-8") as fh:
            fh.write(body)

    def test_only_real_server_blocks_are_listed(self):
        self._write("0.websocket.conf", "map $http_upgrade $connection_upgrade { default upgrade; }\n")
        self._write("waf2monitor_data.conf", "map $http_host $waf2monitor_blocked { default \"\"; }\n")
        self._write(
            "phpfpm_status.conf",
            "server {\n  listen 80;\n  server_name 127.0.0.1;\n  location /nginx_status { stub_status on; }\n}\n",
        )
        self._write(
            "example.com.conf",
            "server {\n  listen 80;\n  server_name example.com www.example.com;\n  root /var/www/example;\n}\n",
        )
        rows = nginxops.list_vhosts()
        self.assertEqual([row["domain"] for row in rows], ["example.com"])
        self.assertEqual(rows[0]["aliases"], ["www.example.com"])
        self.assertEqual(rows[0]["root"], "/var/www/example")
