#!/usr/bin/env python3
"""Santaka apps engine — deploy Next.js / Laravel / CodeIgniter / PHP / static.

Mesin ini bagian dari Santaka Control (panel saat ini).

Setiap app = 1 folder di apps_dir/<slug>, satu blok vhost Caddy per app,
dan (bila perlu) pool PHP-FPM atau unit systemd sendiri.

Domain aplikasi mengikuti config `apps_lan_domain` (mis. "santaka" ->
<slug>.santaka) dan `apps_domain` (mis. "example.com" -> <slug>.example.com).
Bila keduanya kosong, blok Caddy memakai host default `:80`.
"""
import base64
import json
import os
import time
import re
import secrets
import shutil
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
APPS_DIR = "/opt/santaka-apps"
APPS_CONF = os.path.join(APPS_DIR, "apps.json")
LOG_DIR = os.path.join(APPS_DIR, "logs")
PHP_POOL_DIR = "/etc/php/8.2/fpm/pool.d"
DOMAIN_SUFFIX = ""
PUBLIC_DOMAIN = ""
CADDYFILE = "/etc/caddy/Caddyfile"
MANAGED = "# {name} — Santaka managed"

KINDS = ("static", "php", "laravel", "nextjs", "node", "nextprebuilt")

_STATE_DIR = "/var/lib/santaka-control"
DB_SECRET_FILE = os.path.join(_STATE_DIR, "db-admin.secret")


def configure(cfg=None):
    """Terapkan direktori & domain dari config.json. Aman dipanggil sekali saat start."""
    global APPS_DIR, APPS_CONF, LOG_DIR, PHP_POOL_DIR, DOMAIN_SUFFIX
    global PUBLIC_DOMAIN, CADDYFILE, DB_SECRET_FILE, _STATE_DIR
    cfg = cfg or {}
    APPS_DIR = os.path.abspath(str(cfg.get("apps_dir") or "/opt/santaka-apps"))
    APPS_CONF = os.path.join(APPS_DIR, "apps.json")
    LOG_DIR = os.path.join(APPS_DIR, "logs")
    PHP_POOL_DIR = str(cfg.get("php_pool_dir") or "/etc/php/8.2/fpm/pool.d")
    DOMAIN_SUFFIX = str(cfg.get("apps_lan_domain") or "").strip().strip(".")
    PUBLIC_DOMAIN = str(cfg.get("apps_domain") or "").strip().strip(".")
    CADDYFILE = str(cfg.get("caddyfile") or "/etc/caddy/Caddyfile")
    _STATE_DIR = os.path.abspath(str(cfg.get("state_dir") or _STATE_DIR))
    DB_SECRET_FILE = os.path.join(_STATE_DIR, "db-admin.secret")


def _lan_host(slug):
    """Host LAN <slug>.<apps_lan_domain>, kosong bila suffix tidak disetel."""
    return "%s.%s" % (slug, DOMAIN_SUFFIX) if DOMAIN_SUFFIX else ""


def _public_host(slug):
    """Host publik <slug>.<apps_domain>, kosong bila suffix tidak disetel."""
    return "%s.%s" % (slug, PUBLIC_DOMAIN) if PUBLIC_DOMAIN else ""


def _q(p):
    """Quote path untuk shell."""
    return "'" + str(p).replace("'", "'\\''") + "'"


def run(cmd, timeout=20):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, "", str(exc)


# Batas memori build (MB). Box 784 MB: sistem+layanan ~300 MB,
# sisanya dibagi rapi agar `npm run build` tak pernah memicu OOM.
BUILD_RAM_MB = 300


def run_limited(cmd, timeout=20, ram_mb=None, cwd=None):
    """Jalankan proses dengan batas memori virtual via ulimit -v.
    Node/npm memakai max-old-space-size; ulimit menjaga seluruh tree.
    Env build disiapkan agar composer/npm bisa berjalan non-interaktif."""
    ram = ram_mb or BUILD_RAM_MB
    capped = list(cmd)
    is_node = any(os.path.basename(c) in ("npm", "npx", "node", "yarn", "pnpm")
                  for c in capped[:3])
    proto = " ".join(
        "'" + c.replace("'", "'\\''") + "'" for c in capped)
    env_setup = (
        "export HOME=/root COMPOSER_HOME=/root/.composer "
        "COMPOSER_ALLOW_SUPERUSER=1 COMPOSER_NO_INTERACTION=1 "
        "npm_config_cache=/root/.npm CI=1 "
        # V8 perlu ruang virtual besar; batasi HEAP, bukan address space
        "NODE_OPTIONS=--max-old-space-size=256; "
    )
    if is_node:
        # ulimit -v mematikan Node (V8 reserve >1GB virtual). Batasi lewat
        # address space longgar + heap kecil + earlyoom sebagai jaring akhir.
        wrapped = "{0}ulimit -v {1}; exec {2}".format(
            env_setup, 1536 * 1024, proto)
    else:
        wrapped = "{0}ulimit -v {1}; exec {2}".format(
            env_setup, ram * 1024, proto)
    try:
        p = subprocess.run(["sh", "-c", wrapped], capture_output=True,
                           text=True, timeout=timeout, cwd=cwd)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, "", str(exc)


