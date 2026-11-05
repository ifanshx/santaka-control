"""Penyimpanan JSON/JSONL: penulisan atomik, berkas rusak, dan rotasi audit."""
import json
import os
import tempfile
import unittest

from lib import store


class JsonStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip_creates_directory(self):
        path = os.path.join(self.dir, "sub", "data.json")
        store.write_json(path, {"nama": "Sérver", "n": 1})
        self.assertEqual(store.read_json(path), {"nama": "Sérver", "n": 1})

    def test_missing_and_corrupt_return_default(self):
        path = os.path.join(self.dir, "x.json")
        self.assertEqual(store.read_json(path, {}), {})
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{rusak")
        self.assertIsNone(store.read_json(path))
        self.assertEqual(store.read_json(path, {"a": 1}), {"a": 1})

    def test_no_temp_files_left_behind(self):
        path = os.path.join(self.dir, "y.json")
        store.write_json(path, {"a": 1})
        self.assertEqual([n for n in os.listdir(self.dir) if n.startswith(".tmp-")], [])


class JsonlStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "audit.log.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_tail_is_newest_first_and_filtered(self):
        for i in range(5):
            store.append_jsonl(self.path, {"i": i, "who": "ops" if i % 2 else "root"})
        rows = store.tail_jsonl(self.path, limit=3)
        self.assertEqual([r["i"] for r in rows], [4, 3, 2])
        only_root = store.tail_jsonl(self.path, limit=10, query="root")
        self.assertEqual([r["i"] for r in only_root], [4, 2, 0])

    def test_skips_corrupt_lines(self):
        store.append_jsonl(self.path, {"ok": True})
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write("bukan json\n")
        store.append_jsonl(self.path, {"ok": False})
        rows = store.tail_jsonl(self.path)
        self.assertEqual(len(rows), 2)

    def test_rotate_moves_old_file(self):
        store.append_jsonl(self.path, {"x": "a" * 100})
        self.assertTrue(store.rotate_jsonl(self.path, max_bytes=10, keep=2))
        self.assertTrue(os.path.exists(self.path + ".1"))
        self.assertFalse(store.rotate_jsonl(self.path, max_bytes=10, keep=2))


if __name__ == "__main__":
    unittest.main()
