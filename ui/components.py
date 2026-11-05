"""Komponen HTML server-rendered. Semua output di-escape.

Aturan desain: tanpa glow, tanpa blur, bayangan hard-offset.
Aksesibilitas: tombol asli, label asli, aria untuk status hidup.
"""
from html import escape as _e


def e(value):
    return _e("" if value is None else str(value), quote=True)


# ---------- ikon (SVG inline, currentColor, tanpa dependensi) ----------

ICONS = {
        "cpu": '<path d="M9 3v2h6V3h2v2h2a2 2 0 0 1 2 2v2h2v2h-2v4h2v2h-2v2a2 2 0 0 1-2 2h-2v2h-2v-2H9v2H7v-2H5a2 2 0 0 1-2-2v-2H1v-2h2v-4H1v-2h2V7a2 2 0 0 1 2-2h2V3h2Zm10 4H5v12h14V7Zm-2 2v8H7V9h10Zm-2 2H9v4h6v-4Z"/>',
    "ram": '<path d="M2 7h20v10H2V7Zm2 2v6h16V9H4Zm2 1h2v4H6v-4Zm4 0h2v4h-2v-4Zm4 0h2v4h-2v-4Z"/>',
    "temp": '<path d="M12 2a3 3 0 0 0-3 3v8.3a5 5 0 1 0 6 0V5a3 3 0 0 0-3-3Zm1 12.3V5a1 1 0 1 0-2 0v9.3a3 3 0 1 0 2 0Z"/>',
    "server": '<path d="M3 4h18v6H3V4Zm0 10h18v6H3v-6Zm3-7v2h2V7H6Zm0 10v2h2v-2H6Z"/>',
    "redis": '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8Z"/>',
    "terminal": '<path d="m4 17 6-5-6-5v10Zm8 2h8v-2h-8v2ZM2 4v16a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/>',
    "clock": '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 11H7v-2h4V6h2v7Z"/>',
    "dash": '<path d="M3 13h8V3H3v10Zm10 8h8V11h-8v10ZM3 21h8v-6H3v6ZM13 9h8V3h-8v6Z"/>',
    "svc": '<path d="M4 4h16v4H4V4Zm0 6h16v4H4v-4Zm0 6h16v4H4v-4Z"/>',
    "files": '<path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6Z"/>',
    "logs": '<path d="M5 3h11l3 3v15H5V3Zm3 6h8v2H8V9Zm0 4h8v2H8v-2Zm0 4h5v2H8v-2Z"/>',
    "web": '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm7.9 9h-3.4a15.6 15.6 0 0 0-1.2-5.5A8 8 0 0 1 19.9 11ZM12 4c.9 1.3 1.9 3.6 2.3 7H9.7C10.1 7.6 11.1 5.3 12 4ZM4.1 13h3.4c.2 2 .7 3.9 1.2 5.5A8 8 0 0 1 4.1 13Zm3.4-2H4.1a8 8 0 0 1 4.6-5.5C8.2 7 7.7 8.9 7.5 11Zm4.5 9c-.9-1.3-1.9-3.6-2.3-7h4.6c-.4 3.4-1.4 5.7-2.3 7Zm5.4-3.5c.5-1.6 1-3.5 1.2-5.5h3.4a8 8 0 0 1-4.6 5.5Z"/>',
    "apps": '<path d="M4 4h6v6H4V4Zm10 0h6v6h-6V4ZM4 14h6v6H4v-6Zm10 0h6v6h-6v-6Z"/>',
    "docker": '<path d="M4 7h16v3H4V7Zm0 5h16v3H4v-3Zm0 5h16v3H4v-3Z"/>',
    "db": '<path d="M12 3c4.4 0 8 1.3 8 3v12c0 1.7-3.6 3-8 3s-8-1.3-8-3V6c0-1.7 3.6-3 8-3Zm0 2c-3.6 0-6 .9-6 1s2.4 1 6 1 6-.9 6-1-2.4-1-6-1Z"/>',
    "disk": '<path d="M4 5h16v6H4V5Zm0 9h16v5H4v-5Zm3 1.5v2h2v-2H7Z"/>',
    "net": '<path d="M4 9h16v3H4V9Zm3-4h10v2H7V5Zm-2 8h14v6H5v-6Zm3 2v2h2v-2H8Z"/>',
    "cron": '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 5v5.4l4 2.3-1 1.7-5-2.9V7h2Z"/>',
    "backup": '<path d="M12 3 4 7v10l8 4 8-4V7l-8-4Zm0 2.2L17.8 8 12 10.8 6.2 8 12 5.2Z"/>',
    "user": '<path d="M12 4a4 4 0 1 1 0 8 4 4 0 0 1 0-8Zm0 10c4.4 0 8 2 8 4.5V20H4v-1.5C4 16 7.6 14 12 14Z"/>',
    "shield": '<path d="M12 2 4 5v7c0 5 3.4 8.7 8 10 4.6-1.3 8-5 8-10V5l-8-3Z"/>',
    "bell": '<path d="M12 3a5 5 0 0 1 5 5v3l2 3v2H5v-2l2-3V8a5 5 0 0 1 5-5Zm0 18a2.5 2.5 0 0 1-2.4-2h4.8A2.5 2.5 0 0 1 12 21Z"/>',
    "wrench": '<path d="m14.7 3 2.6 2.6-3 3 1.4 1.4 3-3L21.3 9.6 17 14 10 7l4.7-4Z"/>',
    "logout": '<path d="M10 3h8a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-8v-2h8V5h-8V3Zm-1 6 4 3-4 3v-2H4v-2h5V9Z"/>',
    "menu": '<path d="M4 6h16v2H4V6Zm0 5h16v2H4v-2Zm0 5h16v2H4v-2Z"/>',
    "theme": '<path d="M12 2a10 10 0 1 0 0 20V2Z"/>',
    "lang": '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm6.9 7h-2.7a13 13 0 0 0-1-3.6A8 8 0 0 1 18.9 9ZM12 4.2c.7 1 1.5 2.8 1.8 4.8h-3.6C10.5 7 11.3 5.2 12 4.2ZM7.8 5.4a13 13 0 0 0-1 3.6H4.1a8 8 0 0 1 3.7-3.6ZM4.1 11h2.9c0 1.4.2 2.7.5 3.9H4.9A8 8 0 0 1 4.1 11Zm3 6.2c.3-.4.6-.9.8-1.4.2-.7.4-1.5.5-2.3h.4c.4 1.6 1 2.9 1.8 3.7Z"/>',
    "refresh": '<path d="M12 5V2L7 6l5 4V7a5 5 0 1 1-5 5H5a7 7 0 1 0 7-7Z"/>',
    "play": '<path d="M7 4l12 8-12 8V4Z"/>',
    "stop": '<path d="M6 6h12v12H6V6Z"/>',
    "trash": '<path d="M9 3h6l1 2h4v2H4V5h4l1-2ZM5 9h14l-1 12H6L5 9Z"/>',
    "edit": '<path d="M4 17.2 14.6 6.6l2.8 2.8L6.8 20H4v-2.8Zm12-12 1.4-1.4a1 1 0 0 1 1.4 0l1.4 1.4a1 1 0 0 1 0 1.4L18.8 8 16 5.2Z"/>',
    "down": '<path d="M11 3h2v10l3.5-3.5 1.4 1.4L12 17l-5.9-6.1 1.4-1.4L11 13V3ZM5 19h14v2H5v-2Z"/>',
    "up": '<path d="M11 21h2V11l3.5 3.5 1.4-1.4L12 7l-5.9 6.1 1.4 1.4L11 11v10ZM5 3h14v2H5V3Z"/>',
    "plus": '<path d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z"/>',
    "x": '<path d="m6.4 5 5.6 5.6L17.6 5 19 6.4 13.4 12 19 17.6 17.6 19 12 13.4 6.4 19 5 17.6 10.6 12 5 6.4 6.4 5Z"/>',
    "search": '<path d="M10 3a7 7 0 1 1-4.9 12L2 18.1 3.4 19.5 6.5 16.4A7 7 0 0 1 10 3Zm0 2a5 5 0 1 0 0 10 5 5 0 0 0 0-10Z"/>',
    "check": '<path d="m9.6 16.2-4.2-4.2 1.4-1.4 2.8 2.8 6.6-6.6 1.4 1.4-8 8Z"/>',
    "warn": '<path d="M12 2 1 21h22L12 2Zm1 14h-2v2h2v-2Zm0-8h-2v6h2V8Z"/>',
    "clock": '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 5v5.4l4 2.3-1 1.7-5-2.9V7h2Z"/>',
}