def load_apps():
    try:
        with open(APPS_CONF, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return []


def save_apps(apps):
    os.makedirs(APPS_DIR, exist_ok=True)
    with open(APPS_CONF, "w", encoding="utf-8") as fh:
        json.dump(apps, fh, indent=2)


def slugify(name):
    s = re.sub(r"[^a-z0-9-]+", "-", (name or "").lower()).strip("-")
    return s or "app"


def free_port(apps):
    used = {a["port"] for a in apps}
    for p in range(3000, 4000):
        if p not in used:
            return p
    raise ValueError("tidak ada port bebas 3000-3999")


def resolve_source(source):
    """Git URL -> clone; base64 ZIP/bundle -> extract; path server -> pakai langsung.
    Source "bundle:<b64 tar.gz>" = hasil build Next.js (prebuilt), tanpa build di server."""
    src = (source or "").strip()
    if not src:
        raise ValueError("sumber kosong")
    if src.startswith("bundle:"):
        d = os.path.join(APPS_DIR, "repos", secrets.token_hex(4))
        os.makedirs(d, exist_ok=True)
        zpath = os.path.join(d, "bundle.tgz")
        with open(zpath, "wb") as fh:
            fh.write(base64.b64decode(src[7:]))
        rc, out, err = run(["tar", "-xzf", zpath, "-C", d], 900)
        os.remove(zpath)
        if rc != 0:
            raise ValueError("ekstrak bundle gagal: " + (err or out)[-200:])
        # paket standalone membungkus isi dalam folder ─ ratakan
        entries = [e for e in os.listdir(d) if e != "bundle.tgz"]
        if len(entries) == 1 and os.path.isdir(os.path.join(d, entries[0])):
            inner = os.path.join(d, entries[0])
            for f in os.listdir(inner):
                os.rename(os.path.join(inner, f), os.path.join(d, f))
            os.rmdir(inner)
        if not os.path.isfile(os.path.join(d, "server.js")):
            raise ValueError("server.js tidak ditemukan di bundle")
        return d
    if re.match(r"^(https?://|git@)", src):
        d = os.path.join(APPS_DIR, "repos", secrets.token_hex(4))
        rc, out, err = run(["git", "clone", "--depth", "1", src, d], 600)
        if rc != 0:
            raise ValueError("git clone gagal: " + (err or out)[-300:])
        return d
    if src.startswith("zip:"):
        d = os.path.join(APPS_DIR, "zips", secrets.token_hex(4))
        os.makedirs(d, exist_ok=True)
        zpath = os.path.join(d, "app.zip")
        with open(zpath, "wb") as fh:
            fh.write(base64.b64decode(src[4:]))
        rc, out, err = run(["unzip", "-q", "-o", zpath, "-d", d], 300)
        if rc != 0:
            raise ValueError("unzip gagal: " + (err or out)[-300:])
        os.remove(zpath)
        entries = [e for e in os.listdir(d) if not e.startswith(".")]
        if len(entries) == 1 and os.path.isdir(os.path.join(d, entries[0])):
            inner = os.path.join(d, entries[0])
            for f in os.listdir(inner):
                os.rename(os.path.join(inner, f), os.path.join(d, f))
            os.rmdir(inner)
        return d
    path = os.path.realpath(src)
    if not os.path.isdir(path):
        raise ValueError("path di server tidak ada: " + src)
    # salin ke lokasi permanen — sumber di /tmp bisa hilang kapan saja
    dst = os.path.join(APPS_DIR, "repos", secrets.token_hex(4))
    # salin tanpa node_modules/.next/.git agar cepat & hemat disk (pipe tunggal)
    os.makedirs(dst, exist_ok=True)
    copy_cmd = (
        "tar -C {src} --exclude=node_modules --exclude=.next "
        "--exclude=.git --exclude=__pycache__ -cf - . | tar -C {dst} -xf -"
    ).format(src=_q(path), dst=_q(dst))
    rc, out, err = run(["sh", "-c", copy_cmd], 600)
    if rc != 0:
        raise ValueError("gagal menyalin file: " + (err or out)[-200:])
    return dst


def detect_kind(path):
    if os.path.isfile(os.path.join(path, "artisan")) and os.path.isdir(os.path.join(path, "app")):
        return "laravel"
    if os.path.isfile(os.path.join(path, "system", "Core", "CodeIgniter.php")) or \
       os.path.isfile(os.path.join(path, "system", "core", "CodeIgniter.php")):
        return "php"
    pkg = ""
    pj = os.path.join(path, "package.json")
    if os.path.isfile(pj):
        try:
            pkg = open(pj, encoding="utf-8", errors="replace").read()
        except OSError:
            pkg = ""
        if '"next"' in pkg:
            return "nextjs"
        return "node"
    if os.path.isfile(os.path.join(path, "index.php")):
        return "php"
    return "static"


# ---------------------------------------------------------------- caddyfile
def caddy_block(app):
    """Host untuk satu app: suffix LAN, suffix publik, dan domain kustom."""
    hosts = [h for h in (_lan_host(app["slug"]), _public_host(app["slug"])) if h]
    for extra in app.get("custom_domains", []) or []:
        if extra and extra not in hosts:
            hosts.append(extra)
    if not hosts:
        hosts = [":80"]
    head = MANAGED.format(name=app["slug"])
    if app["kind"] == "static":
        body = ("root * " + app["path"] + "\n"
                "file_server\n"
                "try_files {path} /index.html")
    elif app["kind"] in ("laravel", "php"):
        docroot = os.path.join(app["path"], "public")
        if not os.path.isdir(docroot):
            docroot = app["path"]
        body = ("root * " + docroot + "\n"
                "php_fastcgi unix//run/php/app-" + app["slug"] + ".sock\n"
                "file_server\n"
                "try_files {path} /index.php")
    else:  # nextjs / node
        body = "reverse_proxy 127.0.0.1:{}".format(app["port"])
    # kompresi: zstd untuk peramban modern, gzip sebagai cadangan
    body = "encode zstd gzip\n" + body
    # security headers untuk SEMUA site (apps + homepage) — front-line defense
    headers = (
        "header {\n"
        "    Strict-Transport-Security \"max-age=31536000; includeSubDomains\"\n"
        "    X-Content-Type-Options \"nosniff\"\n"
        "    X-Frame-Options \"DENY\"\n"
        "    Referrer-Policy \"no-referrer\"\n"
        "    Permissions-Policy \"geolocation=(), microphone=(), camera=()\"\n"
        "    -Server\n"
        "}\n"
    )
    out = []
    for h in hosts:
        addr = h if h.startswith(":") else "http://" + h
        out.append(head + "\n{addr} {{\n{hdr}{b}\n}}\n".format(
            addr=addr, b=body, hdr=headers))
    return "".join(out)


def sync_caddyfile(apps):
    marker = "— Santaka managed"
    original = ""
    if os.path.isfile(CADDYFILE):
        with open(CADDYFILE, encoding="utf-8") as fh:
            original = fh.read()
    kept, skip, depth = [], False, 0
    for line in original.splitlines(True):
        if skip:
            # hitung buka/tutup kurung: site block selesai saat depth kembali 0
            depth += line.count("{") - line.count("}")
            if depth <= 0:
                skip = False
            continue
        if line.startswith("# ") and marker in line:
            skip = True
            depth = 0  # baris marker sendiri tak punya kurung
            continue
        kept.append(line)
    new = "".join(kept).rstrip("\n") + "\n\n" + "".join(caddy_block(a) for a in apps)
    tmp = CADDYFILE + ".gen"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(new)
    rc, out, err = run(["env", "HOME=/var/lib/caddy",
                        "XDG_CONFIG_HOME=/var/lib/caddy/.config",
                        "caddy", "validate", "--config", tmp], 20)
    if rc != 0:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise ValueError("hasil caddyfile tidak valid: " + (err or out)[-400:])
    os.replace(tmp, CADDYFILE)


# ---------------------------------------------------------------- runtimes
def make_php_pool_env(app):
    """Inject ENV dari .env project ke pool FPM sebagai env[KEY].
    PHP-FPM tidak membaca file .env otomatis — ini menjembataninya."""
    slug = app.get("slug")
    path = app.get("path") or ""
    envf = os.path.join(path, ".env")
    if not slug or not os.path.isfile(envf):
        return
    pool = "/etc/php/8.2/fpm/pool.d/app-{}.conf".format(slug)
    if not os.path.isfile(pool):
        return
    src = open(pool, encoding="utf-8").read()
    src = re.sub(r"^env\[[A-Z_]+\].*\n?", "", src, flags=re.M)
    extra = []
    for line in open(envf, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        val = val.replace('"', "'")
        extra.append('env[%s] = "%s"' % (key, val))
    if extra:
        src = src.rstrip() + "\n\n; env oleh santaka-control\n" + "\n".join(extra) + "\n"
    with open(pool, "w", encoding="utf-8") as fh:
        fh.write(src)


def make_php_pool(app):
    pool = "/etc/php/8.2/fpm/pool.d/app-{}.conf".format(app["slug"])
    content = """[{slug}]
user = www-data
group = www-data
listen = /run/php/app-{slug}.sock
listen.owner = www-data
listen.group = www-data
pm = dynamic
pm.max_children = 4
pm.start_servers = 2
pm.min_spare_servers = 1
pm.max_spare_servers = 3
pm.max_requests = 400
php_admin_value[memory_limit] = 128M
php_admin_value[upload_max_filesize] = 64M
php_admin_value[post_max_size] = 64M
php_admin_value[error_log] = {log}
php_admin_flag[log_errors] = on
catch_workers_output = yes
env[PATH] = /usr/local/bin:/usr/bin:/bin""".format(slug=app["slug"], log=LOG_DIR + "/" + app["slug"] + "-php.log")
    with open(pool, "w", encoding="utf-8") as fh:
        fh.write(content)
    run(["systemctl", "restart", "php8.2-fpm"], 25)


def make_node_unit(app):
    unit_dir = "/etc/systemd/system"
    unit = unit_dir + "/santaka-app-{}.service".format(app["slug"])
    content = """[Unit]
Description=Santaka app {slug}
After=network-online.target

[Service]
Type=simple
WorkingDirectory={path}
ExecStart=/bin/bash -o pipefail -c 'exec {cmd}'
Environment=PORT={port}
Environment=HOSTNAME=127.0.0.1
Environment=NODE_ENV=production
Environment=NODE_PATH={path}/node_modules
# .env project (DB kredensial, dll) - dibuat saat deploy / lewat DETAIL
EnvironmentFile=-{path}/.env
Restart=always
RestartSec=2
MemoryHigh=320M
MemoryMax=420M
Environment=NODE_OPTIONS=--max-old-space-size=320
Environment=NEXT_TELEMETRY_DISABLED=1
StandardOutput=append:{log}
StandardError=append:{log}

[Install]
WantedBy=multi-user.target""".format(slug=app["slug"], path=app["path"],
                                     cmd=app["start_cmd"], port=app["port"],
                                     log=LOG_DIR + "/" + app["slug"] + ".log")
    with open(unit, "w", encoding="utf-8") as fh:
        fh.write(content)


# ---------------------------------------------------------------- actions
def before_deploy(app_kind, app_path):
    """Perintah build yang perlu di server sebelum app jalan.
    Semua build node/composer dijalankan dengan batas memori (run_limited)
    agar deployment besar tidak pernah memicu OOM di box 784 MB."""
    steps = []
    if app_kind in ("laravel", "php"):
        composer = shutil.which("composer")
        if composer and os.path.isfile(os.path.join(app_path, "composer.json")):
            steps.append([composer, "install", "--no-dev", "--optimize-autoloader"])
    if app_kind == "nextprebuilt":
        pass  # sudah dibangun di luar; tidak ada langkah build
    if app_kind == "nextjs":
        npm = shutil.which("npm")
        if npm:
            steps.append([npm, "install", "--no-audit", "--no-fund"])
            # build memakan RAM terbanyak: batasi heap + matikan telemetri
            steps.append(["env", "NODE_OPTIONS=--max-old-space-size=256",
                          "NEXT_TELEMETRY_DISABLED=1",
                          "NEXT_FONT_GOOGLE_MOCKED_RESPONSES=1",
                          npm, "run", "build"])
        # standalone bila tersedia (paling hemat RAM), jika tidak next start
        start_file = os.path.join(app_path, ".next", "standalone", "server.js")
        if os.path.isfile(start_file):
            start_cmd = "node .next/standalone/server.js"
        else:
            start_cmd = "npx next start -p ${PORT}"
    elif app_kind == "node":
        npm = shutil.which("npm")
        if npm and os.path.isfile(os.path.join(app_path, "package.json")):
            steps.append([npm, "install"])
    return steps


def start_runtime(app, apps):
    if app["kind"] in ("laravel", "php"):
        make_php_pool(app)
        make_php_pool_env(app)   # inject DB_* dari .env ke pool FPM
        run(["systemctl", "restart", "php8.2-fpm"], 20)
    elif app["kind"] in ("nextjs", "node", "nextprebuilt"):
        # node tidak membaca .env otomatis — systemd EnvironmentFile yang menjembatani
        make_node_unit(app)   # wajib: regenerasi unit agar berisi EnvironmentFile
        if app["kind"] == "nextprebuilt":
            # .next/static tidak ikut dalam bundle standalone — salin manual
            src_static = os.path.join(app["path"], "..", "static")
            dst_static = os.path.join(app["path"], ".next", "static")
            if os.path.isdir(src_static) and not os.path.isdir(dst_static):
                rc, _, err = run(["cp", "-a", src_static, dst_static], 120)
        run(["systemctl", "daemon-reload"], 10)
        run(["systemctl", "enable", "--now", "santaka-app-" + app["slug"]], 15)


def stop_runtime(app):
    if app["kind"] in ("laravel", "php"):
        pool = PHP_POOL_DIR + "/app-{}.conf".format(app["slug"])
        if os.path.isfile(pool):
            os.remove(pool)
            run(["systemctl", "reload", "php8.2-fpm"], 20)
    elif app["kind"] in ("nextjs", "node", "nextprebuilt"):
        run(["systemctl", "disable", "--now", "santaka-app-" + app["slug"]], 15)
        unit = "/etc/systemd/system/santaka-app-{}.service".format(app["slug"])
        if os.path.isfile(unit):
            os.remove(unit)
        run(["systemctl", "daemon-reload"], 10)


def deploy(slug, source, kind=None, start_cmd=None, name=None, with_db=False, db_engine="postgres"):
    os.makedirs(LOG_DIR, exist_ok=True)
    apps = load_apps()
    slug = slugify(slug)
    if any(a["slug"] == slug for a in apps):
        raise ValueError("slug sudah dipakai: " + slug)
    path = resolve_source(source)
    kind = kind or detect_kind(path)
    if kind not in KINDS:
        raise ValueError("jenis aplikasi tidak dikenal: " + kind)
    port = free_port(apps)
    if kind == "nextprebuilt":
        # hasil build standalone: node server.js (node_modules sudah di dalam)
        start_cmd = "node server.js"
        if not name:
            name = slug
    elif kind in ("nextjs", "node"):
        if not start_cmd:
            start_cmd = "npm start"
            try:
                pkg = json.loads(open(os.path.join(path, "package.json"),
                                      encoding="utf-8").read())
                scripts = pkg.get("scripts") or {}
                if isinstance(scripts.get("start"), str):
                    start_cmd = "npm start"
                elif isinstance(scripts.get("dev"), str):
                    # Next.js: pakai PORT dari environment systemd
                    start_cmd = ("npx next start -p ${PORT}"
                                 if kind == "nextjs" else "npm run dev")
                elif kind == "nextjs":
                    start_cmd = "npx next start -p ${PORT}"
            except (OSError, ValueError):
                if kind == "nextjs":
                    start_cmd = "npx next start -p ${PORT}"
    # database otomatis untuk project dinamis (opsional di wizard)
    db_info = None
    if with_db and kind in ("php", "laravel", "nextjs", "node", "nextprebuilt"):
        if db_engine == "mysql":
            db_info, db_err = mysql_provision(slug)
        else:
            db_info, db_err = db_provision(slug)
        if db_err:
            db_info = None                      # deploy tetap jalan tanpa DB
    app = {"slug": slug, "name": name or slug, "kind": kind, "path": path,
           "domain": _lan_host(slug) or _public_host(slug) or slug, "port": port,
           "start_cmd": start_cmd, "created": int(__import__("time").time()),
           "db": db_info}

    for step in before_deploy(kind, path):
        # build (npm/composer) dibatasi RAM agar tak pernah OOM di box 784 MB
        rc, out, err = run_limited(step, 900, cwd=path)
        if rc != 0:
            raise ValueError("build gagal ('{0}'): {1}".format(
                " ".join(step[-2:])[:80], (err or out)[-280:]))
    if db_info:
        db_write_env(app, db_info)

    sync_caddyfile(apps + [app])
    start_runtime(app, apps + [app])
    run(["systemctl", "reload", "caddy"], 15)
    apps.append(app)
    save_apps(apps)
    return app


def undeploy(slug):
    apps = load_apps()
    app = next((a for a in apps if a["slug"] == slug), None)
    if not app:
        raise ValueError("app tidak ditemukan: " + slug)
    stop_runtime(app)
    # hapus database project bila ada
    if app.get("db"):
        db_drop(slug)
    remaining = [a for a in apps if a["slug"] != slug]
    sync_caddyfile(remaining)
    # wajib: tanpa reload, Caddy masih menyajikan vhost app yang baru dihapus
    # dan mem-proxy ke port yang sudah mati (gejala: 502, bukan 404)
    run(["systemctl", "reload", "caddy"], 15)
    save_apps(remaining)
    return True


def get_app(slug):
    """Cari satu app berdasarkan slug."""
    for a in load_apps():
        if a["slug"] == slug:
            return a
    return None


def _dir_size(path):
    """Total ukuran folder (MB) tanpa mengikuti symlink."""
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                continue
    return round(total / (1024 * 1024), 2)


def app_stats(app):
    """Info lengkap satu project untuk halaman detail."""
    slug = app["slug"]
    path = app.get("path") or ""
    kind = app.get("kind")

    # status runtime
    state = "static" if kind == "static" else "stopped"
    mem_mb = 0
    uptime_s = 0
    if kind in ("nextjs", "node", "nextprebuilt"):
        unit = "santaka-app-" + slug
        rc, out, _ = run(["systemctl", "is-active", unit], 5)
        state = (out or "").strip() or "unknown"
        rc2, out2, _ = run(["systemctl", "show", unit, "-p", "MemoryCurrent",
                            "--value"], 5)
        try:
            mem_mb = round(int((out2 or "0").strip()) / 1048576, 1)
        except ValueError:
            mem_mb = 0
        rc3, out3, _ = run(["systemctl", "show", unit, "-p",
                            "ActiveEnterTimestampMonotonic", "--value"], 5)
        try:
            uptime_s = int(time.time() - int((out3 or "0").strip()) / 1e6)
            if uptime_s < 0 or uptime_s > 10 ** 8:
                uptime_s = 0
        except ValueError:
            uptime_s = 0
    elif kind in ("php", "laravel"):
        rc, out, _ = run(["systemctl", "is-active", "php8.2-fpm"], 5)
        state = "running" if (out or "").strip() == "active" else "stopped"

    # file & env
    files = 0
    try:
        for _r, _d, fs in os.walk(path):
            files += len(fs)
    except OSError:
        files = 0
    env_path = os.path.join(path, ".env")
    env_content = ""
    if os.path.isfile(env_path):
        try:
            env_content = open(env_path, encoding="utf-8",
                               errors="replace").read()[:20000]
        except OSError:
            env_content = ""

    return {
        "slug": slug,
        "name": app.get("name") or slug,
        "kind": kind,
        "path": path,
        "domain": _public_host(slug) or _lan_host(slug) or slug,
        "url": ("https://%s" % _public_host(slug)) if _public_host(slug) else "",
        "state": state,
        "memory_mb": mem_mb,
        "uptime_s": max(0, uptime_s),
        "disk_mb": _dir_size(path) if path and os.path.isdir(path) else 0,
        "files": files,
        "custom_domains": app.get("custom_domains") or [],
        "created": app.get("created"),
        "port": app.get("port"),
        "start_cmd": app.get("start_cmd"),
        "env": env_content,
        "has_env": bool(env_content),
    }


def write_env(slug, content):
    """Tulis file .env project (validasi: hanya KEY=VALUE, tanpa shebang)."""
    app = get_app(slug)
    if not app:
        raise ValueError("project tidak ditemukan")
    path = app.get("path") or ""
    if not path or not os.path.isdir(path):
        raise ValueError("folder project tidak ada")
    for line in content.splitlines():
        s2 = line.strip()
        if not s2 or s2.startswith("#"):
            continue
        if "=" not in s2:
            raise ValueError("baris tidak valid (harus KEY=VALUE): " + s2[:40])
        key = s2.split("=", 1)[0].strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError("nama variabel tidak valid: " + key[:40])
    target = os.path.join(path, ".env")
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(content)
    os.chmod(tmp, 0o600)
    os.replace(tmp, target)
    # restart runtime agar env baru terbaca
    if app.get("kind") in ("nextjs", "node", "nextprebuilt"):
        run(["systemctl", "restart", "santaka-app-" + slug], 20)
    return True


def redeploy(slug):
    """Bangun ulang project di tempat (git pull / composer+npm build / reload).
    Tidak mengubah slug, domain, atau port."""
    apps = load_apps()
    app = None
    for a in apps:
        if a["slug"] == slug:
            app = a
            break
    if not app:
        raise ValueError("project tidak ditemukan")

    path = app.get("path") or ""
    if not path or not os.path.isdir(path):
        raise ValueError("folder project hilang: " + path)

    kind = app.get("kind")
    steps = []

    # git repo -> tarik pembaruan
    if os.path.isdir(os.path.join(path, ".git")):
        steps.append(["git", "-C", path, "pull", "--ff-only"])

    steps.extend(before_deploy(kind, path))

    for step in steps:
        rc, out, err = run_limited(step, 900, cwd=path)
        if rc != 0:
            raise ValueError("redeploy gagal ('{0}'): {1}".format(
                " ".join(step[-2:])[:60], (err or out)[-260:]))

    # restart runtime (php: reload fpm; node: restart unit)
    if kind in ("nextjs", "node", "nextprebuilt"):
        run(["systemctl", "restart", "santaka-app-" + slug], 30)
    elif kind in ("php", "laravel"):
        app_dict = {"slug": slug, "kind": kind, "path": path}
        make_php_pool(app_dict)        # pool baru bila basis kode berubah
        make_php_pool_env(app_dict)    # injek .env (DB kredensial) ke pool
        run(["systemctl", "restart", "php8.2-fpm"], 20)
    run(["systemctl", "reload", "caddy"], 15)
    return app


# ---------------------------------------------------------------- database
DB_ADMIN_ROLE = "santaka_admin"


def _db_admin_pass():
    try:
        return open(DB_SECRET_FILE).read().strip()
    except OSError:
        return None


def mysql_provision(slug):
    """Buat database + user MySQL/MariaDB untuk project (prefix santaka_).
    Return (dict koneksi, None) atau (None, pesan error). Idempotent."""
    mysql_admin = "debian-sys-maint"           # user resmi Debian untuk automation
    cred_file = "/etc/mysql/debian.cnf"
    def mysql_args(extra_db=None):
        args = ["mysql"]
        if os.path.isfile(cred_file):
            # gunakan kredensial debian-sys-maint otomatis
            args = ["mysql", "--defaults-extra-file=" + cred_file]
        if extra_db:
            args.append(extra_db)
        return args

    dbname = "santaka_" + slug.replace("-", "_")[:40]
    dbuser = dbname + "_u"
    dbpass = __import__("secrets").token_hex(12)

    def q(sql):
        return run(mysql_args() + ["-e", sql], 30)

    # role/user
    rc, out, err = q(
        "CREATE USER IF NOT EXISTS '{u}'@'localhost' IDENTIFIED BY '{p}'".format(u=dbuser, p=dbpass))
    if rc != 0:
        return None, "gagal buat user: " + err[:150]
    # database
    rc, out, err = q(
        "CREATE DATABASE IF NOT EXISTS {d} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci".format(d=dbname))
    if rc != 0:
        return None, "gagal buat database: " + err[:150]
    # grant penuh untuk project ini saja
    rc, out, err = q(
        "GRANT ALL PRIVILEGES ON {d}.* TO '{u}'@'localhost'".format(d=dbname, u=dbuser))
    if rc != 0:
        return None, "gagal grant: " + err[:150]
    rc, out, err = q("FLUSH PRIVILEGES")
    if rc != 0:
        return None, "gagal flush: " + err[:100]

    return {
        "engine": "mysql",
        "host": "127.0.0.1",
        "port": "3306",
        "database": dbname,
        "username": dbuser,
        "password": dbpass,
    }, None


def mysql_drop(slug):
    """Hapus database + user MySQL project."""
    cred_file = "/etc/mysql/debian.cnf"
    args = ["mysql"]
    if os.path.isfile(cred_file):
        args = ["mysql", "--defaults-extra-file=" + cred_file]
    dbname = "santaka_" + slug.replace("-", "_")[:40]
    dbuser = dbname + "_u"
    run(args + ["-e", "DROP DATABASE IF EXISTS {d}".format(d=dbname)], 30)
    run(args + ["-e", "DROP USER IF EXISTS '{u}'@'localhost'".format(u=dbuser)], 30)


def db_provision(slug):
    """Buat database + user untuk project (postgres, prefix santaka_).
    Return (dict koneksi, None) atau (None, pesan error). Idempotent."""
    admin_pass = _db_admin_pass()
    if not admin_pass:
        return None, "role admin belum disiapkan"
    dbname = "santaka_" + slug.replace("-", "_")[:40]
    dbuser = dbname + "_u"
    dbpass = __import__("secrets").token_hex(12)

    def psql(sql, db=None):
        """Jalankan psql sebagai postgres, cwd aman, tanpa warning cd."""
        cmd = ["sudo", "-u", "postgres", "-H", "psql", "-v", "ON_ERROR_STOP=1"]
        if db:
            cmd += ["-d", db]
        cmd += ["-c", sql]
        return run(cmd, 30)

    # role
    rc, _, err = psql(
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{u}') "
        "THEN CREATE ROLE {u} LOGIN PASSWORD '{p}'; END IF; END $$;".format(u=dbuser, p=dbpass))
    if rc != 0:
        return None, "gagal buat role: " + err[:150]
    # database
    rc, _, err = psql(
        "SELECT 1 FROM pg_database WHERE datname='{d}'".format(d=dbname))
    if rc != 0:
        return None, "gagal cek database: " + err[:150]
    rc, _, err = psql(
        "CREATE DATABASE {d} OWNER {u}".format(d=dbname, u=dbuser))
    if rc != 0 and "already exists" not in err:
        return None, "gagal buat database: " + err[:150]
    # revoke publik + grant penuh + throttle/rate-limit role project
    rc, _, err = psql(
        "REVOKE ALL ON DATABASE {d} FROM PUBLIC; "
        "GRANT ALL PRIVILEGES ON DATABASE {d} TO {u}; "
        "ALTER ROLE {u} CONNECTION LIMIT 8; "
        "ALTER ROLE {u} SET statement_timeout = '30s'; "
        "ALTER ROLE {u} SET idle_in_transaction_session_timeout = '60s'; "
        "ALTER ROLE {u} SET work_mem = '2MB'".format(d=dbname, u=dbuser), dbname)
    if rc != 0:
        return None, "gagal grant/limit: " + err[:150]
    rc, _, err = psql(
        "ALTER DATABASE {d} SET statement_timeout = '60s'".format(d=dbname))
    if rc != 0:
        return None, "gagal database timeout: " + err[:100]
    return {
        "engine": "postgres",
        "host": "127.0.0.1",
        "port": "5432",
        "database": dbname,
        "username": dbuser,
        "password": dbpass,
    }, None


def db_write_env(app, db):
    """Gabungkan kredensial DB ke file .env project (tanpa menimpa yang ada)."""
    path = app.get("path") or ""
    if not path or not os.path.isdir(path):
        return
    lines = [
        "# database (auto oleh santaka-control)",
        "DB_ENGINE=%s" % db["engine"],
        "DB_HOST=%s" % db["host"],
        "DB_PORT=%s" % db["port"],
        "DB_DATABASE=%s" % db["database"],
        "DB_USERNAME=%s" % db["username"],
        "DB_PASSWORD=%s" % db["password"],
    ]
    if db["engine"] == "postgres":
        url = "postgres://%s:%s@%s:%s/%s" % (db["username"], db["password"],
                                             db["host"], db["port"], db["database"])
    else:
        url = "mysql://%s:%s@%s:%s/%s" % (db["username"], db["password"],
                                          db["host"], db["port"], db["database"])
    lines.append("DATABASE_URL=%s" % url)
    target = os.path.join(path, ".env")
    existing = ""
    if os.path.isfile(target):
        try:
            existing = open(target, encoding="utf-8", errors="replace").read()
        except OSError:
            existing = ""
    # jangan duplikat: buang DB_* & DATABASE_URL lama
    keep = [l for l in existing.splitlines()
            if l.strip() and not l.strip().startswith("DB_") and not l.strip().startswith("DATABASE_URL=")]
    newcontent = "\n".join(keep + lines) + "\n"
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(newcontent)
    os.chmod(tmp, 0o600)
    os.replace(tmp, target)


def db_drop(slug):
    """Hapus database + user project (postgres & mysql)."""
    dbname = "santaka_" + slug.replace("-", "_")[:40]
    dbuser = dbname + "_u"
    admin_pass = _db_admin_pass()
    if admin_pass:   # postgres
        run(["sudo", "-u", "postgres", "psql", "-c",
             "DROP DATABASE IF EXISTS {d}".format(d=dbname)], 30)
        run(["sudo", "-u", "postgres", "psql", "-c",
             "DROP ROLE IF EXISTS {u}".format(u=dbuser)], 30)
    mysql_drop(slug)  # mysql (aman bila tidak ada)


def list_apps():
    apps = load_apps()
    for a in apps:
        a["url"] = "http://{}:{}".format(a["domain"], a["port"])
        if a["kind"] in ("nextjs", "node", "nextprebuilt"):
            rc, out, _ = run(["systemctl", "is-active", "santaka-app-" + a["slug"]], 5)
            a["state"] = out.strip() or "unknown"
        else:
            a["state"] = "static" if a["kind"] == "static" else "php-fpm"
    return apps


def app_log(slug, n=200):
    if not re.fullmatch(r"[a-z0-9-]+", slug or ""):
        raise ValueError("slug tidak valid")
    lines = []
    for f in (LOG_DIR + "/" + slug + ".log", LOG_DIR + "/" + slug + "-php.log"):
        if os.path.isfile(f):
            try:
                with open(f, encoding="utf-8", errors="replace") as fh:
                    lines += fh.read().splitlines()[-n:]
            except OSError:
                pass
    rc, out, _ = run(["journalctl", "-u", "santaka-app-" + slug, "-n", str(n),
                      "--no-pager", "-o", "short-iso"], 10)
    if out:
        lines += out.splitlines()
    return "\n".join(lines[-n:])
