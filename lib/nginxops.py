"""Operasi Nginx: daftar vhost, buat situs, reverse proxy, editor konfigurasi dengan pengujian sintaks.

Semua perubahan konfigurasi diuji via `nginx -t` sebelum diterapkan (rollback otomatis jika sintaks salah).
"""
import os
import re
import shutil
import tempfile
import time

from . import cmd, validate

# Nilai default aman untuk Debian/Ubuntu; ditimpa oleh configure(cfg).
WEB_ROOT = "/var/www"
LOG_DIR = "/var/log/nginx"
VHOST_DIR = "/etc/nginx/conf.d"
NGINX_BIN = ""
CONF_PATH = ""

_NGINX_CANDIDATES = ("/www/server/nginx/sbin/nginx", "/usr/sbin/nginx",
                     "/usr/local/sbin/nginx", "/usr/bin/nginx")
_VHOST_CANDIDATES = ("/etc/nginx/conf.d", "/www/server/panel/vhost/nginx",
                     "/etc/nginx/sites-enabled")


def configure(cfg=None):
    """Terapkan lokasi runtime dari config.json. Aman dipanggil sekali saat start."""
    global WEB_ROOT, LOG_DIR, VHOST_DIR, NGINX_BIN, CONF_PATH
    cfg = cfg or {}
    WEB_ROOT = os.path.abspath(str(cfg.get("web_root") or "/var/www"))
    LOG_DIR = os.path.abspath(str(cfg.get("nginx_log_dir") or "/var/log/nginx"))

    wanted = str(cfg.get("nginx_bin") or "").strip()
    seen = set()
    candidates = []
    for cand in ([wanted] if wanted else []) + list(_NGINX_CANDIDATES) + [
            shutil.which("nginx") or ""]:
        if cand and cand not in seen:
            seen.add(cand)
            candidates.append(cand)
    NGINX_BIN = next((c for c in candidates if os.path.exists(c)), "")

    vdir = str(cfg.get("nginx_vhost_dir") or "").strip()
    if not vdir:
        vdir = next((d for d in _VHOST_CANDIDATES if os.path.isdir(d)),
                    _VHOST_CANDIDATES[0])
    VHOST_DIR = os.path.abspath(vdir)
    CONF_PATH = str(cfg.get("nginx_conf") or "").strip()


def site_root(domain):
    """Docroot situs untuk sebuah domain (web_root/domain)."""
    return os.path.join(WEB_ROOT, str(domain))


def log_path(domain, error=False):
    """Lokasi berkas log akses/galat untuk domain."""
    return os.path.join(LOG_DIR, "%s%s.log" % (domain, ".error" if error else ""))


class NginxError(Exception):
    pass


def _run_nginx(args, timeout=15):
    bin_path = NGINX_BIN or shutil.which("nginx") or "nginx"
    rc, out, err = cmd.run([bin_path] + args, timeout=timeout)
    return rc, (out or "").strip(), (err or "").strip()


def test_config(conf_file=None):
    """Uji sintaks Nginx (nginx -t). Kembalikan (ok, pesan_error)."""
    args = ["-t"]
    target = conf_file or CONF_PATH
    if target:
        args = ["-t", "-c", target]
    rc, out, err = _run_nginx(args, timeout=15)
    blob = (out + "\n" + err).strip()
    if rc == 0 and ("syntax is ok" in blob or "test is successful" in blob):
        return True, "Sintaks Nginx valid."
    return False, blob or "Uji sintaks Nginx gagal."


def reload_nginx():
    """Reload Nginx aman: uji dulu, reload jika valid."""
    ok, msg = test_config()
    if not ok:
        raise NginxError("Konfigurasi Nginx tidak valid, batal reload:\n" + msg)
    rc, out, err = _run_nginx(["-s", "reload"], timeout=15)
    if rc != 0:
        raise NginxError(err or out or "Gagal me-reload Nginx")
    return True


_VERSION_CACHE = {"at": 0.0, "value": ""}


def version():
    """Versi Nginx aktif (di-cache 5 menit) untuk ditampilkan di panel."""
    now = time.time()
    if _VERSION_CACHE["value"] and now - _VERSION_CACHE["at"] < 300:
        return _VERSION_CACHE["value"]
    rc, out, err = _run_nginx(["-v"], timeout=5)
    blob = (err or "") + " " + (out or "")
    match = re.search(r"nginx/([0-9][0-9.]+)", blob)
    value = match.group(1) if match else ""
    _VERSION_CACHE.update({"at": now, "value": value})
    return value


