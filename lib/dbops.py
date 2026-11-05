"""Operasi basis data: daftar, ukuran, dump, pulihkan, matikan kueri.

PostgreSQL diakses lewat user `postgres` (peer auth); MySQL lewat socket root.
Semua nama database divalidasi ketat sebelum masuk ke argumen perintah.
"""
import os
import time

from . import cmd, validate

DUMP_DIR = "/var/backups/santaka/db"
SYSTEM_DBS = {"postgres", "template0", "template1", "information_schema",
              "performance_schema", "mysql", "sys"}


def configure(cfg=None):
    """Terapkan direktori dump dari config.json."""
    global DUMP_DIR
    cfg = cfg or {}
    base = os.path.abspath(str(cfg.get("backup_dir") or "/var/backups/santaka"))
    DUMP_DIR = os.path.join(base, "db")


class DbError(Exception):
    pass


# ---------------- PostgreSQL ----------------

def _psql(sql, timeout=20):
    rc, out, err = cmd.run(["su", "-", "postgres", "-c",
                            "psql -t -A -F '|' -c %s" % _sq(sql)], timeout=timeout)
    if rc != 0:
        raise DbError((err or out or "psql gagal").strip()[:300])
    return out


def _sq(text):
    """Kutip untuk sh -c: satu argumen aman."""
    return "'" + str(text).replace("'", "'\\''") + "'"


def pg_list():
    rows = _psql(
        "SELECT d.datname, pg_size_pretty(pg_database_size(d.datname)), "
        "pg_get_userbyid(d.datdba), pg_encoding_to_char(d.encoding) "
        "FROM pg_database d ORDER BY pg_database_size(d.datname) DESC")
    out = []
    for line in (rows or "").splitlines():
        parts = line.split("|")
        if len(parts) < 4:
            continue
        out.append({
            "name": parts[0], "size": parts[1], "owner": parts[2],
            "encoding": parts[3],
            "system": parts[0] in SYSTEM_DBS,
        })
    return out


