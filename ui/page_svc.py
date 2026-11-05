"""Halaman Layanan (systemd): daftar, aksi lifecycle, log per unit."""
from ui import components as C
from ui import layout


JS = """
<script>
(function(){
  var T = window.SC;
  var body = document.getElementById('svc-rows');
  var search = document.getElementById('svc-q');
  var currentFilter = 'all';
  var all = [];

  function paint(){
    var q = (search.value || '').toLowerCase().trim();
    var filtered = all.filter(function(u){
      var matchQ = !q || (u.unit + ' ' + (u.desc || '')).toLowerCase().indexOf(q) > -1;
      if (!matchQ) return false;
      if (currentFilter === 'active') return u.active === 'active';
      if (currentFilter === 'inactive') return u.active !== 'active' && u.active !== 'failed';
      if (currentFilter === 'failed') return u.active === 'failed';
      return true;
    });

    var cnt = document.getElementById('svc-count');
    if (cnt) cnt.textContent = filtered.length + ' / ' + all.length + ' Layanan';

    // Update stats
    var tot = all.length;
    var actCount = all.filter(function(u){ return u.active === 'active'; }).length;
    var failCount = all.filter(function(u){ return u.active === 'failed'; }).length;
    var enCount = all.filter(function(u){ return u.enabled === 'enabled'; }).length;

    var sTot = document.getElementById('stat-svc-total');
    if (sTot) sTot.textContent = tot;
    var sAct = document.getElementById('stat-svc-active');
    if (sAct) sAct.textContent = actCount;
    var sFail = document.getElementById('stat-svc-failed');
    if (sFail) {
      sFail.textContent = failCount;
      sFail.className = 'vl ' + (failCount > 0 ? 'text-danger' : 'text-success');
    }
    var sEn = document.getElementById('stat-svc-enabled');
    if (sEn) sEn.textContent = enCount;

    if (!filtered.length){
      body.innerHTML = '<tr><td colspan="4" class="tc dim p24">Tidak ada layanan yang cocok dengan filter.</td></tr>';
      return;
    }

    body.innerHTML = filtered.map(function(u){
      var st = u.active === 'active' ? 'ok' : u.active === 'failed' ? 'dg' : 'nu';
      var en = u.enabled === 'enabled' ? 'pk' : 'nu';
      var isOn = u.active === 'active';
      return '<tr data-unit="' + T.esc(u.unit) + '">' +
        '<td><b>' + T.esc(u.unit) + '</b><div class="ds text-muted text-xs mt2">' + T.esc(u.desc || '') + '</div></td>' +
        '<td data-label="Status"><span class="tag ' + st + '">' + T.esc(u.active.toUpperCase()) + '</span></td>' +
        '<td data-label="Autostart"><span class="tag ' + en + '">' + T.esc((u.enabled || '—').toUpperCase()) + '</span></td>' +
        '<td class="act">' +
          (isOn
            ? '<button type="button" class="btn btn-sm btn-outline" data-a="restart">Muat Ulang</button> ' +
              '<button type="button" class="btn btn-sm btn-danger" data-a="stop">Hentikan</button>'
            : '<button type="button" class="btn btn-sm btn-primary" data-a="start">Jalankan</button>') +
          ' <button type="button" class="btn btn-sm btn-outline" data-a="logs">Log</button>' +
        '</td></tr>';
    }).join('');
  }

  function act(unit, action, btn){
    if (action === 'stop'){
      T.confirmDanger({
        title: 'Hentikan Layanan Systemd',
        body: 'Hentikan layanan <b>' + T.esc(unit) + '</b>?',
        ok: 'Hentikan',
        phrase: null
      }).then(function(ok){
        if (ok) send(unit, action, btn);
      });
      return;
    }
    send(unit, action, btn);
  }

  function send(unit, action, btn){
    T.busy(btn, true);
    T.api('/api/services', {method:'POST', body:{unit:unit, action:action}})
      .then(function(){
        T.toast('Berhasil', unit + ' · ' + action, 'ok');
        load();
      })
      .catch(function(e){ T.toast('Gagal', e.message, 'err'); })
      .then(function(){ T.busy(btn, false); });
  }

  function load(){
    T.api('/api/services').then(function(j){
      all = j.items || [];
      paint();
    }).catch(function(e){
      body.innerHTML = '<tr><td colspan="4" class="tc p24 text-danger">Gagal memuat: ' + T.esc(e.message) + '</td></tr>';
    });
  }

  body.addEventListener('click', function(ev){
    var b = ev.target.closest('button[data-a]');
    if (!b) return;
    var tr = b.closest('tr');
    var unit = tr.getAttribute('data-unit');
    var a = b.getAttribute('data-a');
    if (a === 'logs'){
      T.busy(b, true);
      T.api('/api/services/' + encodeURIComponent(unit) + '/logs?n=300')
        .then(function(j){
          T.modal({
            title: 'Journal Log · ' + unit,
            wide: true,
            body: '<pre class="code-editor mono text-xs p12" style="max-height:420px;overflow-y:auto;background:#0B0F17;color:#E2E8F0;border-radius:var(--radius-md);line-height:1.5;">' +
                  T.esc(j.log || '(tidak ada log)') + '</pre>'
          });
        })
        .catch(function(e){ T.toast('Gagal', e.message, 'err'); })
        .then(function(){ T.busy(b, false); });
      return;
    }
    act(unit, a, b);
  });

  document.addEventListener('click', function(e){
    var fltBtn = e.target.closest('[data-svc-filter]');
    if (fltBtn){
      currentFilter = fltBtn.getAttribute('data-svc-filter');
      document.querySelectorAll('[data-svc-filter]').forEach(function(b){
        b.className = 'chip text-xs' + (b === fltBtn ? ' selected' : '');
      });
      paint();
    }
  });

  search.addEventListener('input', paint);
  var relBtn = document.getElementById('svc-reload');
  if (relBtn) relBtn.addEventListener('click', load);

  load();
  setInterval(function(){ if (!document.hidden) load(); }, 15000);
})();
</script>
"""


