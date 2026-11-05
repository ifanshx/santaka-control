"""Keamanan & perawatan: password, 2FA+QR, sesi, notifikasi, maintenance."""
import json
import os
import subprocess
import time

from . import cmd, crypto, store, validate

from . import notify as _notify


class SecError(Exception):
    pass


# ---------- QR untuk 2FA ----------

def qr_svg(text):
    """SVG QR lewat qrencode. Kembalikan string SVG atau None."""
    if not text:
        return None
    try:
        proc = subprocess.run(["qrencode", "-t", "SVG", "-s", "5", "-m", "1",
                               "-l", "M", "-o", "-", text],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=10)
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        pass
    return None


# ---------- notifikasi ----------

def telegram_config():
    return _notify.tg_public()


def telegram_save(token, chat_id, enabled=True):
    if token and (":" not in token or len(token) < 20):
        raise SecError("format token tidak laiknya bot Telegram (angka:token)")
    if chat_id and not str(chat_id).strip().lstrip("-").isdigit():
        raise SecError("chat_id harus berupa angka")
    try:
        return _notify.tg_save(token, chat_id, enabled)
    except _notify.NotifyError as ex:
        raise SecError(str(ex))


def telegram_test():
    try:
        return _notify.tg_test()
    except _notify.NotifyError as ex:
        raise SecError(str(ex))


def mail_config():
    return _notify.mail_public()


def mail_save(host, port, user, password, sender="", tls=True):
    port_n = validate.safe_int(port, 1, 65535, 587)
    try:
        return _notify.mail_save(host, port_n, user, password, sender, tls)
    except _notify.NotifyError as ex:
        raise SecError(str(ex))


def mail_send(to, subject, body):
    try:
        return _notify.mail_send(to, subject, body)
    except _notify.NotifyError as ex:
        raise SecError(str(ex))


# ---------- sesi ----------

def sessions(app, current_sid=None):
    rows = app.sessions.list()
    for r in rows:
        r["current"] = (r.get("sid_full") == current_sid)
        r.pop("sid_full", None)
    return rows


def kill_session(app, sid_prefix):
    if not sid_prefix or len(sid_prefix) < 6:
        raise SecError("penanda sesi tidak sah")
    data = store.read_json(app.sessions.path, {}) or {}
    hits = [k for k in data if k.startswith(sid_prefix)]
    if not hits:
        raise SecError("sesi tidak ditemukan")
    for k in hits:
        data.pop(k, None)
    store.write_json(app.sessions.path, data)
    return len(hits)


# ---------- perawatan ----------

def fstrim():
    rc, out, err = cmd.run(["fstrim", "-av"], timeout=120)
    if rc != 0:
        raise SecError((err or out or "fstrim gagal")[:300])
    return out or "Selesai."


def apt_cache_clean():
    rc, out, err = cmd.run(["apt-get", "clean"], timeout=120)
    if rc != 0:
        raise SecError((err or out or "apt-get clean gagal")[:300])
    rc2, out2, _ = cmd.run(["apt-get", "autoclean"], timeout=180)
    return "Cache paket dibersihkan."


def upgradable():
    rc, out, err = cmd.run(["apt", "list", "--upgradable"], timeout=60)
    rows = []
    for line in (out or "").splitlines():
        if "/" not in line or line.startswith("Listing"):
            continue
        name = line.split("/")[0]
        ver = line.split()[1] if len(line.split()) > 1 else ""
        rows.append({"name": name, "version": ver})
    return rows


def tmp_usage():
    rc, out, _ = cmd.run(["du", "-sh", "/tmp"], timeout=20)
    return (out or "").strip()


def disk_free(path="/"):
    try:
        st = os.statvfs(path)
        return round(st.f_bavail * st.f_frsize / 1024 ** 3, 2)
    except (OSError, AttributeError):
        return 0.0
