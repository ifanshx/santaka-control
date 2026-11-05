# Contributing

## Ground rules

- **Standard library only.** No new runtime dependencies, no build step.
- **No shell interpolation.** System commands run through argument arrays
  (`lib/cmd.py`); user input is validated (`lib/validate.py`) first.
- **Small memory footprint.** Avoid caches without TTL/size limits; the panel
  targets < 35 MB RSS.
- **No secrets in code or git.** Runtime state lives in `config.json`, `data/`,
  and `state_dir` (all git-ignored).
- **UI text is bilingual.** Add new strings to both `id` and `en` tables in
  `ui/i18n.py`; page bodies may keep Indonesian markup for consistency with the
  existing pages.

## Workflow

1. `python -m unittest discover -s tests -t .` — must stay green.
2. `python -m compileall -q server.py lib routes ui tests`.
3. For behaviour changes, add a test that fails before the change. UI-only
   changes can be verified by loading the page and checking the network tab.
4. Keep commits focused; use Conventional Commits
   (`fix(auth): reject expired refresh token`).

## Code review checklist

- Inputs validated at the boundary; permission checked per route.
- No new endpoint without an audit entry for mutating actions.
- No stack traces or internal paths in client responses.
- `HttpOnly`/`SameSite` cookies, `no-store`, and nonce-based CSP preserved.
- Filesystem writes are atomic and use `0600` for state files.
