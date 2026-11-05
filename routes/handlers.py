"""Handler API. Fase P0: stats & info lengkap.

Handler fase berikutnya didefinisikan saat fasenya dikerjakan; sampai itu
mereka mengembalikan 501 dengan pesan jelas (bukan gagal senyap).
"""
import json
import os
import time

from lib import audit, cmd, perm, store, validate
from lib import stats as sysstats
from lib import fsops, logs as logmod, svcmgr
from lib import (apps_engine as appsE, backupops, caddyops, dbops,
                 nginxops, ops, secops)

# ---------- util respons ----------

def _ok(req, data=None, **extra):
    payload = {"ok": True}
    if isinstance(data, dict):
        payload.update(data)
        if "data" not in payload:
            payload["data"] = data
    elif data is not None:
        payload["data"] = data
    if extra:
        payload.update(extra)
    return req.send_json(payload)


def _err(req, msg, code=400):
    return req.send_json({"error": msg}, code)


# ========================= P0: dashboard =========================

def stats(req, app, sess, path, qs, t):
    snap = sysstats.snapshot(app.cfg.get("disk_path", "/"))
    return _ok(req, {"data": snap})


def info(req, app, sess, path, qs, t):
    uname = sysstats.uname()
    return _ok(req, {"data": {
        "app": "Santaka Control",
        "version": "2.0.0",
        "hostname": uname["hostname"],
        "kernel": uname["kernel"],
        "arch": uname["arch"],
        "python": "%d.%d.%d" % __import__("sys").version_info[:3],
        "user": {"username": sess.get("username"), "role": sess.get("role")},
        "perms": sorted(perm.perms_for(sess.get("role"))),
        "uptime": sysstats.uptime(),
        "started": int(time.time()),
        "setup_needed": app.needs_setup(),
        "user_count": app.users.count(),
    }})


# ========================= P1: layanan systemd =========================

def services_list(req, app, sess, path, qs, t):
    force = (qs.get("refresh") or [""])[0] in ("1", "true", "yes")
    try:
        units = svcmgr.list_units(force=force)
        svcmgr.enabled_map(units)
    except svcmgr.SvcError as ex:
        return _err(req, str(ex), 502)
    q = ((qs.get("q") or [""])[0] or "").strip().lower()
    if q:
        units = [u for u in units
                 if q in u["unit"].lower() or q in (u["desc"] or "").lower()]
    return _ok(req, {"items": units, "count": len(units)})


def _unit_from_path(path):
    """/api/services/<unit>/logs -> unit"""
    rest = path[len("/api/services/"):]
    if rest.endswith("/logs"):
        rest = rest[:-len("/logs")]
    from urllib.parse import unquote
    return unquote(rest).strip("/")


def service_logs(req, app, sess, path, qs, t):
    unit = _unit_from_path(path)
    if not validate.unit(unit):
        return _err(req, "nama unit tidak sah", 400)
    lines = (qs.get("n") or ["200"])[0]
    try:
        text = svcmgr.journal(unit, lines)
    except svcmgr.SvcError as ex:
        return _err(req, str(ex), 502)
    return _ok(req, {"unit": unit, "log": text})


def service_action(req, app, sess, path, form, t):
    unit = req.fval(form, "unit")
    act = req.fval(form, "action")
    if not validate.unit(unit):
        return _err(req, "nama unit tidak sah", 400)
    try:
        svcmgr.action(unit, act)
    except svcmgr.SvcError as ex:
        app.audit.write(audit.ACTION, sess, "svc:" + act, target=unit,
                        result="error", detail=str(ex), ip=req.ip)
        return _err(req, str(ex)[:300], 409)
    app.audit.write(audit.ACTION, sess, "svc:" + act, target=unit,
                    result="ok", ip=req.ip)
    return _ok(req, {"unit": unit, "action": act})


# ========================= P1: berkas =========================

def _roots(app):
    return fsops.roots(app.cfg.get("roots") or [])


def files_list(req, app, sess, path, qs, t):
    wanted = (qs.get("path") or [""])[0]
    roots = _roots(app)
    try:
        cur = fsops.resolve(wanted, roots)
    except fsops.EscapeError as ex:
        return _err(req, str(ex), 403)
    try:
        items = fsops.list_dir(cur)
    except fsops.FsError as ex:
        return _err(req, str(ex), 400)
    space = fsops.free_space(cur)
    return _ok(req, {
        "path": cur,
        "parent": fsops.parent_of(cur, roots),
        "roots": roots,
        "items": items,
        "space": space,
    })


def files_download(req, app, sess, path, qs, t):
    wanted = (qs.get("path") or [""])[0]
    try:
        full = fsops.resolve(wanted, _roots(app))
    except fsops.EscapeError as ex:
        return _err(req, str(ex), 403)
    if not os.path.isfile(full):
        return _err(req, "berkas tidak ditemukan", 404)
    try:
        size = os.path.getsize(full)
        req.send_response(200)
        req.send_header("Content-Type", "application/octet-stream")
        req.send_header("Content-Length", str(size))
        req.send_header("Content-Disposition",
                        'attachment; filename="%s"' % os.path.basename(full))
        req.send_header("X-Content-Type-Options", "nosniff")
        req.end_headers()
        if req.command != "HEAD":
            with open(full, "rb") as fh:
                while True:
                    block = fh.read(65536)
                    if not block:
                        break
                    req.wfile.write(block)
        app.audit.write(audit.ACTION, sess, "file:download",
                        target=full, result="ok", ip=req.ip)
        return None
    except OSError as ex:
        return _err(req, "gagal membaca berkas: %s" % ex.strerror, 500)


