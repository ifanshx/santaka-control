"""Metrik sistem dari /proc dan /sys — tanpa perintah eksternal, sangat murah."""
import os
import time

_PREV = {}
_TEMP_ZONES = [
    "/sys/class/thermal/thermal_zone0/temp",
    "/sys/class/thermal/thermal_zone1/temp",
]


def uname():
    """Info sistem yang portabel (os.uname hanya ada di POSIX)."""
    try:
        u = os.uname()
        return {"hostname": u.nodename, "kernel": u.release, "arch": u.machine}
    except AttributeError:
        import platform
        return {"hostname": platform.node() or "localhost",
                "kernel": platform.release() or "-",
                "arch": platform.machine() or "-"}


def hardware():
    """Model perangkat & CPU dari sysfs/procfs (kosong bila tidak tersedia)."""
    model = ""
    for path in ("/proc/device-tree/model", "/sys/firmware/devicetree/base/model"):
        val = _read(path, "")
        if val:
            model = val.replace("\x00", " ").replace("\n", " ").strip()
            break
    cpu = ""
    for line in (_read("/proc/cpuinfo", "") or "").splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip().lower()
        if key in ("model name", "hardware", "model", "cpu model"):
            cpu = val.strip()
            if cpu:
                break
    if not cpu and model:
        cpu = model
    return {"model": model, "cpu": cpu, "cores": cores()}


def _read(path, default=None, limit=8192):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return default


def _num(path, default=0.0, scale=1.0):
    raw = _read(path)
    if raw is None:
        return default
    try:
        return float(raw.strip()) * scale
    except ValueError:
        return default


def uptime():
    raw = _read("/proc/uptime", "0 0")
    try:
        return int(float(raw.split()[0]))
    except (ValueError, IndexError):
        return 0


def loadavg():
    raw = _read("/proc/loadavg", "0 0 0")
    out = []
    for part in raw.split()[:3]:
        try:
            out.append(float(part))
        except ValueError:
            out.append(0.0)
    while len(out) < 3:
        out.append(0.0)
    return out


def memory():
    """Kembalikan total/used/available dalam MB + persen + swap."""
    info = {}
    for line in (_read("/proc/meminfo", "") or "").splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        try:
            info[k.strip()] = int(v.strip().split()[0])  # kB
        except (ValueError, IndexError):
            continue
    total = info.get("MemTotal", 0) / 1024.0
    avail = info.get("MemAvailable", info.get("MemFree", 0)) / 1024.0
    used = total - avail
    swap_total = info.get("SwapTotal", 0) / 1024.0
    swap_free = info.get("SwapFree", 0) / 1024.0
    return {
        "total_mb": round(total, 1),
        "used_mb": round(used, 1),
        "available_mb": round(avail, 1),
        "percent": round(used / total * 100, 1) if total else 0.0,
        "swap_total_mb": round(swap_total, 1),
        "swap_used_mb": round(swap_total - swap_free, 1),
    }


def cpu_percent():
    """Persen CPU sejak panggilan terakhir (delta jiffies)."""
    raw = _read("/proc/stat", "")
    if not raw:
        return 0.0
    line = raw.splitlines()[0]
    parts = line.split()
    if len(parts) < 5:
        return 0.0
    try:
        vals = [int(x) for x in parts[1:11]]
    except ValueError:
        return 0.0
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
    total = sum(vals)
    prev = _PREV.get("cpu")
    _PREV["cpu"] = (total, idle)
    if not prev:
        return 0.0
    dt, di = total - prev[0], idle - prev[1]
    if dt <= 0:
        return 0.0
    return round(max(0.0, min(100.0, (dt - di) / dt * 100.0)), 1)


def cores():
    return os.cpu_count() or 1


def temperature():
    """Suhu tertinggi dari zona termal yang ada (Celsius)."""
    best = None
    for zone in _TEMP_ZONES:
        val = _read(zone)
        if val is None:
            continue
        try:
            c = float(val.strip()) / 1000.0
        except ValueError:
            continue
        if 0 < c < 150 and (best is None or c > best):
            best = c
    return round(best, 1) if best is not None else None


def disk(path="/"):
    """Statistik filesystem: total/used/free GB + persen (portabel)."""
    try:
        st = os.statvfs(path)
    except AttributeError:  # non-POSIX (uji lokal di Windows)
        try:
            import shutil
            t, u, f = shutil.disk_usage(path)
            gb = 1024.0 ** 3
            return {"total_gb": round(t / gb, 2), "used_gb": round(u / gb, 2),
                    "free_gb": round(f / gb, 2),
                    "percent": round(u / t * 100, 1) if t else 0.0}
        except OSError:
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0.0}
    except OSError:
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0.0}
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    used = total - st.f_bfree * st.f_frsize
    gb = 1024.0 ** 3
    return {
        "total_gb": round(total / gb, 2),
        "used_gb": round(used / gb, 2),
        "free_gb": round(free / gb, 2),
        "percent": round(used / total * 100, 1) if total else 0.0,
    }


EXTRA_MOUNTS = ()


def configure(cfg=None):
    """Tambahkan mount yang dipantau dari config (data_mount, disk_path)."""
    global EXTRA_MOUNTS
    cfg = cfg or {}
    extra = []
    for key in ("data_mount", "disk_path"):
        val = str(cfg.get(key) or "").strip()
        if val and val != "/" and val not in extra:
            extra.append(val)
    EXTRA_MOUNTS = tuple(extra)


