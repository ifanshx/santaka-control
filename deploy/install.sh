#!/usr/bin/env bash
# Pasang Santaka Control ke /opt/santaka-control (idempoten, tanpa dependensi).
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/santaka-control}
CONF_DIR=${CONF_DIR:-/etc/santaka-control}
STATE_DIR=${STATE_DIR:-/var/lib/santaka-control}
SERVICE_USER=${SERVICE_USER:-santaka}
SRC_DIR=$(cd "$(dirname "$0")/.." && pwd)

if [ "$(id -u)" -ne 0 ]; then
    echo "jalankan sebagai root" >&2
    exit 1
fi

command -v python3 >/dev/null || { echo "python3 tidak ditemukan" >&2; exit 1; }
PY_VER=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' \
    || { echo "butuh Python >= 3.10 (terpasang $PY_VER)" >&2; exit 1; }

id "$SERVICE_USER" >/dev/null 2>&1 || useradd --system \
    --home "$APP_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"

install -d -m 0755 "$APP_DIR" "$CONF_DIR" "$STATE_DIR"
rsync -a --delete \
    --exclude 'config.json' --exclude 'data/' --exclude '__pycache__/' \
    --exclude '.git/' --exclude 'tests/' \
    "$SRC_DIR"/ "$APP_DIR"/

if [ ! -f "$CONF_DIR/config.json" ]; then
    install -m 0640 -g "$SERVICE_USER" "$SRC_DIR/config.example.json" \
        "$CONF_DIR/config.json"
fi

chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR" "$STATE_DIR"
chown root:"$SERVICE_USER" "$CONF_DIR"
chmod 0750 "$CONF_DIR"

install -m 0644 "$SRC_DIR/deploy/santaka-control.service" \
    /etc/systemd/system/santaka-control.service
systemctl daemon-reload
systemctl enable --now santaka-control.service

echo "Selesai. Panel: http://127.0.0.1:8081/setup (atur akses lewat reverse proxy TLS)."
echo "Konfigurasi: $CONF_DIR/config.json"