def icon(name, size=16):
    """SVG inline. aria-hidden karena selalu mendampingi teks."""
    body = ICONS.get(name, ICONS["dash"])
    return ('<svg width="%d" height="%d" viewBox="0 0 24 24" fill="currentColor" '
            'aria-hidden="true" focusable="false">%s</svg>' % (size, size, body))


# ---------- potongan komponen ----------

def hazard(bottom=False):
    return ""


def tag(text, kind="", title=""):
    t = ' title="%s"' % e(title) if title else ""
    return '<span class="tag %s"%s>%s</span>' % (e(kind), t, e(text))


def lamp(state="of", title=""):
    """Status: warna + bentuk, bukan hanya warna."""
    t = ' title="%s"' % e(title) if title else ""
    return '<span class="lamp %s"%s aria-hidden="true"></span>' % (e(state), t)


def btn(label, action="", kind="", icon_name="", attrs="", small=False,
        disabled=False, wide=False, title=""):
    """Tombol asli (bukan div). `action` jadi atribut data-act."""
    cls = "btn"
    if small:
        cls += " sm"
    if kind:
        cls += " " + kind
    if wide:
        cls += " wide"
    a = ' data-act="%s"' % e(action) if action else ""
    if title:
        a += ' title="%s"' % e(title)
    if disabled:
        a += " disabled"
    if attrs:
        a += " " + attrs
    ic = '<span class="ic">%s</span>' % icon(icon_name) if icon_name else ""
    return '<button type="button" class="%s"%s>%s%s</button>' % (
        cls, a, ic, e(label))


