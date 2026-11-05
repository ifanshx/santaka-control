"""Halaman server-rendered. Setiap halaman = fungsi yang mengembalikan HTML.

Halaman mengembalikan kerangka penuh (shell) atau potongan (untuk fetch).
PAGE_PERMS memetakan id halaman ke izin minimum.
"""
import os
import time

from lib import perm, stats, validate
from ui import components as C
from ui import layout
from ui import (page_cron, page_db, page_files, page_logs,
                page_maintenance, page_network, page_redis, page_security,
                page_svc, page_storage, page_terminal, page_users, page_web)


def _os_pretty():
    """Nama distro/sistem operasi untuk meta dashboard."""
    import platform
    try:
        rel = platform.freedesktop_os_release()
    except (AttributeError, OSError):
        rel = {}
    name = " ".join(x for x in (rel.get("NAME"), rel.get("VERSION")) if x)
    return name or (platform.system() or "Linux")


# ---------- dashboard (P0, lengkap) ----------

def dash(req, app, sess, qs, t):
    snap = stats.snapshot(app.cfg.get("disk_path", "/"))
    mem, disk = snap["mem"], snap["disk"]

    temp = snap["temp"]
    if temp is None:
        temp_txt, temp_kind = "—", ""
    else:
        temp_txt = "%.1f" % temp
        temp_kind = "danger" if temp >= 80 else "warn" if temp >= 70 else "ok"

    # Status badge labels
    cpu_badge = "OPTIMAL" if snap["cpu"] < 60 else "TINGGI" if snap["cpu"] < 85 else "KRITIS"
    mem_badge = "TERSEDIA" if mem["percent"] < 75 else "PADAT"
    temp_badge = "DINGIN" if (temp or 0) < 65 else "HANGAT" if (temp or 0) < 75 else "PANAS"
    disk_badge = "SISA %s GB" % disk["free_gb"]

    m = [
        C.metric(t("dash.cpu"), "%.1f" % snap["cpu"], "%",
                 t("dash.load") + ": " + " ".join("%.2f" % x for x in snap["load"]),
                 percent=snap["cpu"], icon_name="cpu", badge=cpu_badge),
        C.metric(t("dash.mem"), "%.0f" % mem["used_mb"], "/ %d MB" % mem["total_mb"],
                 "Sisa %d MB · swap %d/%d MB" % (
                     mem["available_mb"], mem["swap_used_mb"], mem["swap_total_mb"]),
                 percent=mem["percent"], icon_name="ram", badge=mem_badge),
        C.metric(t("dash.temp"), temp_txt, "°C" if temp is not None else "",
                 t("dash.thermal") + " · %d core" % snap["cores"],
                 percent=(min(100.0, temp / 100.0 * 100) if temp else None),
                 icon_name="temp", badge=temp_badge),
        C.metric(t("dash.disk"), "%.1f" % disk["used_gb"], "/ %s GB" % disk["total_gb"],
                 "Sisa %s GB · %s" % (disk["free_gb"], app.cfg.get("disk_path", "/")),
                 percent=disk["percent"], icon_name="disk", badge=disk_badge),
    ]

    # Core Stack Service Detection from snapshot
    svc_pills = "".join(
        '<div class="svc-pill %s"><span class="pulse-dot %s"></span><span class="svc-name">%s</span><span class="svc-port">%s</span></div>' % (
            "active" if s["up"] else "inactive",
            "green" if s["up"] else "gray",
            C.e(s["name"]), C.e(s["port"])
        ) for s in snap.get("services", [])
    )

    # Hero status banner
    hero = (
        '<div class="dash-hero mb16">'
        '<div class="hero-status">'
        '<div class="hero-dot"></div>'
        '<div class="hero-info">'
        '<div class="hero-title">%s · Status Optimal</div>'
        '<div class="hero-meta">%s · Uptime %.1f Jam · Port %s</div>'
        '</div>'
        '</div>'
        '<div class="hero-actions">'
        '<a href="%s" class="btn sm pk"><span class="ic">%s</span> Terminal</a>'
        '<a href="%s" class="btn sm gh"><span class="ic">%s</span> Berkas</a>'
        '<a href="%s" class="btn sm gh"><span class="ic">%s</span> Vhosts</a>'
        '<a href="%s" class="btn sm gh"><span class="ic">%s</span> MySQL</a>'
        '<button class="btn sm gh" data-action="reload"><span class="ic">%s</span> Segarkan</button>'
        '</div>'
        '</div>' % (
            C.e(str(app.cfg.get("hostname") or snap["hostname"])),
            C.e("%s · %s %s" % (_os_pretty(), snap["kernel"], snap["arch"])),
            snap["uptime_h"],
            C.e(str(app.cfg.get("port") or 8081)),
            layout.url("/terminal"), C.icon("terminal", 13),
            layout.url("/files"), C.icon("files", 13),
            layout.url("/web"), C.icon("web", 13),
            layout.url("/db"), C.icon("db", 13),
            C.icon("refresh", 13),
        )
    )

    svc_strip = (
        '<div class="card mb16 p12">'
        '<div class="row space-between align-center flex-wrap gap8">'
        '<div class="row gap8 align-center flex-wrap">'
        '<span class="text-xs text-muted bold mr8">LAYANAN UTAMA:</span>'
        '%s'
        '</div>'
        '<span class="text-xs text-muted font-mono">Live Telemetri · 3s</span>'
        '</div>'
        '</div>' % svc_pills
    )

    # ----- spesifikasi host (spec-grid) -----
    import platform
    import time as _time
    try:
        tz = _time.strftime("%Z")
    except Exception:
        tz = "—"

    hw = stats.hardware()
    mem = snap["mem"]
    ram_text = "%.0f MB" % mem["total_mb"]
    if mem.get("swap_total_mb"):
        ram_text += " + %.0f MB swap" % mem["swap_total_mb"]
    spec_items = [
        ("Hostname", '<span class="mono bold text-primary">%s</span>' % C.e(snap["hostname"])),
        ("Perangkat", C.e(hw["model"] or "Tidak terdeteksi")),
        ("Prosesor (SoC)", C.e(hw["cpu"] or "%d core" % hw["cores"])),
        ("Kernel Linux", '<span class="mono">%s</span>' % C.e(snap["kernel"])),
        ("Arsitektur", '<span class="mono">%s</span>' % C.e(snap["arch"])),
        ("Total RAM", C.e(ram_text)),
        (t("dash.uptime"), C.e("%.1f jam (Normal)" % snap["uptime_h"])),
        ("Python Server", '<span class="mono">%s (Stdlib)</span>' % C.e(platform.python_version())),
        ("Zona Waktu", '<span class="mono">%s</span>' % C.e(tz)),
        ("Akses Gateway", '<span class="tag ok">%s</span>' % C.e(req.headers.get("Host") or "Lokal")),
    ]
    ident_html = '<div class="spec-grid">%s</div>' % "".join(
        '<div class="spec-row"><span class="spec-k">%s</span><span class="spec-v">%s</span></div>' % (k, v)
        for k, v in spec_items
    )

    # ----- jaringan -----
    net_rows = [(
        '<span class="mono bold">%s</span>' % C.e(d["name"]),
        C.lamp("ok" if d["up"] else "of") + " " + C.e("UP" if d["up"] else "DOWN"),
        '<span class="num text-success">%s/s</span>' % C.e(C.bytes(d.get("rx_ps", 0))),
        '<span class="num text-primary">%s/s</span>' % C.e(C.bytes(d.get("tx_ps", 0))),
        '<span class="num">%s</span>' % C.e(C.bytes(d["rx_bytes"])),
        '<span class="num">%s</span>' % C.e(C.bytes(d["tx_bytes"])),
    ) for d in snap["net"]]
    net_tbl = C.table(
        ["Antarmuka", "Status", "↓ RX/s", "↑ TX/s", "Total RX", "Total TX"],
        net_rows, aligns=["", "", "num", "num", "num", "num"]
    ) if net_rows else C.empty(t("lbl.empty"), "Tidak ada antarmuka jaringan aktif.")

    # ----- proses terberat (dengan rank & mini bar) -----
    proc_rows = []
    max_rss = max([p["rss_mb"] for p in snap["procs"]] or [1.0])
    for i, p in enumerate(snap["procs"][:6], 1):
        pct_bar = min(100, int((p["rss_mb"] / max_rss) * 100))
        proc_rows.append((
            '<span class="proc-rank">%d</span> <span class="mono bold">%s</span>' % (i, C.e(p["name"])),
            '<span class="mono text-muted">%d</span>' % p["pid"],
            '<div class="row gap8 align-center justify-end">'
            '<div class="mini-bar"><div class="mini-fill" style="width:%d%%"></div></div>'
            '<span class="num bold">%.1f MB</span></div>' % (pct_bar, p["rss_mb"])
        ))
    proc_tbl = (C.table(["Aplikasi", "PID", "Konsumsi RSS"], proc_rows,
                        aligns=["", "num", "num"]) if proc_rows
                else C.empty("Tidak ada proses", "Data proses belum tersedia."))

    # ----- mount & storage -----
    data_mount = str(app.cfg.get("data_mount") or "/mnt/data")
    mount_rows = []
    for mo in snap["mounts"]:
        is_data = mo["point"] == data_mount
        point_html = '<b class="mono text-primary">%s</b>' % C.e(mo["point"]) if is_data else '<span class="mono">%s</span>' % C.e(mo["point"])
        badge_label = ' <span class="badge badge-info">DATA</span>' if is_data else ''
        mount_rows.append((
            point_html + badge_label,
            '<span class="mono text-muted text-xs">%s</span>' % C.e(mo["fstype"]),
            '<span class="num">%s GB</span>' % C.e(mo["used_gb"]),
            '<span class="num bold text-success">%s GB</span>' % C.e(mo["free_gb"]),
            '<div class="row gap8 align-center"><div style="flex:1;min-width:64px">%s</div>'
            '<span class="num text-xs text-muted">%d%%</span></div>'
            % (C.meter(mo["percent"]), int(mo["percent"])),
        ))
    mount_tbl = (C.table(
        [t("files.path"), "FS", t("lbl.used"), "Sisa Bebas", "Kapasitas"],
        mount_rows, aligns=["", "", "num", "num", ""]
    ) if mount_rows else C.empty("Tidak ada mount", "Belum ada filesystem terpasang."))

    # Panel telemetri: grafik garis CPU & RAM dengan riwayat 2 menit.
    chart_panel = (
        '<div class="panel">'
        '<div class="panel-head">'
        '<div><h2>Tren Telemetri Real-Time</h2>'
        '<div class="hint">40 sampel · polling 3 detik · jendela 2 menit</div></div>'
        '<div class="row gap8 align-center flex-wrap">'
        '<span class="tele-pill cpu" id="live-cpu-pill"><span class="lamp wr"></span> CPU <b id="live-cpu-val">%.1f%%</b></span>'
        '<span class="tele-pill ram" id="live-ram-pill"><span class="lamp in"></span> RAM <b id="live-ram-val">%.1f%%</b></span>'
        '</div>'
        '</div>'
        '<div class="p16">'
        '<div class="chart-legend mb8">'
        '<span class="cpu"><i></i>CPU</span>'
        '<span class="ram"><i></i>RAM</span>'
        '<span class="text-dim" style="margin-left:auto">2 menit lalu → sekarang</span>'
        '</div>'
        '<div class="chart-wrap">'
        '<canvas class="chart" id="spark" role="img" aria-label="Grafik CPU dan RAM dua menit terakhir"></canvas>'
        '<div class="chart-tip" id="spark-tip" aria-hidden="true"></div>'
        '<div class="chart-empty" id="spark-empty"><b>Menunggu sampel pertama</b><span>Grafik terisi otomatis setiap 3 detik.</span></div>'
        '</div>'
        '</div>'
        '</div>' % (snap["cpu"], mem["percent"])
    )

    body = (
        hero
        + svc_strip
        + '<div id="dash-live"><div class="grid g4">%s</div></div>' % "".join(m)
        + '<div class="mt16">' + chart_panel + '</div>'
        + '<div class="grid g2 mt16">'
        + C.panel("Spesifikasi & Identitas Host", ident_html)
        + C.panel("Trafik Jaringan (Network Throughput)", net_tbl)
        + "</div>"
        + '<div class="grid g2 mt16">'
        + C.panel("Top Proses Berdasarkan RAM", proc_tbl)
        + C.panel("Partisi Penyimpanan & Harddisk", mount_tbl)
        + "</div>"
    )

    # Perbarui angka dan grafik tiap 3 detik tanpa memuat ulang halaman.
    body += ("""
<script>
(function(){
  var el = document.getElementById('dash-live');
  var cv = document.getElementById('spark');
  if (!el || !cv || !window.SC) return;
  var tip = document.getElementById('spark-tip');
  var wait = document.getElementById('spark-empty');
  var MAX = 40, KEY = 'sc.telemetry.v1', REFRESH = 3000;
  var hist = {cpu: [], ram: []};
  var hover = -1;

  // Riwayat dipertahankan antar-reload selama masih segar (maks 15 menit).
  try {
    var saved = JSON.parse(sessionStorage.getItem(KEY) || 'null');
    if (saved && saved.at && Date.now() - saved.at < 900000 &&
        saved.cpu && saved.ram && saved.cpu.length === saved.ram.length) {
      hist.cpu = saved.cpu.slice(-MAX);
      hist.ram = saved.ram.slice(-MAX);
    }
  } catch (e) {}
  if (!hist.cpu.length) {
    var startCpu = parseFloat("__CPU__"), startRam = parseFloat("__RAM__");
    hist.cpu = [startCpu];
    hist.ram = [startRam];
  }

  function save(){
    try {
      sessionStorage.setItem(KEY, JSON.stringify({
        at: Date.now(), cpu: hist.cpu.slice(-MAX), ram: hist.ram.slice(-MAX)
      }));
    } catch (e) {}
  }

  function colors(){
    var dark = document.documentElement.getAttribute('data-theme') !== 'paper';
    return {
      grid: dark ? 'rgba(148,163,184,0.16)' : 'rgba(15,23,42,0.08)',
      label: dark ? 'rgba(148,163,184,0.75)' : 'rgba(71,85,105,0.85)',
      cpu: '#F97316',
      ram: '#06B6D4'
    };
  }

  function draw(){
    var dpr = window.devicePixelRatio || 1;
    var w = cv.clientWidth || 600, h = cv.clientHeight || 150;
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
      cv.width = Math.round(w * dpr);
      cv.height = Math.round(h * dpr);
    }
    var c = cv.getContext('2d');
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, w, h);

    var col = colors();
    var padL = 36, padR = 8, padT = 12, padB = 20;
    var plotW = Math.max(10, w - padL - padR);
    var plotH = Math.max(10, h - padT - padB);
    function yFor(v){ return padT + (1 - Math.max(0, Math.min(100, v)) / 100) * plotH; }

    // Grid + label persen
    c.font = '10px "JetBrains Mono", monospace';
    c.textAlign = 'right';
    c.textBaseline = 'middle';
    for (var i = 0; i <= 4; i++) {
      var pct = 100 - i * 25;
      var y = Math.round(yFor(pct)) + 0.5;
      c.strokeStyle = col.grid;
      c.lineWidth = 1;
      c.beginPath(); c.moveTo(padL, y); c.lineTo(w - padR, y); c.stroke();
      c.fillStyle = col.label;
      c.fillText(pct + '%', padL - 8, y);
    }

    var n = hist.cpu.length;
    if (n >= 2) {
      var step = plotW / (MAX - 1);
      var xFor = function(i){ return padL + plotW - (n - 1 - i) * step; };

      function series(arr, stroke, rgba){
        var grad = c.createLinearGradient(0, padT, 0, padT + plotH);
        grad.addColorStop(0, rgba);
        grad.addColorStop(1, 'rgba(0,0,0,0)');

        c.beginPath();
        c.moveTo(xFor(0), yFor(arr[0]));
        for (var i = 1; i < arr.length; i++) {
          var x0 = xFor(i - 1), y0 = yFor(arr[i - 1]);
          var x1 = xFor(i), y1 = yFor(arr[i]);
          var mx = (x0 + x1) / 2;
          c.bezierCurveTo(mx, y0, mx, y1, x1, y1);
        }
        c.lineTo(xFor(arr.length - 1), padT + plotH);
        c.lineTo(xFor(0), padT + plotH);
        c.closePath();
        c.fillStyle = grad;
        c.fill();

        c.beginPath();
        c.moveTo(xFor(0), yFor(arr[0]));
        for (var j = 1; j < arr.length; j++) {
          var px = xFor(j - 1), py = yFor(arr[j - 1]);
          var cx = xFor(j), cy = yFor(arr[j]);
          var mid = (px + cx) / 2;
          c.bezierCurveTo(mid, py, mid, cy, cx, cy);
        }
        c.strokeStyle = stroke;
        c.lineWidth = 2;
        c.lineJoin = 'round';
        c.lineCap = 'round';
        c.stroke();
      }

      series(hist.ram, col.ram, 'rgba(6,182,212,0.14)');
      series(hist.cpu, col.cpu, 'rgba(249,115,22,0.12)');
    }

    // Penanda hover: garis vertikal + titik + tooltip
    if (hover >= 0 && hover < n && n >= 2) {
      var hx = padL + plotW - (n - 1 - hover) * (plotW / (MAX - 1));
      c.strokeStyle = col.label;
      c.lineWidth = 1;
      c.beginPath(); c.moveTo(hx, padT); c.lineTo(hx, padT + plotH); c.stroke();
      [[hist.cpu[hover], col.cpu], [hist.ram[hover], col.ram]].forEach(function(pair){
        c.beginPath();
        c.arc(hx, yFor(pair[0]), 3, 0, Math.PI * 2);
        c.fillStyle = pair[1];
        c.fill();
        c.strokeStyle = 'rgba(255,255,255,0.9)';
        c.lineWidth = 1.5;
        c.stroke();
      });
      if (tip) {
        var cpuV = hist.cpu[hover], ramV = hist.ram[hover];
        tip.innerHTML = '<span style="color:#F97316">●</span> CPU ' + cpuV.toFixed(1) +
                        '% &nbsp; <span style="color:#06B6D4">●</span> RAM ' + ramV.toFixed(1) + '%';
        tip.style.left = Math.max(60, Math.min(w - 60, hx)) + 'px';
        tip.classList.add('on');
      }
    } else if (tip) {
      tip.classList.remove('on');
    }

    if (wait) wait.classList.toggle('hide', n >= 5);
  }

  function push(s){
    hist.cpu.push(s.cpu);
    hist.ram.push(s.mem.percent);
    if (hist.cpu.length > MAX) hist.cpu.shift();
    if (hist.ram.length > MAX) hist.ram.shift();
    save();
    draw();
  }

  function paint(s){
    var temp = s.temp;
    var vals = [
      s.cpu.toFixed(1) + '%',
      Math.round(s.mem.used_mb) + ' <small>/ ' + Math.round(s.mem.total_mb) + ' MB</small>',
      (temp === null ? '—' : temp.toFixed(1)) + (temp === null ? '' : ' <small>°C</small>'),
      s.disk.used_gb.toFixed(1) + ' <small>/ ' + s.disk.total_gb + ' GB</small>'
    ];
    var cpuValEl = document.getElementById('live-cpu-val');
    if (cpuValEl) cpuValEl.textContent = s.cpu.toFixed(1) + '%';
    var ramValEl = document.getElementById('live-ram-val');
    if (ramValEl) ramValEl.textContent = s.mem.percent.toFixed(1) + '%';
    var nodes = el.querySelectorAll('.metric .vl');
    vals.forEach(function(v, i){ if (nodes[i]) nodes[i].innerHTML = v; });
    var meters = el.querySelectorAll('.meter');
    var pct = [s.cpu, s.mem.percent, temp === null ? 0 : Math.min(100, temp), s.disk.percent];
    meters.forEach(function(m, i){
      var bar = m.querySelector('i');
      if (bar) bar.style.width = Math.max(0, Math.min(100, pct[i] || 0)) + '%';
      m.className = 'meter ' + ((pct[i] || 0) >= 90 ? 'danger'
                      : (pct[i] || 0) >= 75 ? 'warn' : 'ok');
    });
  }

  cv.addEventListener('mousemove', function(ev){
    var rect = cv.getBoundingClientRect();
    var padL = 36, padR = 8;
    var plotW = Math.max(10, rect.width - padL - padR);
    var n = hist.cpu.length;
    if (n < 2) { hover = -1; draw(); return; }
    var ratio = (ev.clientX - rect.left - padL) / plotW;
    var idx = Math.round((MAX - 1) - (1 - ratio) * (MAX - 1));
    var first = Math.max(0, n - MAX);
    hover = Math.max(first, Math.min(n - 1, first + idx));
    draw();
  });
  cv.addEventListener('mouseleave', function(){ hover = -1; draw(); });

  var timer = null;
  function tick(){
    fetch(window.SC.url('/api/stats'), {credentials: 'same-origin'})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(j){ if (!j || !j.data) return; paint(j.data); push(j.data); })
      .catch(function(){});
  }
  function start(){ if (!timer) { tick(); timer = setInterval(tick, REFRESH); } }
  function stop(){ if (timer) { clearInterval(timer); timer = null; } }

  document.addEventListener('visibilitychange', function(){
    document.hidden ? stop() : start();
  });
  window.addEventListener('resize', draw);
  draw();
  start();
})();
</script>
""").replace("__CPU__", "%.1f" % snap["cpu"]).replace("__RAM__", "%.1f" % mem["percent"])

    actions = (C.btn(t("act.refresh"), "", kind="sm gh", icon_name="refresh",
                     attrs='data-action="reload"'))
    return layout.shell(
        sess, app, "dash", t("nav.dash"),
        '<span class="mono">%s</span> · %s %s · %s' % (
            C.e(snap["hostname"]), C.icon("check", 12),
            C.e(t("dash.live")), C.e("%d core" % snap["cores"])),
        body, t, actions=actions
    )


