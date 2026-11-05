"""Rate limiter jendela geser dan backoff login."""
import time
import unittest

from lib import ratelimit


class RateLimiterTest(unittest.TestCase):
    def test_blocks_after_limit(self):
        lim = ratelimit.RateLimiter()
        for _ in range(3):
            self.assertTrue(lim.allow("k", 3, 60))
        self.assertFalse(lim.allow("k", 3, 60))

    def test_window_expiry(self):
        lim = ratelimit.RateLimiter()
        self.assertTrue(lim.allow("k", 1, 0.01))
        self.assertFalse(lim.allow("k", 1, 0.01))
        time.sleep(0.02)
        self.assertTrue(lim.allow("k", 1, 0.01))

    def test_reset_and_keys_isolated(self):
        lim = ratelimit.RateLimiter()
        lim.allow("a", 1, 60)
        self.assertFalse(lim.allow("a", 1, 60))
        self.assertTrue(lim.allow("b", 1, 60))
        lim.reset("a")
        self.assertTrue(lim.allow("a", 1, 60))

    def test_fails_counts(self):
        lim = ratelimit.RateLimiter()
        lim.allow("k", 5, 60)
        lim.allow("k", 5, 60)
        self.assertEqual(lim.fails("k", 60), 2)


class BackoffTest(unittest.TestCase):
    def test_grows_then_caps(self):
        b = ratelimit.Backoff(free_attempts=2, base=0.5, cap=2.0)
        self.assertEqual(b.delay_for(0), 0.0)
        self.assertEqual(b.delay_for(2), 0.0)
        self.assertEqual(b.delay_for(3), 0.5)
        self.assertEqual(b.delay_for(4), 1.0)
        self.assertEqual(b.delay_for(99), 2.0)


if __name__ == "__main__":
    unittest.main()