def meter(percent, kind=""):
    """Bar solid, tanpa glow. `kind` otomatis dari persentase bila kosong."""
    p = max(0.0, min(100.0, float(percent or 0)))
    if not kind:
        kind = "danger" if p >= 90 else "warn" if p >= 75 else "ok"
    return ('<div class="meter %s" role="progressbar" aria-valuenow="%.0f" '
            'aria-valuemin="0" aria-valuemax="100"><i style="width:%.1f%%"></i></div>'
            % (e(kind), p, p))


def metric(label, value, unit="", foot="", percent=None, count=None, icon_name="", badge=""):
    cnt = ' data-count="%s"' % count if count is not None else ""
    ic = ('<span class="metric-icon">%s</span>' % icon(icon_name, 16)) if icon_name else ""
    bdg = ('<span class="tag %s">%s</span>' % (
        "ok" if (percent or 0) < 70 else "warn" if (percent or 0) < 85 else "dg", e(badge)
    )) if badge else ""
    return (
        '<div class="panel lift metric">'
        '<div class="metric-head"><span class="lb">%s</span><div class="row gap6 align-center">%s%s</div></div>'
        '<span class="vl"%s>%s%s</span>'
        '<span class="ft">%s</span>%s'
        '</div>' % (
            e(label), bdg, ic,
            cnt, e(value),
            (' <small>%s</small>' % e(unit)) if unit else "",
            e(foot),
            meter(percent) if percent is not None else "",
        )
    )


def panel(title, body, hint="", actions="", lift=True):
    head = ""
    if title or actions:
        head = ('<div class="panel-head"><div><h2>%s</h2>%s</div>'
                '<div class="btns">%s</div></div>' % (
                    e(title),
                    ('<div class="hint">%s</div>' % e(hint)) if hint else "",
                    actions,
                ))
    return '<div class="panel%s">%s%s</div>' % (" lift" if lift else "", head, body)


def empty(title, message, mark="—"):
    return ('<div class="empty"><div class="mk" aria-hidden="true">%s</div>'
            '<div class="tt">%s</div><div class="ms">%s</div></div>'
            % (e(mark), e(title), e(message)))


def skeletons(rows=4, large=False):
    out = []
    for _ in range(rows):
        out.append('<div class="sk%s mb8"></div>' % (" lg" if large else ""))
    return "".join(out)


def table(headers, rows, aligns=None):
    aligns = aligns or []
    th = "".join(
        '<th%s>%s</th>' % (' class="%s"' % aligns[i] if i < len(aligns) and aligns[i] else "", e(h))
        for i, h in enumerate(headers)
    )
    body = ""
    for row in rows:
        tds = ""
        for i, cell in enumerate(row):
            cls = aligns[i] if i < len(aligns) and aligns[i] else ""
            lbl = headers[i] if i < len(headers) else ""
            attrs = ""
            if cls:
                attrs += ' class="%s"' % cls
            if lbl and cls != "act":
                attrs += ' data-label="%s"' % e(lbl)
            tds += "<td%s>%s</td>" % (attrs, cell)
        body += "<tr>%s</tr>" % tds
    return ('<div class="tbl-wrap"><table class="tbl"><thead><tr>%s</tr></thead>'
            "<tbody>%s</tbody></table></div>" % (th, body))