def list_vhosts():
    """Daftar virtual host pengguna di direktori vhost yang dikonfigurasi.

    Berkas pendukung (potongan `map`/`upstream`, endpoint status Nginx) tidak
    dihitung sebagai situs supaya panel hanya menampilkan vhost sungguhan.
    """
    os.makedirs(VHOST_DIR, exist_ok=True)
    rows = []
    try:
        filenames = os.listdir(VHOST_DIR)
    except OSError:
        return rows

    for fname in sorted(filenames):
        if not fname.endswith(".conf") or fname.startswith("0."):
            continue
        full = os.path.join(VHOST_DIR, fname)
        if not os.path.isfile(full):
            continue
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            continue

        if not re.search(r"(^|\n)\s*server\s*\{", content):
            continue
        if "stub_status" in content:
            continue

        # Ekstrak server_name
        server_names = []
        sn_match = re.search(r"server_name\s+([^;]+);", content)
        if sn_match:
            server_names = sn_match.group(1).strip().split()

        # Ekstrak root direktori
        root_dir = ""
        root_match = re.search(r"root\s+([^;]+);", content)
        if root_match:
            root_dir = root_match.group(1).strip()

        # Ekstrak proxy target jika ada
        proxy_pass = ""
        proxy_match = re.search(r"proxy_pass\s+([^;]+);", content)
        if proxy_match:
            proxy_pass = proxy_match.group(1).strip()

        # Cek SSL
        has_ssl = "ssl_certificate" in content or "listen 443" in content

        domain_main = server_names[0] if server_names else fname[:-5]
        target_online = None
        if proxy_pass:
            try:
                import urllib.parse, socket
                parsed = urllib.parse.urlparse(proxy_pass)
                p_host = parsed.hostname or "127.0.0.1"
                p_port = parsed.port or (443 if parsed.scheme == "https" else 80)
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.2)
                res = sock.connect_ex((p_host, int(p_port)))
                sock.close()
                target_online = (res == 0)
            except Exception:
                target_online = False

        rows.append({
            "file": fname,
            "path": full,
            "domain": domain_main,
            "aliases": server_names[1:] if len(server_names) > 1 else [],
            "root": root_dir,
            "proxy": proxy_pass,
            "ssl": has_ssl,
            "target_online": target_online,
            "type": "Reverse Proxy" if proxy_pass else "PHP/Static",
            "size": os.path.getsize(full),
            "mtime": int(os.path.getmtime(full)),
        })
    return rows