def _file_op(req, app, sess, form, t, op, fn):
    base = req.fval(form, "path")
    roots = _roots(app)
    try:
        base_dir = fsops.resolve(base, roots)
        result = fn(base_dir, roots)
    except (fsops.EscapeError, fsops.FsError) as ex:
        app.audit.write(audit.ACTION, sess, "file:" + op, target=base,
                        result="error", detail=str(ex), ip=req.ip)
        return _err(req, str(ex), 400)
    app.audit.write(audit.ACTION, sess, "file:" + op, target=str(result),
                    result="ok", ip=req.ip)
    return _ok(req, {"result": str(result)})


def files_mkdir(req, app, sess, path, form, t):
    name = req.fval(form, "name")
    return _file_op(req, app, sess, form, t, "mkdir",
                    lambda base, roots: fsops.mkdir(base, name, roots))


def files_delete(req, app, sess, path, form, t):
    name = req.fval(form, "name")
    recursive = req.fval(form, "recursive") in ("1", "true", "on", "yes")
    return _file_op(req, app, sess, form, t, "delete",
                    lambda base, roots: fsops.delete(base, name, roots, recursive))


def files_rename(req, app, sess, path, form, t):
    name = req.fval(form, "name")
    to = req.fval(form, "to")
    return _file_op(req, app, sess, form, t, "rename",
                    lambda base, roots: fsops.rename(base, name, to, roots))



def files_read(req, app, sess, path, qs, t):
    wanted = (qs.get("path") or [""])[0]
    roots = _roots(app)
    try:
        data = fsops.read_text(wanted, roots)
        return _ok(req, data)
    except (fsops.EscapeError, fsops.FsError) as ex:
        return _err(req, str(ex), 400)

def files_save(req, app, sess, path, form, t):
    target = req.fval(form, "path")
    content = req.fval(form, "content")
    roots = _roots(app)
    try:
        fsops.write_text(target, content, roots)
        app.audit.write(audit.ACTION, sess, "file:edit", target=target, result="ok", ip=req.ip)
        return _ok(req, {"message": "Berkas berhasil disimpan"})
    except (fsops.EscapeError, fsops.FsError) as ex:
        return _err(req, str(ex), 400)

def files_touch(req, app, sess, path, form, t):
    name = req.fval(form, "name")
    return _file_op(req, app, sess, form, t, "touch",
                    lambda base, roots: fsops.touch(base, name, roots))


def upload_stream(req, app, sess, path, t):
    """Unggah multipart: tulis streaming ke disk, batasi ukuran."""
    from urllib.parse import parse_qs, urlparse
    qs = parse_qs(urlparse(req.path).query)
    dest = (qs.get("path") or [""])[0]
    roots = _roots(app)
    try:
        dest_dir = fsops.resolve(dest, roots)
    except fsops.EscapeError as ex:
        return _err(req, str(ex), 403)
    if not os.path.isdir(dest_dir):
        return _err(req, "folder tujuan tidak ada", 400)
    length = validate.safe_int(req.headers.get("Content-Length"), 0,
                               fsops.MAX_UPLOAD * 2, 0)
    if not length:
        return _err(req, "isi unggahan kosong", 400)
    try:
        saved = fsops.stream_multipart(
            req.rfile, length, req.headers.get("Content-Type", ""),
            dest_dir, roots)
    except (fsops.FsError, fsops.EscapeError) as ex:
        app.audit.write(audit.ACTION, sess, "file:upload", target=dest_dir,
                        result="error", detail=str(ex), ip=req.ip)
        return _err(req, str(ex), 400)
    app.audit.write(audit.ACTION, sess, "file:upload", target=dest_dir,
                    result="ok", detail="%d berkas" % len(saved), ip=req.ip)
    return _ok(req, {"saved": saved, "count": len(saved)})


# ========================= P1: log =========================

def logs_read(req, app, sess, path, form, t):
    source = req.fval(form, "source", "unit")
    unit = req.fval(form, "unit")
    lines = req.fval(form, "lines", "200")
    try:
        if source == "dmesg":
            text = logmod.dmesg(lines)
        elif source == "access":
            text = logmod.caddy_access(lines)
        else:
            text = logmod.journal_unit(unit or None, lines)
    except Exception as ex:
        return _err(req, "gagal membaca log: %s" % ex, 502)
    return _ok(req, {"source": source, "unit": unit, "log": text})


# ========================= P2: web server (Caddy) =========================

def web_info(req, app, sess, path, qs, t):
    try:
        text = caddyops.read()
        st = caddyops.status()
    except caddyops.CaddyError as ex:
        return _err(req, str(ex), 502)
    try:
        site_rows = caddyops.sites()
    except caddyops.CaddyError:
        site_rows = []
    if (qs.get("raw") or [""])[0] in ("1", "true"):
        return _ok(req, {"data": st, "sites": site_rows, "caddyfile": text,
                         "backups": caddyops.backups()})
    return _ok(req, {"data": st, "sites": site_rows,
                     "backups": caddyops.backups(),
                     "size": len(text)})


