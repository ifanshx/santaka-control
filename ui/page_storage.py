"""Halaman Penyimpanan: disk, mount, SMART, dan fstab."""
from ui import components as C
from ui import layout

JS = """
<script>
(function(){
  var T = window.SC;
  var hostCfg = document.getElementById('st-cfg');
  var DATA_MOUNT = (hostCfg && hostCfg.getAttribute('data-data-mount')) || '/mnt/data';

  function gb(v){ return (Math.round((v || 0) * 10) / 10).toFixed(1); }

  function paintCards(ms){
    var byPoint = {};
    (ms || []).forEach(function(m){ byPoint[m.point] = m; });
    var data = byPoint[DATA_MOUNT];
    var root = byPoint['/'];
    var dTag = document.getElementById('st-data-tag');
    if (data){
      document.getElementById('st-data-total').innerHTML = gb(data.total_gb) + ' <small>GB</small>';
      document.getElementById('st-data-free').innerHTML = gb(data.free_gb) + ' <small>GB</small>';
      document.getElementById('st-data-path').textContent = (data.device || '') + ' · ' + data.point;
      var pctD = Math.round((data.used_gb / (data.total_gb || 1)) * 100);
      dTag.textContent = pctD + '% TERPAKAI';
      dTag.className = 'tag ' + (pctD >= 85 ? 'danger' : pctD >= 70 ? 'warn' : 'ok');
    } else {
      document.getElementById('st-data-total').innerHTML = '—';
      document.getElementById('st-data-path').textContent = DATA_MOUNT + ' belum terpasang';
      dTag.textContent = 'TIDAK ADA';
      dTag.className = 'tag nu';
    }
    if (root){
      var pctR = Math.round((root.used_gb / (root.total_gb || 1)) * 100);
      document.getElementById('st-root').innerHTML = gb(root.used_gb) + ' <small>/ ' + gb(root.total_gb) + ' GB</small>';
      document.getElementById('st-root-ft').textContent = 'Sisa ' + gb(root.free_gb) + ' GB pada partisi ' + root.point;
      var rTag = document.getElementById('st-root-tag');
      rTag.textContent = pctR + '%';
      rTag.className = 'tag ' + (pctR >= 85 ? 'danger' : pctR >= 70 ? 'warn' : 'ok');
    }
    document.getElementById('st-mount-count').innerHTML = (ms || []).length + ' <small>Mount</small>';
    document.getElementById('st-mount-list').textContent = (ms || []).map(function(m){ return m.point; }).join(', ') || '—';
  }

  function paint(j){
    var rows = j.disks || [];
    document.getElementById('st-rows').innerHTML = rows.length ? rows.map(function(d){
      var pad = d.depth ? 'padding-left:' + (d.depth * 20) + 'px;' : '';
      var nameDisplay = d.type === 'disk'
        ? '<b class="mono text-primary font-bold">' + T.esc(d.name) + '</b>'
        : '<b class="mono text-main font-bold">' + T.esc(d.name) + '</b>';

      return '<tr><td style="' + pad + '">' + nameDisplay + '</td>' +
        '<td data-label="Tipe"><span class="tag ' + (d.type==='disk'?'in':'nu') + '">' + T.esc(d.type.toUpperCase()) + '</span></td>' +
        '<td class="num mono" data-label="Ukuran">' + T.esc(d.size) + '</td>' +
        '<td class="mono text-xs" data-label="FS">' + T.esc(d.fstype || '—') + '</td>' +
        '<td class="mono text-xs" data-label="Mount">' + T.esc(d.mount || '—') + '</td>' +
        '<td class="act">' + (d.type === 'disk'
          ? '<button type="button" class="btn btn-sm btn-outline" data-smart="/dev/' + T.esc(d.name) + '">Uji SMART</button>'
          : '') + '</td></tr>';
    }).join('') : '<tr><td colspan="6" class="tc dim p24">Tidak ada perangkat disk terdeteksi.</td></tr>';

    var ms = j.mounts || [];
    paintCards(ms);

    document.getElementById('st-mnt').innerHTML = ms.length ? ms.map(function(m){
      var isData = m.point === DATA_MOUNT;
      var ptDisplay = isData
        ? '<b class="mono text-primary font-bold">' + T.esc(m.point) + '</b> <span class="badge badge-info text-xs">DATA</span>'
        : '<span class="mono text-main font-bold">' + T.esc(m.point) + '</span>';

      var pct = Math.round((m.used_gb / (m.used_gb + m.free_gb || 1)) * 100) || 0;
      var meterCls = pct >= 85 ? 'danger' : pct >= 70 ? 'warn' : 'ok';
      var meterHtml = '<div class="meter ' + meterCls + '"><i style="width:' + pct + '%"></i></div>';

      return '<tr><td>' + ptDisplay + '</td>' +
        '<td class="mono text-muted text-xs">' + T.esc(m.device) + '</td>' +
        '<td class="mono text-xs">' + T.esc(m.fstype) + '</td>' +
        '<td class="num mono text-xs">' + T.esc(m.used_gb) + ' GB</td>' +
        '<td class="num mono font-bold text-success">' + T.esc(m.free_gb) + ' GB</td>' +
        '<td style="min-width:120px;">' + meterHtml + '</td></tr>';
    }).join('') : '<tr><td colspan="6" class="tc dim p24">Tidak ada filesystem terpasang.</td></tr>';

    document.getElementById('st-fstab').textContent = j.fstab || '(kosong)';
  }

  function load(){
    fetch((T && T.url ? T.url('/api/storage') : '/api/storage'))
      .then(r => r.json())
      .then(function(res){ paint(res.data || res); })
      .catch(function(e){ if (T && T.toast) T.toast('Gagal', e.message, 'err'); });
  }

  document.addEventListener('click', function(ev){
    var b = ev.target.closest('[data-smart]');
    if (!b) return;
    var dev = b.getAttribute('data-smart');
    if (T && T.busy) T.busy(b, true);
    fetch((T && T.url ? T.url('/api/storage/action') : '/api/storage/action'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF': document.querySelector('meta[name="csrf"]')?.content || '' },
      body: JSON.stringify({op:'smart', device:dev})
    })
    .then(r => r.json())
    .then(function(j){
      var smart = j.data?.smart || j.smart || {};
      T.modal({
        title: 'Kesehatan Disk SMART · ' + dev,
        wide: true,
        body: '<div class="row gap8 align-center mb12"><span class="text-xs text-muted bold">STATUS KESEHATAN:</span><span class="badge badge-success">' + T.esc(smart.health || 'PASSED') + '</span></div>' +
              '<pre class="code-editor mono text-xs p12" style="max-height:440px;overflow-y:auto;">' + T.esc(smart.raw || '(laporan SMART kosong)') + '</pre>'
      });
    })
    .catch(function(e){ if (T && T.toast) T.toast('Gagal', e.message, 'err'); })
    .finally(function(){ if (T && T.busy) T.busy(b, false); });
  });

  var relBtn = document.getElementById('st-reload');
  if (relBtn) relBtn.addEventListener('click', load);
  load();
})();
</script>
"""