def mounts():
    """Daftar mount penting (/, /boot, /mnt/*, /media/*, plus config) tanpa perintah luar."""
    want = set(("/", "/boot", "/var/log", "/opt")) | set(EXTRA_MOUNTS)
    out = []
    if not os.path.exists("/proc/mounts"):   # non-Linux
        return out
    try:
        with open("/proc/mounts", "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 3:
                    continue
                dev, point, fstype = parts[0], parts[1], parts[2]
                if point in want or point.startswith(("/mnt/", "/media/")):
                    if fstype in ("tmpfs", "devtmpfs", "overlay") and point != "/":
                        continue
                    d = disk(point)
                    out.append({
                        "device": dev, "point": point, "fstype": fstype,
                        "total_gb": d["total_gb"], "used_gb": d["used_gb"],
                        "free_gb": d["free_gb"], "percent": d["percent"],
                    })
    except OSError:
        pass
    out.sort(key=lambda m: m["point"])
    return out


def net_devices():
    """Antarmuka jaringan (kecuali lo) beserta alamat IPv4-nya."""
    result = []
    base = "/sys/class/net"
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return result
    for name in names:
        if name == "lo":
            continue
        state = (_read(os.path.join(base, name, "operstate")) or "").strip()
        rx = _num(os.path.join(base, name, "statistics", "rx_bytes"))
        tx = _num(os.path.join(base, name, "statistics", "tx_bytes"))
        result.append({
            "name": name,
            "state": state or "unknown",
            "up": state == "up",
            "rx_bytes": int(rx),
            "tx_bytes": int(tx),
        })
    return result


def net_rate():
    """Kecepatan RX/TX per detik (delta dari sampling sebelumnya)."""
    devs = net_devices()
    now = time.time()
    prev = _PREV.get("net")
    rates = []
    for d in devs:
        rx_ps = tx_ps = 0.0
        if prev:
            pd = prev["devices"].get(d["name"])
            dt = now - prev["t"]
            if pd and dt > 0:
                rx_ps = max(0.0, (d["rx_bytes"] - pd["rx_bytes"]) / dt)
                tx_ps = max(0.0, (d["tx_bytes"] - pd["tx_bytes"]) / dt)
        rates.append(dict(d, rx_ps=int(rx_ps), tx_ps=int(tx_ps)))
    _PREV["net"] = {"t": now, "devices": {d["name"]: d for d in devs}}
    return rates


def processes(limit=8):
    """Proses dengan RSS terbesar (MB)."""
    rows = []
    pids = []
    try:
        for entry in os.listdir("/proc"):
            if entry.isdigit():
                pids.append(entry)
    except OSError:
        return rows
    for pid in pids:
        try:
            with open("/proc/%s/statm" % pid, "r") as fh:
                pages = int(fh.read().split()[1])
            with open("/proc/%s/cmdline" % pid, "rb") as fh:
                cmd = fh.read(128).split(b"\x00")[0].decode("utf-8", "replace")
            if not cmd:
                continue
            rows.append({"pid": int(pid), "name": os.path.basename(cmd),
                         "rss_mb": round(pages * 4096 / 1048576.0, 1)})
        except (OSError, ValueError, IndexError):
            continue
    rows.sort(key=lambda r: r["rss_mb"], reverse=True)
    return rows[:limit]


def core_services():
    """Status cepat layanan utama server tanpa shell (hanya cek socket/pid/proc)."""
    nginx = os.path.exists("/www/server/nginx/logs/nginx.pid") or os.path.exists("/run/nginx.pid")
    mariadb = os.path.exists("/tmp/mysql.sock") or os.path.exists("/run/mysqld/mysqld.sock")
    postgres = os.path.exists("/var/run/postgresql/.s.PGSQL.5432") or os.path.exists("/tmp/.s.PGSQL.5432")
    p_names = []
    try:
        for p in os.listdir("/proc"):
            if p.isdigit():
                try:
                    with open("/proc/" + p + "/cmdline", "rb") as f:
                        cmd = f.read(64).split(b"\x00")[0].decode("utf-8", "ignore")
                        if cmd:
                            p_names.append(os.path.basename(cmd).lower())
                except OSError:
                    pass
    except OSError:
        pass
    redis = any("redis" in x for x in p_names)
    cf = any("cloudflared" in x for x in p_names)
    return [
        {"name": "Nginx", "up": nginx, "port": "80 / 888"},
        {"name": "MariaDB", "up": mariadb, "port": "3306"},
        {"name": "Redis", "up": redis, "port": "6379"},
        {"name": "PostgreSQL", "up": postgres, "port": "5432"},
        {"name": "Cloudflared", "up": cf, "port": "Tunnel Edge"},
    ]


def snapshot(disk_path="/"):
    """Potret lengkap untuk dashboard. Dipanggil tiap 3 detik -> harus murah."""
    load = loadavg()
    up = uptime()
    sysinfo = uname()
    return {
        "ts": int(time.time()),
        "uptime": up,
        "uptime_h": round(up / 3600.0, 1),
        "hostname": sysinfo["hostname"],
        "kernel": sysinfo["kernel"],
        "arch": sysinfo["arch"],
        "services": core_services(),
        "cpu": cpu_percent(),
        "cores": cores(),
        "load": load,
        "temp": temperature(),
        "mem": memory(),
        "disk": disk(disk_path),
        "mounts": mounts(),
        "net": net_rate(),
        "procs": processes(),
    }