def web_validate(req, app, sess, path, form, t):
    text = req.fval(form, "caddyfile")
    if not text:
        return _err(req, "isi Caddyfile kosong", 400)
    ok, msg = caddyops.validate(text)
    return req.send_json({"ok": ok, "valid": ok, "message": msg}, 200 if ok else 422)


def web_apply(req, app, sess, path, form, t):
    """Simpan Caddyfile (hanya bila valid) lalu muat ulang Caddy."""
    text = req.fval(form, "caddyfile")
    if not text.strip():
        return _err(req, "isi Caddyfile kosong", 400)
    ok, msg, bak = caddyops.save(text)
    if not ok:
        app.audit.write(audit.ACTION, sess, "web:apply", target="Caddyfile",
                        result="error", detail=msg, ip=req.ip)
        return req.send_json({"ok": False, "error": msg}, 422)
    try:
        how = caddyops.reload()
    except caddyops.CaddyError as ex:
        app.audit.write(audit.ACTION, sess, "web:apply", target="Caddyfile",
                        result="error", detail=str(ex), ip=req.ip)
        return req.send_json({"ok": False, "error": "tersimpan tetapi gagal dimuat: %s" % ex,
                              "backup": bak}, 502)
    app.audit.write(audit.ACTION, sess, "web:apply", target="Caddyfile",
                    result="ok", detail="%s · backup %s" % (how, bak or "-"), ip=req.ip)
    return _ok(req, {"message": msg, "reload": how, "backup": bak})


# ========================= P2: aplikasi =========================

def apps_list(req, app, sess, path, qs, t):
    try:
        items = appsE.list_apps()
    except Exception as ex:
        return _err(req, "gagal membaca daftar aplikasi: %s" % ex, 502)
    out = []
    for a in items:
        row = dict(a)
        try:
            row["stats"] = appsE.app_stats(a)
        except Exception:
            row["stats"] = {}
        out.append(row)
    return _ok(req, {"items": out, "count": len(out),
                     "kinds": list(appsE.KINDS)})


def app_detail(req, app, sess, path, qs, t):
    slug = path[len("/api/apps/"):].strip("/")
    if not validate.slug(slug):
        return _err(req, "slug tidak sah", 400)
    try:
        a = appsE.get_app(slug)
    except Exception as ex:
        return _err(req, str(ex), 502)
    if not a:
        return _err(req, "aplikasi tidak ditemukan", 404)
    env_path = os.path.join(a.get("path", ""), ".env")
    env_text = ""
    try:
        with open(env_path, "r", encoding="utf-8", errors="replace") as fh:
            env_text = fh.read()[:20000]
    except OSError:
        pass
    return _ok(req, {"item": a, "env": env_text,
                     "log": appsE.app_log(slug, 120)})


def apps_action(req, app, sess, path, form, t):
    slug = req.fval(form, "slug")
    act = req.fval(form, "action")
    if not validate.slug(slug):
        return _err(req, "slug tidak sah", 400)
    try:
        if act == "start":
            appsE.start_runtime(appsE.get_app(slug), appsE.list_apps())
        elif act == "stop":
            appsE.stop_runtime(appsE.get_app(slug))
        elif act == "redeploy":
            appsE.redeploy(slug)
        elif act == "remove":
            appsE.undeploy(slug)
        else:
            return _err(req, "aksi tidak dikenal: %s" % act, 400)
    except Exception as ex:
        app.audit.write(audit.ACTION, sess, "app:" + act, target=slug,
                        result="error", detail=str(ex)[:300], ip=req.ip)
        return _err(req, str(ex)[:300], 409)
    app.audit.write(audit.ACTION, sess, "app:" + act, target=slug,
                    result="ok", ip=req.ip)
    return _ok(req, {"slug": slug, "action": act})


def apps_env(req, app, sess, path, form, t):
    slug = req.fval(form, "slug")
    content = req.fval(form, "content")
    if not validate.slug(slug):
        return _err(req, "slug tidak sah", 400)
    try:
        appsE.write_env(slug, content)
    except Exception as ex:
        app.audit.write(audit.ACTION, sess, "app:env", target=slug,
                        result="error", detail=str(ex)[:200], ip=req.ip)
        return _err(req, str(ex)[:300], 409)
    app.audit.write(audit.ACTION, sess, "app:env", target=slug,
                    result="ok", ip=req.ip)
    return _ok(req, {"slug": slug})


def apps_deploy(req, app, sess, path, form, t):
    slug = req.fval(form, "slug").strip().lower()
    source = req.fval(form, "source").strip()
    kind = req.fval(form, "kind") or None
    with_db = req.fval(form, "with_db") in ("1", "true", "on")
    db_engine = req.fval(form, "db_engine") or "postgres"
    if not validate.slug(slug):
        return _err(req, "slug tidak sah (huruf kecil, angka, tanda hubung)", 400)
    if not source:
        return _err(req, "sumber wajib diisi", 400)
    try:
        result = appsE.deploy(slug, source, kind=kind, with_db=with_db,
                              db_engine=db_engine)
    except Exception as ex:
        app.audit.write(audit.ACTION, sess, "app:deploy", target=slug,
                        result="error", detail=str(ex)[:400], ip=req.ip)
        return _err(req, str(ex)[:400], 409)
    app.audit.write(audit.ACTION, sess, "app:deploy", target=slug,
                    result="ok", detail=str(result.get("domain", "")), ip=req.ip)
    return _ok(req, {"item": result})