def pg_dump(name, timeout=600):
    if not validate.sql_name(name):
        raise DbError("nama database tidak sah")
    os.makedirs(DUMP_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = os.path.join(DUMP_DIR, "%s-%s.dump" % (name, stamp))
    # User postgres tidak boleh menulis ke DUMP_DIR -> dump ke /tmp lalu pindah.
    tmp = "/tmp/sc-pgdump-%s.dump" % stamp
    try:
        rc, out, err = cmd.run(
            ["su", "-", "postgres", "-c",
             "pg_dump -Fc -f %s %s" % (_sq(tmp), _sq(name))], timeout=timeout)
        if rc != 0:
            raise DbError((err or out or "pg_dump gagal").strip()[:300])
        import shutil as _shm
        _shm.move(tmp, target)          # /tmp (tmpfs) -> HDD: bukan rename
        os.chmod(target, 0o640)
    except OSError as ex:
        raise DbError("gagal memindahkan dump: %s" % ex.strerror)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
    return target


def pg_create(name):
    """Buat database PostgreSQL baru."""
    if not validate.sql_name(name):
        raise DbError("Nama database tidak sah")
    if name in SYSTEM_DBS:
        raise DbError("Nama database dilindungi sistem")
    rc, out, err = cmd.run(["psql", "-h", "127.0.0.1", "-U", "postgres", "-c", "CREATE DATABASE %s;" % name], timeout=15)
    if rc != 0:
        raise DbError((err or out or "Gagal membuat database PostgreSQL").strip()[:200])
    return True


def pg_restore(name, path, timeout=900):
    if not validate.sql_name(name):
        raise DbError("nama database tidak sah")
    if not os.path.isfile(path):
        raise DbError("berkas dump tidak ditemukan")
    import shutil as _sh
    tmp = "/tmp/sc-pgrestore-%d.dump" % int(time.time())
    try:
        _sh.copyfile(path, tmp)
        os.chmod(tmp, 0o644)
        rc, out, err = cmd.run(
            ["su", "-", "postgres", "-c",
             "pg_restore --clean --if-exists -d %s %s" % (_sq(name), _sq(tmp))],
            timeout=timeout)
        if rc != 0:
            raise DbError((err or out or "pg_restore gagal").strip()[:300])
    except OSError as ex:
        raise DbError("gagal menyiapkan berkas dump: %s" % ex.strerror)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    return True


def pg_activity():
    rows = _psql(
        "SELECT pid, datname, usename, state, "
        "round(extract(epoch from now()-query_start))::text, "
        "left(regexp_replace(query, '\\s+', ' ', 'g'), 90) "
        "FROM pg_stat_activity WHERE state <> 'idle' AND pid <> pg_backend_pid() "
        "ORDER BY query_start LIMIT 30")
    out = []
    for line in (rows or "").splitlines():
        p = line.split("|")
        if len(p) < 6:
            continue
        out.append({"pid": p[0], "db": p[1], "user": p[2], "state": p[3],
                    "secs": p[4], "query": p[5]})
    return out


def pg_kill(pid):
    pid = validate.safe_int(pid, 1, 4194304)
    if not pid:
        raise DbError("pid tidak sah")
    _psql("SELECT pg_terminate_backend(%d)" % pid, timeout=10)
    return True


# ---------------- MySQL / MariaDB ----------------

def my_list():
    rc, out, err = cmd.run(["mysql", "-N", "-B", "-e",
                            "SELECT table_schema, "
                            "ROUND(SUM(data_length+index_length)/1048576, 1) "
                            "FROM information_schema.tables GROUP BY table_schema"],
                           timeout=20)
    if rc != 0:
        raise DbError((err or out or "mysql gagal").strip()[:300])
    sizes = {}
    for line in (out or "").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            sizes[parts[0]] = parts[1]
    rc2, out2, err2 = cmd.run(["mysql", "-N", "-B", "-e", "SHOW DATABASES"],
                              timeout=15)
    if rc2 != 0:
        raise DbError((err2 or out2 or "mysql gagal").strip()[:300])
    rows = []
    for name in (out2 or "").splitlines():
        name = name.strip()
        if not name:
            continue
        rows.append({
            "name": name,
            "size": (sizes.get(name, "0") or "0") + " MB",
            "owner": "root",
            "encoding": "utf8mb4",
            "system": name in SYSTEM_DBS,
        })
    return rows

def my_create(name, username=None, password=None):
    """Buat database MariaDB baru dengan charset utf8mb4."""
    if not validate.sql_name(name):
        raise DbError("Nama database tidak sah (hanya huruf, angka, garis bawah).")
    if name in SYSTEM_DBS:
        raise DbError("Nama database dilindungi sistem.")
    
    sql_cmds = [
        "CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" % name
    ]
    if username and password:
        if not validate.sql_name(username):
            raise DbError("Nama user database tidak sah.")
        safe_pass = str(password).replace("'", "\\'")
        sql_cmds.append("CREATE USER IF NOT EXISTS '%s'@'localhost' IDENTIFIED BY '%s';" % (username, safe_pass))
        sql_cmds.append("GRANT ALL PRIVILEGES ON `%s`.* TO '%s'@'localhost';" % (name, username))
        sql_cmds.append("FLUSH PRIVILEGES;")

    combined_sql = " ".join(sql_cmds)
    rc, out, err = cmd.run(["mysql", "-e", combined_sql], timeout=20)
    if rc != 0:
        raise DbError((err or out or "Gagal membuat database").strip()[:300])
    return True


def my_drop(name):
    """Hapus database MariaDB (menolak database sistem)."""
    if not validate.sql_name(name):
        raise DbError("Nama database tidak sah.")
    if name in SYSTEM_DBS:
        raise DbError("Dilarang menghapus database sistem: %s" % name)
    rc, out, err = cmd.run(["mysql", "-e", "DROP DATABASE `%s`;" % name], timeout=20)
    if rc != 0:
        raise DbError((err or out or "Gagal menghapus database").strip()[:300])
    return True


def my_dump(name, timeout=600):
    if not validate.sql_name(name):
        raise DbError("nama database tidak sah")
    os.makedirs(DUMP_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = os.path.join(DUMP_DIR, "%s-%s.sql.gz" % (name, stamp))
    shell = "mysqldump --single-transaction --routines %s | gzip > %s" % (
        _sq(name), _sq(target))
    rc, out, err = cmd.run(["sh", "-c", shell], timeout=timeout)
    if rc != 0:
        raise DbError((err or out or "mysqldump gagal").strip()[:300])
    try:
        os.chmod(target, 0o640)
    except OSError:
        pass
    return target


def my_restore(name, path, timeout=900):
    if not validate.sql_name(name):
        raise DbError("nama database tidak sah")
    if not os.path.isfile(path):
        raise DbError("berkas dump tidak ditemukan")
    if path.endswith(".gz"):
        shell = "gunzip -c %s | mysql %s" % (_sq(path), _sq(name))
    else:
        shell = "mysql %s < %s" % (_sq(name), _sq(path))
    rc, out, err = cmd.run(["sh", "-c", shell], timeout=timeout)
    if rc != 0:
        raise DbError((err or out or "restore gagal").strip()[:300])
    return True


def my_activity():
    rc, out, err = cmd.run(
        ["mysql", "-N", "-B", "-e",
         "SELECT id, db, user, command, time, LEFT(REPLACE(info,'\\n',' '),90) "
         "FROM information_schema.processlist WHERE command <> 'Sleep' "
         "ORDER BY time DESC LIMIT 30"], timeout=15)
    if rc != 0:
        return []
    rows = []
    for line in (out or "").splitlines():
        p = line.split("\t")
        if len(p) >= 6:
            rows.append({"pid": p[0], "db": p[1], "user": p[2],
                         "state": p[3], "secs": p[4], "query": p[5]})
    return rows


def my_kill(pid):
    pid = validate.safe_int(pid, 1, 4294967295)
    if not pid:
        raise DbError("pid tidak sah")
    rc, out, err = cmd.run(["mysql", "-e", "KILL %d" % pid], timeout=10)
    if rc != 0:
        raise DbError((err or out or "kill gagal").strip()[:200])
    return True


# ---------------- daftar dump yang ada ----------------

def dumps(limit=60):
    rows = []
    try:
        names = os.listdir(DUMP_DIR)
    except OSError:
        return rows
    for name in names:
        full = os.path.join(DUMP_DIR, name)
        if not os.path.isfile(full):
            continue
        try:
            st = os.stat(full)
        except OSError:
            continue
        engine = "postgres" if name.endswith(".dump") else \
                 "mysql" if name.endswith((".sql", ".sql.gz")) else "?"
        rows.append({
            "name": name, "path": full, "size": st.st_size,
            "mtime": int(st.st_mtime), "engine": engine,
        })
    rows.sort(key=lambda r: r["mtime"], reverse=True)
    return rows[:limit]
