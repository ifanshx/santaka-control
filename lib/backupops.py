"""Cadangan: daftar arsip, verifikasi SHA256, jalankan, dan status unit."""
import os
import subprocess
import time

from . import cmd, validate

BACKUP_DIR = "/var/backups/santaka"
SUMS = os.path.join(BACKUP_DIR, "SHA256SUMS.txt")
MAIN_UNIT = "santaka-backup.service"
DB_UNIT = "santaka-db-backup.service"


def configure(cfg=None):
    """Terapkan direktori cadangan dari config.json."""
    global BACKUP_DIR, SUMS
    cfg = cfg or {}
    BACKUP_DIR = os.path.abspath(str(cfg.get("backup_dir") or "/var/backups/santaka"))
    SUMS = os.path.join(BACKUP_DIR, "SHA256SUMS.txt")


class BackupError(Exception):
    pass


def archives(limit=40):
    rows = []
    try:
        names = os.listdir(BACKUP_DIR)
    except OSError:
        return rows
    for name in names:
        if not name.endswith((".tar.gz", ".tgz")):
            continue
        full = os.path.join(BACKUP_DIR, name)
        try:
            st = os.stat(full)
        except OSError:
            continue
        rows.append({"name": name, "path": full, "size": st.st_size,
                     "mtime": int(st.st_mtime)})
    rows.sort(key=lambda r: r["mtime"], reverse=True)
    return rows[:limit]


def db_backups(limit=20):
    base = os.path.join(BACKUP_DIR, "db")
    rows = []
    try:
        names = sorted(os.listdir(base), reverse=True)
    except OSError:
        return rows
    for name in names[:limit]:
        full = os.path.join(base, name)
        if not os.path.isdir(full):
            continue
        files = []
        try:
            for f in os.listdir(full):
                p = os.path.join(full, f)
                try:
                    files.append({"name": f, "size": os.path.getsize(p)})
                except OSError:
                    pass
        except OSError:
            pass
        try:
            st = os.stat(full)
        except OSError:
            continue
        rows.append({"name": name, "path": full, "mtime": int(st.st_mtime),
                     "files": files})
    return rows


def verify(archive_name):
    """Verifikasi satu arsip terhadap SHA256SUMS.txt. (ok, pesan)."""
    if not validate.filename(archive_name):
        raise BackupError("nama arsip tidak sah")
    if not os.path.isfile(SUMS):
        return False, "SHA256SUMS.txt tidak ditemukan"
    want = None
    try:
        with open(SUMS, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2 and parts[1].lstrip("*") == archive_name:
                    want = parts[0]
                    break
    except OSError as ex:
        raise BackupError("tidak bisa membaca SHA256SUMS: %s" % ex.strerror)
    if not want:
        return False, "arsip tidak tercantum di SHA256SUMS.txt"
    path = os.path.join(BACKUP_DIR, archive_name)
    rc, out, err = cmd.run(["sha256sum", path], timeout=300)
    if rc != 0:
        raise BackupError((err or out or "sha256sum gagal")[:200])
    got = (out or "").split()[0] if out else ""
    if got == want:
        return True, "Integritas cocok (%s…)" % want[:16]
    return False, "TIDAK COCOK — arsip mungkin rusak"


def unit_state(unit):
    rc, out, _ = cmd.run(["systemctl", "is-active", unit], timeout=8)
    return (out or "unknown").strip()


def run_backup(which="main"):
    """Mulai cadangan di latar belakang. Kembalikan pesan status."""
    unit = MAIN_UNIT if which == "main" else DB_UNIT
    state = unit_state(unit)
    if state in ("activating", "active"):
        return "Cadangan sedang berjalan (%s)" % state
    rc, out, err = cmd.run(["systemctl", "start", "--no-block", unit], timeout=15)
    if rc != 0:
        raise BackupError((err or out or "gagal memulai cadangan: %s" % unit)[:300])
    return "Cadangan dimulai (%s)" % unit


def last_run(unit=MAIN_UNIT):
    """Timestamp selesai terakhir dari journal unit."""
    rc, out, _ = cmd.run(["systemctl", "show", unit,
                          "-p", "ExecMainExitTimestampMonotonic",
                          "-p", "InactiveEnterTimestampMonotonic",
                          "-p", "ActiveState"], timeout=10)
    data = {}
    for line in (out or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k] = v.strip()
    return {"state": data.get("ActiveState", "unknown")}
