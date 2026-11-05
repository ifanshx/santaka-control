"""Operasi Redis: status memori, client aktif, hit rate, dan pembersihan cache."""
from . import cmd

class RedisError(Exception):
    pass


def info():
    """Ambil ringkasan performa dan memori Redis."""
    rc, out, err = cmd.run(["redis-cli", "info"], timeout=5)
    if rc != 0:
        return {
            "active": False,
            "error": (err or out or "Redis tidak berjalan").strip()[:100],
            "used_memory": "0 MB",
            "maxmemory": "64 MB",
            "keys": 0,
            "clients": 0,
            "uptime_days": 0,
            "hit_rate": "0%",
        }

    raw = {}
    for line in (out or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        raw[k.strip()] = v.strip()

    # Hitung total keys di db0
    keys_count = 0
    db0 = raw.get("db0", "")
    if "keys=" in db0:
        try:
            keys_count = int(db0.split("keys=")[1].split(",")[0])
        except (IndexError, ValueError):
            pass

    # Hit rate
    hits = int(raw.get("keyspace_hits", 0) or 0)
    misses = int(raw.get("keyspace_misses", 0) or 0)
    total_ops = hits + misses
    hit_rate = f"{(hits / total_ops * 100):.1f}%" if total_ops > 0 else "100%"

    return {
        "active": True,
        "version": raw.get("redis_version", "7.0"),
        "used_memory": raw.get("used_memory_human", "0M"),
        "used_memory_rss": raw.get("used_memory_rss_human", "0M"),
        "maxmemory": raw.get("maxmemory_human", "64.00M"),
        "maxmemory_policy": raw.get("maxmemory_policy", "allkeys-lru"),
        "keys": keys_count,
        "clients": int(raw.get("connected_clients", 0) or 0),
        "uptime_days": int(raw.get("uptime_in_days", 0) or 0),
        "hit_rate": hit_rate,
        "ops_per_sec": int(raw.get("instantaneous_ops_per_sec", 0) or 0),
    }


def flush_all():
    """Bersihkan seluruh cache keys di Redis."""
    rc, out, err = cmd.run(["redis-cli", "flushall"], timeout=10)
    if rc != 0:
        raise RedisError(err or out or "Gagal membersihkan Redis")
    return True


def ping():
    """Uji latency roundtrip ke socket Redis."""
    import time
    t0 = time.perf_counter()
    rc, out, err = cmd.run(["redis-cli", "ping"], timeout=3)
    dt_ms = (time.perf_counter() - t0) * 1000
    if rc != 0:
        raise RedisError(err or out or "Ping gagal")
    return {"response": (out or "").strip(), "latency_ms": round(dt_ms, 2)}


def list_keys(pattern="*", count=100):
    """Scan keys di Redis secara non-blocking."""
    pattern = (pattern or "*").strip() or "*"
    rc, out, err = cmd.run(["redis-cli", "--raw", "scan", "0", "match", pattern, "count", str(count)], timeout=5)
    if rc != 0:
        raise RedisError(err or out or "Scan gagal")
    lines = [l.strip() for l in (out or "").splitlines() if l.strip()]
    if not lines or len(lines) <= 1:
        return []
    # Baris pertama adalah cursor scanner berikutnya, baris 1+ adalah keys
    keys = lines[1:]
    items = []
    for k in keys[:count]:
        k = k.strip()
        if not k:
            continue
        rc_t, out_t, _ = cmd.run(["redis-cli", "--raw", "type", k], timeout=2)
        rc_ttl, out_ttl, _ = cmd.run(["redis-cli", "--raw", "ttl", k], timeout=2)
        ttl_val = -1
        try:
            ttl_val = int((out_ttl or "").strip())
        except ValueError:
            pass
        items.append({
            "key": k,
            "type": (out_t or "string").strip(),
            "ttl": ttl_val,
        })
    items.sort(key=lambda x: x["key"])
    return items


def get_key(key):
    """Ambil detail tipe, TTL, dan nilai value dari key."""
    key = (key or "").strip()
    if not key:
        raise RedisError("Key tidak boleh kosong")
    rc_t, out_t, _ = cmd.run(["redis-cli", "--raw", "type", key], timeout=2)
    k_type = (out_t or "string").strip()
    if k_type == "string":
        rc, out, err = cmd.run(["redis-cli", "--raw", "get", key], timeout=5)
    elif k_type == "hash":
        rc, out, err = cmd.run(["redis-cli", "hgetall", key], timeout=5)
    elif k_type == "list":
        rc, out, err = cmd.run(["redis-cli", "lrange", key, "0", "50"], timeout=5)
    elif k_type in ("set", "zset"):
        rc, out, err = cmd.run(["redis-cli", "smembers" if k_type == "set" else "zrange", key, "0", "50"], timeout=5)
    else:
        rc, out, err = cmd.run(["redis-cli", "--raw", "dump", key], timeout=5)
    rc_ttl, out_ttl, _ = cmd.run(["redis-cli", "--raw", "ttl", key], timeout=2)
    ttl_val = -1
    try:
        ttl_val = int((out_ttl or "").strip())
    except ValueError:
        pass
    return {
        "key": key,
        "type": k_type,
        "ttl": ttl_val,
        "value": (out or "")[:4000],
    }


def set_key(key, value, ttl=None):
    """Simpan key-value baru ke Redis dengan opsi TTL."""
    key = (key or "").strip()
    if not key:
        raise RedisError("Key tidak boleh kosong")
    args = ["redis-cli", "set", key, str(value or "")]
    if ttl:
        try:
            ttl_sec = int(ttl)
            if ttl_sec > 0:
                args += ["ex", str(ttl_sec)]
        except ValueError:
            pass
    rc, out, err = cmd.run(args, timeout=5)
    if rc != 0:
        raise RedisError(err or out or "Gagal menyimpan key")
    return True


def delete_key(key):
    """Hapus satu key dari Redis."""
    key = (key or "").strip()
    if not key:
        raise RedisError("Key tidak boleh kosong")
    rc, out, err = cmd.run(["redis-cli", "del", key], timeout=5)
    if rc != 0:
        raise RedisError(err or out or "Gagal menghapus key")
    return True
