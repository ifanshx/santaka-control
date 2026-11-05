"""Halaman Manajemen Basis Data: kelola MariaDB, ekspor SQL, dan akses phpMyAdmin."""
from lib import dbops
from ui import components as C
from ui import layout


def render(req, app, sess, qs, t):
    csrf = req.csrf_token(sess)
    base = layout.BASE_PATH
    pma = str(app.cfg.get("phpmyadmin_url") or "").strip()
    pma_link = (
        f'<a href="{C.e(pma)}" target="_blank" rel="noopener" '
        f'class="btn btn-outline sm" title="Buka phpMyAdmin di tab baru">'
        f'{C.icon("db", 13)} phpMyAdmin ↗</a>' if pma else ""
    )
    dump_dir = dbops.DUMP_DIR

    html = f"""
<!-- KARTU STATUS MESIN DATABASE (MARIADB) -->
<div class="grid g4 mb16">
  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">TOTAL DATABASE</span>
      <span class="metric-icon">{C.icon("db", 15)}</span>
    </div>
    <span class="vl" id="stat-total-db">0</span>
    <span class="ft">Basis data yang terdeteksi di server ini</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">TOTAL UKURAN DATA</span>
      <span class="tag ok" id="stat-size-badge">AKTIF</span>
    </div>
    <span class="vl text-primary" id="stat-total-size">0 <small>MB</small></span>
    <span class="ft">Kapasitas tabel di disk</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">MESIN DATABASE</span>
      <span class="tag ok" id="stat-engine-tag">MEMERIKSA</span>
    </div>
    <span class="vl" style="font-size:22px;" id="stat-engine">—</span>
    <span class="ft">Mesin yang tersedia untuk dikelola</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">DEFAULT CHARSET</span>
      <span class="tag ok">UTF8MB4</span>
    </div>
    <span class="vl text-success">utf8mb4</span>
    <span class="ft">Collation: utf8mb4_unicode_ci</span>
  </div>
</div>

<!-- TABEL DATABASE AKTIF -->
<div class="card mb24 p0 overflow-hidden">
  <div class="card-header p16 border-b row space-between align-center flex-wrap gap8">
    <div class="row gap12 align-center">
      <h3 class="card-title text-sm m0">DAFTAR DATABASE USER &amp; SISTEM</h3>
      <span class="badge badge-success text-xs" id="db-count">Memuat...</span>
    </div>
    <div class="row gap8 align-center flex-wrap">
      <div class="srch" style="max-width: 230px;">
        <span class="ic">{C.icon("search", 13)}</span>
        <input type="text" id="db-search" placeholder="Cari nama database..." class="form-input text-xs" style="padding-left: 32px; height: 32px;" />
      </div>
      {pma_link}
      <button type="button" class="btn btn-outline sm" id="btn-db-refresh" title="Muat ulang daftar">{C.icon("refresh", 13)} Segarkan</button>
      <button type="button" class="btn btn-primary sm" id="btn-db-add">{C.icon("plus", 13)} Tambah Database</button>
    </div>
  </div>
  <div class="table-responsive">
    <table class="data-table" id="table-databases">
      <thead>
        <tr>
          <th>NAMA DATABASE</th>
          <th>UKURAN DATA</th>
          <th>CHARSET DEFAULT</th>
          <th>STATUS SISTEM</th>
          <th style="text-align: right;">AKSI TINDAKAN</th>
        </tr>
      </thead>
      <tbody id="db-tbody">
        <tr><td colspan="5" class="text-center p24 text-muted">Memuat daftar database...</td></tr>
      </tbody>
    </table>
  </div>
</div>

<!-- TABEL RIWAYAT BACKUP DUMP SQL -->
<div class="card mb24 p0 overflow-hidden">
  <div class="card-header p16 border-b row space-between align-center flex-wrap gap8">
    <div class="row gap8 align-center">
      <span class="metric-icon">{C.icon("backup", 15)}</span>
      <h3 class="card-title text-sm m0">ARSIP BACKUP DUMP SQL ({C.e(dump_dir)})</h3>
    </div>
    <span class="text-xs text-muted" id="dumps-count">0 Arsip</span>
  </div>
  <div class="table-responsive">
    <table class="data-table" id="table-dumps">
      <thead>
        <tr>
          <th>NAMA BERKAS ARSIP (.SQL.GZ)</th>
          <th>UKURAN ARSIP</th>
          <th>WAKTU PEMBUATAN</th>
          <th style="text-align: right;">AKSI UNDUH / KELOLA</th>
        </tr>
      </thead>
      <tbody id="dumps-tbody">
        <tr><td colspan="4" class="text-center p24 text-muted">Memuat arsip dump...</td></tr>
      </tbody>
    </table>
  </div>
</div>

<!-- MODAL TAMBAH DATABASE BARU -->
<div class="modal-overlay hidden" id="modal-add-db">
  <div class="modal-box card" style="max-width: 520px;">
    <div class="modal-header row space-between align-center border-b p16">
      <div class="row gap8 align-center">
        <span class="metric-icon">{C.icon("db", 15)}</span>
        <h3 class="card-title text-sm m0">Buat Database MariaDB Baru</h3>
      </div>
      <button type="button" class="btn-close" id="btn-close-add-db">&times;</button>
    </div>
    <div class="modal-body p16">
      <div class="form-group mb16">
        <label class="form-label">Nama Database *</label>
        <input type="text" id="add-dbname" class="form-input mono" placeholder="contoh: santaka_app" />
        <span class="form-help text-xs text-muted">Hanya huruf kecil, angka, dan garis bawah (_).</span>
      </div>

      <div class="form-group mb16">
        <label class="form-label">Username Khusus Database (Opsional)</label>
        <input type="text" id="add-dbuser" class="form-input mono" placeholder="contoh: santaka_user" />
        <span class="form-help text-xs text-muted">Akan diberi izin penuh (ALL PRIVILEGES) ke database ini.</span>
      </div>

      <div class="form-group mb16">
        <label class="form-label">Password User Database (Opsional)</label>
        <input type="password" id="add-dbpass" class="form-input mono" placeholder="Minimal 8 karakter" />
      </div>
    </div>
    <div class="modal-footer row justify-end gap8 border-t p16">
      <button type="button" class="btn btn-outline" id="btn-cancel-add-db">Batal</button>
      <button type="button" class="btn btn-primary" id="btn-save-db">Buat Database Sekarang</button>
    </div>
  </div>
</div>

<script>
(function(){{
var allDbList = [];
var allDumpsList = [];

function openAddModal() {{
  document.getElementById('add-dbname').value = '';
  document.getElementById('add-dbuser').value = '';
  document.getElementById('add-dbpass').value = '';
  document.getElementById('modal-add-db').classList.remove('hidden');
  document.getElementById('add-dbname').focus();
}}

function closeAddModal() {{
  document.getElementById('modal-add-db').classList.add('hidden');
}}

function renderDbTable(list) {{
  var tbody = document.getElementById('db-tbody');
  if (list.length === 0) {{
    tbody.innerHTML = '<tr><td colspan="5" class="text-center p24 text-muted">Tidak ada database yang cocok dengan pencarian.</td></tr>';
    return;
  }}
  var html = '';
  list.forEach(function(d) {{
    var isSys = d.system;
    var badge = isSys
      ? '<span class="badge badge-warning">SISTEM (INTERNAL)</span>'
      : '<span class="badge badge-success"><span class="pulse-dot green"></span> USER AKTIF</span>';
      
    var actionBtns = isSys
      ? '<span class="text-xs text-muted">Dilindungi sistem</span>'
      : '<button type="button" class="btn btn-sm btn-outline" data-dump="' + escapeHtml(d.name) + '" title="Ekspor dump .sql.gz ke folder backup">Dump Backup</button> ' +
        '<button type="button" class="btn btn-sm btn-danger" data-drop="' + escapeHtml(d.name) + '" title="Hapus database permanen">Hapus</button>';

    html += '<tr>' +
      '<td><div class="row gap6 align-center"><span class="mono font-bold text-main">' + escapeHtml(d.name) + '</span></div></td>' +
      '<td><span class="mono text-muted text-xs">' + escapeHtml(d.size) + '</span></td>' +
      '<td><span class="mono text-xs text-success">utf8mb4</span></td>' +
      '<td>' + badge + '</td>' +
      '<td style="text-align: right;" class="row justify-end gap6 align-center flex-wrap">' + actionBtns + '</td>' +
    '</tr>';
  }});
  tbody.innerHTML = html;
}}

function renderDumpsTable(dumps) {{
  var dumpsBody = document.getElementById('dumps-tbody');
  var countEl = document.getElementById('dumps-count');
  if (countEl) countEl.textContent = dumps.length + ' Arsip Backup';
  
  if (dumps.length === 0) {{
    dumpsBody.innerHTML = '<tr><td colspan="4" class="text-center p24 text-muted">Belum ada berkas dump SQL di {C.e(dump_dir)}.</td></tr>';
    return;
  }}
  var dhtml = '';
  dumps.forEach(function(du) {{
    var sizeText = du.size > 1048576
      ? (du.size / 1048576).toFixed(2) + ' MB'
      : Math.round(du.size / 1024) + ' KB';
    var dt = new Date(du.mtime * 1000).toLocaleString('id-ID', {{
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    }});
    dhtml += '<tr>' +
      '<td><div class="row gap6 align-center"><b class="mono text-sm text-primary">' + escapeHtml(du.name) + '</b></div></td>' +
      '<td><span class="mono text-muted text-xs">' + sizeText + '</span></td>' +
      '<td><span class="text-xs text-muted">' + dt + '</span></td>' +
      '<td style="text-align: right;" class="row justify-end gap6 align-center">' +
        '<a href="{base}/api/files/download?path=' + encodeURIComponent(du.path) + '" class="btn btn-sm btn-outline" title="Unduh berkas .sql.gz">Unduh ↗</a>' +
        '<button type="button" class="btn btn-sm btn-danger" data-deldump="' + escapeHtml(du.name) + '" title="Hapus berkas arsip">Hapus</button>' +
      '</td>' +
    '</tr>';
  }});
  dumpsBody.innerHTML = dhtml;
}}

function loadDatabases() {{
  var tbody = document.getElementById('db-tbody');
  tbody.innerHTML = '<tr><td colspan="5" class="text-center p24 text-muted">Memuat data MariaDB...</td></tr>';

  fetch('{base}/api/db')
    .then(r => r.json())
    .then(res => {{
      if (!res.ok) {{
        tbody.innerHTML = '<tr><td colspan="5" class="text-center p24 text-danger">Gagal: ' + res.error + '</td></tr>';
        return;
      }}
      var dataObj = res.data || res;
      allDbList = dataObj.mysql || [];
      document.getElementById('db-count').textContent = allDbList.length + ' Database';

      // Update stat cards
      var totalDb = allDbList.length;
      var totalMb = 0;
      allDbList.forEach(function(d) {{
        var num = parseFloat(d.size) || 0;
        totalMb += num;
      }});
      document.getElementById('stat-total-db').textContent = totalDb;
      var engines = [];
      if (!(dataObj.errors || {{}}).mysql) engines.push('MariaDB');
      if (!(dataObj.errors || {{}}).postgres) engines.push('PostgreSQL');
      var engEl = document.getElementById('stat-engine');
      var engTag = document.getElementById('stat-engine-tag');
      if (engEl) engEl.textContent = engines.join(' + ') || '—';
      if (engTag) {{
        engTag.textContent = engines.length ? 'TERSEDIA' : 'TIDAK ADA';
        engTag.className = 'tag ' + (engines.length ? 'ok' : 'warn');
      }}
      document.getElementById('stat-total-size').innerHTML = totalMb.toFixed(1) + ' <small>MB</small>';

      renderDbTable(allDbList);

      allDumpsList = dataObj.dumps || [];
      renderDumpsTable(allDumpsList);
    }})
    .catch(err => {{
      tbody.innerHTML = '<tr><td colspan="5" class="text-center p24 text-danger">Error: ' + err + '</td></tr>';
    }});
}}

function filterDatabases() {{
  var q = (document.getElementById('db-search').value || '').trim().toLowerCase();
  var filtered = allDbList.filter(function(d) {{
    return !q || (d.name || '').toLowerCase().indexOf(q) > -1;
  }});
  renderDbTable(filtered);
}}

function submitAddDb() {{
  var name = document.getElementById('add-dbname').value.trim().toLowerCase();
  var user = document.getElementById('add-dbuser').value.trim();
  var pass = document.getElementById('add-dbpass').value.trim();

  if (!name) {{
    if (window.SC && window.SC.toast) window.SC.toast('Validasi', 'Nama database wajib diisi!', 'warn');
    else alert('Nama database wajib diisi!');
    return;
  }}

  var btn = document.getElementById('btn-save-db');
  btn.disabled = true;

  fetch('{base}/api/db/mysql/create', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-CSRF': '{csrf}' }},
    body: JSON.stringify({{ name: name, user: user || null, pass: pass || null }})
  }})
  .then(r => r.json())
  .then(res => {{
    if (res.ok) {{
      closeAddModal();
      if (window.SC && window.SC.toast) window.SC.toast('Berhasil', 'Database ' + name + ' berhasil dibuat!', 'ok');
      loadDatabases();
    }} else {{
      if (window.SC && window.SC.toast) window.SC.toast('Gagal', res.error || 'Gagal membuat database', 'err');
      else alert('Gagal: ' + res.error);
    }}
  }})
  .catch(err => {{
    if (window.SC && window.SC.toast) window.SC.toast('Error', String(err), 'err');
  }})
  .finally(() => btn.disabled = false);
}}

function dumpDb(name) {{
  if (window.SC && window.SC.toast) window.SC.toast('Mengekspor', 'Membuat dump SQL untuk ' + name + '...', 'info');
  fetch('{base}/api/db/mysql/dump', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-CSRF': '{csrf}' }},
    body: JSON.stringify({{ name: name }})
  }})
  .then(r => r.json())
  .then(res => {{
    if (res.ok) {{
      if (window.SC && window.SC.toast) window.SC.toast('Dump Selesai', 'Backup ' + name + ' tersimpan di {C.e(dump_dir)}', 'ok');
      loadDatabases();
    }} else {{
      if (window.SC && window.SC.toast) window.SC.toast('Gagal Dump', res.error || 'Gagal membuat dump', 'err');
    }}
  }})
  .catch(err => {{
    if (window.SC && window.SC.toast) window.SC.toast('Error', String(err), 'err');
  }});
}}

function dropDb(name) {{
  if (window.SC && window.SC.confirmDanger) {{
    window.SC.confirmDanger({{
      title: 'Hapus Database MariaDB',
      body: 'PERINGATAN: Seluruh tabel dan data di dalam database <b>' + escapeHtml(name) + '</b> akan dihapus permanen!',
      ok: 'Hapus Database',
      phrase: name
    }}).then(function(ok) {{
      if (ok) doDropDb(name);
    }});
  }} else {{
    if (confirm('Yakin ingin menghapus database ' + name + '?')) doDropDb(name);
  }}
}}

function doDropDb(name) {{
  fetch('{base}/api/db/mysql/drop', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-CSRF': '{csrf}' }},
    body: JSON.stringify({{ name: name }})
  }})
  .then(r => r.json())
  .then(res => {{
    if (res.ok) {{
      if (window.SC && window.SC.toast) window.SC.toast('Dihapus', 'Database ' + name + ' berhasil dihapus', 'ok');
      loadDatabases();
    }} else {{
      if (window.SC && window.SC.toast) window.SC.toast('Gagal Hapus', res.error || 'Gagal menghapus database', 'err');
    }}
  }})
  .catch(err => {{
    if (window.SC && window.SC.toast) window.SC.toast('Error', String(err), 'err');
  }});
}}

function deleteDump(name) {{
  if (window.SC && window.SC.confirmDanger) {{
    window.SC.confirmDanger({{
      title: 'Hapus Berkas Dump',
      body: 'Hapus file arsip backup <b>' + escapeHtml(name) + '</b> dari harddisk?',
      ok: 'Hapus Berkas',
      phrase: null
    }}).then(function(ok) {{
      if (ok) doDeleteDump(name);
    }});
  }} else {{
    if (confirm('Hapus file ' + name + '?')) doDeleteDump(name);
  }}
}}

function doDeleteDump(name) {{
  fetch('{base}/api/db/mysql/dump/delete', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-CSRF': '{csrf}' }},
    body: JSON.stringify({{ name: name }})
  }})
  .then(r => r.json())
  .then(res => {{
    if (res.ok) {{
      if (window.SC && window.SC.toast) window.SC.toast('Dihapus', 'Berkas dump ' + name + ' dihapus', 'ok');
      loadDatabases();
    }} else {{
      if (window.SC && window.SC.toast) window.SC.toast('Gagal', res.error, 'err');
    }}
  }})
  .catch(err => {{
    if (window.SC && window.SC.toast) window.SC.toast('Error', String(err), 'err');
  }});
}}

function escapeHtml(text) {{
  var map = {{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }};
  return String(text || '').replace(/[&<>"']/g, function(m) {{ return map[m]; }});
}}

// Helper bind click listener by ID
function bind(id, fn) {{
  var el = document.getElementById(id);
  if (el) el.addEventListener('click', fn);
}}

bind('btn-db-refresh', loadDatabases);
bind('btn-db-add', openAddModal);
bind('btn-close-add-db', closeAddModal);
bind('btn-cancel-add-db', closeAddModal);
bind('btn-save-db', submitAddDb);

var searchEl = document.getElementById('db-search');
if (searchEl) searchEl.addEventListener('input', filterDatabases);

// Event delegation for database table and dump table
document.addEventListener('click', function(e) {{
  var dumpBtn = e.target.closest('[data-dump]');
  if (dumpBtn) {{
    dumpDb(dumpBtn.getAttribute('data-dump'));
    return;
  }}
  var dropBtn = e.target.closest('[data-drop]');
  if (dropBtn) {{
    dropDb(dropBtn.getAttribute('data-drop'));
    return;
  }}
  var delDumpBtn = e.target.closest('[data-deldump]');
  if (delDumpBtn) {{
    deleteDump(delDumpBtn.getAttribute('data-deldump'));
    return;
  }}
}});

loadDatabases();
}})();
</script>
"""
    return layout.shell(sess, app, "db", "Databases (MySQL)",
                        "Pusat kelola database, ekspor SQL, dan phpMyAdmin",
                        html, t)