# ---------- setup awal ----------

def setup_page(t, csrf, theme="paper"):
    return (
        layout.head("Setup", t)
        + "<body>\n" + C.hazard()
        + '<div class="login-shell"><div class="login-box">'
        + '<div class="brand mb16"><span class="badge">SC</span>'
          '<span class="name">Santaka Control</span></div>'
        + "<h1>Buat administrator pertama</h1>"
        + '<p class="sub">Panel ini belum memiliki pengguna. Buat akun '
          "administrator untuk mengamankan akses.</p>"
        + '<form method="post" action="/setup">'
        + '<input type="hidden" name="csrf" value="%s">' % C.e(csrf)
        + '<div class="stack">'
        + C.field("Nama pengguna", "username", required=True,
                  help="Huruf kecil, angka, garis bawah. 3–32 karakter.")
        + C.field("Kata sandi", "password", kind="password", required=True,
                  help="Minimal 10 karakter. Simpan di pengelola kata sandi.")
        + C.field("Ulangi kata sandi", "password2", kind="password", required=True)
        + "</div>"
        + '<div class="mt16"><button class="btn pk wide" type="submit">'
        + "Buat akun administrator</button></div>"
        + "</form></div></div>"
        + C.hazard(bottom=True)
        + "</body></html>"
    )


