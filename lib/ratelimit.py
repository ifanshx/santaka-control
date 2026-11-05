"""Rate limit in-memory: jendela geser sederhana, tanpa dependensi."""
import threading
import time


class RateLimiter:
    def __init__(self):
        self._hits = {}
        self._lock = threading.Lock()

    def allow(self, key, limit, window):
        """Catat percobaan. True bila masih di bawah `limit` dalam `window` detik."""
        now = time.time()
        with self._lock:
            bucket = [t for t in self._hits.get(key, []) if now - t < window]
            allowed = len(bucket) < limit
            bucket.append(now)
            self._hits[key] = bucket
            if len(self._hits) > 4096:
                self._sweep(now)
            return allowed

    def fails(self, key, window):
        now = time.time()
        with self._lock:
            return len([t for t in self._hits.get(key, []) if now - t < window])

    def reset(self, key):
        with self._lock:
            self._hits.pop(key, None)

    def _sweep(self, now):
        for k in list(self._hits.keys()):
            if not [t for t in self._hits[k] if now - t < 86400]:
                self._hits.pop(k, None)


class Backoff:
    """Penundaan bertahap setelah beberapa kegagalan (anti brute-force)."""

    def __init__(self, free_attempts=3, base=0.5, cap=4.0):
        self.free = free_attempts
        self.base = base
        self.cap = cap

    def delay_for(self, fail_count):
        if fail_count <= self.free:
            return 0.0
        n = fail_count - self.free
        return min(self.cap, self.base * (2 ** (n - 1)))
