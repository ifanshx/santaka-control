"""Halaman Berkas: jelajah, editor kode, unggah, unduh, buat berkas/folder, ubah nama, hapus."""
from ui import components as C
from ui import layout


def render(req, app, sess, qs, t):
    csrf = req.csrf_token(sess)
    base = layout.BASE_PATH
    icons = ("files", "disk", "terminal", "web")
    roots = [str(r) for r in (app.cfg.get("roots") or []) if str(r).startswith("/")]
    root_chips = "".join(
        '<button type="button" class="chip text-xs" data-jump="%s">%s %s</button>'
        % (C.e(path), C.icon(icons[i % len(icons)], 12), C.e(path))
        for i, path in enumerate(roots[:4])
    )

    html = f"""
<!-- BARIS LOMPAT CEPAT KE ROOT DIREKTORI -->
<div class="card mb16 p12">
  <div class="row space-between align-center flex-wrap gap8">
    <div class="row gap8 align-center flex-wrap">
      <span class="text-xs text-muted bold mr8">LOMPAT ROOT:</span>
      {root_chips}
    </div>
    <div class="row gap8 align-center">
      <span class="text-xs text-muted font-mono" id="f-space">Memuat kapasitas...</span>
    </div>
  </div>
</div>

<!-- BREADCRUMB & JALUR NAVIGASI -->
<div class="row space-between align-center mb16 flex-wrap gap8">
  <div class="flex-1" id="f-crumbs"><span class="dim">Memuat jalur...</span></div>
  <button type="button" class="btn btn-outline sm" id="btn-copy-path" title="Salin path direktori saat ini ke clipboard">{C.icon("edit", 13)} Salin Path</button>
</div>

<!-- TABEL BERKAS & DIREKTORI DENGAN TOOLBAR -->
<div class="card mb24 p0 overflow-hidden">
  <div class="card-header p16 border-b row space-between align-center flex-wrap gap8">
    <div class="row gap12 align-center">
      <h3 class="card-title text-sm m0">DAFTAR BERKAS &amp; DIREKTORI</h3>
      <span class="badge badge-success text-xs" id="items-count">Memuat...</span>
    </div>
    <div class="row gap8 align-center flex-wrap">
      <div class="srch" style="max-width: 220px;">
        <span class="ic">{C.icon("search", 13)}</span>
        <input type="text" id="file-search" placeholder="Cari nama berkas..." class="form-input text-xs" style="padding-left: 32px; height: 32px;" />
      </div>
      <button type="button" class="btn btn-outline sm" id="f-mkdir">{C.icon("plus", 13)} Folder Baru</button>
      <button type="button" class="btn btn-outline sm" id="f-touch">{C.icon("plus", 13)} Berkas Baru</button>
      <label class="btn btn-primary sm" for="f-upload" style="cursor: pointer; margin: 0;">
        {C.icon("up", 13)} Unggah
      </label>
      <input type="file" id="f-upload" multiple class="hidden" />
      <button type="button" class="btn btn-outline sm" id="f-reload" title="Muat ulang direktori">{C.icon("refresh", 13)} Segarkan</button>
    </div>
  </div>
  <div class="table-responsive">
    <table class="data-table" id="table-files">
      <thead>
        <tr>
          <th>NAMA BERKAS / FOLDER</th>
          <th class="num">UKURAN</th>
          <th class="num">WAKTU DIUBAH</th>
          <th>IZIN</th>
          <th style="text-align: right;">AKSI TINDAKAN</th>
        </tr>
      </thead>
      <tbody id="f-rows">
        <tr><td colspan="5" class="text-center p24 text-muted">Memuat daftar berkas...</td></tr>
      </tbody>
    </table>
  </div>
</div>

<!-- DROPZONE UNGGAH BERKAS -->
<div class="drop mb24" id="f-drop">
  <div class="row gap8 align-center justify-center">
    <span class="text-primary">{C.icon("up", 20)}</span>
    <span>Tarik &amp; jatuhkan berkas ke sini untuk mengunggah langsung ke folder ini</span>
  </div>
</div>

<!-- MODAL FOLDER BARU -->
<div class="modal-overlay hidden" id="modal-mkdir">
  <div class="modal-box card" style="max-width: 480px;">
    <div class="modal-header row space-between align-center border-b p16">
      <h3 class="card-title text-sm m0">Buat Folder Baru</h3>
      <button type="button" class="btn-close" id="btn-close-mkdir">&times;</button>
    </div>
    <div class="modal-body p16">
      <div class="form-group mb16">
        <label class="form-label">Nama Folder *</label>
        <input type="text" id="input-mkdir-name" class="form-input mono" placeholder="contoh: uploads atau public_html" />
      </div>
    </div>
    <div class="modal-footer row justify-end gap8 border-t p16">
      <button type="button" class="btn btn-outline" id="btn-cancel-mkdir">Batal</button>
      <button type="button" class="btn btn-primary" id="btn-submit-mkdir">Buat Folder</button>
    </div>
  </div>
</div>

<!-- MODAL BERKAS BARU -->
<div class="modal-overlay hidden" id="modal-touch">
  <div class="modal-box card" style="max-width: 480px;">
    <div class="modal-header row space-between align-center border-b p16">
      <h3 class="card-title text-sm m0">Buat Berkas Teks Baru</h3>
      <button type="button" class="btn-close" id="btn-close-touch">&times;</button>
    </div>
    <div class="modal-body p16">
      <div class="form-group mb16">
        <label class="form-label">Nama Berkas *</label>
        <input type="text" id="input-touch-name" class="form-input mono" placeholder="contoh: index.php atau .env atau config.json" />
      </div>
    </div>
    <div class="modal-footer row justify-end gap8 border-t p16">
      <button type="button" class="btn btn-outline" id="btn-cancel-touch">Batal</button>
      <button type="button" class="btn btn-primary" id="btn-submit-touch">Buat Berkas</button>
    </div>
  </div>
</div>

<!-- MODAL UBAH NAMA (RENAME) -->
<div class="modal-overlay hidden" id="modal-rename">
  <div class="modal-box card" style="max-width: 480px;">
    <div class="modal-header row space-between align-center border-b p16">
      <h3 class="card-title text-sm m0">Ubah Nama Berkas / Folder</h3>
      <button type="button" class="btn-close" id="btn-close-rename">&times;</button>
    </div>
    <div class="modal-body p16">
      <div class="form-group mb16">
        <label class="form-label">Nama Baru *</label>
        <input type="text" id="input-rename-name" class="form-input mono" />
      </div>
    </div>
    <div class="modal-footer row justify-end gap8 border-t p16">
      <button type="button" class="btn btn-outline" id="btn-cancel-rename">Batal</button>
      <button type="button" class="btn btn-primary" id="btn-submit-rename">Simpan Perubahan</button>
    </div>
  </div>
</div>

<!-- MODAL EDITOR BERKAS TEKS (BUILT-IN CODE VIEWER & EDITOR) -->
<div class="modal-overlay hidden" id="modal-edit-file">
  <div class="modal-box modal-lg card" style="max-width: 860px;">
    <div class="modal-header row space-between align-center border-b p16">
      <div class="row gap8 align-center">
        <span class="metric-icon">{C.icon("edit", 15)}</span>
        <div>
          <h3 class="card-title text-sm m0">Editor Berkas: <span id="file-editor-title" class="mono text-primary font-bold"></span></h3>
          <p class="text-xs text-muted m0 mt4 mono" id="file-editor-path"></p>
        </div>
      </div>
      <button type="button" class="btn-close" id="btn-close-file-editor">&times;</button>
    </div>
    <div class="modal-body p16">
      <textarea id="file-editor-content" class="code-editor mono text-xs p12" rows="20" spellcheck="false" style="width:100%;background:#0B0F17;color:#E2E8F0;border-radius:var(--radius-md);border:1px solid var(--border);line-height:1.6;"></textarea>
      <div id="file-editor-msg" class="alert-box mt8 hidden"></div>
    </div>
    <div class="modal-footer row space-between align-center border-t p16">
      <span class="text-xs text-muted">Shortcut: <kbd class="kbd-hint">Ctrl + S</kbd> untuk simpan</span>
      <div class="row gap8">
        <button type="button" class="btn btn-outline" id="btn-cancel-file-editor">Tutup</button>
        <button type="button" class="btn btn-primary" id="btn-save-file-editor">Simpan Berkas</button>
      </div>
    </div>
  </div>
</div>

<script>
(function(){{
var cur = '';
var currentEditingPath = '';
var oldRenameName = '';
var allItemsList = [];

var rows = document.getElementById('f-rows');
var crumbs = document.getElementById('f-crumbs');
var upIn = document.getElementById('f-upload');
var drop = document.getElementById('f-drop');

function fmtPath(p){{
  var parts = p.split('/').filter(Boolean);
  var html = '<a href="#" class="bc-pill" data-go="/">/</a>';
  var acc = '';
  parts.forEach(function(seg){{
    acc += '/' + seg;
    html += ' <span class="text-muted">/</span> <a href="#" class="bc-pill" data-go="' + escapeHtml(acc) + '">' + escapeHtml(seg) + '</a>';
  }});
  return html;
}}

function getFileIcon(name, isDir){{
  if (isDir) return '&#128193;';
  var ext = name.split('.').pop().toLowerCase();
  if (['py','js','ts','php','sh','bash'].indexOf(ext) > -1) return '&#128220;';
  if (['json','yml','yaml','conf','ini','env','xml','sql'].indexOf(ext) > -1) return '&#9881;&#65039;';
  if (['tar','gz','tgz','zip','7z','rar','bz2'].indexOf(ext) > -1) return '&#128230;';
  if (['html','htm','css','svg'].indexOf(ext) > -1) return '&#127760;';
  return '&#128196;';
}}

function isEditable(name){{
  var ext = name.split('.').pop().toLowerCase();
  var editableExts = ['txt','md','json','yml','yaml','conf','ini','env','py','js','ts','php','sh','bash','css','html','htm','sql','xml','log'];
  return editableExts.indexOf(ext) > -1 || name.indexOf('.') === -1;
}}

function paint(j){{
  cur = j.path;
  crumbs.innerHTML = fmtPath(cur);
  var space = j.space || {{}};
  var freeGb = (space.free / 1073741824).toFixed(1);
  var totGb = (space.total / 1073741824).toFixed(1);
  document.getElementById('f-space').textContent = freeGb + ' GB bebas dari ' + totGb + ' GB';

  allItemsList = j.items || [];
  document.getElementById('items-count').textContent = allItemsList.length + ' Item';
  renderTable(allItemsList, j.parent);
}}

function renderTable(items, parent){{
  var html = '';
  if (parent && parent !== cur){{
    html += '<tr class="parent-row"><td colspan="5">' +
      '<a href="#" class="row gap6 align-center text-primary font-bold" data-go="' + escapeHtml(parent) + '">' +
      '<span>&larr;</span> <span>Induk Folder (' + escapeHtml(parent) + ')</span></a>' +
      '</td></tr>';
  }}

  items.forEach(function(it){{
    var iconGlyph = getFileIcon(it.name, it.dir);
    var nameLink = it.dir
      ? '<a href="#" class="mono font-bold text-main" data-go="' + escapeHtml(it.path) + '">' + escapeHtml(it.name) + '</a>'
      : (isEditable(it.name)
         ? '<a href="#" class="mono font-bold text-main" data-edit="' + escapeHtml(it.path) + '" title="Klik untuk edit berkas">' + escapeHtml(it.name) + '</a>'
         : '<span class="mono font-bold text-main">' + escapeHtml(it.name) + '</span>');

    var linkBadge = it.link ? ' <span class="tag nu text-xs">tautan</span>' : '';

    var sizeStr = it.dir ? '—' : formatBytes(it.size);
    var timeStr = formatAgo(it.mtime);
    var modeStr = it.mode ? '<span class="mono text-muted text-xs">' + escapeHtml(it.mode) + '</span>' : '—';

    var actions = '';
    if (it.dir) {{
      actions += '<button type="button" class="btn btn-sm btn-outline" data-go="' + escapeHtml(it.path) + '">Buka</button> ';
    }} else {{
      if (isEditable(it.name)) {{
        actions += '<button type="button" class="btn btn-sm btn-primary" data-edit="' + escapeHtml(it.path) + '" title="Edit di editor web">Edit</button> ';
      }}
      actions += '<a href="' + (window.SC ? window.SC.url('/api/files/download?path=' + encodeURIComponent(it.path)) : '/api/files/download?path=' + encodeURIComponent(it.path)) + '" class="btn btn-sm btn-outline" title="Unduh berkas">Unduh ↗</a> ';
    }}
    actions += '<button type="button" class="btn btn-sm btn-outline" data-rn="' + escapeHtml(it.name) + '" title="Ubah nama">Ubah</button> ';
    actions += '<button type="button" class="btn btn-sm btn-danger" data-rm="' + escapeHtml(it.name) + '" data-dir="' + (it.dir?1:0) + '" title="Hapus">Hapus</button>';

    html += '<tr>' +
      '<td><div class="row gap8 align-center"><span>' + iconGlyph + '</span> ' + nameLink + linkBadge + '</div></td>' +
      '<td class="num mono text-xs">' + sizeStr + '</td>' +
      '<td class="num text-xs text-muted">' + timeStr + '</td>' +
      '<td>' + modeStr + '</td>' +
      '<td style="text-align: right;" class="row justify-end gap6 align-center flex-wrap">' + actions + '</td>' +
    '</tr>';
  }});

  if (!html) html = '<tr><td colspan="5" class="text-center p24 text-muted">Folder ini kosong.</td></tr>';
  rows.innerHTML = html;
}}

function formatBytes(n){{
  n = Number(n) || 0;
  var u = ['B', 'KB', 'MB', 'GB', 'TB'], i = 0;
  while (n >= 1024 && i < u.length - 1) {{ n /= 1024; i++; }}
  return (i === 0 ? n : n.toFixed(1)) + ' ' + u[i];
}}

function formatAgo(ts){{
  if (!ts) return '—';
  var s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return s + 's lalu';
  if (s < 3600) return Math.floor(s / 60) + 'm lalu';
  if (s < 86400) return Math.floor(s / 3600) + 'j lalu';
  return Math.floor(s / 86400) + 'h lalu';
}}

function filterFiles(){{
  var q = (document.getElementById('file-search').value || '').trim().toLowerCase();
  var filtered = allItemsList.filter(function(it){{
    return !q || (it.name || '').toLowerCase().indexOf(q) > -1;
  }});
  renderTable(filtered, null);
}}

function load(path){{
  var urlPath = window.SC ? window.SC.url('/api/files?path=' + encodeURIComponent(path || '')) : '/api/files?path=' + encodeURIComponent(path || '');
  fetch(urlPath, {{ credentials: 'same-origin' }})
    .then(r => r.json())
    .then(res => {{
      if (res.ok) {{
        paint(res.data || res);
      }} else {{
        if (window.SC && window.SC.toast) window.SC.toast('Gagal', res.error, 'err');
      }}
    }})
    .catch(e => {{
      if (window.SC && window.SC.toast) window.SC.toast('Gagal', String(e), 'err');
    }});
}}

// Folder Baru Modal
function openMkdirModal(){{
  document.getElementById('input-mkdir-name').value = '';
  document.getElementById('modal-mkdir').classList.remove('hidden');
  document.getElementById('input-mkdir-name').focus();
}}
function closeMkdirModal(){{ document.getElementById('modal-mkdir').classList.add('hidden'); }}

function submitMkdir(){{
  var name = document.getElementById('input-mkdir-name').value.trim();
  if (!name) return;
  fetch(window.SC.url('/api/files/mkdir'), {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-CSRF': '{csrf}' }},
    body: JSON.stringify({{ path: cur, name: name }})
  }})
  .then(r => r.json())
  .then(res => {{
    if (res.ok) {{
      closeMkdirModal();
      window.SC.toast('Berhasil', 'Folder ' + name + ' dibuat', 'ok');
      load(cur);
    }} else {{
      window.SC.toast('Gagal', res.error, 'err');
    }}
  }})
  .catch(e => window.SC.toast('Error', String(e), 'err'));
}}

// Berkas Baru Modal
function openTouchModal(){{
  document.getElementById('input-touch-name').value = '';
  document.getElementById('modal-touch').classList.remove('hidden');
  document.getElementById('input-touch-name').focus();
}}
function closeTouchModal(){{ document.getElementById('modal-touch').classList.add('hidden'); }}

function submitTouch(){{
  var name = document.getElementById('input-touch-name').value.trim();
  if (!name) return;
  fetch(window.SC.url('/api/files/touch'), {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-CSRF': '{csrf}' }},
    body: JSON.stringify({{ path: cur, name: name }})
  }})
  .then(r => r.json())
  .then(res => {{
    if (res.ok) {{
      closeTouchModal();
      window.SC.toast('Berhasil', 'Berkas ' + name + ' dibuat', 'ok');
      load(cur);
    }} else {{
      window.SC.toast('Gagal', res.error, 'err');
    }}
  }})
  .catch(e => window.SC.toast('Error', String(e), 'err'));
}}

// Rename Modal
function openRenameModal(name){{
  oldRenameName = name;
  document.getElementById('input-rename-name').value = name;
  document.getElementById('modal-rename').classList.remove('hidden');
  document.getElementById('input-rename-name').focus();
}}
function closeRenameModal(){{ document.getElementById('modal-rename').classList.add('hidden'); }}

function submitRename(){{
  var newName = document.getElementById('input-rename-name').value.trim();
  if (!newName || newName === oldRenameName) {{ closeRenameModal(); return; }}
  fetch(window.SC.url('/api/files/rename'), {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-CSRF': '{csrf}' }},
    body: JSON.stringify({{ path: cur, name: oldRenameName, to: newName }})
  }})
  .then(r => r.json())
  .then(res => {{
    if (res.ok) {{
      closeRenameModal();
      window.SC.toast('Berhasil', 'Nama diubah jadi ' + newName, 'ok');
      load(cur);
    }} else {{
      window.SC.toast('Gagal', res.error, 'err');
    }}
  }})
  .catch(e => window.SC.toast('Error', String(e), 'err'));
}}

// File Editor Modal
function openFileEditor(filePath){{
  currentEditingPath = filePath;
  var fileName = filePath.split('/').pop();
  document.getElementById('file-editor-title').textContent = fileName;
  document.getElementById('file-editor-path').textContent = filePath;
  document.getElementById('file-editor-content').value = 'Memuat isi berkas...';
  document.getElementById('file-editor-msg').classList.add('hidden');
  document.getElementById('modal-edit-file').classList.remove('hidden');

  fetch(window.SC.url('/api/files/read?path=' + encodeURIComponent(filePath)))
    .then(r => r.json())
    .then(res => {{
      if (res.ok) {{
        var d = res.data || res;
        document.getElementById('file-editor-content').value = d.content || '';
      }} else {{
        window.SC.toast('Gagal', res.error, 'err');
        closeFileEditor();
      }}
    }})
    .catch(e => {{
      window.SC.toast('Error', String(e), 'err');
    }});
}}

function closeFileEditor(){{
  document.getElementById('modal-edit-file').classList.add('hidden');
}}

function saveFileContent(){{
  if (!currentEditingPath) return;
  var content = document.getElementById('file-editor-content').value;
  var btn = document.getElementById('btn-save-file-editor');
  btn.disabled = true;

  fetch(window.SC.url('/api/files/save'), {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-CSRF': '{csrf}' }},
    body: JSON.stringify({{ path: currentEditingPath, content: content }})
  }})
  .then(r => r.json())
  .then(res => {{
    if (res.ok) {{
      window.SC.toast('Tersimpan', 'Berkas berhasil disimpan', 'ok');
      setTimeout(closeFileEditor, 600);
      load(cur);
    }} else {{
      window.SC.toast('Gagal Simpan', res.error, 'err');
    }}
  }})
  .catch(e => window.SC.toast('Error', String(e), 'err'))
  .finally(() => btn.disabled = false);
}}

function deleteItem(name, isDir){{
  window.SC.confirmDanger({{
    title: 'Hapus ' + (isDir ? 'Folder' : 'Berkas'),
    body: '<b>' + escapeHtml(name) + '</b> akan dihapus secara permanen dari server. Tindakan ini tidak dapat dibatalkan.',
    ok: 'Hapus Permanen',
    phrase: isDir ? name : null
  }}).then(function(ok){{
    if (!ok) return;
    fetch(window.SC.url('/api/files/delete'), {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json', 'X-CSRF': '{csrf}' }},
      body: JSON.stringify({{ path: cur, name: name, recursive: isDir ? 1 : 0 }})
    }})
    .then(r => r.json())
    .then(res => {{
      if (res.ok) {{
        window.SC.toast('Dihapus', name + ' berhasil dihapus', 'ok');
        load(cur);
      }} else {{
        window.SC.toast('Gagal Hapus', res.error, 'err');
      }}
    }})
    .catch(e => window.SC.toast('Error', String(e), 'err'));
  }});
}}

function upload(files){{
  if (!files || !files.length) return;
  var fd = new FormData();
  for (var i = 0; i < files.length; i++) fd.append('file', files[i]);
  window.SC.toast('Mengunggah', files.length + ' berkas...', 'info');

  fetch(window.SC.url('/api/upload?path=' + encodeURIComponent(cur)), {{
    method: 'POST',
    body: fd,
    credentials: 'same-origin',
    headers: {{ 'X-CSRF': '{csrf}' }}
  }})
  .then(r => r.json())
  .then(j => {{
    if (j.error) throw new Error(j.error);
    window.SC.toast('Berhasil', (j.count || files.length) + ' berkas diunggah!', 'ok');
    load(cur);
  }})
  .catch(e => window.SC.toast('Gagal Unggah', e.message, 'err'));
}}

function copyCurrentPath(){{
  if (!navigator.clipboard) return;
  navigator.clipboard.writeText(cur || '/')
    .then(() => window.SC.toast('Tersalin', 'Path direktori disalin ke clipboard: ' + cur, 'ok'))
    .catch(e => alert('Gagal salin: ' + e));
}}

function escapeHtml(text){{
  var map = {{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }};
  return String(text || '').replace(/[&<>"']/g, function(m) {{ return map[m]; }});
}}

// Helper bind click listener by ID
function bind(id, fn){{
  var el = document.getElementById(id);
  if (el) el.addEventListener('click', fn);
}}

bind('f-mkdir', openMkdirModal);
bind('f-touch', openTouchModal);
bind('f-reload', function(){{ load(cur); }});
bind('btn-close-mkdir', closeMkdirModal);
bind('btn-cancel-mkdir', closeMkdirModal);
bind('btn-submit-mkdir', submitMkdir);
bind('btn-close-touch', closeTouchModal);
bind('btn-cancel-touch', closeTouchModal);
bind('btn-submit-touch', submitTouch);
bind('btn-close-rename', closeRenameModal);
bind('btn-cancel-rename', closeRenameModal);
bind('btn-submit-rename', submitRename);
bind('btn-close-file-editor', closeFileEditor);
bind('btn-cancel-file-editor', closeFileEditor);
bind('btn-save-file-editor', saveFileContent);
bind('btn-copy-path', copyCurrentPath);

var sInput = document.getElementById('file-search');
if (sInput) sInput.addEventListener('input', filterFiles);

upIn.addEventListener('change', function(){{ upload(upIn.files); upIn.value = ''; }});

['dragenter','dragover'].forEach(function(ev){{
  drop.addEventListener(ev, function(e){{ e.preventDefault(); drop.classList.add('over'); }});
}});
['dragleave','drop'].forEach(function(ev){{
  drop.addEventListener(ev, function(e){{ e.preventDefault(); drop.classList.remove('over'); }});
}});
drop.addEventListener('drop', function(e){{
  e.preventDefault();
  drop.classList.remove('over');
  if (e.dataTransfer && e.dataTransfer.files) upload(e.dataTransfer.files);
}});

// Global click event delegation for folder navigation, editing, rename, delete
document.addEventListener('click', function(e){{
  var jumpBtn = e.target.closest('[data-jump]');
  if (jumpBtn) {{
    e.preventDefault();
    load(jumpBtn.getAttribute('data-jump'));
    return;
  }}
  var goEl = e.target.closest('[data-go]');
  if (goEl) {{
    e.preventDefault();
    load(goEl.getAttribute('data-go'));
    return;
  }}
  var editEl = e.target.closest('[data-edit]');
  if (editEl) {{
    e.preventDefault();
    openFileEditor(editEl.getAttribute('data-edit'));
    return;
  }}
  var rnBtn = e.target.closest('[data-rn]');
  if (rnBtn) {{
    openRenameModal(rnBtn.getAttribute('data-rn'));
    return;
  }}
  var rmBtn = e.target.closest('[data-rm]');
  if (rmBtn) {{
    var name = rmBtn.getAttribute('data-rm');
    var isDir = rmBtn.getAttribute('data-dir') === '1';
    deleteItem(name, isDir);
    return;
  }}
}});

// Shortcut Ctrl+S in file editor
document.addEventListener('keydown', function(e){{
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {{
    var editModal = document.getElementById('modal-edit-file');
    if (editModal && !editModal.classList.contains('hidden')) {{
      e.preventDefault();
      saveFileContent();
    }}
  }}
}});

load('');
}})();
</script>
"""
    return layout.shell(sess, app, "files", "File Explorer",
                        "Penjelajah berkas server, editor kode, dan manajemen storage",
                        html, t)