# ========================= P3: basis data =========================

def db_list(req, app, sess, path, qs, t):
    out = {"postgres": [], "mysql": [], "errors": {}}
    try:
        out["postgres"] = dbops.pg_list()
    except dbops.DbError as ex:
        out["errors"]["postgres"] = str(ex)
    try:
        out["mysql"] = dbops.my_list()
    except dbops.DbError as ex:
        out["errors"]["mysql"] = str(ex)
    try:
        out["activity"] = {"postgres": dbops.pg_activity(),
                           "mysql": dbops.my_activity()}
    except Exception:
        out["activity"] = {"postgres": [], "mysql": []}
    out["dumps"] = dbops.dumps()
    return _ok(req, out)


def db_action(req, app, sess, path, form, t):
    op = req.fval(form, "op")
    engine = req.fval(form, "engine")
    name = req.fval(form, "name")
    path_file = req.fval(form, "path")
    pid = req.fval(form, "pid")

    def done(msg):
        app.audit.write(audit.ACTION, sess, "db:" + op,
                        target="%s/%s" % (engine, name or pid),
                        result="ok", detail=msg, ip=req.ip)
        return _ok(req, {"message": msg})

    try:
        if op == "dump":
            f = (dbops.pg_dump(name) if engine == "postgres"
                 else dbops.my_dump(name))
            return done("Dump dibuat: %s" % os.path.basename(f))
        if op == "restore":
            ok = (dbops.pg_restore(name, path_file) if engine == "postgres"
                  else dbops.my_restore(name, path_file))
            return done("Pemulihan selesai untuk %s" % name)
        if op == "kill":
            ok = (dbops.pg_kill(pid) if engine == "postgres"
                  else dbops.my_kill(pid))
            return done("Kueri %s dihentikan" % pid)
    except dbops.DbError as ex:
        app.audit.write(audit.ACTION, sess, "db:" + op,
                        target="%s/%s" % (engine, name or pid),
                        result="error", detail=str(ex)[:300], ip=req.ip)
        return _err(req, str(ex), 409)
    return _err(req, "operasi tidak dikenal: %s" % op, 400)


# ========================= P3: cadangan =========================

def backup_list(req, app, sess, path, qs, t):
    return _ok(req, {
        "archives": backupops.archives(),
        "db": backupops.db_backups(),
        "state": {"main": backupops.unit_state(backupops.MAIN_UNIT),
                  "db": backupops.unit_state(backupops.DB_UNIT)},
        "dir": backupops.BACKUP_DIR,
    })


def backup_action(req, app, sess, path, form, t):
    op = req.fval(form, "op")
    name = req.fval(form, "name")
    try:
        if op == "run":
            which = req.fval(form, "which") or "main"
            msg = backupops.run_backup(which)
            app.audit.write(audit.ACTION, sess, "backup:run", target=which,
                            result="ok", ip=req.ip)
            return _ok(req, {"message": msg})
        if op == "verify":
            ok, msg = backupops.verify(name)
            app.audit.write(audit.ACTION, sess, "backup:verify", target=name,
                            result="ok" if ok else "error", detail=msg, ip=req.ip)
            return req.send_json({"ok": ok, "message": msg}, 200 if ok else 422)
    except backupops.BackupError as ex:
        app.audit.write(audit.ACTION, sess, "backup:" + op, target=name,
                        result="error", detail=str(ex)[:200], ip=req.ip)
        return _err(req, str(ex), 409)
    return _err(req, "operasi tidak dikenal: %s" % op, 400)


# ========================= P4: Docker =========================

def docker_list(req, app, sess, path, qs, t):
    if not ops.docker_available():
        return _ok(req, {"available": False, "containers": [], "images": [],
                         "volumes": [], "networks": []})
    out = {"available": True}
    for key, fn in (("containers", ops.docker_containers),
                    ("images", ops.docker_images),
                    ("volumes", ops.docker_volumes),
                    ("networks", ops.docker_networks)):
        try:
            out[key] = fn()
        except ops.OpError as ex:
            out[key] = []
            out.setdefault("errors", {})[key] = str(ex)
    return _ok(req, out)


def docker_action(req, app, sess, path, form, t):
    op = req.fval(form, "op")
    name = req.fval(form, "name")
    try:
        if op == "logs":
            text = ops.docker_logs(name, req.fval(form, "lines", "200"))
            return _ok(req, {"logs": text})
        ops.docker_action(name, op)
    except ops.OpError as ex:
        app.audit.write(audit.ACTION, sess, "docker:" + op, target=name,
                        result="error", detail=str(ex)[:240], ip=req.ip)
        return _err(req, str(ex), 409)
    app.audit.write(audit.ACTION, sess, "docker:" + op, target=name,
                    result="ok", ip=req.ip)
    return _ok(req, {"name": name, "action": op})


# ========================= P4: penyimpanan =========================

def storage_list(req, app, sess, path, qs, t):
    out = {}
    try:
        out["disks"] = ops.disks()
    except ops.OpError as ex:
        out["disks"] = []
        out["errors"] = {"disks": str(ex)}
    out["mounts"] = sysstats.mounts()
    out["fstab"] = ops.fstab()
    out["usage"] = sysstats.disk(app.cfg.get("disk_path", "/"))
    return _ok(req, out)


