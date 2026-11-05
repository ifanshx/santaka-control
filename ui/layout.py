"""Kerangka halaman: shell ber-navigasi, halaman login, dan kepala HTML.

Menu difilter per-izin: pengguna hanya melihat yang boleh dibukanya.
"""
from . import components as C
from lib import perm

APP_NAME = "Santaka Control"
GITHUBISH = "SC"

import os as _os


def _asset_ver():
    """Sidik versi berkas statis: berubah saat isi berubah -> cache busting."""
    base = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "static")
    parts = []
    for name in ("app.css", "app.js"):
        try:
            st = _os.stat(_os.path.join(base, name))
            parts.append("%s-%d-%d" % (name[0], int(st.st_mtime), st.st_size))
        except OSError:
            parts.append(name[0] + "-0")
    import hashlib
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:10]


ASSET_VER = _asset_ver()

# Prefix mount, diisi saat runtime oleh App (lihat layout.set_base).
BASE_PATH = ""


def set_base(path):
    """Set prefix mount panel (mis. '/control'). Dipanggil sekali saat boot."""
    global BASE_PATH
    p = (path or "").strip()
    if p in ("", "/"):
        BASE_PATH = ""
    else:
        BASE_PATH = "/" + p.strip("/")


def url(path):
    """Buat URL panel yang sadar-prefix.

    Path non-panel (/api, /static, /favicon, absolut) dibiarkan apa adanya.
    """
    p = str(path or "")
    if p.startswith(("http://", "https://", "//", "#")):
        return p
    if not p.startswith("/"):
        p = "/" + p
    for keep in ("/api/", "/static/", "/favicon"):
        if p.startswith(keep):
            return p
    if not BASE_PATH:
        return p
    if p == "/":
        return BASE_PATH
    return BASE_PATH + p


def asset(name):
    """URL berkas statis dengan versi (aman di-cache lama)."""
    return "/static/%s?v=%s" % (name, ASSET_VER)


# (grup, [(id, ikon, kunci_i18n, izin)])
NAV = [
    ("nav.group.main", [
        ("dash", "dash", "Dashboard", perm.VIEW),
    ]),
    ("nav.group.server", [
        ("web", "web", "Websites & Vhosts", perm.VIEW),
        ("db", "db", "Databases (MySQL)", perm.VIEW),
        ("redis", "redis", "Redis Cache", perm.VIEW),
        ("files", "files", "File Explorer", perm.VIEW),
        ("svc", "svc", "Service Manager", perm.VIEW),
        ("terminal", "terminal", "Web Terminal", perm.SECURITY),
        ("logs", "logs", "System Logs", perm.LOG_VIEW),
    ]),
    ("nav.group.data", [
        ("storage", "disk", "Storage", perm.VIEW),
        ("network", "net", "Network", perm.VIEW),
    ]),
    ("nav.group.security", [
        ("security", "shield", "Security & Firewall", perm.SECURITY),
        ("users", "user", "Admin Users", perm.USER_MANAGE),
        ("audit", "clock", "Audit Logs", perm.VIEW),
    ]),
    ("nav.group.system", [
        ("cron", "cron", "Cron Jobs", perm.VIEW),
        ("maintenance", "wrench", "Maintenance", perm.MAINT),
    ]),
]


def visible_nav(user):
    """Kembalikan NAV dengan entri yang izinnya tidak dimiliki dibuang."""
    out = []
    for group_key, items in NAV:
        allowed = [(i, ic, k) for (i, ic, k, p) in items if perm.can(user, p)]
        if allowed:
            out.append((group_key, allowed))
    return out


