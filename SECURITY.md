# Security policy

## Supported versions

Only the latest release on `main` receives security fixes.

## Reporting a vulnerability

Do **not** open a public issue for security problems. Send a private report to
the maintainer address listed on the repository profile, including:

- affected version/commit,
- a minimal reproduction (request, payload, or configuration),
- impact assessment (what an attacker gains),
- whether the panel is exposed directly or behind a reverse proxy.

You can expect an acknowledgement within 72 hours. Please give us time to ship
a fix before public disclosure.

## Threat model

Santaka Control is a single-tenant administration panel for one host. It runs
with the privileges of the user that starts it (usually root) and exposes
destructive operations. The intended deployment is:

```
internet ──TLS reverse proxy / tunnel──> 127.0.0.1:8081 (panel)
```

Hardening that is applied by default:

- Origin/CSRF checks on every mutating request (session-bound HMAC token).
- Strict validators before any filesystem or process operation; commands are
  executed with argument arrays, never through a shell.
- PBKDF2-SHA256 password hashes, TOTP 2FA, single-use recovery codes.
- Per-IP and per-account login rate limiting with progressive backoff.
- `HttpOnly`, `SameSite=Lax` cookies, `Secure` only when the request is HTTPS.
- CSP with per-response nonce, `nosniff`, `no-store`, HSTS when TLS is detected.
- Audit trail (JSONL) for logins, mutations, and permission denials.
- Config/data files written with mode `0600` and atomic replaces.

Out of scope: host compromise before the panel starts, kernel/iptables bypass,
and third-party services you configure (databases, CDNs, tunnels).