def storage_action(req, app, sess, path, form, t):
    op = req.fval(form, "op")
    dev = req.fval(form, "device")
    if op == "smart":
        try:
            data = ops.smart(dev)
        except ops.OpError as ex:
            return _err(req, str(ex), 409)
        return _ok(req, {"smart": data})
    return _err(req, "operasi tidak dikenal: %s" % op, 400)


# ========================= P4: jaringan =========================

def network_list(req, app, sess, path, qs, t):
    out = {"interfaces": ops.interfaces(), "listening": ops.listening()}
    try:
        out["fail2ban"] = ops.fail2ban()
    except Exception as ex:
        out["fail2ban"] = {"available": False, "jails": [], "detail": {},
                           "error": str(ex)}
    if (qs.get("rules") or [""])[0] in ("1", "true"):
        out["rules"] = ops.firewall_rules()
    return _ok(req, out)


def network_action(req, app, sess, path, form, t):
    op = req.fval(form, "op")
    if op == "unban":
        jail = req.fval(form, "jail")
        ip = req.fval(form, "ip")
        try:
            ops.fail2ban_unban(jail, ip)
        except ops.OpError as ex:
            app.audit.write(audit.ACTION, sess, "net:unban",
                            target="%s/%s" % (jail, ip), result="error",
                            detail=str(ex)[:200], ip=req.ip)
            return _err(req, str(ex), 409)
        app.audit.write(audit.ACTION, sess, "net:unban",
                        target="%s/%s" % (jail, ip), result="ok", ip=req.ip)
        return _ok(req, {"message": "%s dibuka dari %s" % (ip, jail)})
    return _err(req, "operasi tidak dikenal: %s" % op, 400)


# ========================= P4: jadwal =========================

def cron_list(req, app, sess, path, qs, t):
    return _ok(req, {"crontab": ops.crontab(), "timers": ops.timers()})


def cron_action(req, app, sess, path, form, t):
    op = req.fval(form, "op")
    if op == "save":
        text = req.fval(form, "crontab")
        try:
            ops.save_crontab(text)
        except ops.OpError as ex:
            app.audit.write(audit.ACTION, sess, "cron:save", result="error",
                            detail=str(ex)[:200], ip=req.ip)
            return _err(req, str(ex), 409)
        app.audit.write(audit.ACTION, sess, "cron:save", result="ok", ip=req.ip)
        return _ok(req, {"message": "Crontab disimpan"})
    return _err(req, "operasi tidak dikenal: %s" % op, 400)


# ========================= P5: pengguna =========================

def _public_user(u):
    return {
        "username": u.get("username"),
        "display": u.get("display") or u.get("username"),
        "role": u.get("role"),
        "disabled": bool(u.get("disabled")),
        "totp": bool(u.get("totp")),
        "recovery": len(u.get("recovery") or []),
        "created": u.get("created", 0),
        "last_login": u.get("last_login", 0),
    }


def users_list(req, app, sess, path, qs, t):
    rows = [_public_user(u) for u in app.users.all().values()]
    rows.sort(key=lambda r: r["username"])
    return _ok(req, {"items": rows, "count": len(rows),
                     "roles": perm.ROLE_ORDER,
                     "role_labels": perm.ROLE_LABEL})


def users_action(req, app, sess, path, form, t):
    op = req.fval(form, "op")
    username = req.fval(form, "username").strip().lower()
    try:
        if op == "create":
            password = req.fval(form, "password")
            role = req.fval(form, "role") or perm.ROLE_VIEWER
            display = req.fval(form, "display") or username
            if not validate.username(username):
                raise ValueError("username tidak sah (huruf kecil, 3–32 karakter)")
            if len(password) < 10:
                raise ValueError("kata sandi minimal 10 karakter")
            if role not in perm.ROLE_ORDER:
                raise ValueError("role tidak sah")
            if not perm.can_manage_user(sess, role):
                raise ValueError("tidak boleh membuat role tersebut")
            app.users.create(username, password, role=role, display=display,
                             created_by=sess.get("username"))
            msg = "Pengguna %s dibuat" % username
        elif op == "role":
            role = req.fval(form, "role")
            if not perm.can_manage_user(sess, role):
                raise ValueError("tidak boleh memberi role tersebut")
            app.users.set_role(username, role)
            app.sessions.destroy_user(username)
            msg = "Role %s diubah menjadi %s" % (username, role)
        elif op == "password":
            password = req.fval(form, "password")
            if len(password) < 10:
                raise ValueError("kata sandi minimal 10 karakter")
            app.users.set_password(username, password)
            app.sessions.destroy_user(username)
            msg = "Kata sandi %s direset" % username
        elif op == "disable":
            flag = req.fval(form, "disabled") in ("1", "true", "on")
            app.users.disable(username, flag)
            if flag:
                app.sessions.destroy_user(username)
            msg = "Pengguna %s %s" % (username, "dinonaktifkan" if flag else "diaktifkan")
        elif op == "delete":
            app.users.delete(username)
            app.sessions.destroy_user(username)
            msg = "Pengguna %s dihapus" % username
        else:
            return _err(req, "operasi tidak dikenal: %s" % op, 400)
    except ValueError as ex:
        app.audit.write(audit.ACTION, sess, "user:" + op, target=username,
                        result="error", detail=str(ex)[:200], ip=req.ip)
        return _err(req, str(ex), 409)
    app.audit.write(audit.ACTION, sess, "user:" + op, target=username,
                    result="ok", ip=req.ip)
    return _ok(req, {"message": msg})


