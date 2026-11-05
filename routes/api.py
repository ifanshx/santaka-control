"""Router API + form. Setiap entri menyatakan izin yang dibutuhkan.

Guard izin dipusatkan di sini supaya tidak ada route yang lupa memeriksanya.
"""
import json
import os
import time

from lib import audit, cmd, perm, validate
from ui import i18n

# route GET: path -> (izin, nama handler di routes/handlers)
GET_ROUTES = {
    "/api/stats": (perm.VIEW, "stats"),
    "/api/info": (perm.VIEW, "info"),
    "/api/services": (perm.VIEW, "services_list"),
    "/api/files": (perm.VIEW, "files_list"),
    "/api/files/read": (perm.VIEW, "files_read"),
    "/api/docker": (perm.VIEW, "docker_list"),
    "/api/apps": (perm.VIEW, "apps_list"),
    "/api/web": (perm.VIEW, "web_info"),
    "/api/db": (perm.VIEW, "db_list"),
    "/api/backups": (perm.VIEW, "backup_list"),
    "/api/storage": (perm.VIEW, "storage_list"),
    "/api/network": (perm.VIEW, "network_list"),
    "/api/cron": (perm.VIEW, "cron_list"),
    "/api/audit": (perm.VIEW, "audit_list"),
    "/api/users": (perm.USER_MANAGE, "users_list"),
    "/api/sessions": (perm.SECURITY, "sessions_list"),
    "/api/alerts": (perm.ALERTS, "alerts_info"),
    "/api/nginx/sites": (perm.VIEW, "nginx_sites"),
    "/api/nginx/vhost": (perm.VIEW, "nginx_vhost"),
    "/api/nginx/test": (perm.VIEW, "nginx_test"),
    "/api/nginx/logs": (perm.LOG_VIEW, "nginx_logs"),
    "/api/redis/info": (perm.VIEW, "redis_info"),
    "/api/redis/ping": (perm.VIEW, "redis_ping"),
    "/api/redis/keys": (perm.VIEW, "redis_keys"),
    "/api/redis/get": (perm.VIEW, "redis_get"),
}

# route POST: path -> (izin, handler)
POST_ROUTES = {
    "/api/services": (perm.SERVICE, "service_action"),
    "/api/files/mkdir": (perm.FILE_WRITE, "files_mkdir"),
    "/api/files/delete": (perm.FILE_WRITE, "files_delete"),
    "/api/files/rename": (perm.FILE_WRITE, "files_rename"),
    "/api/files/save": (perm.FILE_WRITE, "files_save"),
    "/api/files/touch": (perm.FILE_WRITE, "files_touch"),
    "/api/logs": (perm.LOG_VIEW, "logs_read"),
    "/api/web/validate": (perm.VIEW, "web_validate"),
    "/api/web/apply": (perm.WEB_CONFIG, "web_apply"),
    "/api/apps/action": (perm.APP_CONTROL, "apps_action"),
    "/api/apps/env": (perm.APP_DEPLOY, "apps_env"),
    "/api/apps/deploy": (perm.APP_DEPLOY, "apps_deploy"),
    "/api/db/action": (perm.DB_MANAGE, "db_action"),
    "/api/backup/action": (perm.BACKUP_RUN, "backup_action"),
    "/api/docker/action": (perm.DOCKER, "docker_action"),
    "/api/storage/action": (perm.STORAGE, "storage_action"),
    "/api/network/action": (perm.NETWORK, "network_action"),
    "/api/cron/action": (perm.CRON_WRITE, "cron_action"),
    "/api/users/action": (perm.USER_MANAGE, "users_action"),
    "/api/security/action": (perm.SECURITY, "security_action"),
    "/api/alerts/action": (perm.ALERTS, "alerts_action"),
    "/api/maintenance/action": (perm.MAINT, "maintenance_action"),
    "/api/nginx/add": (perm.WEB_CONFIG, "nginx_add"),
    "/api/nginx/delete": (perm.WEB_CONFIG, "nginx_delete"),
    "/api/nginx/save": (perm.WEB_CONFIG, "nginx_save"),
    "/api/nginx/reload": (perm.WEB_CONFIG, "nginx_reload"),
    "/api/project/deploy_zip": (perm.WEB_CONFIG, "project_deploy_zip"),
    "/api/redis/flush": (perm.SERVICE, "redis_flush"),
    "/api/redis/set": (perm.SERVICE, "redis_set"),
    "/api/redis/delete": (perm.SERVICE, "redis_delete"),
    "/api/terminal/exec": (perm.SECURITY, "terminal_exec"),
    "/api/db/mysql/create": (perm.DB_MANAGE, "db_mysql_create"),
    "/api/db/mysql/drop": (perm.DB_MANAGE, "db_mysql_drop"),
    "/api/db/mysql/dump": (perm.DB_MANAGE, "db_mysql_dump"),
    "/api/db/mysql/dump/delete": (perm.DB_MANAGE, "db_mysql_dump_delete"),
}