def add_vhost(domain, root_dir=None, proxy_pass=None, aliases=None, php_version="84", is_fullstack=False, api_pass=None):
    """Buat vhost Nginx baru secara aman dengan verifikasi dan reload otomatis."""
    domain = re.sub(r"^https?://", "", (domain or "").strip().lower()).rstrip("/")
    if not validate.hostname(domain):
        raise NginxError("Nama domain tidak valid: %s" % domain)

    all_domains = [domain]
    if aliases:
        for a in aliases:
            a = a.strip().lower()
            if a and validate.hostname(a) and a not in all_domains:
                all_domains.append(a)

    vhost_file = os.path.join(VHOST_DIR, "%s.conf" % domain)
    if os.path.exists(vhost_file):
        raise NginxError("Situs %s sudah ada." % domain)

    if not root_dir:
        root_dir = site_root(domain)
    root_dir = os.path.abspath(root_dir)
    os.makedirs(root_dir, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    domains_str = " ".join(all_domains)
    acc_log = log_path(domain)
    err_log = log_path(domain, error=True)

    if is_fullstack and api_pass:
        api_pass = api_pass.strip()
        if not api_pass.endswith("/"):
            api_pass += "/"
        if not api_pass.endswith("/api/"):
            api_pass += "api/"

        index_file = os.path.join(root_dir, "index.html")
        if not os.path.exists(index_file):
            try:
                with open(index_file, "w", encoding="utf-8") as fh:
                    fh.write(f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="utf-8">
    <title>Situs Siap &middot; {domain}</title>
    <style>body {{ font-family: sans-serif; background: #0B0F17; color: #F8FAFC; text-align: center; padding: 40px; }}</style>
</head>
<body>
    <h1>Situs {domain} Siap!</h1>
    <p>Unggah berkas Next.js frontend Anda ke folder ini via menu File Explorer atau tombol Upload ZIP.</p>
</body>
</html>""")
            except OSError:
                pass

        vhost_content = f"""server
{{
    listen 80;
    server_name {domains_str};
    index index.html index.htm;
    root {root_dir};

    access_log {acc_log};
    error_log {err_log};

    # Enterprise Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Gzip Optimization
    gzip on;
    gzip_min_length 1k;
    gzip_comp_level 4;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;
    gzip_vary on;

    # Jalur 1: Backend REST API
    location /api/ {{
        proxy_pass {api_pass};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    # Jalur 2: Frontend Next.js / Static SPA fallback
    location / {{
        try_files $uri $uri/ /index.html;
    }}

    location /_next/static/ {{
        expires 30d;
        add_header Cache-Control "public, immutable";
    }}

    location ~ ^/(\\.user.ini|\\.htaccess|\\.git|\\.env|\\.svn|\\.project|LICENSE|README.md)
    {{
        return 404;
    }}
}}
"""
    elif proxy_pass:
        proxy_pass = proxy_pass.strip()
        vhost_content = f"""server
{{
    listen 80;
    server_name {domains_str};
    access_log {acc_log};
    error_log {err_log};

    # Enterprise Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location / {{
        proxy_pass {proxy_pass};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}

    location ~ ^/(\\.user.ini|\\.htaccess|\\.git|\\.env|\\.svn|\\.project|LICENSE|README.md)
    {{
        return 404;
    }}
}}
"""
    else:
        index_file = os.path.join(root_dir, "index.html")
        if not os.path.exists(index_file):
            try:
                with open(index_file, "w", encoding="utf-8") as fh:
                    fh.write(f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Selamat Datang di {domain}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0B0F17; color: #F8FAFC; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; }}
        .card {{ background: #131C2E; border: 1px solid #1E293B; border-radius: 12px; padding: 36px; max-width: 500px; width: 100%; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); text-align: center; }}
        h1 {{ font-size: 22px; margin-bottom: 8px; color: #38BDF8; }}
        p {{ font-size: 13.5px; color: #94A3B8; line-height: 1.6; margin-bottom: 24px; }}
        .badge {{ background: rgba(16,185,129,0.15); color: #10B981; border: 1px solid rgba(16,185,129,0.3); padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; display: inline-block; margin-bottom: 16px; }}
        .path {{ background: #080C14; border: 1px solid #1E293B; border-radius: 6px; padding: 10px 14px; font-family: monospace; font-size: 12.5px; color: #FBBF24; word-break: break-all; margin-bottom: 20px; }}
        .ft {{ font-size: 12px; color: #64748B; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">&#10003; STATUS SITUS AKTIF</div>
        <h1>{domain}</h1>
        <p>Situs web Anda telah berhasil dipasang di Nginx dan siap digunakan.</p>
        <div class="path">Root Direktori:<br>{root_dir}</div>
        <div class="ft">Dikelola oleh Santaka Control</div>
    </div>
</body>
</html>""")
            except OSError:
                pass

        vhost_content = f"""server
{{
    listen 80;
    server_name {domains_str};
    index index.html index.htm index.php default.html;
    root {root_dir};

    access_log {acc_log};
    error_log {err_log};

    # Enterprise Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Gzip Optimization
    gzip on;
    gzip_min_length 1k;
    gzip_comp_level 4;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;
    gzip_vary on;

    include enable-php.conf;

    location / {{
        try_files $uri $uri/ /index.html /index.php?$args;
    }}

    location ~ ^/(\\.user.ini|\\.htaccess|\\.git|\\.env|\\.svn|\\.project|LICENSE|README.md)
    {{
        return 404;
    }}

    location ~ .*\\.(gif|jpg|jpeg|png|bmp|swf|svg|webp|ico)$
    {{
        expires      30d;
        error_log /dev/null;
        access_log /dev/null;
    }}

    location ~ .*\\.(js|css)?$
    {{
        expires      12h;
        error_log /dev/null;
        access_log /dev/null;
    }}
}}
"""

    # Buat file default index jika folder kosong
    index_file = os.path.join(root_dir, "index.html")
    if not os.path.exists(index_file) and not proxy_pass:
        try:
            with open(index_file, "w", encoding="utf-8") as f:
                f.write(f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{domain}</title></head>"
                        f"<body style='font-family:sans-serif;text-align:center;padding:50px;background:#0b0f17;color:#f8fafc;'>"
                        f"<h1>{domain}</h1><p style='color:#94a3b8;'>Website baru berhasil dibuat di Santaka Server.</p></body></html>")
        except OSError:
            pass

    # Tulis vhost sementara untuk uji sintaks
    tmp_vhost = vhost_file + ".tmp"
    try:
        with open(tmp_vhost, "w", encoding="utf-8") as f:
            f.write(vhost_content)
        os.replace(tmp_vhost, vhost_file)
        reload_nginx()
    except Exception as e:
        if os.path.exists(vhost_file):
            try:
                os.remove(vhost_file)
                _run_nginx(["-s", "reload"])
            except OSError:
                pass
        raise NginxError("Gagal memasang situs: %s" % str(e))
    return True


def delete_vhost(domain, delete_files=False):
    """Hapus vhost Nginx dan reload aman."""
    domain = (domain or "").strip().lower()
    vhost_file = os.path.join(VHOST_DIR, "%s.conf" % domain)
    if not os.path.exists(vhost_file):
        raise NginxError("Situs %s tidak ditemukan." % domain)

    # Backup isi jika perlu
    backup_path = vhost_file + ".bak"
    try:
        os.replace(vhost_file, backup_path)
        reload_nginx()
        os.remove(backup_path)
    except Exception as e:
        if os.path.exists(backup_path):
            os.replace(backup_path, vhost_file)
        raise NginxError("Gagal menghapus vhost: %s" % str(e))
    return True


def read_vhost(domain):
    """Baca konten vhost untuk editor visual."""
    domain = (domain or "").strip().lower()
    vhost_file = os.path.join(VHOST_DIR, "%s.conf" % domain)
    if not os.path.exists(vhost_file):
        raise NginxError("Berkas vhost %s tidak ditemukan." % domain)
    try:
        with open(vhost_file, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as e:
        raise NginxError("Tidak bisa membaca vhost: %s" % e.strerror)


def save_vhost(domain, content):
    """Simpan vhost dari editor dengan validasi sintaks & rollback otomatis."""
    domain = (domain or "").strip().lower()
    vhost_file = os.path.join(VHOST_DIR, "%s.conf" % domain)
    if not os.path.exists(vhost_file):
        raise NginxError("Berkas vhost %s tidak ditemukan." % domain)

    bak_file = vhost_file + ".bak"
    try:
        with open(bak_file, "w", encoding="utf-8") as f:
            f.write(read_vhost(domain))
        with open(vhost_file, "w", encoding="utf-8") as f:
            f.write(content)
        reload_nginx()
        try:
            os.remove(bak_file)
        except OSError:
            pass
        return True, "Konfigurasi Nginx berhasil disimpan dan di-reload."
    except Exception as e:
        # Rollback otomatis ke versi sebelumnya
        if os.path.exists(bak_file):
            with open(bak_file, "r", encoding="utf-8") as f:
                prev = f.read()
            with open(vhost_file, "w", encoding="utf-8") as f:
                f.write(prev)
            try:
                _run_nginx(["-s", "reload"])
                os.remove(bak_file)
            except OSError:
                pass
        raise NginxError("Sintaks Nginx salah! Perubahan dibatalkan demi keamanan:\n%s" % str(e))


def domain_logs(domain, lines=100):
    """Baca tail access log & error log untuk domain tertentu."""
    domain = re.sub(r"[^a-zA-Z0-9_.-]", "", domain or "")
    if not domain:
        raise NginxError("Domain tidak valid")
    acc_path = log_path(domain)
    err_path = log_path(domain, error=True)
    acc = ""
    err = ""
    if os.path.exists(acc_path):
        rc, out, _ = cmd.run(["tail", "-n", str(lines), acc_path], timeout=5)
        acc = out or ""
    if os.path.exists(err_path):
        rc, out, _ = cmd.run(["tail", "-n", str(lines), err_path], timeout=5)
        err = out or ""
    return {"domain": domain, "access": acc, "error": err}



def extract_archive(archive_path, target_dir):
    """Ekstrak arsip .zip atau .tar.gz secara aman ke target_dir."""
    os.makedirs(target_dir, exist_ok=True)
    extracted_count = 0
    if archive_path.endswith(".zip"):
        import zipfile
        with zipfile.ZipFile(archive_path, "r") as zf:
            for member in zf.namelist():
                norm = os.path.normpath(member)
                if norm.startswith("..") or os.path.isabs(norm):
                    continue
                zf.extract(member, target_dir)
                extracted_count += 1
    elif archive_path.endswith((".tar.gz", ".tgz")):
        import tarfile
        with tarfile.open(archive_path, "r:gz") as tf:
            for member in tf.getmembers():
                norm = os.path.normpath(member.name)
                if norm.startswith("..") or os.path.isabs(norm):
                    continue
                tf.extract(member, target_dir)
                extracted_count += 1
    else:
        raise NginxError("Format arsip tidak didukung (gunakan .zip atau .tar.gz)")

    cmd.run(["chown", "-R", "www:www", target_dir])
    cmd.run(["chmod", "-R", "755", target_dir])
    return extracted_count