# ========================= P5: keamanan =========================

def sessions_list(req, app, sess, path, qs, t):
    rows = secops.sessions(app, sess.get("sid"))
    return _ok(req, {"items": rows, "count": len(rows)})


def security_action(req, app, sess, path, form, t):
    op = req.fval(form, "op")
    me = app.users.get(sess.get("username"))
    try:
        if op == "password":
            old = req.fval(form, "old")
            new = req.fval(form, "new")
            if not me or not crypto.verify_password(old, me.get("password", "")):
                raise ValueError("kata sandi lama salah")
            if len(new) < 10:
                raise ValueError("kata sandi baru minimal 10 karakter")
            if new == old:
                raise ValueError("kata sandi baru harus berbeda")
            app.users.set_password(me["username"], new)
            removed = app.sessions.destroy_user(me["username"], keep_sid=sess.get("sid"))
            app.audit.write(audit.ACTION, sess, "security:password", result="ok",
                            detail="%d sesi lain dicabut" % removed, ip=req.ip)
            return _ok(req, {"message": "Kata sandi diperbarui. %d sesi lain dicabut." % removed})

        if op == "2fa_start":
            secret, uri = app.users.start_totp(me["username"])
            svg = secops.qr_svg(uri)
            app.audit.write(audit.ACTION, sess, "security:2fa_start", result="ok", ip=req.ip)
            return _ok(req, {"secret": secret, "uri": uri, "qr": svg})

        if op == "2fa_enable":
            codes = app.users.verify_totp(me["username"], req.fval(form, "code"))
            if not codes:
                raise ValueError("kode tidak cocok, coba lagi")
            app.audit.write(audit.ACTION, sess, "security:2fa_enable", result="ok", ip=req.ip)
            return _ok(req, {"message": "2FA aktif", "recovery": codes})

        if op == "2fa_disable":
            if me.get("totp") and not app.users.check_code(me, req.fval(form, "code")):
                raise ValueError("kode 2FA atau pemulihan tidak cocok")
            app.users.disable_totp(me["username"])
            app.audit.write(audit.ACTION, sess, "security:2fa_disable", result="ok", ip=req.ip)
            return _ok(req, {"message": "2FA dimatikan"})

        if op == "recovery_regen":
            secret = me.get("totp")
            if not secret:
                raise ValueError("aktifkan 2FA lebih dulu")
            if not app.users.check_code(me, req.fval(form, "code")):
                raise ValueError("kode tidak cocok")
            codes = crypto.new_recovery_codes(8)
            app.users.update(me["username"],
                             recovery=[crypto.sha256_hex(c) for c in codes])
            app.audit.write(audit.ACTION, sess, "security:recovery", result="ok", ip=req.ip)
            return _ok(req, {"recovery": codes})

        if op == "kill_session":
            n = secops.kill_session(app, req.fval(form, "sid"))
            app.audit.write(audit.ACTION, sess, "security:kill_session",
                            target=req.fval(form, "sid"), result="ok", ip=req.ip)
            return _ok(req, {"message": "%d sesi dicabut" % n})
    except (ValueError, secops.SecError) as ex:
        app.audit.write(audit.ACTION, sess, "security:" + op, result="error",
                        detail=str(ex)[:200], ip=req.ip)
        return _err(req, str(ex), 409)
    return _err(req, "operasi tidak dikenal: %s" % op, 400)


# ========================= P5: notifikasi =========================

def alerts_info(req, app, sess, path, qs, t):
    return _ok(req, {"telegram": secops.telegram_config(),
                     "mail": secops.mail_config()})


def alerts_action(req, app, sess, path, form, t):
    op = req.fval(form, "op")
    try:
        if op == "telegram_save":
            secops.telegram_save(req.fval(form, "token"), req.fval(form, "chat_id"))
            msg = "Konfigurasi Telegram disimpan"
        elif op == "telegram_test":
            msg = secops.telegram_test()
        elif op == "mail_save":
            secops.mail_save(req.fval(form, "host"), req.fval(form, "port"),
                             req.fval(form, "user"), req.fval(form, "password"),
                             req.fval(form, "sender"))
            msg = "Konfigurasi SMTP disimpan"
        else:
            return _err(req, "operasi tidak dikenal: %s" % op, 400)
    except secops.SecError as ex:
        app.audit.write(audit.ACTION, sess, "alerts:" + op, result="error",
                        detail=str(ex)[:200], ip=req.ip)
        return _err(req, str(ex), 409)
    app.audit.write(audit.ACTION, sess, "alerts:" + op, result="ok", ip=req.ip)
    return _ok(req, {"message": msg})


# ========================= P5: perawatan =========================

def maintenance_action(req, app, sess, path, form, t):
    op = req.fval(form, "op")
    try:
        if op == "fstrim":
            msg = secops.fstrim()
        elif op == "apt_clean":
            msg = secops.apt_cache_clean()
        else:
            return _err(req, "operasi tidak dikenal: %s" % op, 400)
    except secops.SecError as ex:
        app.audit.write(audit.ACTION, sess, "maint:" + op, result="error",
                        detail=str(ex)[:200], ip=req.ip)
        return _err(req, str(ex), 409)
    app.audit.write(audit.ACTION, sess, "maint:" + op, result="ok", ip=req.ip)
    return _ok(req, {"message": msg[:400]})


