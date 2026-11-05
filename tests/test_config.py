"""Konfigurasi runtime: semua modul memakai lokasi dari config.json.

Regresi: dulu path /www/wwwroot, /www/wwwlogs, /mnt/data/backup, dan domain
santaka.my.id tertanam di kode sehingga panel tidak bisa dipasang di host lain.
"""
import os
import tempfile
import unittest

from lib import apps_engine, backupops, dbops, nginxops, stats


class ConfigureTest(unittest.TestCase):
    def tearDown(self):
        for mod in (nginxops, backupops, dbops, apps_engine, stats):
            mod.configure({})

    def test_nginx_paths(self):
        www = os.path.abspath("/srv/www")
        logs = os.path.abspath("/var/log/nx")
        nginxops.configure({"web_root": www, "nginx_log_dir": logs})
        self.assertEqual(nginxops.site_root("a.test"), os.path.join(www, "a.test"))
        self.assertEqual(nginxops.log_path("a.test"), os.path.join(logs, "a.test.log"))
        self.assertEqual(nginxops.log_path("a.test", error=True),
                         os.path.join(logs, "a.test.error.log"))

    def test_nginx_bin_prefers_config(self):
        with tempfile.NamedTemporaryFile(suffix="-nginx") as fh:
            nginxops.configure({"nginx_bin": fh.name})
            self.assertEqual(nginxops.NGINX_BIN, fh.name)

    def test_backup_and_dump_dirs(self):
        backupops.configure({"backup_dir": "/srv/cadangan"})
        dbops.configure({"backup_dir": "/srv/cadangan"})
        self.assertEqual(os.path.basename(backupops.SUMS), "SHA256SUMS.txt")
        self.assertEqual(os.path.dirname(backupops.SUMS), os.path.abspath("/srv/cadangan"))
        self.assertEqual(dbops.DUMP_DIR, os.path.join(os.path.abspath("/srv/cadangan"), "db"))

    def test_apps_domains_and_caddy(self):
        apps_engine.configure({"apps_lan_domain": "lan", "apps_domain": "example.test"})
        self.assertEqual(apps_engine._lan_host("shop"), "shop.lan")
        self.assertEqual(apps_engine._public_host("shop"), "shop.example.test")
        block = apps_engine.caddy_block({"slug": "shop", "kind": "static",
                                         "path": "/tmp/app", "custom_domains": []})
        self.assertIn("http://shop.lan", block)
        self.assertIn("http://shop.example.test", block)
        self.assertNotIn("santaka.my.id", block)

    def test_apps_without_domains_uses_default_addr(self):
        apps_engine.configure({})
        block = apps_engine.caddy_block({"slug": "x", "kind": "static",
                                         "path": "/tmp", "custom_domains": []})
        self.assertTrue(block.splitlines()[1].startswith(":80 {"))

    def test_apps_state_paths(self):
        apps_engine.configure({"apps_dir": "/srv/apps", "state_dir": "/srv/state"})
        self.assertEqual(apps_engine.APPS_CONF,
                         os.path.join(os.path.abspath("/srv/apps"), "apps.json"))
        self.assertEqual(apps_engine.DB_SECRET_FILE,
                         os.path.join(os.path.abspath("/srv/state"), "db-admin.secret"))

    def test_stats_extra_mounts(self):
        stats.configure({"data_mount": "/srv/data"})
        self.assertIn("/srv/data", stats.EXTRA_MOUNTS)
        stats.configure({"data_mount": "/"})
        self.assertEqual(stats.EXTRA_MOUNTS, ())


class ServerDefaultsTest(unittest.TestCase):
    def test_defaults_are_kebab_free_and_documented(self):
        import server
        cfg = server.DEFAULT_CONFIG
        for key in ("web_root", "nginx_log_dir", "backup_dir", "state_dir",
                    "apps_dir", "caddyfile", "data_mount", "terminal_user",
                    "phpmyadmin_url", "apps_domain", "apps_lan_domain"):
            self.assertIn(key, cfg, key)
        self.assertEqual(cfg["bind"], "127.0.0.1")
        self.assertTrue(cfg["roots"])
        self.assertNotIn("/mnt/data", cfg["roots"])


if __name__ == "__main__":
    unittest.main()
