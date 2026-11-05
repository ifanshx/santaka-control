# Configuration reference

`config.json` lives next to `server.py` unless `SANTANTAKA_CONFIG` points
somewhere else. Unknown keys are ignored. If `secret` is empty, a random secret
is generated and written on first start — rotating it invalidates sessions and
CSRF tokens.

## Core

| Key | Default | Meaning |
| --- | --- | --- |
| `port` | `8081` | Listen port |
| `bind` | `127.0.0.1` | Bind address; keep loopback behind a TLS proxy |
| `hostname` | `santaka.local` | Display name in the UI and shell prompt |
| `base_path` | `""` | Sub-path prefix when the proxy strips one (e.g. `/control`) |
| `secret` | `""` | HMAC key for sessions and CSRF; auto-generated if empty |
| `disk_path` | `"/"` | Filesystem reported as "root" on the dashboard |
| `roots` | `["/var/www", "/srv", "/opt", "/home"]` | Allowed file-explorer roots (absolute paths) |
| `session_ttl` | `43200` | Session lifetime in seconds (12 h) |
| `login_attempts` | `6` | Allowed login attempts per IP **and** per account within `login_window` |
| `login_window` | `300` | Rate-limit window in seconds |

## Web server integrations

| Key | Default | Meaning |
| --- | --- | --- |
| `web_root` | `/var/www` | Parent directory for site roots (`web_root/<domain>`) |
| `nginx_bin` | `""` | Path to the nginx binary; auto-detected when empty |
| `nginx_vhost_dir` | `""` | Directory containing vhost files; auto-detected when empty |
| `nginx_conf` | `""` | Main nginx config passed to `nginx -t -c`; defaults to the binary's config |
| `nginx_log_dir` | `/var/log/nginx` | Access/error log directory for vhosts |
| `caddyfile` | `/etc/caddy/Caddyfile` | Caddyfile managed for deployed apps |
| `apps_dir` | `/opt/santaka-apps` | Application root (`apps.json`, logs, releases) |
| `apps_domain` | `""` | Public suffix for apps (`shop.example.com`); empty disables it |
| `apps_lan_domain` | `""` | LAN suffix for apps (`shop.lan`); empty disables it |
| `php_pool_dir` | `/etc/php/8.2/fpm/pool.d` | PHP-FPM pool directory |
| `phpmyadmin_url` | `""` | Optional link shown on the database page |

If both app suffixes are empty, generated Caddy blocks listen on `:80`; set at
least one suffix for per-app virtual hosts.

## Storage

| Key | Default | Meaning |
| --- | --- | --- |
| `data_mount` | `/mnt/data` | Primary data mount highlighted in Storage/dashboard |
| `backup_dir` | `/var/backups/santaka` | Archive directory + `SHA256SUMS.txt`; dumps go to `backup_dir/db` |
| `state_dir` | `/var/lib/santaka-control` | Runtime state (e.g. generated DB admin secret) |

## Interface

| Key | Default | Meaning |
| --- | --- | --- |
| `terminal_user` | `root` | Shell user label/account for the web terminal |
| `phpmyadmin_url` | `""` | See above |

## Example for a Debian host with aaPanel

```json
{
  "hostname": "santaka-server",
  "roots": ["/www/wwwroot", "/mnt/data", "/root", "/var/www"],
  "web_root": "/www/wwwroot",
  "nginx_vhost_dir": "/www/server/panel/vhost/nginx",
  "nginx_bin": "/www/server/nginx/sbin/nginx",
  "nginx_log_dir": "/www/wwwlogs",
  "caddyfile": "/etc/caddy/Caddyfile",
  "data_mount": "/mnt/data",
  "backup_dir": "/mnt/data/backup",
  "state_dir": "/root/.santaka-control",
  "apps_domain": "santaka.my.id",
  "apps_lan_domain": "santaka",
  "phpmyadmin_url": "http://192.168.88.254:888/phpmyadmin/"
}
```

Environment variables `SANTANTAKA_CONFIG` and `SANTANTAKA_DATA` move the config
and the `users.json`/`sessions.json`/`audit.log.jsonl` state without touching
application files.