def render(req, app, sess, qs, t):
    data_mount = app.cfg.get("data_mount") or "/mnt/data"
    stat_cards = f"""
<div class="grid g4 mb16" id="st-cfg" data-data-mount="{C.e(data_mount)}">
  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">PENYIMPANAN DATA</span>
      <span class="tag ok" id="st-data-tag">—</span>
    </div>
    <span class="vl text-primary" id="st-data-total">—</span>
    <span class="ft" id="st-data-path">{C.e(data_mount)}</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">SISA BEBAS DATA</span>
      <span class="tag in">TERSEDIA</span>
    </div>
    <span class="vl text-success" id="st-data-free">—</span>
    <span class="ft">Kapasitas penyimpanan data</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">ROOT SYSTEM</span>
      <span class="tag ok" id="st-root-tag">—</span>
    </div>
    <span class="vl" id="st-root">—</span>
    <span class="ft" id="st-root-ft">Memuat kapasitas root...</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">MOUNT AKTIF</span>
      <span class="tag in">TERPANTAU</span>
    </div>
    <span class="vl" id="st-mount-count">—</span>
    <span class="ft" id="st-mount-list">Memuat mount...</span>
  </div>
</div>
"""

    table_disks = (
        '<div class="card mb24 p0 overflow-hidden">'
        '<div class="card-header p16 border-b row space-between align-center flex-wrap gap8">'
        '<div class="row gap8 align-center">'
        f'<span class="metric-icon">{C.icon("disk", 15)}</span>'
        '<h3 class="card-title text-sm m0">DAFTAR PERANGKAT DISK &amp; PARTISI (lsblk)</h3>'
        '</div>'
        f'<button type="button" class="btn btn-outline sm" id="st-reload">{C.icon("refresh", 13)} Segarkan</button>'
        '</div>'
        '<div class="table-responsive"><table class="data-table"><thead><tr>'
        '<th>NAMA PERANGKAT</th><th>TIPE</th><th class="num">KAPASITAS</th><th>FILESYSTEM</th><th>TITIK MOUNT</th><th class="act">AKSI TINDAKAN</th>'
        '</tr></thead><tbody id="st-rows">'
        '<tr><td colspan="6" class="tc dim p24">Memuat daftar disk...</td></tr>'
        '</tbody></table></div></div>'
    )

    table_mounts = (
        '<div class="card mb24 p0 overflow-hidden">'
        '<div class="card-header p16 border-b">'
        '<h3 class="card-title text-sm m0">PARTISI FILESYSTEM AKTIF (df -h)</h3>'
        '</div>'
        '<div class="table-responsive"><table class="data-table"><thead><tr>'
        '<th>TITIK MOUNT</th><th>DEVICE</th><th>FILESYSTEM</th><th class="num">TERPAKAI</th><th class="num">SISA BEBAS</th><th>PENGGUNAAN</th>'
        '</tr></thead><tbody id="st-mnt">'
        '<tr><td colspan="6" class="tc dim p24">Memuat mount aktif...</td></tr>'
        '</tbody></table></div></div>'
    )

    fstab_card = (
        '<div class="card p0 overflow-hidden">'
        '<div class="card-header p16 border-b">'
        '<h3 class="card-title text-sm m0">KONFIGURASI MOUNT PERMANEN (/etc/fstab)</h3>'
        '</div>'
        '<pre class="code-editor mono text-xs p16 m0" id="st-fstab" '
        'style="line-height:1.6;overflow-x:auto;">(memuat fstab...)</pre></div>'
    )

    body = stat_cards + table_disks + table_mounts + fstab_card
    return layout.shell(sess, app, "storage", "Penyimpanan",
                        "Kesehatan disk SMART, partisi penyimpanan, dan mount permanen",
                        body + JS, t)