def head(title, t, extra_css="", lang="id", theme="paper"):
    """Kepala HTML. Aset memakai versi agar cache browser tidak basi."""
    is_dark = theme in ("night", "dark")
    theme_color = "#0B0F17" if is_dark else "#FFFFFF"
    color_scheme = "dark" if is_dark else "light"
    parts = [
        "<!DOCTYPE html>\n",
        '<html lang="%s" data-theme="%s" data-base="%s">\n<head>\n'
        % (C.e(lang), C.e(theme), C.e(BASE_PATH)),
        '<meta charset="utf-8">\n',
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n',
        '<meta name="referrer" content="same-origin">\n',
        '<meta name="theme-color" content="%s">\n' % theme_color,
        '<meta name="color-scheme" content="%s">\n' % color_scheme,
        '<meta name="robots" content="noindex, nofollow, noarchive">\n',
        "<title>%s \u00b7 %s</title>\n" % (C.e(title), C.e(APP_NAME)),
        '<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">\n',
        '<link rel="stylesheet" href="%s">\n' % asset("app.css"),
        extra_css or "",
        "</head>\n",
    ]
    return "".join(parts)


def _nav_html(nav, current, t):
    parts = []
    for group_key, items in nav:
        parts.append('<div class="grp">%s</div>' % C.e(t(group_key)))
        for item_id, icon_name, label_key in items:
            cls = ' class="on"' if item_id == current else ""
            aria = ' aria-current="page"' if item_id == current else ""
            parts.append(
                '<a href="%s"%s%s><span class="ic">%s</span>'
                '<span class="lbl">%s</span></a>'
                % (url("/" + item_id), cls, aria, C.icon(icon_name),
                   C.e(t(label_key)))
            )
    return "".join(parts)


def shell(user, app, current, title, subtitle, body, t, actions="", toast_msgs=None):
    """Halaman utama: sidebar + topbar + isi. `user` dict (username, role)."""
    role = (user or {}).get("role", "viewer")
    username = (user or {}).get("username", "-")
    from lib import session as _sessionmod
    csrf = ""
    if app is not None:
        csrf = _sessionmod.csrf_for((user or {}).get("sid"),
                                    (app.cfg or {}).get("secret", ""))
    nav_html = _nav_html(visible_nav(user), current, t)

    toasts = "".join(
        '<div class="toast %s" role="status"><span class="tt">%s</span>'
        '<span class="ms">%s</span></div>' % (C.e(k), C.e(ti), C.e(ms))
        for (k, ti, ms) in (toast_msgs or [])
    )

    theme = (user or {}).get("theme") or "paper"
    page = head(title, t, lang=t.lang, theme=theme)
    inject = ('<meta name="csrf" content="%s">\n'
              '<script src="%s"></script>\n</head>'
              % (C.e(csrf), asset("app.js")))
    page = page.replace("</head>", inject)
    return (
        page
        + "<body>\n"
        + '<a class="skip" href="#main">Lewati ke konten</a>\n'
                + '<div class="wrap">\n'
        + '<aside class="side" id="side" aria-label="Navigasi utama">\n'
        + '<div class="brand"><span class="badge" aria-hidden="true">SC</span>'
          '<span class="name">Santaka<small>Control</small></span></div>\n'
        + '<nav class="nav">%s</nav>\n' % nav_html
        + '<div class="side-foot">'
          '<div class="who">'
          '<span class="avatar" aria-hidden="true">%s</span>'
          '<span class="meta"><span class="u" title="%s">%s</span>'
          '<span class="role %s">%s</span></span>'
          '</div>'
          '<div class="foot-actions">'
          '<button class="btn sm gh wide" id="logoutBtn">%s %s</button>'
          "</div></div>\n"
        % (C.e((username or "?")[:1]), C.e(username), C.e(username),
           C.e(role), C.e(role.upper()),
           C.icon("logout", 14), C.e(t("act.logout")))
        + "</aside>\n"
        + '<script>(function(){function r(){var s=document.querySelector("#side .nav");'
          'if(!s)return;var a=s.querySelector(\'a[aria-current="page"]\');if(!a)return;'
          'var sr=s.getBoundingClientRect(),ar=a.getBoundingClientRect();'
          'if(ar.top>=sr.top&&ar.bottom<=sr.bottom)return;'
          's.scrollTop=Math.max(0,Math.min('
          's.scrollTop+(ar.top-sr.top)-(sr.height-ar.height)/2,'
          's.scrollHeight-s.clientHeight));}'
          'if(document.readyState==="loading"){'
          'requestAnimationFrame(r);window.addEventListener("load",r);}'
          'else{r();}})();</script>\n'
        + '<div class="main">\n'
        + '<div class="mob-bar">'
          '<button class="btn sm" id="burger" aria-expanded="false" '
          'aria-controls="side" aria-label="Buka menu">%s</button>'
          '<span class="brand"><span class="badge">SC</span>'
          '<span class="name">Santaka</span></span>'
          "</div>\n" % C.icon("menu")
        + '<header class="top">'
          '<div class="ttl">'
          '<div class="breadcrumb"><span class="bc-app">Santaka</span>'
          '<span class="bc-sep">/</span><span class="bc-cur">%s</span></div>'
          '<div class="sub">%s</div></div>'
          '<div class="acts">'
          '<button class="btn sm gh search-trigger" id="cmdTrigger" aria-haspopup="dialog" '
          'title="Cari menu atau perintah (Ctrl+K)">'
          '%s <span class="lbl">Cari menu atau perintah</span> <kbd class="kbd-hint">Ctrl K</kbd></button>'
          '<button class="btn sm gh icon-only" id="langBtn" '
          'aria-label="Ganti bahasa antarmuka" title="Ganti bahasa (ID / EN)">ID</button>'
          '<button class="btn sm gh icon-only theme-toggle-btn" id="themeBtn" '
          'aria-label="Ganti tema terang atau gelap" title="Ganti tema (Terang / Gelap)">%s</button>'
          "</div></header>\n"
        % (C.e(title), subtitle, C.icon("search", 14), C.icon("theme", 14))
        + '<main class="view" id="main">%s</main>\n' % body
        + "</div>\n</div>\n"
        + '<div class="toasts" id="toasts" aria-live="polite">%s</div>\n' % toasts
        + """
<div class="cmd-overlay hidden" id="cmdOverlay" role="dialog" aria-modal="true" aria-label="Command Palette">
  <div class="cmd-box">
    <div class="cmd-head">
      <span class="cmd-icon"><svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M10 3a7 7 0 1 1-4.9 12L2 18.1 3.4 19.5 6.5 16.4A7 7 0 0 1 10 3Zm0 2a5 5 0 1 0 0 10 5 5 0 0 0 0-10Z"/></svg></span>
      <input type="text" id="cmdInput" class="cmd-input" placeholder="Cari menu atau perintah (misal: Terminal, Nginx, Redis)..." autocomplete="off" spellcheck="false">
      <kbd class="cmd-esc" id="cmdClose">ESC</kbd>
    </div>
    <div class="cmd-list" id="cmdList"></div>
    <div class="cmd-foot">
      <span>Gunakan <kbd>↑</kbd> <kbd>↓</kbd> untuk memilih</span>
      <span><kbd>↵</kbd> untuk membuka</span>
      <span><kbd>ESC</kbd> untuk menutup</span>
    </div>
  </div>
</div>
"""
        + "</body>\n</html>\n"
    )


