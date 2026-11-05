"""Audit trail aksi mutasi: siapa, kapan, target, hasil. JSONL + rotasi."""
import os
import time

from . import store

ACTION = "action"
LOGIN = "login"
DENIED = "denied"


class Auditor:
    def __init__(self, path, max_bytes=2_000_000):
        self.path = path
        self.max_bytes = max_bytes
        self._writes = 0

    def write(self, kind, user, action, target="", result="ok", detail="", ip=""):
        if isinstance(user, dict):
            uname = user.get("username") or "-"
            urole = user.get("role") or ""
        else:
            uname = user or "-"
            urole = ""
        store.append_jsonl(self.path, {
            "ts": int(time.time()),
            "iso": time.strftime("%Y-%m-%d %H:%M:%S"),
            "kind": kind,
            "user": uname,
            "role": urole,
            "action": action,
            "target": target,
            "result": result,
            "detail": detail[:500],
            "ip": ip,
        })
        self._writes += 1
        if self._writes % 200 == 0:
            store.rotate_jsonl(self.path, self.max_bytes)

    def list(self, limit=200, query=None):
        return store.tail_jsonl(self.path, limit=limit, query=query)
