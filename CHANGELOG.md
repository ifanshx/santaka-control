# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `SANTANTAKA_CONFIG` / `SANTANTAKA_DATA` environment overrides for packaged
  deployments and tests.
- `stats.hardware()` for device/CPU detection; dashboard and terminal MOTD now
  read live hardware data.
- Test suite (validators, crypto, users/permissions, rate limiting, atomic
  store, configuration plumbing, and a full HTTP setup/login/CSRF flow) with a
  GitHub Actions matrix for Python 3.10, 3.12, and 3.13.
- Repository assets: MIT license, security policy, example configuration,
  systemd unit, install script, and documentation.

### Changed
- Every runtime path and deployment-specific value is now configurable:
  `web_root`, nginx binary/vhost/log paths, Caddyfile, apps directory, PHP pool
  directory, backup/dump directories, state directory, data mount, app domains,
  phpMyAdmin URL, and terminal user. Hardcoded `santaka.my.id`, `/www/wwwroot`,
  `/www/wwwlogs`, `/opt/santaka-apps`, and `/root/.santaka-db-secret` references
  are gone from the UI and logic.
- Storage, network, dashboard, and terminal pages derive metrics from live data
  instead of static text.
- Login page copy no longer claims 2FA is mandatory; TLS footer is proxy-neutral.

### Fixed
- `POST /setup` and `POST /login` now enforce the CSRF token (previously a
  cross-site form could claim an unprovisioned panel or perform login CSRF).
- Buttons using inline `onclick` no longer fail under the nonce-based CSP; they
  use delegated `data-action` handlers.
- Dark-mode-only colors were removed from fstab/SMART viewers so both themes
  stay readable.

## [0.1.0] - 2026-11-01
- Initial internal release: dashboard, services, files, nginx/vhosts, databases,
  Redis, storage, network, cron, users, security, maintenance, audit, terminal.
