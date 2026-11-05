"""Halaman Manajemen Web Server Nginx: kelola vhost, reverse proxy, editor konfigurasi, dan pembaca log."""
import json

from lib import nginxops
from ui import components as C
from ui import layout


def render(req, app, sess, qs, t):
    csrf = req.csrf_token(sess)
    base = layout.BASE_PATH
    web_root = str(app.cfg.get("web_root") or "/var/www")
    log_dir = nginxops.LOG_DIR
    web_root_js = json.dumps(web_root)
    nginx_version = nginxops.version()
    nginx_label = ("Nginx " + nginx_version) if nginx_version else "Tidak terpasang"
    log_dir_js = json.dumps(log_dir)

    html = f"""
<!-- STATS OVERVIEW VHOST -->
<div class="grid g4 mb16">
  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">TOTAL SITUS TERPASANG</span>
      <span class="metric-icon">{C.icon("web", 15)}</span>
    </div>
    <span class="vl" id="stat-total-sites">0</span>
    <span class="ft">Virtual host aktif di Nginx</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">REVERSE PROXY</span>
      <span class="tag in" id="stat-proxy-badge">PROXY</span>
    </div>
    <span class="vl text-primary" id="stat-proxy-sites">0</span>
    <span class="ft">Next.js / Node.js / Python / Go</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">PHP &amp; WEB STATIK</span>
      <span class="metric-icon">{C.icon("files", 15)}</span>
    </div>
    <span class="vl text-success" id="stat-static-sites">0</span>
    <span class="ft">Root direktori situs web</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">ENGINE NGINX</span>
      <span class="tag ok">TERKONFIGURASI</span>
    </div>
    <span class="vl" style="font-size:22px;">{C.e(nginx_label)}</span>
    <span class="ft"><span class="pulse-dot green"></span> Port 80 &amp; 888 Listening</span>
  </div>
</div>

<!-- TOOLBAR KONTROL UTAMA DENGAN VIEW TOGGLE (TABEL & KARTU) -->
<div class="card mb24 p0 overflow-hidden">
  <div class="card-header p16 border-b row space-between align-center flex-wrap gap8">
    <div class="row gap12 align-center">
      <h3 class="card-title text-sm m0">DAFTAR SITUS &amp; VHOST</h3>
      <span class="badge badge-success text-xs" id="sites-count">Memuat...</span>
      <div class="row gap4 ml8">
        <button type="button" class="chip text-xs selected" id="view-mode-table" title="Tampilan Tabel Detail">Tabel</button>
        <button type="button" class="chip text-xs" id="view-mode-cards" title="Tampilan Kartu Visual ala Vercel">Kartu Grid</button>
      </div>
    </div>
    <div class="row gap8 align-center flex-wrap">
      <div class="srch" style="max-width: 240px;">
        <span class="ic">{C.icon("search", 13)}</span>
        <input type="text" id="site-search" placeholder="Cari domain atau target..." class="form-input text-xs" style="padding-left: 32px; height: 32px;" />
      </div>
      <button type="button" class="btn btn-outline sm" id="btn-nginx-test" title="Uji sintaks seluruh konfigurasi">{C.icon("check", 13)} Uji Sintaks</button>
      <button type="button" class="btn btn-outline sm" id="btn-nginx-reload" title="Reload Nginx tanpa downtime">{C.icon("play", 13)} Reload Nginx</button>
      <button type="button" class="btn btn-outline sm" id="btn-nginx-refresh" title="Muat ulang daftar">{C.icon("refresh", 13)} Segarkan</button>
      <button type="button" class="btn btn-primary sm" id="btn-nginx-add">{C.icon("plus", 13)} Tambah Website</button>
    </div>
  </div>

  <!-- CONTAINER 1: TAMPILAN TABEL DETAIL -->
  <div class="table-responsive" id="container-table">
    <table class="data-table" id="table-sites">
      <thead>
        <tr>
          <th>DOMAIN &amp; ALIAS</th>
          <th>TIPE LAYANAN</th>
          <th>TARGET / ROOT DIREKTORI</th>
          <th>STATUS KEAMANAN &amp; UPSTREAM</th>
          <th style="text-align: right;">AKSI TINDAKAN</th>
        </tr>
      </thead>
      <tbody id="sites-tbody">
        <tr><td colspan="5" class="text-center p24 text-muted">Memuat daftar situs...</td></tr>
      </tbody>
    </table>
  </div>

  <!-- CONTAINER 2: TAMPILAN KARTU VISUAL (VERCEL/CLOUDFLARE STYLE) -->
  <div class="p16 hidden" id="container-cards">
    <div class="grid g2" id="sites-cards-grid"></div>
  </div>
</div>

<!-- MODAL TAMBAH SITUS / WIZARD DEPLOY PROJECT LENGKAP -->
<div class="modal-overlay hidden" id="modal-add">
  <div class="modal-box card" style="max-width: 640px;">
    <div class="modal-header row space-between align-center border-b p16">
      <div class="row gap8 align-center">
        <span class="metric-icon">{C.icon("web", 15)}</span>
        <h3 class="card-title text-sm m0">Deploy Project / Website Baru</h3>
      </div>
      <button type="button" class="btn-close" id="btn-close-add">&times;</button>
    </div>
    <div class="modal-body p16">
      <!-- Pilihan Arsitektur Project -->
      <label class="form-label mb6">Pilih Arsitektur &amp; Template Project:</label>
      <div class="row gap8 flex-wrap mb16">
        <button type="button" class="chip text-xs selected" data-tpl="fullstack">{C.icon("apps", 11)} ⚡ Fullstack (Next.js + Go/Node + DB)</button>
        <button type="button" class="chip text-xs" data-tpl="nextjs">{C.icon("terminal", 11)} Reverse Proxy Port (:3000)</button>
        <button type="button" class="chip text-xs" data-tpl="static">{C.icon("files", 11)} PHP / HTML Statik</button>
        <button type="button" class="chip text-xs" data-tpl="custom">Target Kustom</button>
      </div>

      <div class="form-group mb16">
        <label class="form-label">Nama Domain Utama *</label>
        <input type="text" id="add-domain" class="form-input mono font-bold" placeholder="contoh: domain.com atau app.domain.com" />
        <span class="form-help text-xs text-muted">Domain harus sudah diarahkan di DNS Cloudflare ke IP server / tunnel.</span>
      </div>

      <!-- Field Khusus Fullstack Dual Routing -->
      <div class="form-group mb16" id="group-fullstack">
        <label class="form-label">Target Backend REST API (Port Lokal) *</label>
        <input type="text" id="add-api-pass" class="form-input mono" value="http://127.0.0.1:8080/api/" />
        <span class="form-help text-xs text-muted">Semua request ke <code>/api/*</code> otomatis diteruskan ke backend Go / Node.js ini.</span>
      </div>

      <!-- Field Reverse Proxy Standar -->
      <div class="form-group mb16 hidden" id="group-proxy">
        <label class="form-label">Target Reverse Proxy URL *</label>
        <input type="text" id="add-proxy" class="form-input mono" placeholder="http://127.0.0.1:3000" />
      </div>

      <!-- Field Webroot Folder (PHP/Static) -->
      <div class="form-group mb16 hidden" id="group-root">
        <label class="form-label">Root Direktori Berkas Web</label>
        <input type="text" id="add-root" class="form-input mono" placeholder="{C.e(web_root)}/domain.com" />
      </div>

      <!-- Auto Provisioning Database Checkbox -->
      <div class="card p12 mb16" style="background:var(--surface-2);border-radius:var(--radius-md);">
        <label class="form-label mb6">Integrasi Database Otomatis:</label>
        <div class="row gap12 align-center flex-wrap">
          <label class="row gap6 align-center text-xs" style="cursor:pointer;">
            <input type="radio" name="auto_db" value="postgres" id="db-radio-pg" checked />
            <b class="text-main">PostgreSQL 18</b> (Rekomendasi Modern)
          </label>
          <label class="row gap6 align-center text-xs" style="cursor:pointer;">
            <input type="radio" name="auto_db" value="mysql" id="db-radio-my" />
            <b class="text-main">MariaDB / MySQL</b>
          </label>
          <label class="row gap6 align-center text-xs" style="cursor:pointer;">
            <input type="radio" name="auto_db" value="none" id="db-radio-none" />
            <span class="text-muted">Tanpa Database</span>
          </label>
        </div>
        <div class="text-xs text-muted mt6">Panel akan otomatis menjalankan <code>CREATE DATABASE</code> dan menyiapkan koneksi.</div>
      </div>

      <div class="form-group mb16">
        <div class="row space-between align-center mb4">
          <label class="form-label m0">Alias Domain Tambahan (Opsional)</label>
          <button type="button" class="btn btn-sm gh text-xs" id="btn-add-www">+ Tambah www</button>
        </div>
        <input type="text" id="add-alias" class="form-input mono" placeholder="www.domain.com" />
      </div>

      <!-- Live Summary Preview Box -->
      <div class="card p12" style="background:var(--surface-2);border-radius:var(--radius-md);">
        <div class="text-xs text-muted bold mb4">RINGKASAN DEPLOYMENT:</div>
        <div class="text-xs mono text-primary font-bold" id="add-summary-text">Arsitektur Fullstack: Frontend Next.js + Backend API port 8080 + Database PostgreSQL.</div>
      </div>
    </div>
    <div class="modal-footer row justify-end gap8 border-t p16">
      <button type="button" class="btn btn-outline" id="btn-cancel-add">Batal</button>
      <button type="button" class="btn btn-primary" id="btn-save-site">Deploy Project Sekarang</button>
    </div>
  </div>
</div>

<!-- MODAL UPLOAD & DEPLOY ZIP 1-KLIK -->
<div class="modal-overlay hidden" id="modal-deploy-zip">
  <div class="modal-box card" style="max-width: 540px;">
    <div class="modal-header row space-between align-center border-b p16">
      <div class="row gap8 align-center">
        <span class="metric-icon">{C.icon("up", 15)}</span>
        <div>
          <h3 class="card-title text-sm m0">Upload &amp; Deploy ZIP: <span id="deploy-zip-domain" class="mono text-primary font-bold"></span></h3>
          <p class="text-xs text-muted m0 mt4">Ekstrak otomatis build Next.js / HTML ke webroot.</p>
        </div>
      </div>
      <button type="button" class="btn-close" id="btn-close-deploy-zip">&times;</button>
    </div>
    <div class="modal-body p16">
      <div class="drop p24 mb16" id="zip-dropzone" style="cursor:pointer;">
        <div class="row gap8 align-center justify-center mb8">
          <span class="text-primary">{C.icon("up", 24)}</span>
          <b class="text-main">Pilih berkas ZIP / TAR.GZ project build</b>
        </div>
        <p class="text-xs text-muted m0">Tarik berkas .zip (hasil build `out/` Next.js atau frontend) ke sini, atau klik tombol di bawah.</p>
        <input type="file" id="zip-file-input" accept=".zip,.tar.gz,.tgz" class="hidden" />
      </div>
      <div id="zip-selected-file" class="card p12 mb12 hidden" style="background:var(--surface-2);">
        <div class="row space-between align-center">
          <span class="mono text-xs font-bold text-main" id="zip-file-name">—</span>
          <span class="badge badge-success text-xs" id="zip-file-size">—</span>
        </div>
      </div>
      <div id="zip-deploy-progress" class="text-xs text-primary font-bold hidden mb12">Sedang mengunggah dan mengekstrak berkas ke server...</div>
    </div>
    <div class="modal-footer row space-between align-center border-t p16">
      <label for="zip-file-input" class="btn btn-outline sm" style="cursor:pointer;margin:0;">Pilih Berkas ZIP</label>
      <div class="row gap8">
        <button type="button" class="btn btn-outline sm" id="btn-cancel-deploy-zip">Batal</button>
        <button type="button" class="btn btn-primary sm" id="btn-submit-deploy-zip" disabled>Mulai Deploy</button>
      </div>
    </div>
  </div>
</div>
<!-- MODAL EDITOR KONFIGURASI NGINX -->
<div class="modal-overlay hidden" id="modal-edit">
  <div class="modal-box modal-lg card" style="max-width: 840px;">
    <div class="modal-header row space-between align-center border-b p16">
      <div>
        <h3 class="card-title text-sm m0">Editor Konfigurasi Nginx: <span id="edit-domain-title" class="mono text-primary font-bold"></span></h3>
        <p class="text-xs text-muted m0 mt4">Setiap penyimpanan otomatis diuji via <code class="mono">nginx -t</code>. Rollback otomatis jika ada salah sintaks.</p>
      </div>
      <button type="button" class="btn-close" id="btn-close-edit">&times;</button>
    </div>
    <div class="modal-body p16">
      <div class="row gap8 align-center flex-wrap mb8">
        <span class="text-xs text-muted bold">SISIPKAN SNIPPET:</span>
        <button type="button" class="chip text-xs" data-snip="cors">+ CORS Headers</button>
        <button type="button" class="chip text-xs" data-snip="ws">+ WebSocket Upgrade</button>
        <button type="button" class="chip text-xs" data-snip="gzip">+ Gzip Compression</button>
        <button type="button" class="chip text-xs" data-snip="cache">+ Static Cache 30 Hari</button>
      </div>
      <textarea id="edit-nginx-content" class="code-editor mono text-xs p12" rows="18" spellcheck="false" style="width:100%;background:#0B0F17;color:#E2E8F0;border-radius:var(--radius-md);border:1px solid var(--border);line-height:1.6;"></textarea>
      <div id="edit-msg" class="alert-box mt8 hidden"></div>
    </div>
    <div class="modal-footer row space-between align-center border-t p16">
      <span class="text-xs text-muted">Shortcut: <kbd class="kbd-hint">Ctrl + S</kbd> untuk simpan</span>
      <div class="row gap8">
        <button type="button" class="btn btn-outline" id="btn-cancel-edit">Tutup</button>
        <button type="button" class="btn btn-primary" id="btn-save-vhost">Simpan &amp; Terapkan</button>
      </div>
    </div>
  </div>
</div>

<!-- MODAL PEMBACA LOG SITUS (ACCESS & ERROR LOGS) -->
<div class="modal-overlay hidden" id="modal-logs">
  <div class="modal-box modal-lg card" style="max-width: 860px;">
    <div class="modal-header row space-between align-center border-b p16">
      <div class="row gap8 align-center">
        <span class="metric-icon">{C.icon("logs", 15)}</span>
        <div>
          <h3 class="card-title text-sm m0">Log Web Server: <span id="log-domain-title" class="mono text-primary font-bold"></span></h3>
          <p class="text-xs text-muted m0 mt4">Memantau lalu lintas HTTP akses dan galat Nginx secara live.</p>
        </div>
      </div>
      <button type="button" class="btn-close" id="btn-close-logs">&times;</button>
    </div>
    <div class="modal-body p16">
      <div class="row gap8 mb12">
        <button type="button" class="btn btn-sm btn-primary flex-1" id="tab-log-access">Access Log ({C.e(log_dir)}/[domain].log)</button>
        <button type="button" class="btn btn-sm btn-outline flex-1" id="tab-log-error">Error Log ({C.e(log_dir)}/[domain].error.log)</button>
      </div>
      <pre id="log-access-content" class="code-editor mono text-xs p12" style="max-height: 380px; overflow-y: auto; background:#0B0F17; color:#E2E8F0; border-radius:var(--radius-md); border:1px solid var(--border); white-space: pre-wrap; line-height:1.5;"></pre>
      <pre id="log-error-content" class="code-editor mono text-xs p12 hidden" style="max-height: 380px; overflow-y: auto; background:#0B0F17; color:#FCA5A5; border-radius:var(--radius-md); border:1px solid var(--border); white-space: pre-wrap; line-height:1.5;"></pre>
    </div>
    <div class="modal-footer row space-between align-center border-t p16">
      <span class="text-xs text-muted">Menampilkan 120 baris terbaru</span>
      <div class="row gap8">
        <button type="button" class="btn btn-outline sm" id="btn-refresh-logs">Segarkan Log</button>
        <button type="button" class="btn btn-outline sm" id="btn-cancel-logs">Tutup</button>
      </div>
    </div>
  </div>
</div>

<script>
(function(){{
var currentEditDomain = '';
var currentLogDomain = '';
var currentSiteType = 'proxy';
var currentViewMode = 'table';
var allSitesList = [];

function selectTemplate(tpl){{
  var chips = document.querySelectorAll('[data-tpl]');
  chips.forEach(c => c.className = 'chip text-xs' + (c.getAttribute('data-tpl') === tpl ? ' selected' : ''));

  var grpP = document.getElementById('group-proxy');
  var grpR = document.getElementById('group-root');
  var inpP = document.getElementById('add-proxy');
  var summary = document.getElementById('add-summary-text');

  if (tpl === 'nextjs') {{
    currentSiteType = 'proxy';
    grpP.classList.remove('hidden');
    grpR.classList.add('hidden');
    inpP.value = 'http://127.0.0.1:3000';
    if (summary) summary.textContent = 'Reverse proxy ke aplikasi Next.js/Node port 3000 dengan WebSocket upgrade.';
  }} else if (tpl === 'golang') {{
    currentSiteType = 'proxy';
    grpP.classList.remove('hidden');
    grpR.classList.add('hidden');
    inpP.value = 'http://127.0.0.1:8080';
    if (summary) summary.textContent = 'Reverse proxy ke backend Golang binary di port 8080.';
  }} else if (tpl === 'python') {{
    currentSiteType = 'proxy';
    grpP.classList.remove('hidden');
    grpR.classList.add('hidden');
    inpP.value = 'http://127.0.0.1:5000';
    if (summary) summary.textContent = 'Reverse proxy ke aplikasi Python (Flask / FastAPI / Gunicorn) di port 5000.';
  }} else if (tpl === 'static') {{
    currentSiteType = 'static';
    grpP.classList.add('hidden');
    grpR.classList.remove('hidden');
    if (summary) summary.textContent = 'Webroot berkas PHP / HTML statik dengan index.html selamat datang otomatis.';
  }} else {{
    currentSiteType = 'proxy';
    grpP.classList.remove('hidden');
    grpR.classList.add('hidden');
    inpP.value = '';
    if (summary) summary.textContent = 'Konfigurasi target kustom sesuai port atau socket yang Anda inginkan.';
  }}
}}

function cleanDomainInput(val){{
  return (val || '').trim().toLowerCase().replace(/^https?:\\/\\//, '').replace(/\\/.*$/, '');
}}

function autoSuggestAlias(){{
  var d = cleanDomainInput(document.getElementById('add-domain').value);
  if (d && !d.startsWith('www.') && d.indexOf('.') > -1) {{
    document.getElementById('add-root').placeholder = {web_root_js} + '/' + d;
  }}
}}

function addWwwAlias(){{
  var d = cleanDomainInput(document.getElementById('add-domain').value);
  if (!d) return;
  if (!d.startsWith('www.')) {{
    document.getElementById('add-alias').value = 'www.' + d;
  }}
}}

function openAddModal(){{
  document.getElementById('add-domain').value = '';
  document.getElementById('add-alias').value = '';
  document.getElementById('add-root').value = '';
  selectTemplate('nextjs');
  document.getElementById('modal-add').classList.remove('hidden');
  document.getElementById('add-domain').focus();
}}

function closeAddModal(){{
  document.getElementById('modal-add').classList.add('hidden');
}}

function openEditModal(domain){{
  currentEditDomain = domain;
  document.getElementById('edit-domain-title').textContent = domain;
  document.getElementById('edit-nginx-content').value = '# Memuat konfigurasi Nginx untuk ' + domain + '...';
  document.getElementById('edit-msg').classList.add('hidden');
  document.getElementById('modal-edit').classList.remove('hidden');

  fetch('{base}/api/nginx/vhost?domain=' + encodeURIComponent(domain))
    .then(r => r.json())
    .then(res => {{
      if (res.ok) {{
        document.getElementById('edit-nginx-content').value = (res.data ? res.data.content : res.content) || '';
      }} else {{
        if (window.SC && window.SC.toast) window.SC.toast('Gagal', 'Gagal memuat vhost: ' + res.error, 'err');
        closeEditModal();
      }}
    }})
    .catch(err => {{
      if (window.SC && window.SC.toast) window.SC.toast('Error', String(err), 'err');
    }});
}}

function closeEditModal(){{
  document.getElementById('modal-edit').classList.add('hidden');
}}

function openLogsModal(domain){{
  currentLogDomain = domain;
  document.getElementById('log-domain-title').textContent = domain;
  document.getElementById('log-access-content').textContent = 'Memuat log akses...';
  document.getElementById('log-error-content').textContent = 'Memuat log error...';
  selectLogTab('access');
  document.getElementById('modal-logs').classList.remove('hidden');
  refreshCurrentLogs();
}}

function closeLogsModal(){{
  document.getElementById('modal-logs').classList.add('hidden');
}}

function selectLogTab(tab){{
  var btnAcc = document.getElementById('tab-log-access');
  var btnErr = document.getElementById('tab-log-error');
  var preAcc = document.getElementById('log-access-content');
  var preErr = document.getElementById('log-error-content');

  if (tab === 'access') {{
    btnAcc.className = 'btn btn-sm btn-primary flex-1';
    btnErr.className = 'btn btn-sm btn-outline flex-1';
    preAcc.classList.remove('hidden');
    preErr.classList.add('hidden');
  }} else {{
    btnAcc.className = 'btn btn-sm btn-outline flex-1';
    btnErr.className = 'btn btn-sm btn-primary flex-1';
    preAcc.classList.add('hidden');
    preErr.classList.remove('hidden');
  }}
}}

function refreshCurrentLogs(){{
  if (!currentLogDomain) return;
  fetch('{base}/api/nginx/logs?domain=' + encodeURIComponent(currentLogDomain) + '&n=120')
    .then(r => r.json())
    .then(res => {{
      if (res.ok) {{
        document.getElementById('log-access-content').textContent = (res.data ? res.data.access : res.access) || '(Access log kosong atau belum ada kunjungan)';
        document.getElementById('log-error-content').textContent = (res.data ? res.data.error : res.error) || '(Error log bersih - tidak ada galat)';
      }} else {{
        if (window.SC && window.SC.toast) window.SC.toast('Gagal', res.error, 'err');
      }}
    }})
    .catch(err => {{
      if (window.SC && window.SC.toast) window.SC.toast('Error', String(err), 'err');
    }});
}}

function testNginxConfig(){{
  if (window.SC && window.SC.toast) window.SC.toast('Pengujian', 'Menguji konfigurasi Nginx via nginx -t...', 'info');
  fetch('{base}/api/nginx/test')
    .then(r => r.json())
    .then(res => {{
      if (res.ok) {{
        if (window.SC && window.SC.toast) window.SC.toast('Sintaks Valid', (res.data ? res.data.message : res.message) || 'Semua konfigurasi Nginx aman & valid.', 'ok');
      }} else {{
        if (window.SC && window.SC.toast) window.SC.toast('Sintaks Salah', res.error, 'err');
      }}
    }})
    .catch(e => {{ if (window.SC && window.SC.toast) window.SC.toast('Error', String(e), 'err'); }});
}}

function reloadNginxService(){{
  if (window.SC && window.SC.toast) window.SC.toast('Reload', 'Memuat ulang Nginx tanpa downtime...', 'info');
  fetch('{base}/api/nginx/reload', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-CSRF': '{csrf}' }}
  }})
  .then(r => r.json())
  .then(res => {{
    if (res.ok) {{
      if (window.SC && window.SC.toast) window.SC.toast('Berhasil', (res.data ? res.data.message : res.message) || 'Nginx di-reload!', 'ok');
      loadSites();
    }} else {{
      if (window.SC && window.SC.toast) window.SC.toast('Gagal Reload', res.error, 'err');
    }}
  }})
  .catch(e => {{ if (window.SC && window.SC.toast) window.SC.toast('Error', String(e), 'err'); }});
}}

function insertSnippet(type){{
  var ta = document.getElementById('edit-nginx-content');
  var lines = [];
  if (type === 'cors') {{
    lines = [
      '    # CORS Headers',
      '    add_header Access-Control-Allow-Origin * always;',
      '    add_header Access-Control-Allow-Methods "GET, POST, OPTIONS, PUT, DELETE" always;',
      '    add_header Access-Control-Allow-Headers "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization" always;'
    ];
  }} else if (type === 'ws') {{
    lines = [
      '    # WebSocket Upgrade Headers',
      '    proxy_http_version 1.1;',
      '    proxy_set_header Upgrade $http_upgrade;',
      '    proxy_set_header Connection "upgrade";'
    ];
  }} else if (type === 'gzip') {{
    lines = [
      '    # Gzip Compression',
      '    gzip on;',
      '    gzip_min_length 1024;',
      '    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;'
    ];
  }} else if (type === 'cache') {{
    lines = [
      '    # Static Assets Cache',
      '    location ~* \\.(jpg|jpeg|png|gif|ico|css|js|woff2|woff|svg)$ {{',
      '        expires 30d;',
      '        add_header Cache-Control "public, no-transform";',
      '    }}'
    ];
  }}
  if (lines.length > 0) {{
    var nl = String.fromCharCode(10);
    var text = nl + lines.join(nl) + nl;
    var pos = ta.selectionStart || ta.value.length;
    ta.value = ta.value.substring(0, pos) + text + ta.value.substring(pos);
    if (window.SC && window.SC.toast) window.SC.toast('Snippet', 'Snippet berhasil disisipkan', 'info');
  }}
}}

function submitSaveVhost(){{
  var btn = document.getElementById('btn-save-vhost');
  var msg = document.getElementById('edit-msg');
  var content = document.getElementById('edit-nginx-content').value;
  btn.disabled = true;
  msg.className = 'alert-box alert-info mt8';
  msg.textContent = 'Memvalidasi konfigurasi dengan nginx -t...';
  msg.classList.remove('hidden');

  fetch('{base}/api/nginx/save', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-CSRF': '{csrf}' }},
    body: JSON.stringify({{ domain: currentEditDomain, content: content }})
  }})
  .then(r => r.json())
  .then(res => {{
    if (res.ok) {{
      msg.className = 'alert-box alert-success mt8';
      msg.textContent = res.data.message || 'Konfigurasi Nginx valid dan berhasil diterapkan!';
      if (window.SC && window.SC.toast) window.SC.toast('Tersimpan', 'Konfigurasi vhost ' + currentEditDomain + ' berhasil di-reload!', 'ok');
      setTimeout(closeEditModal, 1200);
      loadSites();
    }} else {{
      msg.className = 'alert-box alert-danger mt8';
      msg.textContent = res.error || 'Sintaks salah!';
      if (window.SC && window.SC.toast) window.SC.toast('Validasi Gagal', res.error, 'err');
    }}
  }})
  .catch(err => {{
    msg.className = 'alert-box alert-danger mt8';
    msg.textContent = 'Network Error: ' + err;
  }})
  .finally(() => btn.disabled = false);
}}

function submitAddSite(){{
  var rawDomain = document.getElementById('add-domain').value;
  var domain = cleanDomainInput(rawDomain);
  var rootDir = document.getElementById('add-root').value.trim();
  var proxyPass = document.getElementById('add-proxy').value.trim();
  var aliases = document.getElementById('add-alias').value.trim().split(/\\s+/).filter(Boolean);

  if (!domain) {{
    if (window.SC && window.SC.toast) window.SC.toast('Validasi', 'Nama domain utama wajib diisi!', 'warn');
    return;
  }}
  if (currentSiteType === 'proxy' && !proxyPass) {{
    if (window.SC && window.SC.toast) window.SC.toast('Validasi', 'Target URL proxy wajib diisi!', 'warn');
    return;
  }}

  var btn = document.getElementById('btn-save-site');
  btn.disabled = true;

  var payload = {{
    domain: domain,
    root: currentSiteType === 'static' ? (rootDir || null) : null,
    proxy: currentSiteType === 'proxy' ? proxyPass : null,
    aliases: aliases
  }};

  fetch('{base}/api/nginx/add', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-CSRF': '{csrf}' }},
    body: JSON.stringify(payload)
  }})
  .then(r => r.json())
  .then(res => {{
    if (res.ok) {{
      closeAddModal();
      if (window.SC && window.SC.toast) window.SC.toast('Berhasil', 'Situs ' + domain + ' berhasil dibuat!', 'ok');
      loadSites();
    }} else {{
      if (window.SC && window.SC.toast) window.SC.toast('Gagal', res.error || 'Gagal membuat situs', 'err');
    }}
  }})
  .catch(err => {{
    if (window.SC && window.SC.toast) window.SC.toast('Error', String(err), 'err');
  }})
  .finally(() => btn.disabled = false);
}}

function deleteSite(domain){{
  if (window.SC && window.SC.confirmDanger) {{
    window.SC.confirmDanger({{
      title: 'Hapus Virtual Host',
      body: 'Yakin ingin menghapus situs <b>' + escapeHtml(domain) + '</b>? File konfigurasi Nginx akan dicabut.',
      ok: 'Hapus Situs',
      phrase: domain
    }}).then(function(ok){{
      if (ok) doDeleteSite(domain);
    }});
  }}
}}

function doDeleteSite(domain){{
  fetch('{base}/api/nginx/delete', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-CSRF': '{csrf}' }},
    body: JSON.stringify({{ domain: domain }})
  }})
  .then(r => r.json())
  .then(res => {{
    if (res.ok) {{
      if (window.SC && window.SC.toast) window.SC.toast('Dihapus', 'Situs ' + domain + ' berhasil dihapus', 'ok');
      loadSites();
    }} else {{
      if (window.SC && window.SC.toast) window.SC.toast('Gagal', res.error, 'err');
    }}
  }})
  .catch(err => alert('Network error: ' + err));
}}

function filterSites(){{
  var q = (document.getElementById('site-search').value || '').trim().toLowerCase();
  var filtered = allSitesList.filter(function(s){{
    var text = (s.domain + ' ' + (s.aliases || []).join(' ') + ' ' + (s.proxy || '') + ' ' + (s.root || '')).toLowerCase();
    return !q || text.indexOf(q) > -1;
  }});
  renderSitesView(filtered);
}}

function emptySitesText(){{
  var q = (document.getElementById('site-search').value || '').trim();
  return q ? 'Tidak ada situs yang cocok dengan pencarian.' : 'Belum ada situs web. Klik “Tambah Website” untuk membuat vhost pertama.';
}}

function renderSitesView(list){{
  renderSitesTable(list);
  renderSitesCards(list);
}}

function renderSitesTable(list){{
  var tbody = document.getElementById('sites-tbody');
  if (list.length === 0) {{
    tbody.innerHTML = '<tr><td colspan="5" class="text-center p24 text-muted">' + emptySitesText() + '</td></tr>';
    return;
  }}
  var html = '';
  list.forEach(function(s){{
    var aliasesPills = '';
    if (s.aliases && s.aliases.length) {{
      aliasesPills = '<div class="row gap4 mt4 flex-wrap">' +
        s.aliases.map(function(a){{ return '<span class="chip text-xs">' + escapeHtml(a) + '</span>'; }}).join('') +
        '</div>';
    }}
    
    var domainCol = '<div class="row gap6 align-center">' +
      '<b class="text-main mono font-bold">' + escapeHtml(s.domain) + '</b>' +
      '<a href="https://' + escapeHtml(s.domain) + '" target="_blank" class="btn sm gh p4" title="Buka situs di tab baru">↗</a>' +
      '</div>' + aliasesPills;

    var typeBadge = s.proxy
      ? '<span class="badge badge-info">REVERSE PROXY</span>'
      : '<span class="badge badge-success">PHP / STATIK</span>';
      
    var targetText = s.proxy
      ? '<div class="row gap6 align-center"><span class="pulse-dot ' + (s.target_online ? 'green' : 'gray') + '"></span><span class="mono text-primary font-bold">' + escapeHtml(s.proxy) + '</span></div>'
      : '<span class="mono text-muted text-xs">' + escapeHtml(s.root || '—') + '</span>';
      
    var statusBadge = s.proxy
      ? (s.target_online
         ? '<span class="badge badge-success"><span class="pulse-dot green"></span> UPSTREAM ONLINE</span>'
         : '<span class="badge badge-warning"><span class="pulse-dot gray"></span> UPSTREAM OFFLINE</span>')
      : '<span class="badge badge-success"><span class="pulse-dot green"></span> ROOT TERSEDIA</span>';
    
    var folderBtn = !s.proxy && s.root
      ? '<a href="/files?path=' + encodeURIComponent(s.root) + '" class="btn btn-sm btn-outline" title="Buka root folder di File Explorer">Folder 📁</a> '
      : '';

    html += '<tr>' +
      '<td>' + domainCol + '</td>' +
      '<td>' + typeBadge + '</td>' +
      '<td>' + targetText + '</td>' +
      '<td>' + statusBadge + '</td>' +
      '<td style="text-align: right;" class="row justify-end gap6 align-center flex-wrap">' +
        folderBtn +
        '<button type="button" class="btn btn-sm btn-outline" data-conf="' + escapeHtml(s.domain) + '" title="Edit konfigurasi Nginx">Conf</button>' +
        '<button type="button" class="btn btn-sm btn-outline" data-log="' + escapeHtml(s.domain) + '" title="Lihat log akses dan galat">Logs</button>' +
        '<a href="https://' + escapeHtml(s.domain) + '" target="_blank" class="btn btn-sm btn-outline" title="Buka domain">Buka ↗</a>' +
        '<button type="button" class="btn btn-sm btn-danger" data-del="' + escapeHtml(s.domain) + '" title="Hapus situs">Hapus</button>' +
      '</td>' +
    '</tr>';
  }});
  tbody.innerHTML = html;
}}

function renderSitesCards(list){{
  var grid = document.getElementById('sites-cards-grid');
  if (!grid) return;
  if (list.length === 0) {{
    grid.innerHTML = '<div class="p24 text-center text-muted col-span-2">' + emptySitesText() + '</div>';
    return;
  }}
  var html = '';
  list.forEach(function(s){{
    var typeBadge = s.proxy
      ? '<span class="badge badge-info">REVERSE PROXY</span>'
      : '<span class="badge badge-success">PHP / STATIK</span>';

    var statusPill = s.proxy
      ? (s.target_online
         ? '<span class="badge badge-success text-xs"><span class="pulse-dot green"></span> UPSTREAM ONLINE</span>'
         : '<span class="badge badge-warning text-xs"><span class="pulse-dot gray"></span> UPSTREAM OFFLINE</span>')
      : '<span class="badge badge-success text-xs"><span class="pulse-dot green"></span> ROOT TERSEDIA</span>';

    var targetBlock = s.proxy
      ? '<div class="p10 card mb12" style="background:var(--surface-2);border-radius:var(--radius-md);">' +
        '<div class="text-xs text-muted bold mb2">TARGET REVERSE PROXY:</div>' +
        '<div class="mono text-primary font-bold text-sm">' + escapeHtml(s.proxy) + '</div>' +
        '</div>'
      : '<div class="p10 card mb12" style="background:var(--surface-2);border-radius:var(--radius-md);">' +
        '<div class="text-xs text-muted bold mb2">WEBROOT FOLDER:</div>' +
        '<div class="mono text-main text-xs">' + escapeHtml(s.root || '—') + '</div>' +
        '</div>';

    var folderBtn = !s.proxy && s.root
      ? '<a href="/files?path=' + encodeURIComponent(s.root) + '" class="btn btn-sm btn-outline" title="Buka di File Explorer">Folder 📁</a>'
      : '';

    var aliasesHtml = (s.aliases && s.aliases.length)
      ? '<div class="row gap4 mb12 flex-wrap">' + s.aliases.map(a => '<span class="chip text-xs">' + escapeHtml(a) + '</span>').join('') + '</div>'
      : '<div class="mb12"></div>';

    html += '<div class="card p16 lift">' +
      '<div class="row space-between align-center mb8">' +
        '<div class="row gap8 align-center">' +
          '<span class="metric-icon">🌐</span>' +
          '<b class="text-main mono font-bold text-sm">' + escapeHtml(s.domain) + '</b>' +
        '</div>' +
        statusPill +
      '</div>' +
      aliasesHtml +
      targetBlock +
      '<div class="row space-between align-center border-t pt12 flex-wrap gap6">' +
        '<div class="row gap6">' + typeBadge + '</div>' +
        '<div class="row gap6 align-center flex-wrap">' +
          folderBtn +
          '<button type="button" class="btn btn-sm btn-outline" data-conf="' + escapeHtml(s.domain) + '">Conf</button>' +
          '<button type="button" class="btn btn-sm btn-outline" data-log="' + escapeHtml(s.domain) + '">Logs</button>' +
          '<a href="https://' + escapeHtml(s.domain) + '" target="_blank" class="btn btn-sm btn-outline">Buka ↗</a>' +
          '<button type="button" class="btn btn-sm btn-danger" data-del="' + escapeHtml(s.domain) + '">Hapus</button>' +
        '</div>' +
      '</div>' +
    '</div>';
  }});
  grid.innerHTML = html;
}}

function setViewMode(mode){{
  currentViewMode = mode;
  var btnTbl = document.getElementById('view-mode-table');
  var btnCrd = document.getElementById('view-mode-cards');
  var cTbl = document.getElementById('container-table');
  var cCrd = document.getElementById('container-cards');

  if (mode === 'cards') {{
    btnCrd.className = 'chip text-xs selected';
    btnTbl.className = 'chip text-xs';
    cTbl.classList.add('hidden');
    cCrd.classList.remove('hidden');
  }} else {{
    btnTbl.className = 'chip text-xs selected';
    btnCrd.className = 'chip text-xs';
    cCrd.classList.add('hidden');
    cTbl.classList.remove('hidden');
  }}
}}

function loadSites(){{
  var tbody = document.getElementById('sites-tbody');
  tbody.innerHTML = '<tr><td colspan="5" class="text-center p24 text-muted">Memuat data vhost Nginx...</td></tr>';

  fetch('{base}/api/nginx/sites')
    .then(r => r.json())
    .then(res => {{
      if (!res.ok) {{
        tbody.innerHTML = '<tr><td colspan="5" class="text-center p24 text-danger">Gagal: ' + res.error + '</td></tr>';
        return;
      }}
      allSitesList = res.data || [];
      document.getElementById('sites-count').textContent = allSitesList.length + ' Situs Aktif';

      var total = allSitesList.length;
      var proxyCount = allSitesList.filter(s => s.proxy).length;
      var staticCount = total - proxyCount;
      document.getElementById('stat-total-sites').textContent = total;
      document.getElementById('stat-proxy-sites').textContent = proxyCount;
      document.getElementById('stat-static-sites').textContent = staticCount;

      renderSitesView(allSitesList);
    }})
    .catch(err => {{
      tbody.innerHTML = '<tr><td colspan="5" class="text-center p24 text-danger">Error: ' + err + '</td></tr>';
    }});
}}

function escapeHtml(text){{
  var map = {{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }};
  return String(text || '').replace(/[&<>"']/g, function(m){{ return map[m]; }});
}}

// Helper bind click listener by ID
function bind(id, fn){{
  var el = document.getElementById(id);
  if (el) el.addEventListener('click', fn);
}}

// Bind static header & modal buttons
bind('btn-nginx-test', testNginxConfig);
bind('btn-nginx-reload', reloadNginxService);
bind('btn-nginx-refresh', loadSites);
bind('btn-nginx-add', openAddModal);
bind('btn-close-add', closeAddModal);
bind('btn-cancel-add', closeAddModal);
bind('btn-save-site', submitAddSite);
bind('btn-close-edit', closeEditModal);
bind('btn-cancel-edit', closeEditModal);
bind('btn-save-vhost', submitSaveVhost);
bind('btn-close-logs', closeLogsModal);
bind('btn-cancel-logs', closeLogsModal);
bind('btn-refresh-logs', refreshCurrentLogs);
bind('btn-add-www', addWwwAlias);
bind('tab-log-access', function(){{ selectLogTab('access'); }});
bind('tab-log-error', function(){{ selectLogTab('error'); }});

bind('view-mode-table', function(){{ setViewMode('table'); }});
bind('view-mode-cards', function(){{ setViewMode('cards'); }});

var sSearch = document.getElementById('site-search');
if (sSearch) sSearch.addEventListener('input', filterSites);

var aDomain = document.getElementById('add-domain');
if (aDomain) aDomain.addEventListener('input', autoSuggestAlias);

// Template chip listeners
document.addEventListener('click', function(e){{
  var tplBtn = e.target.closest('[data-tpl]');
  if (tplBtn) {{
    selectTemplate(tplBtn.getAttribute('data-tpl'));
    return;
  }}
  var snipBtn = e.target.closest('[data-snip]');
  if (snipBtn) {{
    insertSnippet(snipBtn.getAttribute('data-snip'));
    return;
  }}
  var confBtn = e.target.closest('[data-conf]');
  if (confBtn) {{
    openEditModal(confBtn.getAttribute('data-conf'));
    return;
  }}
  var logBtn = e.target.closest('[data-log]');
  if (logBtn) {{
    openLogsModal(logBtn.getAttribute('data-log'));
    return;
  }}
  var delBtn = e.target.closest('[data-del]');
  if (delBtn) {{
    deleteSite(delBtn.getAttribute('data-del'));
    return;
  }}
}});

// Shortcut Ctrl+S in editor textarea
document.addEventListener('keydown', function(e){{
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {{
    var editModal = document.getElementById('modal-edit');
    if (editModal && !editModal.classList.contains('hidden')) {{
      e.preventDefault();
      submitSaveVhost();
    }}
  }}
}});

loadSites();
}})();
</script>
"""
    return layout.shell(sess, app, "web", "Websites & Vhosts",
                        "Kelola domain web, reverse proxy Next.js/Node, dan konfigurasi Nginx",
                        html, t)