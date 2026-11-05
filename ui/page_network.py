"""Halaman Jaringan: antarmuka, port mendengarkan, firewall, fail2ban."""
from ui import components as C
from ui import layout

JS = """
<script>
(function(){
  var T = window.SC;
  var allPortsList = [];

  function paint(j){
    var ifs = j.interfaces || [];
    document.getElementById('nw-ifs').innerHTML = ifs.length ? ifs.map(function(i){
      var up = String(i.state || '').toLowerCase() === 'up';
      return '<tr><td class="mono font-bold">' + T.esc(i.name) + '</td>' +
        '<td data-label="Status"><span class="badge ' + (up?'badge-success':'badge-warning') + '"><span class="pulse-dot ' + (up?'green':'gray') + '"></span> ' + T.esc(i.state.toUpperCase()) + '</span></td>' +
        '<td class="mono font-bold text-primary" data-label="Alamat IP">' + T.esc((i.addrs || []).join(', ') || '—') + '</td></tr>';
    }).join('') : '<tr><td colspan="3" class="tc dim p24">Tidak ada antarmuka jaringan terdeteksi.</td></tr>';

    allPortsList = j.listening || [];
    renderPortsTable(allPortsList);

    var primary = null;
    ifs.forEach(function(i){
      if (!primary && String(i.state || '').toLowerCase() === 'up' && (i.addrs || []).length) primary = i;
    });
    var ipEl = document.getElementById('nw-primary-ip');
    var ifEl = document.getElementById('nw-primary-if');
    var addrs = primary ? primary.addrs : [];
    var ip4 = addrs.filter(function(a){ return a.indexOf(':') === -1; });
    if (ipEl) ipEl.textContent = ip4[0] || addrs[0] || '—';
    if (ifEl) ifEl.textContent = primary ? primary.name + ' · UP' : 'TIDAK ADA LINK';

    var n = (j.listening || []).length;
    var pEl = document.getElementById('stat-ports-open');
    if (pEl) pEl.innerHTML = n + ' <small>Port</small>';

    var rules = (j.rules || '').trim();
    var pill = document.getElementById('nw-fw');
    var val = document.getElementById('nw-fw-val');
    if (pill) {
      pill.textContent = rules ? 'IPTABLES AKTIF' : 'TIDAK TERDETEKSI';
      pill.className = 'tag ' + (rules ? 'ok' : 'warn');
    }
    if (val) val.textContent = rules ? 'Aktif' : '—';

    var f = j.fail2ban || {};
    var fTag = document.getElementById('nw-f2b-tag');
    var fVal = document.getElementById('nw-f2b-val');
    if (fTag) {
      fTag.textContent = f.available ? 'AKTIF' : 'NONAKTIF';
      fTag.className = 'tag ' + (f.available ? 'ok' : 'warn');
    }
    if (fVal) fVal.textContent = f.available
      ? (f.jails || []).length + ' Jail' : 'Nonaktif';
    if (!f.available){
      document.getElementById('nw-f2b').innerHTML =
        '<div class="p16 text-muted text-xs">Layanan fail2ban tidak aktif di sistem ini. Proteksi port tetap bergantung pada firewall host.</div>';
      return;
    }
    var html = '';
    (f.jails || []).forEach(function(name){
      var d = (f.detail || {})[name] || {banned:[], current:'0', total:'0'};
      html += '<div class="card mb8 p12">' +
        '<div class="row between mb8"><b class="mono font-bold">' + T.esc(name) + '</b>' +
        '<span class="badge ' + (parseInt(d.current,10)>0?'badge-danger':'badge-success') + '">' +
        T.esc(d.current) + ' diblokir · total ' + T.esc(d.total) + '</span></div>';
      if ((d.banned || []).length){
        html += (d.banned || []).map(function(ip){
          return '<div class="row space-between align-center p6 border-b"><span class="mono text-xs">' + T.esc(ip) + '</span>' +
            '<button type="button" class="btn btn-sm btn-outline" data-unban="' + T.esc(ip) + '" data-jail="' + T.esc(name) + '">Buka blokir</button></div>';
        }).join('');
      } else {
        html += '<div class="text-xs text-muted">Tidak ada alamat IP yang sedang diblokir.</div>';
      }
      html += '</div>';
    });
    document.getElementById('nw-f2b').innerHTML = html || '<div class="p16 text-muted text-xs">Tidak ada jail aktif.</div>';
  }

  function renderPortsTable(list){
    var tbody = document.getElementById('nw-ls');
    var countEl = document.getElementById('ports-count');
    if (countEl) countEl.textContent = list.length + ' Port Mendengarkan';
    if (!list.length){
      tbody.innerHTML = '<tr><td colspan="2" class="tc dim p24">Tidak ada port yang cocok.</td></tr>';
      return;
    }
    tbody.innerHTML = list.map(function(p){
      var host = p.local.split(':')[0];
      var isLocal = host.indexOf('127.') === 0 || host === '::1' || host === '[::1]';
      var scopeBadge = isLocal
        ? '<span class="badge badge-info text-xs">LOOPBACK ONLY</span>'
        : '<span class="badge badge-success text-xs">PUBLIK / LAN</span>';

      return '<tr>' +
        '<td><div class="row gap8 align-center"><b class="mono font-bold text-main">' + T.esc(p.local) + '</b> ' + scopeBadge + '</div></td>' +
        '<td><span class="mono text-primary font-bold">' + T.esc(p.proc || '—') + '</span></td>' +
      '</tr>';
    }).join('');
  }

  function filterPorts(){
    var q = (document.getElementById('port-search').value || '').trim().toLowerCase();
    var filtered = allPortsList.filter(function(p){
      return !q || (p.local + ' ' + (p.proc || '')).toLowerCase().indexOf(q) > -1;
    });
    renderPortsTable(filtered);
  }

  function load(){
    fetch((T && T.url ? T.url('/api/network?rules=1') : '/api/network?rules=1'))
      .then(r => r.json())
      .then(function(res){ paint(res.data || res); })
      .catch(function(e){ if (T && T.toast) T.toast('Gagal', e.message, 'err'); });
  }

  document.addEventListener('click', function(ev){
    var b = ev.target.closest('[data-unban]');
    if (!b) return;
    var ip = b.getAttribute('data-unban'), jail = b.getAttribute('data-jail');
    T.confirmDanger({
      title: 'Buka Blokir IP',
      body: 'Buka blokir IP <b>' + T.esc(ip) + '</b> dari jail <b>' + T.esc(jail) + '</b>?',
      ok: 'Buka Blokir'
    }).then(function(ok){
      if (!ok) return;
      if (T && T.busy) T.busy(b, true);
      fetch((T && T.url ? T.url('/api/network/action') : '/api/network/action'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF': document.querySelector('meta[name="csrf"]')?.content || '' },
        body: JSON.stringify({op:'unban', jail:jail, ip:ip})
      })
      .then(r => r.json())
      .then(function(j){
        if (T && T.toast) T.toast('Berhasil', j.message || 'Blokir dibuka', 'ok');
        load();
      })
      .catch(function(e){ if (T && T.toast) T.toast('Gagal', e.message, 'err'); })
      .finally(function(){ if (T && T.busy) T.busy(b, false); });
    });
  });

  var relBtn = document.getElementById('nw-reload');
  if (relBtn) relBtn.addEventListener('click', load);

  var pSearch = document.getElementById('port-search');
  if (pSearch) pSearch.addEventListener('input', filterPorts);

  load();
})();
</script>
"""