# ---------- halaman lain (P1..P5): stub jujur ----------

def _stub(page_id, title_key, phase, note):
    def render(req, app, sess, qs, t):
        body = (
            C.panel(t(title_key),
                    C.empty("Belum dibangun",
                            "%s akan tersedia pada %s. Halaman ini sengaja "
                            "dikosongkan, bukan gagal diam-diam."
                            % (note, phase), mark="…"),
                    lift=False)
            + '<p class="dim mt16" style="font-size:12px">Fondasi (P0) sudah '
              "aktif: autentikasi multi-peran, sesi yang dapat dicabut, "
              "jejak audit, dan token CSRF pada setiap aksi.</p>"
        )
        return layout.shell(sess, app, page_id, t(title_key),
                            "Fase %s" % phase, body, t)
    return render


def audit_page(req, app, sess, qs, t):
    limit = validate.safe_int((qs.get("n") or ["200"])[0], 1, 1000, 200)
    rows = app.audit.list(limit=limit)

    total_entries = len(rows)
    login_count = sum(1 for r in rows if r.get("kind") == "login")
    action_count = sum(1 for r in rows if r.get("kind") == "action")
    denied_count = sum(1 for r in rows if r.get("result") in ("denied", "badpass", "bad2fa", "ratelimited"))

    stat_cards = f"""
<div class="grid g4 mb16">
  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">TOTAL AKTIVITAS AUDIT</span>
      <span class="metric-icon">{C.icon("clock", 15)}</span>
    </div>
    <span class="vl text-primary">{total_entries}</span>
    <span class="ft">Entri jejak audit terekam</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">AKTIVITAS LOGIN</span>
      <span class="tag in">SESI</span>
    </div>
    <span class="vl">{login_count}</span>
    <span class="ft">Percobaan masuk pengguna</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">MUTASI SISTEM</span>
      <span class="tag ok">TERVERIFIKASI</span>
    </div>
    <span class="vl text-success">{action_count}</span>
    <span class="ft">Operasi ubah berkas, service, vhost</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">AKSES DITOLAK / GAGAL</span>
      <span class="tag {'danger' if denied_count > 0 else 'ok'}">{'PERHATIAN' if denied_count > 0 else 'AMAN'}</span>
    </div>
    <span class="vl {'text-danger' if denied_count > 0 else 'text-success'}">{denied_count}</span>
    <span class="ft">Percobaan login / aksi tanpa izin</span>
  </div>
</div>
"""

    trs = []
    for r in rows:
        kind = r.get("kind", "")
        cls = {"login": "in", "denied": "dg", "action": "ok"}.get(kind, "nu")
        res = r.get("result", "")
        res_cls = "ok" if res == "ok" else "dg" if res in ("denied", "badpass",
                                                           "bad2fa", "ratelimited") else "wr"
        trs.append((
            '<span class="mono text-xs">%s</span>' % C.e(r.get("iso", "")),
            '<b class="mono font-bold text-main">%s</b>' % C.e(r.get("user", "-")),
            '<span class="tag %s">%s</span>' % (cls, C.e(kind.upper())),
            '<span class="mono font-bold text-primary">%s</span>' % C.e(r.get("action", "")),
            '<span class="mono text-xs">%s</span>' % (C.e(r.get("target", "")) or '<span class="dim">—</span>'),
            '<span class="tag %s">%s</span>' % (res_cls, C.e(res.upper())),
            '<span class="mono font-bold text-xs">%s</span>' % C.e(r.get("ip", "")),
        ))

    table_html = C.table([t("au.time"), t("au.user"), "Jenis", t("au.action"),
                          t("au.target"), t("au.result"), t("au.ip")], trs) if trs else C.empty("Jejak audit kosong", "Belum ada aktivitas tercatat.")
    table_html = table_html.replace('class="tbl-wrap"', 'class="tbl-wrap tbl-scroll"', 1)

    table_card = f"""
<div class="card mb24 p0 overflow-hidden">
  <div class="card-header p16 border-b row space-between align-center flex-wrap gap8">
    <div class="row gap12 align-center flex-wrap">
      <h3 class="card-title text-sm m0">DAFTAR LOG AKTIVITAS KEAMANAN</h3>
      <span class="badge badge-success text-xs" id="audit-count">{total_entries} Entri</span>
    </div>
    <div class="row gap8 align-center">
      <div class="srch" style="max-width:300px;">
        <span class="ic">{C.icon("search", 13)}</span>
        <input type="text" id="audit-search" placeholder="Cari waktu, user, aksi, atau IP" class="form-input" />
      </div>
      <button type="button" class="btn btn-outline sm" data-action="reload">{C.icon("refresh", 13)} Segarkan</button>
    </div>
  </div>
  {table_html}
  <div class="tbl-pager" id="audit-pager">
    <span id="audit-range" aria-live="polite">Memuat…</span>
    <span class="nav">
      <button type="button" class="btn sm gh" id="audit-prev">Sebelumnya</button>
      <span id="audit-page" class="mono" style="min-width:72px;text-align:center">1 / 1</span>
      <button type="button" class="btn sm gh" id="audit-next">Berikutnya</button>
    </span>
  </div>
</div>
"""

    script = """
<script>
(function(){
  var sInput = document.getElementById('audit-search');
  var tbody = document.querySelector('.card .data-table tbody, .card .tbl tbody');
  var pager = document.getElementById('audit-pager');
  if (!sInput || !tbody || !pager) return;
  var all = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
  var countEl = document.getElementById('audit-count');
  var rangeEl = document.getElementById('audit-range');
  var pageEl = document.getElementById('audit-page');
  var prevEl = document.getElementById('audit-prev');
  var nextEl = document.getElementById('audit-next');
  var PER = 50, page = 1, list = all;

  function render(){
    var pages = Math.max(1, Math.ceil(list.length / PER));
    page = Math.max(1, Math.min(page, pages));
    var from = (page - 1) * PER, to = Math.min(list.length, from + PER);
    all.forEach(function(tr){ tr.style.display = 'none'; });
    list.slice(from, to).forEach(function(tr){ tr.style.display = ''; });
    rangeEl.textContent = list.length
      ? 'Menampilkan ' + (from + 1) + '–' + to + ' dari ' + list.length + ' entri'
      : 'Tidak ada entri yang cocok';
    pageEl.textContent = page + ' / ' + pages;
    prevEl.disabled = page <= 1;
    nextEl.disabled = page >= pages;
    if (countEl) countEl.textContent = list.length + (list.length === all.length ? ' Entri' : ' Hasil');
  }

  sInput.addEventListener('input', function(){
    var q = sInput.value.trim().toLowerCase();
    list = !q ? all : all.filter(function(tr){
      return tr.textContent.toLowerCase().indexOf(q) > -1;
    });
    page = 1;
    render();
  });

  prevEl.addEventListener('click', function(){ page--; render(); });
  nextEl.addEventListener('click', function(){ page++; render(); });
  render();
})();
</script>
"""
    body = stat_cards + table_card + script
    return layout.shell(sess, app, "audit", t("nav.audit"),
                        "Semua aksi mutasi, akses kontrol, dan verifikasi IP klien", body, t)

