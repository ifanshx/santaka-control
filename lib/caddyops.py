"""Operasi Caddy yang aman: baca, validasi, tulis, muat ulang.

Prinsip: konfigurasi baru WAJIB lolos `caddy validate` pada berkas sementara
sebelum menyentuh berkas hidup. Berkas lama disimpan sebagai .bak.
"""
import os
import re
import shutil
import time

from . import cmd

CADDYFILE = "/etc/caddy/Caddyfile"
BACKUP_DIR = "/var/backups/santaka-caddy"

SITE_RE = re.compile(r"^(?:https?://)?([A-Za-z0-9*._\-]+(?::\d+)?)\s*\{", re.M)
UPSTREAM_RE = re.compile(r"reverse_proxy\s+([^\s{]+)")
ROOT_RE = re.compile(r"root\s+\*?\s*([^\s{]+)")


class CaddyError(Exception):
    pass


def _clean_error(blob, tmp_path=""):
    """Ambil pesan galat yang berguna dari log JSON Caddy, buang noise."""
    import json as _json
    best = ""
    for line in (blob or "").splitlines():
        line = line.strip()
        if not line:
            continue
        msg = None
        if line.startswith("{"):
            try:
                rec = _json.loads(line)
            except ValueError:
                rec = None
            if isinstance(rec, dict):
                if rec.get("level") in ("warn", "info", "debug"):
                    continue
                msg = rec.get("msg") or rec.get("error")
        else:
            msg = line
        if not msg:
            continue
        low = msg.lower()
        if "unable to determine directory" in low or "falling back" in low:
            continue
        msg = msg.replace(tmp_path, "Caddyfile") if tmp_path else msg
        # ambil bagian setelah titik dua terakhir pada path sementara
        if "Caddyfile:" in msg:
            msg = msg[msg.index("Caddyfile:"):]
        best = msg.strip()[:400]
        if "error" in low or "invalid" in low or "unrecognized" in low \
                or "parsed" in low or "not allowed" in low:
            break
    if not best:
        best = "Konfigurasi tidak valid (periksa sintaks Caddyfile)."
    return best


def read():
    try:
        with open(CADDYFILE, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError as ex:
        raise CaddyError("tidak bisa membaca Caddyfile: %s" % ex.strerror)


def sites():
    """Daftar situs: host, tujuan (reverse_proxy atau root), dan jenisnya."""
    text = read()
    out = []
    lines = text.splitlines()
    cur = None
    depth = 0
    for raw in lines:
        line = raw.strip()
        m = SITE_RE.match(raw)
        if m and depth == 0:
            cur = {"host": m.group(1), "upstream": "", "root": "",
                   "import": "", "kind": "?"}
            depth = raw.count("{") - raw.count("}")
            continue
        if cur is not None:
            up = UPSTREAM_RE.search(line)
            if up and not cur["upstream"]:
                cur["upstream"] = up.group(1)
            rt = ROOT_RE.search(line)
            if rt and not cur["root"]:
                cur["root"] = rt.group(1)
            if line.startswith("import "):
                cur["import"] = line.split(None, 1)[1].strip()
            depth += raw.count("{") - raw.count("}")
            if depth <= 0:
                if cur["upstream"]:
                    cur["kind"] = "proxy"
                elif cur["root"]:
                    cur["kind"] = "static/php"
                elif cur["import"]:
                    cur["kind"] = "import"
                    cur["upstream"] = "import " + cur["import"]
                else:
                    cur["kind"] = "?"
                out.append(cur)
                cur = None
    return out


def validate(text):
    """Validasi teks Caddyfile lewat berkas sementara. (ok, pesan)."""
    tmp = "/tmp/sc-caddy-probe-%d.conf" % int(time.time() * 1000)
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        rc, out, err = cmd.run(["caddy", "validate", "--config", tmp,
                                "--adapter", "caddyfile"], timeout=25)
        blob = (out or "") + ("\n" + err if err else "")
        if rc == 0:
            return True, "Konfigurasi valid."
        return False, _clean_error(blob, tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def save(text):
    """Tulis Caddyfile hanya bila valid. Kembalikan (ok, pesan, path backup)."""
    ok, msg = validate(text)
    if not ok:
        return False, msg, None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = os.path.join(BACKUP_DIR, "Caddyfile-%s" % stamp)
    try:
        if os.path.exists(CADDYFILE):
            shutil.copy2(CADDYFILE, bak)
        tmp = CADDYFILE + ".new"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, 0o644)
        os.replace(tmp, CADDYFILE)
    except OSError as ex:
        return False, "gagal menulis Caddyfile: %s" % ex.strerror, None
    ok2, msg2 = validate(open(CADDYFILE, encoding="utf-8").read())
    if not ok2:
        try:
            shutil.copy2(bak, CADDYFILE)
        except OSError:
            pass
        return False, "dibatalkan, berkas lama dipulihkan: %s" % msg2, bak
    return True, "Tersimpan. Muat ulang Caddy untuk menerapkan.", bak


def reload():
    rc, out, err = cmd.run(["systemctl", "reload", "caddy"], timeout=30)
    if rc != 0:
        rc, out, err = cmd.run(["systemctl", "restart", "caddy"], timeout=40)
        if rc != 0:
            raise CaddyError((err or out or "caddy menolak dimuat ulang")[:300])
        return "restart"
    return "reload"


def status():
    rc, out, _ = cmd.run(["systemctl", "is-active", "caddy"], timeout=8)
    rc2, ver, _ = cmd.run(["caddy", "version"], timeout=8)
    return {"active": (out or "").strip(), "version": (ver or "").strip()}


def backups(limit=20):
    rows = []
    try:
        for name in sorted(os.listdir(BACKUP_DIR), reverse=True)[:limit]:
            full = os.path.join(BACKUP_DIR, name)
            try:
                st = os.stat(full)
            except OSError:
                continue
            rows.append({"name": name, "size": st.st_size, "mtime": int(st.st_mtime)})
    except OSError:
        pass
    return rows