def render(req, app, sess, qs, t):
    stat_cards = f"""
<div class="grid g4 mb16">
  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">TOTAL LAYANAN</span>
      <span class="metric-icon">{C.icon("svc", 15)}</span>
    </div>
    <span class="vl" id="stat-svc-total">0</span>
    <span class="ft">Systemd unit terdaftar</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">LAYANAN AKTIF</span>
      <span class="tag ok">RUNNING</span>
    </div>
    <span class="vl text-success" id="stat-svc-active">0</span>
    <span class="ft">Berjalan normal di latar belakang</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">STATUS GAGAL</span>
      <span class="tag ok" id="stat-svc-failed-tag">SISTEM</span>
    </div>
    <span class="vl text-success" id="stat-svc-failed">0</span>
    <span class="ft">Unit dengan status failed</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">AUTOSTART</span>
      <span class="tag in">ENABLED</span>
    </div>
    <span class="vl text-primary" id="stat-svc-enabled">0</span>
    <span class="ft">Otomatis berjalan saat boot STB</span>
  </div>
</div>
"""

    toolbar = f"""
<div class="card-header p16 border-b row space-between align-center flex-wrap gap8">
  <div class="row gap12 align-center">
    <h3 class="card-title text-sm m0">DAFTAR SYSTEMD SERVICES</h3>
    <span class="badge badge-success text-xs" id="svc-count">Memuat...</span>
  </div>
  <div class="row gap8 align-center flex-wrap">
    <div class="row gap6 align-center flex-wrap mr8">
      <button type="button" class="chip text-xs selected" data-svc-filter="all">Semua</button>
      <button type="button" class="chip text-xs" data-svc-filter="active">🟢 Aktif</button>
      <button type="button" class="chip text-xs" data-svc-filter="inactive">⚪ Nonaktif</button>
      <button type="button" class="chip text-xs" data-svc-filter="failed">🔴 Failed</button>
    </div>
    <div class="srch" style="max-width:240px;">
      <span class="ic">{C.icon("search", 13)}</span>
      <input type="text" id="svc-q" placeholder="Cari nama layanan..." class="form-input text-xs" style="padding-left:32px;height:32px;" />
    </div>
    <button type="button" class="btn btn-outline sm" id="svc-reload">{C.icon("refresh", 13)} Segarkan</button>
  </div>
</div>
"""

    table = (
        '<div class="table-responsive"><table class="data-table"><thead><tr>'
        '<th>NAMA LAYANAN &amp; DESKRIPSI</th><th>STATUS AKTIF</th><th>AUTOSTART BOOT</th><th class="act">AKSI TINDAKAN</th>'
        '</tr></thead><tbody id="svc-rows">'
        '<tr><td colspan="4" class="tc dim p24">Memuat data layanan systemd...</td></tr>'
        "</tbody></table></div>"
    )

    body = stat_cards + '<div class="card mb24 p0 overflow-hidden">' + toolbar + table + '</div>'
    return layout.shell(sess, app, "svc", "Service Manager",
                        "Manajemen lifecycle systemd services dan pembaca journalctl per unit",
                        body + JS, t)