def render(req, app, sess, qs, t):
    stat_cards = """
<div class="grid g4 mb16">
  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">IP SERVER LOKAL</span>
      <span class="tag in" id="nw-primary-if">MEMUAT</span>
    </div>
    <span class="vl text-primary font-mono font-bold" style="font-size:22px;" id="nw-primary-ip">—</span>
    <span class="ft">Alamat antarmuka jaringan utama</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">PORT MENDENGARKAN</span>
      <span class="tag in">LISTENING</span>
    </div>
    <span class="vl" id="stat-ports-open">— <small>Port</small></span>
    <span class="ft">Socket TCP/UDP yang menerima koneksi</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">STATUS FIREWALL</span>
      <span class="tag ok" id="nw-fw">MEMERIKSA</span>
    </div>
    <span class="vl text-success" style="font-size:22px;" id="nw-fw-val">—</span>
    <span class="ft">Filter paket Linux kernel</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">FAIL2BAN</span>
      <span class="tag in" id="nw-f2b-tag">MEMERIKSA</span>
    </div>
    <span class="vl" style="font-size:22px;" id="nw-f2b-val">—</span>
    <span class="ft">Blokir otomatis percobaan brute force</span>
  </div>
</div>
"""

    table_ifs = (
        '<div class="card mb24 p0 overflow-hidden">'
        '<div class="card-header p16 border-b row space-between align-center flex-wrap gap8">'
        '<div class="row gap8 align-center">'
        f'<span class="metric-icon">{C.icon("net", 15)}</span>'
        '<h3 class="card-title text-sm m0">ANTARMUKA JARINGAN (NETWORK INTERFACES)</h3>'
        '</div>'
        f'<button type="button" class="btn btn-outline sm" id="nw-reload">{C.icon("refresh", 13)} Segarkan</button>'
        '</div>'
        '<div class="table-responsive"><table class="data-table"><thead><tr>'
        '<th>NAMA INTERFACE</th><th>STATUS OPERASIONAL</th><th>ALAMAT IP / CIDR</th>'
        '</tr></thead><tbody id="nw-ifs">'
        '<tr><td colspan="3" class="tc dim p24">Memuat data antarmuka jaringan...</td></tr>'
        '</tbody></table></div></div>'
    )

    table_ports = f"""
<div class="card mb24 p0 overflow-hidden">
  <div class="card-header p16 border-b row space-between align-center flex-wrap gap8">
    <div class="row gap12 align-center">
      <h3 class="card-title text-sm m0">PORT MENDENGARKAN (LISTENING SOCKETS)</h3>
      <span class="badge badge-success text-xs" id="ports-count">Memuat...</span>
    </div>
    <div class="srch" style="max-width:240px;">
      <span class="ic">{C.icon("search", 13)}</span>
      <input type="text" id="port-search" placeholder="Cari nomor port atau proses..." class="form-input text-xs" style="padding-left:32px;height:32px;" />
    </div>
  </div>
  <div class="table-responsive"><table class="data-table"><thead><tr>
    <th>ALAMAT LOCAL &amp; NOMOR PORT</th><th>NAMA PROSES / DAEMON</th>
  </tr></thead><tbody id="nw-ls">
    <tr><td colspan="2" class="tc dim p24">Memuat port mendengarkan...</td></tr>
  </tbody></table></div>
</div>
"""

    fail2ban_card = (
        '<div class="card p0 overflow-hidden">'
        '<div class="card-header p16 border-b">'
        '<h3 class="card-title text-sm m0">KEAMANAN INTRUSI (FAIL2BAN JAILS)</h3>'
        '</div>'
        '<div id="nw-f2b" class="p12">Memuat status fail2ban...</div>'
        '</div>'
    )

    body = stat_cards + table_ifs + table_ports + fail2ban_card
    return layout.shell(sess, app, "network", "Jaringan",
                        "Antarmuka jaringan, port yang mendengarkan, dan status firewall",
                        body + JS, t)
