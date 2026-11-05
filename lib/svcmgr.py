"""Operasi systemd: daftar unit, aksi lifecycle, status autostart, log."""
import time

from . import cmd, validate

# `systemctl list-unit-files` terukur 3.4 detik di perangkat ini.
# Status autostart hampir tidak pernah berubah -> cache 5 menit.
_FILES_CACHE = {"ts": 0.0, "map": {}}
_FILES_TTL = 300
_LIST_CACHE = {"ts": 0.0, "rows": []}
_LIST_TTL = 3

ALLOWED_ACTIONS = ("start", "stop", "restart", "reload", "enable", "disable",
                   "mask", "unmask")


class SvcError(Exception):
    pass


def list_units(kind="service", limit=400, force=False):
    """Daftar unit beserta status aktif dan keterangan singkat (cache 3 dtk)."""
    now = time.time()
    if not force and _LIST_CACHE["rows"] and now - _LIST_CACHE["ts"] < _LIST_TTL:
        return list(_LIST_CACHE["rows"])
    rc, out, err = cmd.run([
        "systemctl", "list-units", "--type=" + kind, "--all", "--no-legend",
        "--no-pager", "--plain"
    ], timeout=15)
    rows = []
    if rc != 0 and not out:
        raise SvcError(err or "systemctl gagal")
    for line in (out or "").splitlines():
        line = line.strip()
        if not line:
            continue
        # format: UNIT LOAD ACTIVE SUB DESCRIPTION...
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        unit, load, active, sub = parts[0], parts[1], parts[2], parts[3]
        desc = parts[4] if len(parts) > 4 else ""
        rows.append({
            "unit": unit,
            "load": load,
            "active": active,
            "sub": sub,
            "desc": desc,
            "enabled": None,       # diisi terpisah agar tidak 400 panggilan
        })
        if len(rows) >= limit:
            break
    if rows:
        _LIST_CACHE["ts"] = now
        _LIST_CACHE["rows"] = rows
    return rows


def is_enabled(unit):
    if not validate.unit(unit):
        return None
    rc, out, _ = cmd.run(["systemctl", "is-enabled", unit], timeout=6)
    return (out or "").strip() or ("disabled" if rc else "unknown")


def _unit_files(force=False):
    """Peta unit -> status autostart, di-cache agar tidak menahan 3.4 detik."""
    now = time.time()
    if not force and _FILES_CACHE["map"] and now - _FILES_CACHE["ts"] < _FILES_TTL:
        return _FILES_CACHE["map"]
    rc, out, _ = cmd.run(["systemctl", "list-unit-files", "--no-legend",
                          "--no-pager", "--type=service"], timeout=20)
    mapping = {}
    for line in (out or "").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            mapping[parts[0]] = parts[1]
    if mapping:
        _FILES_CACHE["ts"] = now
        _FILES_CACHE["map"] = mapping
    return mapping


def enabled_map(units):
    """Tempelkan status autostart ke setiap unit (memakai cache)."""
    mapping = _unit_files()
    for u in units:
        u["enabled"] = mapping.get(u["unit"], "—")
    return units


def action(unit, act):
    if not validate.unit(unit):
        raise SvcError("nama unit tidak sah")
    if act not in ALLOWED_ACTIONS:
        raise SvcError("aksi tidak dikenal: %s" % act)
    rc, out, err = cmd.run(["systemctl", act, unit], timeout=45)
    if rc != 0:
        raise SvcError((err or out or "systemctl menolak").strip()[:400])
    return True


def status(unit):
    if not validate.unit(unit):
        raise SvcError("nama unit tidak sah")
    rc, out, err = cmd.run(["systemctl", "show", unit, "-p", "ActiveState",
                            "-p", "SubState", "-p", "MainPID",
                            "-p", "ExecMainStartTimestampMonotonic"], timeout=10)
    data = {}
    for line in (out or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k] = v.strip()
    return data


def journal(unit, lines=200):
    if not validate.unit(unit):
        raise SvcError("nama unit tidak sah")
    n = validate.safe_int(lines, 10, 5000, 200)
    rc, out, err = cmd.run([
        "journalctl", "-u", unit, "-n", str(n), "--no-pager",
        "--output=short-iso"
    ], timeout=20)
    return out or err or "(tidak ada log)"