# route dinamis (prefix): path-awalan -> (izin, handler)
GET_PREFIX = [
    ("/api/files/download", perm.VIEW, "files_download"),
    ("/api/services/", perm.LOG_VIEW, "service_logs"),
    ("/api/apps/", perm.VIEW, "app_detail"),
]

_handlers = None


def handlers():
    """Muat modul handler secara lambat (hindari impor melingkar)."""
    global _handlers
    if _handlers is None:
        from . import handlers as h
        _handlers = h
    return _handlers


def _resolve(mod, name):
    fn = getattr(handlers(), name, None)
    if fn is None:
        raise RuntimeError("handler tidak ditemukan: %s" % name)
    return fn


def dispatch_get(req, app, sess, path, qs, t):
    for prefix, needed, name in GET_PREFIX:
        if path.startswith(prefix):
            if not perm.can(sess, needed):
                app.audit.write(audit.DENIED, sess, "get:" + prefix,
                                result="denied", ip=req.ip)
                return req.send_json({"error": "akses ditolak"}, 403)
            return _resolve("get", name)(req, app, sess, path, qs, t)

    entry = GET_ROUTES.get(path)
    if not entry:
        return req.send_json({"error": "endpoint tidak ditemukan"}, 404)
    needed, name = entry
    if not perm.can(sess, needed):
        app.audit.write(audit.DENIED, sess, "get:" + path,
                        result="denied", ip=req.ip)
        return req.send_json({"error": "akses ditolak"}, 403)
    return _resolve("get", name)(req, app, sess, path, qs, t)


def dispatch_post(req, app, sess, path, form, t):
    entry = POST_ROUTES.get(path)
    if not entry:
        return req.send_json({"error": "endpoint tidak ditemukan"}, 404)
    needed, name = entry
    if not perm.can(sess, needed):
        app.audit.write(audit.DENIED, sess, "post:" + path,
                        result="denied", ip=req.ip)
        return req.send_json({"error": "akses ditolak"}, 403)
    return _resolve("post", name)(req, app, sess, path, form, t)


def dispatch_form(req, app, sess, path, form, t, back):
    """POST dari <form> HTML tanpa JS: jalankan lalu kembali ke halaman asal."""
    fake = req
    entry = POST_ROUTES.get(path)
    if not entry:
        return req.redirect(back)
    needed, name = entry
    if not perm.can(sess, needed):
        app.audit.write(audit.DENIED, sess, "form:" + path,
                        result="denied", ip=req.ip)
        return req.redirect(back + ("&" if "?" in back else "?") + "err=denied")
    result = _resolve("post", name)(fake, app, sess, path, form, t)
    # API handler sudah mengirim respons JSON; untuk form kita arahkan balik.
    return None if result is None else req.redirect(back)


def handle_upload(req, app, sess, path, t):
    """Unggah multipart streaming: tidak menahan seluruh isi di memori."""
    entry = ("/api/upload", perm.FILE_WRITE)
    if not perm.can(sess, entry[1]):
        app.audit.write(audit.DENIED, sess, "upload", result="denied", ip=req.ip)
        return req.send_json({"error": "akses ditolak"}, 403)
    from . import handlers as h
    return h.upload_stream(req, app, sess, path, t)