def help_page(req, app, sess, qs, t):
    items = [
        ("Autentikasi", "Setiap login memakai kata sandi + kode 2FA (TOTP) atau "
                        "kode pemulihan sekali pakai. Sesi berlaku %d jam dan dapat dicabut."
                        % int(app.cfg.get("session_ttl", 43200) // 3600)),
        ("Peran pengguna", "<b>Viewer</b> hanya membaca. <b>Operator</b> dapat "
                           "mengelola layanan, berkas, aplikasi, dan cadangan. "
                           "<b>Admin</b> memegang seluruh kendali termasuk pengguna dan keamanan."),
        ("Konfirmasi destruktif", "Tindakan berisiko meminta Anda mengetik nama "
                                  "sasaran sebelum dijalankan."),
        ("Jejak audit", "Setiap aksi mutasi, percobaan login, dan penolakan izin "
                        "tercatat dengan waktu, pengguna, sasaran, dan alamat IP."),
        ("Batas memori", "Panel ini menargetkan pemakaian RAM di bawah 35 MB agar "
                         "tidak berebut dengan layanan lain di perangkat."),
    ]
    acc = ""
    for i, (h, b) in enumerate(items):
        acc += ('<details class="acc"%s><summary>%s</summary>'
                '<div class="acc-bd">%s</div></details>'
                % (" open" if i == 0 else "", C.e(h), b))
    sev = C.dl([
        ("Panel", layout.APP_NAME),
        ("Python", "%d.%d.%d" % __import__("sys").version_info[:3]),
        ("Pengguna terdaftar", str(app.users.count())),
        ("Sesi aktif", str(len(app.sessions.list()))),
    ])
    body = (C.panel("Panduan singkat", acc)
            + '<div class="mt16">' + C.panel("Informasi panel", sev) + "</div>")
    return layout.shell(sess, app, "help", t("nav.help"),
                        "Cara kerja panel dan model keamanannya", body, t)


# ---------- registri halaman ----------

PAGES = {
    "dash": dash,
    "audit": audit_page,
    "help": help_page,
    "svc": page_svc.render,
    "files": page_files.render,
    "logs": page_logs.render,
    "web": page_web.render,
    "db": page_db.render,
    "storage": page_storage.render,
    "network": page_network.render,
    "cron": page_cron.render,
    "users": page_users.render,
    "security": page_security.render,
    "maintenance": page_maintenance.render,
    "redis": page_redis.render,
    "terminal": page_terminal.render,
}

PAGE_PERMS = {
    "dash": perm.VIEW, "audit": perm.VIEW, "help": perm.VIEW,
    "users": perm.USER_MANAGE, "security": perm.SECURITY,
    "maintenance": perm.MAINT,
    "logs": perm.LOG_VIEW,
    "redis": perm.VIEW,
    "terminal": perm.SECURITY,
}
