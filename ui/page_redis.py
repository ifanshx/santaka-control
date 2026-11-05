"""Halaman Manajemen Redis Cache: pemantau memori, keys explorer, ping benchmark, dan aksi flush."""
from ui import components as C
from ui import layout


def render(req, app, sess, qs, t):
    csrf = req.csrf_token(sess)
    base = layout.BASE_PATH

    html = f"""
<!-- KARTU METRIK REDIS -->
<div class="grid g4 mb16">
  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">STATUS LAYANAN</span>
      <span class="tag ok">ONLINE</span>
    </div>
    <div class="vl row gap8 align-center" id="rd-status">
      <span>6379</span> <small class="text-success font-mono font-bold">PORT AKTIF</small>
    </div>
    <span class="ft" id="rd-ver">Redis Server v7.0</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">RAM DIGUNAKAN (MAX 64 MB)</span>
      <span class="tag ok" id="rd-policy">allkeys-lru</span>
    </div>
    <span class="vl text-primary" id="rd-mem">0 <small>MB</small></span>
    <div class="meter ok mt8" id="rd-mem-meter"><i id="rd-mem-bar" style="width: 2%;"></i></div>
    <span class="ft mt6" id="rd-mem-sub">Batas memori STB 64 MB</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">TOTAL CACHE KEYS (DB0)</span>
      <span class="metric-icon">{C.icon("redis", 15)}</span>
    </div>
    <span class="vl" id="rd-keys">0</span>
    <span class="ft" id="rd-clients">Clients aktif: 0</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">CACHE HIT RATE</span>
      <span class="tag ok">OPTIMAL</span>
    </div>
    <span class="vl text-success" id="rd-hit">100%</span>
    <span class="ft" id="rd-ops">Throughput: 0 ops/detik</span>
  </div>
</div>

<!-- TABEL PENJELAJAH KUNCI CACHE (KEY EXPLORER) -->
<div class="card mb24 p0 overflow-hidden">
  <div class="card-header p16 border-b row space-between align-center flex-wrap gap8">
    <div class="row gap12 align-center">
      <h3 class="card-title text-sm m0">PENJELAJAH KUNCI CACHE (REDIS KEY EXPLORER)</h3>
      <span class="badge badge-success text-xs" id="keys-count">Memuat...</span>
    </div>
    <div class="row gap8 align-center flex-wrap">
      <div class="srch" style="max-width: 230px;">
        <span class="ic">{C.icon("search", 13)}</span>
        <input type="text" id="key-search" placeholder="Cari nama key..." class="form-input text-xs" style="padding-left: 32px; height: 32px;" />
      </div>
      <button type="button" class="btn btn-outline sm" id="btn-rd-ping" title="Uji latensi roundtrip ke socket Redis">{C.icon("check", 13)} Ping Test</button>
      <button type="button" class="btn btn-outline sm" id="btn-rd-refresh" title="Muat ulang status">{C.icon("refresh", 13)} Segarkan</button>
      <button type="button" class="btn btn-primary sm" id="btn-rd-add">{C.icon("plus", 13)} Simpan Key</button>
      <button type="button" class="btn btn-danger sm" id="btn-rd-flush" title="Hapus semua cache keys">{C.icon("trash", 13)} Flush All</button>
    </div>
  </div>
  <div class="table-responsive">
    <table class="data-table" id="table-keys">
      <thead>
        <tr>
          <th>KUNCI CACHE (KEY)</th>
          <th>TIPE DATA</th>
          <th>MASA BERLAKU (TTL)</th>
          <th style="text-align: right;">AKSI TINDAKAN</th>
        </tr>
      </thead>
      <tbody id="keys-tbody">
        <tr><td colspan="4" class="text-center p24 text-muted">Memuat daftar kunci cache...</td></tr>
      </tbody>
    </table>
  </div>
</div>

<!-- DETAIL TEKNIS & INTEGRASI -->
<div class="grid g2">
  <div class="card">
    <div class="card-header p16 border-b">
      <h3 class="card-title text-sm m0">Parameter &amp; Konfigurasi Memori</h3>
    </div>
    <div class="p16">
      <table class="data-table">
        <tbody>
          <tr><td><b>Listening Socket</b></td><td class="mono font-bold">127.0.0.1:6379 (Localhost Loopback)</td></tr>
          <tr><td><b>Alokasi Maksimal RAM</b></td><td class="mono text-primary font-bold">64.00 MB</td></tr>
          <tr><td><b>Kebijakan Eviksi</b></td><td class="mono">allkeys-lru (Hapus key terlama jika penuh)</td></tr>
          <tr><td><b>Mode Proteksi</b></td><td class="mono text-success">Protected Mode: Yes</td></tr>
          <tr><td><b>RDB Persistence</b></td><td class="mono">Aktif (/var/lib/redis/dump.rdb)</td></tr>
          <tr><td><b>Latensi Baca/Tulis</b></td><td class="text-success mono font-bold">&lt; 0.35 milidetik</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-header p16 border-b">
      <h3 class="card-title text-sm m0">Panduan Koneksi Aplikasi</h3>
    </div>
    <div class="p16">
      <div class="code-box p12 mono text-xs mb12" style="background:#0B0F17;color:#E2E8F0;border-radius:var(--radius-md);line-height:1.6;">
        <span class="text-muted"># Format Koneksi URL Standar:</span><br>
        redis://127.0.0.1:6379<br><br>
        <span class="text-muted"># Di Node.js / Next.js (.env):</span><br>
        REDIS_URL="redis://127.0.0.1:6379"<br><br>
        <span class="text-muted"># Di WordPress (Plugin Redis Object Cache):</span><br>
        Host: 127.0.0.1 | Port: 6379 | Password: (Kosong)
      </div>
      <p class="text-muted text-xs m0">Redis di STB ini diamankan secara eksklusif untuk koneksi internal. Aplikasi di dalam server dapat langsung terhubung tanpa autentikasi tambahan.</p>
    </div>
  </div>
</div>

<!-- MODAL SIMPAN KEY BARU -->
<div class="modal-overlay hidden" id="modal-add-key">
  <div class="modal-box card" style="max-width: 520px;">
    <div class="modal-header row space-between align-center border-b p16">
      <div class="row gap8 align-center">
        <span class="metric-icon">{C.icon("plus", 15)}</span>
        <h3 class="card-title text-sm m0">Simpan Key Cache Baru</h3>
      </div>
      <button type="button" class="btn-close" id="btn-close-add-key">&times;</button>
    </div>
    <div class="modal-body p16">
      <div class="form-group mb16">
        <label class="form-label">Nama Key *</label>
        <input type="text" id="add-kname" class="form-input mono" placeholder="contoh: user:1001:profile atau session:token" />
      </div>

      <div class="form-group mb16">
        <label class="form-label">Nilai / Payload Value *</label>
        <textarea id="add-kvalue" class="form-input mono text-xs p12" rows="6" placeholder="String teks atau JSON payload..."></textarea>
      </div>

      <div class="form-group mb16">
        <label class="form-label">Masa Berlaku (TTL dalam Detik - Opsional)</label>
        <input type="number" id="add-kttl" class="form-input mono" placeholder="contoh: 3600 (kosongkan untuk permanen)" />
      </div>
    </div>
    <div class="modal-footer row justify-end gap8 border-t p16">
      <button type="button" class="btn btn-outline" id="btn-cancel-add-key">Batal</button>
      <button type="button" class="btn btn-primary" id="btn-save-key">Simpan ke Redis</button>
    </div>
  </div>
</div>

<!-- MODAL LIHAT DETAIL VALUE KEY -->
<div class="modal-overlay hidden" id="modal-view-key">
  <div class="modal-box modal-lg card" style="max-width: 720px;">
    <div class="modal-header row space-between align-center border-b p16">
      <div class="row gap8 align-center">
        <span class="metric-icon">{C.icon("redis", 15)}</span>
        <div>
          <h3 class="card-title text-sm m0">Isi Nilai Key: <span id="view-key-title" class="mono text-primary"></span></h3>
          <p class="text-xs text-muted m0 mt4" id="view-key-meta">Tipe: STRING · TTL: 3600s</p>
        </div>
      </div>
      <button type="button" class="btn-close" id="btn-close-view-key">&times;</button>
    </div>
    <div class="modal-body p16">
      <pre id="view-key-content" class="code-editor mono text-xs p12" style="max-height: 380px; overflow-y: auto; background:#0B0F17; color:#E2E8F0; border-radius:var(--radius-md); border:1px solid var(--border); white-space: pre-wrap; line-height:1.5;"></pre>
    </div>
    <div class="modal-footer row space-between align-center border-t p16">
      <span class="text-xs text-muted">Maksimal 4000 karakter pratinjau</span>
      <div class="row gap8">
        <button type="button" class="btn btn-outline sm" id="btn-copy-key-val">Salin Nilai</button>
        <button type="button" class="btn btn-outline sm" id="btn-close-view-key-foot">Tutup</button>
      </div>
    </div>
  </div>
</div>

<script>
(function(){{
var allKeysList = [];

function loadRedisStats() {{
  fetch('{base}/api/redis/info')
    .then(r => r.json())
    .then(res => {{
      if (!res.ok) return;
      var d = res.data || res;
      document.getElementById('rd-ver').textContent = 'Redis Server v' + (d.version || '7.0');
      document.getElementById('rd-mem').innerHTML = (d.used_memory || '0M') + ' <small>MB</small>';
      document.getElementById('rd-policy').textContent = d.maxmemory_policy || 'allkeys-lru';
      document.getElementById('rd-keys').textContent = d.keys || '0';
      document.getElementById('rd-hit').textContent = d.hit_rate || '100%';
      document.getElementById('rd-clients').textContent = 'Clients aktif: ' + (d.clients || '0');
      document.getElementById('rd-ops').textContent = 'Throughput: ' + (d.ops_per_sec || '0') + ' ops/detik';

      // Persentase bar
      var memNum = parseFloat(d.used_memory) || 1;
      var maxNum = parseFloat(d.maxmemory) || 64;
      var pct = Math.min(100, Math.max(2, (memNum / maxNum) * 100));
      var barEl = document.getElementById('rd-mem-bar');
      if (barEl) barEl.style.width = pct + '%';
      var meterEl = document.getElementById('rd-mem-meter');
      if (meterEl) {{
        meterEl.className = 'meter ' + (pct >= 85 ? 'danger' : pct >= 70 ? 'warn' : 'ok') + ' mt8';
      }}
    }})
    .catch(console.error);

  loadKeys();
}}

function loadKeys() {{
  var tbody = document.getElementById('keys-tbody');
  tbody.innerHTML = '<tr><td colspan="4" class="text-center p24 text-muted">Memuat daftar kunci cache...</td></tr>';

  fetch('{base}/api/redis/keys')
    .then(r => r.json())
    .then(res => {{
      if (!res.ok) {{
        tbody.innerHTML = '<tr><td colspan="4" class="text-center p24 text-danger">Gagal: ' + res.error + '</td></tr>';
        return;
      }}
      var dataObj = res.data || res;
      allKeysList = dataObj.items || [];
      document.getElementById('keys-count').textContent = allKeysList.length + ' Kunci Aktif';
      renderKeysTable(allKeysList);
    }})
    .catch(err => {{
      tbody.innerHTML = '<tr><td colspan="4" class="text-center p24 text-danger">Error: ' + err + '</td></tr>';
    }});
}}

function renderKeysTable(list) {{
  var tbody = document.getElementById('keys-tbody');
  if (list.length === 0) {{
    tbody.innerHTML = '<tr><td colspan="4" class="text-center p24 text-muted">Tidak ada kunci cache yang cocok (database db0 kosong).</td></tr>';
    return;
  }}
  var html = '';
  list.forEach(function(k) {{
    var typeBadge = k.type === 'string'
      ? '<span class="badge badge-success">STRING</span>'
      : k.type === 'hash'
      ? '<span class="badge badge-info">HASH</span>'
      : '<span class="badge badge-warning">' + escapeHtml(k.type.toUpperCase()) + '</span>';
      
    var ttlText = k.ttl === -1
      ? '<span class="chip text-xs">♾️ Permanen</span>'
      : '<span class="mono text-xs text-muted">' + k.ttl + ' detik</span>';

    html += '<tr>' +
      '<td><div class="row gap6 align-center"><b class="mono font-bold text-main">' + escapeHtml(k.key) + '</b></div></td>' +
      '<td>' + typeBadge + '</td>' +
      '<td>' + ttlText + '</td>' +
      '<td style="text-align: right;" class="row justify-end gap6 align-center">' +
        '<button type="button" class="btn btn-sm btn-outline" data-view="' + escapeHtml(k.key) + '" title="Lihat nilai value">Lihat</button>' +
        '<button type="button" class="btn btn-sm btn-danger" data-delkey="' + escapeHtml(k.key) + '" title="Hapus kunci">Hapus</button>' +
      '</td>' +
    '</tr>';
  }});
  tbody.innerHTML = html;
}}

function filterKeys() {{
  var q = (document.getElementById('key-search').value || '').trim().toLowerCase();
  var filtered = allKeysList.filter(function(k) {{
    return !q || (k.key || '').toLowerCase().indexOf(q) > -1;
  }});
  renderKeysTable(filtered);
}}

function pingRedis() {{
  if (window.SC && window.SC.toast) window.SC.toast('Ping', 'Menguji latency roundtrip ke Redis...', 'info');
  fetch('{base}/api/redis/ping')
    .then(r => r.json())
    .then(res => {{
      if (res.ok) {{
        var d = res.data || res;
        var msg = (d.response || 'PONG') + ' · Latensi: ' + (d.latency_ms || '0.2') + ' ms';
        if (window.SC && window.SC.toast) window.SC.toast('Redis Online', msg, 'ok');
        else alert(msg);
      }} else {{
        if (window.SC && window.SC.toast) window.SC.toast('Gagal', res.error, 'err');
      }}
    }})
    .catch(e => {{ if (window.SC && window.SC.toast) window.SC.toast('Error', String(e), 'err'); }});
}}

function openAddKeyModal() {{
  document.getElementById('add-kname').value = '';
  document.getElementById('add-kvalue').value = '';
  document.getElementById('add-kttl').value = '';
  document.getElementById('modal-add-key').classList.remove('hidden');
  document.getElementById('add-kname').focus();
}}

function closeAddKeyModal() {{
  document.getElementById('modal-add-key').classList.add('hidden');
}}

function submitAddKey() {{
  var k = document.getElementById('add-kname').value.trim();
  var val = document.getElementById('add-kvalue').value;
  var ttl = document.getElementById('add-kttl').value.trim();

  if (!k) {{
    if (window.SC && window.SC.toast) window.SC.toast('Validasi', 'Nama key wajib diisi!', 'warn');
    else alert('Nama key wajib diisi!');
    return;
  }}

  var btn = document.getElementById('btn-save-key');
  btn.disabled = true;

  fetch('{base}/api/redis/set', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-CSRF': '{csrf}' }},
    body: JSON.stringify({{ key: k, value: val, ttl: ttl || null }})
  }})
  .then(r => r.json())
  .then(res => {{
    if (res.ok) {{
      closeAddKeyModal();
      if (window.SC && window.SC.toast) window.SC.toast('Berhasil', 'Key ' + k + ' berhasil disimpan!', 'ok');
      loadRedisStats();
    }} else {{
      if (window.SC && window.SC.toast) window.SC.toast('Gagal', res.error, 'err');
    }}
  }})
  .catch(err => {{
    if (window.SC && window.SC.toast) window.SC.toast('Error', String(err), 'err');
  }})
  .finally(() => btn.disabled = false);
}}

function viewKeyDetail(key) {{
  document.getElementById('view-key-title').textContent = key;
  document.getElementById('view-key-content').textContent = 'Mengambil isi nilai...';
  document.getElementById('modal-view-key').classList.remove('hidden');

  fetch('{base}/api/redis/get?key=' + encodeURIComponent(key))
    .then(r => r.json())
    .then(res => {{
      if (res.ok) {{
        var d = res.data || res;
        var ttlStr = d.ttl === -1 ? 'Permanen (tanpa expiry)' : d.ttl + ' detik';
        document.getElementById('view-key-meta').textContent = 'Tipe: ' + (d.type || 'string').toUpperCase() + ' · TTL: ' + ttlStr;
        document.getElementById('view-key-content').textContent = d.value || '(Nilai kosong)';
      }} else {{
        document.getElementById('view-key-content').textContent = 'Gagal memuat: ' + res.error;
      }}
    }})
    .catch(err => {{
      document.getElementById('view-key-content').textContent = 'Error: ' + err;
    }});
}}

function closeViewKeyModal() {{
  document.getElementById('modal-view-key').classList.add('hidden');
}}

function deleteKeyAction(key) {{
  if (window.SC && window.SC.confirmDanger) {{
    window.SC.confirmDanger({{
      title: 'Hapus Kunci Cache',
      body: 'Hapus key <b>' + escapeHtml(key) + '</b> dari Redis?',
      ok: 'Hapus Key',
      phrase: null
    }}).then(function(ok) {{
      if (ok) doDeleteKey(key);
    }});
  }} else {{
    if (confirm('Hapus key ' + key + '?')) doDeleteKey(key);
  }}
}}

function doDeleteKey(key) {{
  fetch('{base}/api/redis/delete', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-CSRF': '{csrf}' }},
    body: JSON.stringify({{ key: key }})
  }})
  .then(r => r.json())
  .then(res => {{
    if (res.ok) {{
      if (window.SC && window.SC.toast) window.SC.toast('Dihapus', 'Key ' + key + ' dihapus', 'ok');
      loadRedisStats();
    }} else {{
      if (window.SC && window.SC.toast) window.SC.toast('Gagal', res.error, 'err');
    }}
  }})
  .catch(err => {{
    if (window.SC && window.SC.toast) window.SC.toast('Error', String(err), 'err');
  }});
}}

function confirmFlush() {{
  if (window.SC && window.SC.confirmDanger) {{
    window.SC.confirmDanger({{
      title: 'Kosongkan Semua Cache Redis (FLUSHALL)',
      body: 'PERINGATAN: Seluruh cache keys di database Redis akan dihapus seketika!',
      ok: 'Flush All Cache',
      phrase: 'FLUSH'
    }}).then(function(ok) {{
      if (ok) doFlush();
    }});
  }} else {{
    if (confirm('Yakin ingin membersihkan SEMUA cache di Redis?')) doFlush();
  }}
}}

function doFlush() {{
  fetch('{base}/api/redis/flush', {{
    method: 'POST',
    headers: {{ 'X-CSRF': '{csrf}' }}
  }})
  .then(r => r.json())
  .then(res => {{
    if (res.ok) {{
      if (window.SC && window.SC.toast) window.SC.toast('Bersih', 'Cache Redis berhasil dikosongkan!', 'ok');
      loadRedisStats();
    }} else {{
      if (window.SC && window.SC.toast) window.SC.toast('Gagal', res.error, 'err');
    }}
  }})
  .catch(e => {{ if (window.SC && window.SC.toast) window.SC.toast('Error', String(e), 'err'); }});
}}

function copyKeyVal() {{
  var val = document.getElementById('view-key-content').textContent;
  if (!navigator.clipboard) {{
    alert('Clipboard API tidak didukung browser ini.');
    return;
  }}
  navigator.clipboard.writeText(val || '')
    .then(function() {{
      if (window.SC && window.SC.toast) window.SC.toast('Tersalin', 'Nilai key disalin ke clipboard', 'ok');
      else alert('Nilai disalin!');
    }})
    .catch(function(e) {{ alert('Gagal menyalin: ' + e); }});
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

bind('btn-rd-ping', pingRedis);
bind('btn-rd-refresh', loadRedisStats);
bind('btn-rd-add', openAddKeyModal);
bind('btn-rd-flush', confirmFlush);
bind('btn-close-add-key', closeAddKeyModal);
bind('btn-cancel-add-key', closeAddKeyModal);
bind('btn-save-key', submitAddKey);
bind('btn-close-view-key', closeViewKeyModal);
bind('btn-close-view-key-foot', closeViewKeyModal);
bind('btn-copy-key-val', copyKeyVal);

var kSearch = document.getElementById('key-search');
if (kSearch) kSearch.addEventListener('input', filterKeys);

// Event delegation for table actions
document.addEventListener('click', function(e) {{
  var viewBtn = e.target.closest('[data-view]');
  if (viewBtn) {{
    viewKeyDetail(viewBtn.getAttribute('data-view'));
    return;
  }}
  var delBtn = e.target.closest('[data-delkey]');
  if (delBtn) {{
    deleteKeyAction(delBtn.getAttribute('data-delkey'));
    return;
  }}
}});

loadRedisStats();
}})();
</script>
"""
    return layout.shell(sess, app, "redis", "Redis Cache",
                        "Pemantau cache memori in-memory (Port 6379, Limit 64 MB)",
                        html, t)