def audit_list(req, app, sess, path, qs, t):
    limit = validate.safe_int((qs.get("n") or ["200"])[0], 1, 1000, 200)
    query = ((qs.get("q") or [""])[0] or "").strip().lower() or None
    rows = app.audit.list(limit=limit, query=query)
    return _ok(req, {"items": rows, "count": len(rows)})

# ========================= NGINX & VHOST =========================
def nginx_sites(req, app, sess, path, qs, t):
    from lib import nginxops
    try:
        rows = nginxops.list_vhosts()
        return _ok(req, rows)
    except Exception as ex:
        return _err(req, str(ex), 500)

def nginx_add(req, app, sess, path, form, t):
    from lib import nginxops, dbops
    import re
    domain = req.fval(form, "domain")
    root_dir = req.fval(form, "root") or None
    proxy_pass = req.fval(form, "proxy") or None
    is_fullstack = req.fval(form, "is_fullstack") in ("1", "true", "on", "yes", True)
    api_pass = req.fval(form, "api_pass") or None
    aliases = form.get("aliases") if isinstance(form, dict) else None
    if isinstance(aliases, str):
        aliases = aliases.split()
    create_db = req.fval(form, "create_db")

    extra_msg = []
    db_info = {}
    if create_db:
        clean_name = "db_" + re.sub(r"[^a-zA-Z0-9_]", "_", domain).strip("_")[:28]
        if create_db == "postgres":
            try:
                dbops.pg_create(clean_name)
                extra_msg.append(f"Database PostgreSQL '{clean_name}' dibuat")
                db_info = {"type": "PostgreSQL", "name": clean_name, "url": f"postgres://postgres@127.0.0.1:5432/{clean_name}"}
            except Exception as e:
                extra_msg.append(f"Peringatan DB: {e}")
        elif create_db == "mysql":
            try:
                dbops.my_create(clean_name)
                extra_msg.append(f"Database MariaDB '{clean_name}' dibuat")
                db_info = {"type": "MariaDB", "name": clean_name, "url": f"mysql://root@127.0.0.1:3306/{clean_name}"}
            except Exception as e:
                extra_msg.append(f"Peringatan DB: {e}")

    try:
        nginxops.add_vhost(domain, root_dir=root_dir, proxy_pass=proxy_pass, aliases=aliases, is_fullstack=is_fullstack, api_pass=api_pass)
        app.audit.write(audit.ACTION, sess, "nginx:add_site", target=domain, result="ok", ip=req.ip)
        msg = f"Situs {domain} berhasil dibuat!"
        if extra_msg:
            msg += " (" + ", ".join(extra_msg) + ")"
        return _ok(req, {"message": msg, "domain": domain, "database": db_info})
    except nginxops.NginxError as ex:
        return _err(req, str(ex), 400)


def project_deploy_zip(req, app, sess, path, form, t):
    from lib import nginxops
    domain = req.fval(form, "domain")
    archive_path = req.fval(form, "archive")
    target_dir = nginxops.site_root(domain)
    try:
        count = nginxops.extract_archive(archive_path, target_dir)
        nginxops.reload_nginx()
        app.audit.write(audit.ACTION, sess, "project:deploy_zip", target=domain, result="ok", detail=f"{count} berkas", ip=req.ip)
        return _ok(req, {"message": f"Deployment selesai! {count} berkas berhasil diekstrak.", "count": count})
    except Exception as ex:
        return _err(req, str(ex), 400)

def nginx_delete(req, app, sess, path, form, t):
    from lib import nginxops
    domain = req.fval(form, "domain")
    try:
        nginxops.delete_vhost(domain)
        app.audit.write(audit.ACTION, sess, "nginx:delete_site", target=domain, result="ok", ip=req.ip)
        return _ok(req, {"message": f"Situs {domain} berhasil dihapus"})
    except nginxops.NginxError as ex:
        return _err(req, str(ex), 400)

def nginx_vhost(req, app, sess, path, qs, t):
    from lib import nginxops
    domain = (qs.get("domain") or [""])[0]
    try:
        content = nginxops.read_vhost(domain)
        return _ok(req, {"domain": domain, "content": content})
    except nginxops.NginxError as ex:
        return _err(req, str(ex), 404)

def nginx_save(req, app, sess, path, form, t):
    from lib import nginxops
    domain = req.fval(form, "domain")
    content = req.fval(form, "content")
    try:
        ok, msg = nginxops.save_vhost(domain, content)
        app.audit.write(audit.ACTION, sess, "nginx:save_vhost", target=domain, result="ok", ip=req.ip)
        return _ok(req, {"message": msg})
    except nginxops.NginxError as ex:
        return _err(req, str(ex), 400)

# ========================= REDIS OPS =========================
def nginx_test(req, app, sess, path, qs, t):
    from lib import nginxops
    ok, msg = nginxops.test_config()
    if ok:
        return _ok(req, {"message": msg})
    return _err(req, msg, 400)

def nginx_reload(req, app, sess, path, form, t):
    from lib import nginxops
    try:
        nginxops.reload_nginx()
        app.audit.write(audit.ACTION, sess, "nginx:reload", result="ok", ip=req.ip)
        return _ok(req, {"message": "Nginx berhasil di-reload tanpa downtime!"})
    except nginxops.NginxError as ex:
        return _err(req, str(ex), 400)