def login_page(t, csrf, error="", username="", lang="id", setup_needed=False,
               theme="paper", show_code=False):
    """Halaman login mandiri (tanpa sidebar). Form asli, bisa dipakai tanpa JS."""
    err = ('<div id="loginError" class="toast err mb16" role="alert">'
           '<span class="tt">%s</span><span class="ms">%s</span></div>'
           % (C.e(t("st.error")), C.e(error))) if error else (
           '<div id="loginError" class="toast err mb16" role="alert" hidden>'
           '<span class="tt">%s</span><span class="ms"></span></div>'
           % C.e(t("st.error")))

    setup_box = ""
    if setup_needed:
        setup_box = (
            '<div class="panel mb16"><div class="panel-head"><h3>Setup awal</h3></div>'
            '<div class="p16"><p class="muted" style="font-size:13px">Belum ada pengguna. '
            "Buat akun administrator pertama untuk mengamankan panel ini.</p></div></div>"
        )

    features = [
        ("shield", t("auth.f1t"), t("auth.f1d")),
        ("clock", t("auth.f2t"), t("auth.f2d")),
        ("server", t("auth.f3t"), t("auth.f3d")),
    ]
    feature_html = "".join(
        '<li><span class="ic">%s</span><span><b>%s</b><span>%s</span></span></li>'
        % (C.icon(ic, 13), C.e(title), C.e(desc))
        for ic, title, desc in features
    )

    lp = head("Masuk", t, lang=lang, theme=theme).replace(
        "</head>", '<meta name="csrf" content="%s">\n'
        '<script src="%s"></script>\n</head>'
        % (C.e(csrf), asset("app.js")))
    return (
        lp
        + "<body>\n"
        + '<div class="auth">\n'
        + '<aside class="auth-aside">\n'
        + '<div class="auth-brand"><span class="mark" aria-hidden="true">SC</span>'
          '<span class="t">Santaka Control<small>%s</small></span></div>\n'
          % C.e(t("auth.sub"))
        + '<div class="auth-copy">'
          '<h2>%s</h2>'
          '<p>%s</p>'
          '<ul class="auth-list">%s</ul>'
          '</div>\n' % (C.e(t("auth.tagline")), C.e(t("auth.desc")),
                         feature_html)
        + '<div class="auth-foot">%s <span>%s</span></div>\n'
          % (C.icon("shield", 13), C.e(t("auth.foot")))
        + '</aside>\n'
        + '<main class="auth-main">\n'
        + '<div class="auth-tools">'
          '<button type="button" class="btn sm gh icon-only" id="langBtn" '
          'aria-label="Ganti bahasa antarmuka" title="Ganti bahasa (ID / EN)">%s</button>'
          '<button type="button" class="btn sm gh icon-only theme-toggle-btn" id="themeBtn" '
          'aria-label="Ganti tema terang atau gelap" title="Ganti tema (Terang / Gelap)">%s</button>'
          '</div>\n' % (C.e((lang or "id").upper()), C.icon("theme", 14))
        + '<div class="auth-card">\n'
        + '<div class="brand"><span class="badge">SC</span>'
          '<span class="name">Santaka Control</span></div>\n'
        + setup_box
        + err
        + '<h1>%s</h1>\n' % C.e(t("login.title"))
        + '<p class="sub">%s</p>\n' % C.e(t("login.sub"))
        + '<form id="loginForm" method="post" action="%s" autocomplete="on">' % url("/login")
        + '<input type="hidden" name="csrf" value="%s">' % C.e(csrf)
        + '<div class="stack">'
        + C.field(t("login.user"), "username", value=username,
                  required=True, autocomplete="username", placeholder="admin")
        + C.field(t("login.password"), "password", kind="password",
                  required=True, autocomplete="current-password",
                  placeholder="\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022")
        + '<div id="loginCodeSection"%s>' % ("" if show_code else " hidden")
        + C.field(t("login.code"), "code", value="", placeholder="000000",
                  help=t("login.codeHelp"),
                  autocomplete="one-time-code", extra_class="otp")
        + '</div><noscript><style>#loginCodeSection[hidden]{display:block!important}</style></noscript>'
        + "</div>"
        + '<div class="mt16"><button id="loginSubmit" class="btn pk wide" type="submit">%s %s</button></div>'
          % (C.icon("shield", 15), C.e(t("act.login")))
        + "</form>\n"
        + '<div class="auth-note">%s<span>%s</span></div>\n'
          % (C.icon("clock", 14), C.e(t("login.note")))
        + "</div>\n</main>\n</div>\n"
        + "</body>\n</html>\n"
    )

def error_page(code, message, t=None):
    """Halaman galat yang tenang: tidak pernah membocorkan stack trace."""
    t = t or (lambda k: k)
    return (
        head("Galat %s" % code, t)
        + "<body>\n"
                + '<div class="login-shell"><div class="login-box tc">\n'
        + '<div class="mk" style="font-size:48px;font-weight:900">%s</div>\n' % C.e(code)
        + '<h1 class="mt8">%s</h1>\n' % C.e(message)
        + '<p class="sub mt8">Kejadian ini tercatat. Bila berulang, '
          "periksa log panel.</p>\n"
        + '<div class="btns" style="justify-content:center">'
          '<a class="btn pk" href="%s">%s</a></div>\n' % (url("/"), C.e(t("act.back")))
        + "</div></div>\n"
                + "</body>\n</html>\n"
    )
