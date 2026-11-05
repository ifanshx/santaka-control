#!/usr/bin/env python3
"""Notifikasi Santaka: Telegram dan email SMTP.

Dimiliki panel ini (dulu menumpang modul panel lama). Konfigurasi disimpan di
data/ milik panel sendiri, permission 600.
"""
import json
import os
import smtplib
import ssl
import time
import urllib.parse
import urllib.request
from email.message import EmailMessage

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")
TG_CFG = os.path.join(DATA_DIR, "telegram.json")
MAIL_CFG = os.path.join(DATA_DIR, "mail.json")


class NotifyError(Exception):
    pass


def _read(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _write(path, data, mode=0o600):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(tmp, mode)
    os.replace(tmp, path)


# ==================== TELEGRAM ====================

def tg_config():
    data = _read(TG_CFG, {}) or {}
    return {
        "enabled": bool(data.get("enabled", True)),
        "token": str(data.get("token") or ""),
        "chat_id": str(data.get("chat_id") or ""),
    }


def tg_public():
    cfg = tg_config()
    token = cfg["token"]
    return {
        "configured": bool(token and cfg["chat_id"]),
        "enabled": cfg["enabled"],
        "chat_id": cfg["chat_id"],
        "token_hint": (token[:6] + "…" + token[-4:]) if len(token) > 12 else "",
        "has_token": bool(token),
    }


def tg_save(token, chat_id, enabled=True):
    cfg = tg_config()
    if token:
        cfg["token"] = token.strip()
    if chat_id:
        cfg["chat_id"] = str(chat_id).strip()
    cfg["enabled"] = bool(enabled)
    if not cfg["token"] or not cfg["chat_id"]:
        raise NotifyError("token dan chat_id harus terisi")
    _write(TG_CFG, cfg)
    return True


def tg_send(text, silent=False):
    """Kirim pesan. Kembalikan (ok, pesan)."""
    cfg = tg_config()
    if not (cfg["enabled"] and cfg["token"] and cfg["chat_id"]):
        return False, "telegram belum dikonfigurasi"
    url = "https://api.telegram.org/bot%s/sendMessage" % cfg["token"]
    payload = urllib.parse.urlencode({
        "chat_id": cfg["chat_id"],
        "text": text[:4000],
        "parse_mode": "HTML",
        "disable_notification": bool(silent),
    }).encode()
    try:
        req = urllib.request.Request(url, data=payload)
        resp = urllib.request.urlopen(req, timeout=15)
        return resp.status == 200, ""
    except Exception as ex:
        return False, str(ex)[:200]


def tg_test():
    ok, err = tg_send("🔔 <b>SANTAKA</b>\nPesan uji dari Santaka Control.")
    if not ok:
        raise NotifyError("gagal mengirim: %s" % err)
    return "Pesan uji terkirim."


# ==================== EMAIL SMTP ====================

def mail_config():
    data = _read(MAIL_CFG, {}) or {}
    return {
        "host": data.get("host", ""),
        "port": int(data.get("port") or 587),
        "user": data.get("user", ""),
        "password": data.get("password", ""),
        "sender": data.get("sender") or data.get("user", ""),
        "tls": bool(data.get("tls", True)),
    }


def mail_public():
    cfg = mail_config()
    return {
        "configured": bool(cfg["host"] and cfg["user"]),
        "host": cfg["host"],
        "port": cfg["port"],
        "user": cfg["user"],
        "sender": cfg["sender"],
        "has_password": bool(cfg["password"]),
        "tls": cfg["tls"],
    }


def mail_save(host, port, user, password, sender="", tls=True):
    cfg = mail_config()
    if host:
        cfg["host"] = host.strip()
    if port:
        cfg["port"] = int(port)
    if user:
        cfg["user"] = user.strip()
    if password:
        cfg["password"] = password
    if sender:
        cfg["sender"] = sender.strip()
    cfg["tls"] = bool(tls)
    if not (cfg["host"] and cfg["user"] and cfg["password"]):
        raise NotifyError("host, pengguna, dan kata sandi SMTP wajib terisi")
    _write(MAIL_CFG, cfg)
    return True


def mail_send(to, subject, body):
    cfg = mail_config()
    if not (cfg["host"] and cfg["user"] and cfg["password"]):
        raise NotifyError("SMTP belum dikonfigurasi")
    msg = EmailMessage()
    msg["From"] = cfg["sender"] or cfg["user"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        if cfg["port"] == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=25,
                                  context=ctx) as s:
                s.login(cfg["user"], cfg["password"])
                s.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=25) as s:
                if cfg["tls"]:
                    s.starttls(context=ssl.create_default_context())
                s.login(cfg["user"], cfg["password"])
                s.send_message(msg)
    except Exception as ex:
        raise NotifyError("gagal mengirim email: %s" % str(ex)[:200])
    return True


if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) or "Pesan uji dari Santaka Control."
    ok, err = tg_send("🔔 <b>SANTAKA</b>\n" + text)
    print("OK" if ok else "FAIL: %s" % err)
