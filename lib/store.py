"""Penyimpanan JSON atomik: users, config, sesi. Menulis lewat file sementara."""
import json
import os
import tempfile
import threading

_locks = {}
_global = threading.Lock()


def _lock_for(path):
    with _global:
        if path not in _locks:
            _locks[path] = threading.RLock()
        return _locks[path]


def read_json(path, default=None):
    """Baca JSON. File rusak/tidak ada -> default (tidak melempar)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def write_json(path, data, mode=0o600):
    """Tulis JSON secara atomik: temp file di direktori sama, lalu os.replace."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    with _lock_for(path):
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp, mode)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    return True


def append_jsonl(path, record, mode=0o600):
    """Tambah satu baris JSON (untuk audit log)."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    with _lock_for(path):
        new = not os.path.exists(path)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()
        if new:
            try:
                os.chmod(path, mode)
            except OSError:
                pass


def tail_jsonl(path, limit=200, query=None):
    """Ambil `limit` baris terakhir, terbaru dulu. Filter `query` (lowercase)."""
    rows = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if query:
                    blob = json.dumps(rec, ensure_ascii=False).lower()
                    if query not in blob:
                        continue
                rows.append(rec)
    except OSError:
        return []
    return list(reversed(rows[-limit:]))


def rotate_jsonl(path, max_bytes=2_000_000, keep=2):
    """Rotasi sederhana bila file audit melebihi max_bytes."""
    try:
        if os.path.getsize(path) < max_bytes:
            return False
    except OSError:
        return False
    with _lock_for(path):
        for i in range(keep, 0, -1):
            src = "%s.%d" % (path, i - 1) if i > 1 else path
            dst = "%s.%d" % (path, i)
            if os.path.exists(src):
                try:
                    os.replace(src, dst)
                except OSError:
                    pass
    return True