def nginx_logs(req, app, sess, path, qs, t):
    from lib import nginxops
    domain = (qs.get("domain") or [""])[0]
    lines = validate.safe_int((qs.get("n") or ["100"])[0], 1, 1000, 100)
    try:
        data = nginxops.domain_logs(domain, lines)
        return _ok(req, data)
    except Exception as ex:
        return _err(req, str(ex), 400)


def redis_info(req, app, sess, path, qs, t):
    from lib import redisops
    data = redisops.info()
    return _ok(req, data)

def redis_flush(req, app, sess, path, form, t):
    from lib import redisops
    try:
        redisops.flush_all()
        app.audit.write(audit.ACTION, sess, "redis:flush_all", result="ok", ip=req.ip)
        return _ok(req, {"message": "Cache Redis berhasil dikosongkan"})
    except redisops.RedisError as ex:
        return _err(req, str(ex), 500)


def redis_ping(req, app, sess, path, qs, t):
    from lib import redisops
    try:
        data = redisops.ping()
        return _ok(req, data)
    except redisops.RedisError as ex:
        return _err(req, str(ex), 500)

def redis_keys(req, app, sess, path, qs, t):
    from lib import redisops
    pattern = (qs.get("q") or ["*"])[0]
    count = validate.safe_int((qs.get("count") or ["100"])[0], 1, 500, 100)
    try:
        items = redisops.list_keys(pattern=pattern, count=count)
        return _ok(req, {"items": items, "count": len(items)})
    except redisops.RedisError as ex:
        return _err(req, str(ex), 500)

def redis_get(req, app, sess, path, qs, t):
    from lib import redisops
    key = (qs.get("key") or [""])[0]
    try:
        data = redisops.get_key(key)
        return _ok(req, data)
    except redisops.RedisError as ex:
        return _err(req, str(ex), 404)

def redis_set(req, app, sess, path, form, t):
    from lib import redisops
    key = req.fval(form, "key")
    val = req.fval(form, "value")
    ttl = req.fval(form, "ttl")
    try:
        redisops.set_key(key, val, ttl)
        app.audit.write(audit.ACTION, sess, "redis:set", target=key, result="ok", ip=req.ip)
        return _ok(req, {"message": f"Key {key} berhasil disimpan"})
    except redisops.RedisError as ex:
        return _err(req, str(ex), 400)

def redis_delete(req, app, sess, path, form, t):
    from lib import redisops
    key = req.fval(form, "key")
    try:
        redisops.delete_key(key)
        app.audit.write(audit.ACTION, sess, "redis:delete", target=key, result="ok", ip=req.ip)
        return _ok(req, {"message": f"Key {key} berhasil dihapus"})
    except redisops.RedisError as ex:
        return _err(req, str(ex), 400)


# ========================= TERMINAL WEB =========================
def terminal_exec(req, app, sess, path, form, t):
    from lib import termops
    cmd_str = req.fval(form, "cmd")
    cwd = req.fval(form, "cwd", "/root")
    data = termops.run_command(cmd_str, cwd=cwd, timeout=30)
    app.audit.write(audit.ACTION, sess, "term:exec", target=cmd_str[:60], result="rc:%d" % data["rc"], ip=req.ip)
    return _ok(req, data)

# ========================= MYSQL OPS =========================
def db_mysql_create(req, app, sess, path, form, t):
    from lib import dbops
    name = req.fval(form, "name")
    user = req.fval(form, "user") or None
    pw = req.fval(form, "pass") or None
    try:
        dbops.my_create(name, user, pw)
        app.audit.write(audit.ACTION, sess, "db:mysql_create", target=name, result="ok", ip=req.ip)
        return _ok(req, {"message": f"Database {name} berhasil dibuat"})
    except dbops.DbError as ex:
        return _err(req, str(ex), 400)

def db_mysql_drop(req, app, sess, path, form, t):
    from lib import dbops
    name = req.fval(form, "name")
    try:
        dbops.my_drop(name)
        app.audit.write(audit.ACTION, sess, "db:mysql_drop", target=name, result="ok", ip=req.ip)
        return _ok(req, {"message": f"Database {name} berhasil dihapus"})
    except dbops.DbError as ex:
        return _err(req, str(ex), 400)

def db_mysql_dump(req, app, sess, path, form, t):
    from lib import dbops
    name = req.fval(form, "name")
    try:
        dump_path = dbops.my_dump(name)
        app.audit.write(audit.ACTION, sess, "db:mysql_dump", target=name, result="ok", ip=req.ip)
        return _ok(req, {"path": dump_path, "message": f"Dump {name} berhasil dibuat"})
    except dbops.DbError as ex:
        return _err(req, str(ex), 400)


def db_mysql_dump_delete(req, app, sess, path, form, t):
    from lib import dbops
    name = req.fval(form, "name")
    if not name or ".." in name or "/" in name:
        return _err(req, "Nama berkas dump tidak sah", 400)
    full = os.path.join(dbops.DUMP_DIR, name)
    if os.path.isfile(full):
        try:
            os.remove(full)
            app.audit.write(audit.ACTION, sess, "db:dump_delete", target=name, result="ok", ip=req.ip)
            return _ok(req, {"message": f"Berkas dump {name} berhasil dihapus"})
        except OSError as ex:
            return _err(req, str(ex), 400)
    return _err(req, "Berkas tidak ditemukan", 404)