def field(label, name, kind="text", value="", placeholder="", help="",
          required=False, attrs="", autocomplete="off", extra_class=""):
    fid = "f_" + name.replace("[", "_").replace("]", "")
    req = " required" if required else ""
    a = ' aria-describedby="%s_h"' % fid if help else ""
    return (
        '<div class="field">'
        '<label for="%s">%s</label>'
        '<input id="%s" name="%s" type="%s" value="%s" placeholder="%s"%s%s%s '
        'class="%s" autocomplete="%s">'
        '%s'
        "</div>" % (
            e(fid), e(label) + (" *" if required else ""),
            e(fid), e(name), e(kind), e(value), e(placeholder), req, a,
            ' ' + attrs if attrs else "", e(extra_class), e(autocomplete),
            ('<span class="help" id="%s_h">%s</span>' % (e(fid), e(help))) if help else "",
        )
    )


def textarea_field(label, name, value="", help="", rows=8, mono=True, placeholder=""):
    fid = "a_" + name.replace("[", "_").replace("]", "")
    return (
        '<div class="field">'
        '<label for="%s">%s</label>'
        '<textarea id="%s" name="%s" rows="%d" class="%s" placeholder="%s"%s></textarea>'
        "%s</div>" % (
            e(fid), e(label), e(fid), e(name), rows,
            "mono-area" if mono else "", e(placeholder),
            ' aria-describedby="%s_h"' % fid if help else "",
            ('<span class="help" id="%s_h">%s</span>' % (e(fid), e(help))) if help else "",
        )
    )


def select_field(label, name, options, selected="", help=""):
    fid = "s_" + name.replace("[", "_").replace("]", "")
    opts = "".join(
        '<option value="%s"%s>%s</option>' % (
            e(v), " selected" if str(v) == str(selected) else "", e(t))
        for v, t in options
    )
    return (
        '<div class="field"><label for="%s">%s</label>'
        '<select id="%s" name="%s">%s</select>%s</div>' % (
            e(fid), e(label), e(fid), e(name), opts,
            ('<span class="help">%s</span>' % e(help)) if help else "",
        )
    )


def segmented(name, options, current="", attrs=""):
    """Kontrol segmented gaya iOS. Tombol asli, aria-pressed."""
    btns = "".join(
        '<button type="button" data-seg="%s" data-val="%s" aria-pressed="%s"%s>%s</button>'
        % (e(name), e(v), "true" if str(v) == str(current) else "false",
           ' ' + attrs if attrs else "", e(t))
        for v, t in options
    )
    return '<div class="seg" role="group" aria-label="%s">%s</div>' % (e(name), btns)


def term(text, cls=""):
    return '<pre class="term %s" tabindex="0">%s</pre>' % (e(cls), e(text))


def dl(pairs):
    inner = "".join("<dt>%s</dt><dd>%s</dd>" % (e(k), v) for k, v in pairs)
    return '<dl class="dl">%s</dl>' % inner


# ---------- formatter (dipakai halaman) ----------

def bytes(n, precision=1):
    """Format ukuran byte jadi B/KB/MB/GB/TB."""
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        n = 0.0
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024.0
        i += 1
    if i == 0:
        return "%d B" % n
    return ("%." + str(precision) + "f %s") % (n, units[i])


def dur(seconds):
    """Durasi ringkas: 3h 2j / 5j 12m / 42m."""
    try:
        s = max(0, int(seconds or 0))
    except (TypeError, ValueError):
        s = 0
    d, h, m = s // 86400, (s % 86400) // 3600, (s % 3600) // 60
    if d:
        return "%dd %dj" % (d, h)
    if h:
        return "%dj %dm" % (h, m)
    return "%dm" % m


def ago(ts):
    """Waktu relatif dari epoch (bahasa Indonesia ringkas)."""
    import time as _t
    try:
        ts = int(ts or 0)
    except (TypeError, ValueError):
        return "—"
    if ts <= 0:
        return "—"
    s = max(0, int(_t.time()) - ts)
    if s < 60:
        return "%ds lalu" % s
    if s < 3600:
        return "%dm lalu" % (s // 60)
    if s < 86400:
        return "%dj lalu" % (s // 3600)
    return "%dh lalu" % (s // 86400)


def stamp(ts, fmt="%d %b %H:%M"):
    """Timestamp absolut singkat."""
    import time as _t
    try:
        return _t.strftime(fmt, _t.localtime(int(ts or 0)))
    except (TypeError, ValueError, OSError):
        return "—"

def search_input(name, placeholder, label, attrs="", elem_id=None):
    """Kolom pencarian dengan label benar (placeholder bukan label).

    `elem_id` dipakai bila JavaScript halaman mencari id tertentu.
    """
    fid = elem_id or ("q_" + name)
    return (
        '<div class="field">'
        '<label for="%s" class="sr-only">%s</label>'
        '<input id="%s" name="%s" type="search" placeholder="%s"%s>'
        "</div>" % (e(fid), e(label), e(fid), e(name), e(placeholder),
                    " " + attrs if attrs else "")
    )
