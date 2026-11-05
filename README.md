# Santaka Control

A single-file, dependency-free control panel for a Linux home server. Everything
is served by the Python standard library: no build step, no Node runtime, no
database. The panel renders HTML on the server, streams logs/files, and executes
system operations through argument arrays (never a shell).

```
internet ── TLS reverse proxy / tunnel ──> 127.0.0.1:8081 ──> santaka-control
```

## Highlights

| Area | What you get |
| --- | --- |
| Dashboard | CPU, memory, thermals, disks, network throughput, service health, live chart |
| Web server | Nginx vhosts (PHP, static, reverse proxy), validation, reload/rollback of config |
| Applications | Zip deploy, PHP-FPM pools, Node/Next.js services, Caddy blocks per app |
| Databases | MariaDB/PostgreSQL list, create/drop, SQL dump + restore, optional phpMyAdmin link |
| Files | Explorer inside configured roots, editor, upload, download, rename, delete |
| Services | systemd start/stop/restart/enable, unit status, journal tail |
| Terminal | Audited interactive shell per session |
| Security | Password policy, TOTP 2FA + QR, recovery codes, active sessions, firewall view |
| Data safety | Atomic JSON writes, backup + SHA256 verification, audit JSONL, rotation |
| UI | Server-rendered, light/dark theme, Indonesian & English, keyboard palette, mobile layout |

Everything destructive is permission-checked (`viewer` → `operator` → `admin`),
CSRF-protected, and written to an audit trail.

## Requirements

- Linux (systemd) with Python **3.10+** (3.11/3.12/3.13/3.14 tested in CI).
- Root (or a dedicated user with sudo) if you want service/file/system control.
- A TLS-terminating reverse proxy or tunnel in front of the panel. The default
  bind address is `127.0.0.1`; do not expose port 8081 to the internet.

## Quick start

```bash
sudo mkdir -p /opt/santaka-control
sudo cp -r . /opt/santaka-control/
cd /opt/santaka-control
sudo cp config.example.json config.json
$EDITOR config.json          # set hostname, roots, integration paths

sudo useradd --system --home /opt/santaka-control --shell /usr/sbin/nologin santaka
sudo chown -R santaka:santaka /opt/santaka-control
sudo -u santaka python3 server.py        # first run: open http://127.0.0.1:8081/setup
```

The first visit creates the initial administrator (minimum 10-character
password). Enable TOTP 2FA from **Security** right after the first login.

### Run as a service

```bash
sudo install -m 0644 deploy/santaka-control.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now santaka-control
sudo systemctl status santaka-control
```

Environment overrides (useful for packages/containers, see the unit file):

| Variable | Meaning |
| --- | --- |
| `SANTANTAKA_CONFIG` | absolute path to `config.json` (default `<app>/config.json`) |
| `SANTANTAKA_DATA` | directory for `users.json`, `sessions.json`, `audit.log.jsonl` |

### Reverse proxy

The panel assumes the proxy terminates TLS and forwards to loopback:

```nginx
location / {
    proxy_pass http://127.0.0.1:8081;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

`CF-Connecting-IP`, `X-Forwarded-For`, and `X-Real-IP` are trusted **only** when
the request comes from loopback, so client IPs in the audit log stay correct
behind Cloudflare Tunnel or any local proxy. Cookies become `Secure`
automatically when the scheme is HTTPS.

## Configuration

All keys, defaults, and examples live in [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md).
`config.example.json` is the canonical reference; unknown keys are ignored, and
missing keys fall back to the defaults in `server.py`.

## Development

```bash
python -m compileall -q server.py lib routes ui tests
python -m unittest discover -s tests -t . -v
```

There are no third-party dependencies and no lockfile to maintain. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the review checklist and style rules.

## Architecture

```
server.py          HTTP server, routing, auth, CSRF, security headers
routes/api.py      API dispatch + permission prefixes
routes/handlers.py API handlers (files, services, nginx, db, apps, ...)
lib/*              pure logic: crypto, users, storage, stats, validators, ops
ui/*               server-rendered pages, layout, components, i18n
ui/static/*        app.css, app.js, fonts (self-hosted, no CDN)
```

Design constraints: standard library only, small memory footprint (target
< 35 MB RSS), no telemetry, no remote fonts, and no stack traces in responses.

## License

MIT — see [`LICENSE`](LICENSE). Bundled fonts are licensed under the SIL Open
Font License; see [`docs/third-party/`](docs/third-party/).
