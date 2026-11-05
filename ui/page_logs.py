"""Halaman Log: journal per unit, dmesg kernel, dan log akses web."""
from ui import components as C
from ui import layout


JS = """
<script>
(function(){
  var T = window.SC;
  var out = document.getElementById('l-out');
  var sel = document.getElementById('l-unit');
  var src = document.getElementById('l-source');
  var ln = document.getElementById('l-lines');
  var q = document.getElementById('l-q');
  var timer = null;

  function render(text){
    var qq = (q.value || '').toLowerCase().trim();
    var lines = (text || '').split('\\n');
    if (qq) lines = lines.filter(function(l){ return l.toLowerCase().indexOf(qq) > -1; });
    out.textContent = lines.join('\\n') || '(tidak ada baris yang cocok dengan kata kunci)';
    out.scrollTop = out.scrollHeight;
  }

  function fetchLog(){
    var body = {source: src.value, unit: sel.value, lines: ln.value};
    if (T && T.busy) T.busy(document.getElementById('l-go'), true);
    fetch((T && T.url ? T.url('/api/logs') : '/api/logs'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF': document.querySelector('meta[name="csrf"]')?.content || '' },
      body: JSON.stringify(body)
    })
    .then(r => r.json())
    .then(function(j){ render(j.log || j.data?.log || ''); })
    .catch(function(e){ out.textContent = 'Gagal memuat log: ' + e.message; })
    .finally(function(){ if (T && T.busy) T.busy(document.getElementById('l-go'), false); });
  }

  function toggleSource(){
    var isUnit = src.value === 'unit';
    sel.disabled = !isUnit;
    var uWrap = document.getElementById('l-unit-wrap');
    if (uWrap) uWrap.style.opacity = isUnit ? 1 : .45;
  }

  document.getElementById('l-go').onclick = fetchLog;
  document.getElementById('l-q').addEventListener('input', function(){
    if (window.__lastLog) render(window.__lastLog);
  });
  src.onchange = toggleSource;

  var followBtn = document.getElementById('l-follow');
  if (followBtn) {
    followBtn.onclick = function(){
      if (timer){
        clearInterval(timer); timer = null;
        followBtn.className = 'btn btn-sm btn-outline';
        followBtn.textContent = 'Ikuti Live';
        if (T && T.toast) T.toast('Live Tail', 'Streaming log dihentikan', 'info');
      } else {
        timer = setInterval(fetchLog, 3000);
        followBtn.className = 'btn btn-sm btn-primary';
        followBtn.textContent = 'Berhenti';
        if (T && T.toast) T.toast('Live Tail', 'Memantau log setiap 3 detik', 'ok');
        fetchLog();
      }
    };
  }

  var copyBtn = document.getElementById('l-copy');
  if (copyBtn) {
    copyBtn.onclick = function(){
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(out.textContent || '')
        .then(() => { if (T && T.toast) T.toast('Tersalin', 'Log disalin ke clipboard', 'ok'); })
        .catch(e => alert('Gagal salin: ' + e));
    };
  }

  var clearBtn = document.getElementById('l-clear');
  if (clearBtn) {
    clearBtn.onclick = function(){
      out.textContent = '(tampilan log dibersihkan)';
    };
  }

  var orig = render;
  render = function(text){ window.__lastLog = text; orig(text); };

  // isi daftar unit dari API layanan
  fetch((T && T.url ? T.url('/api/services') : '/api/services'))
    .then(r => r.json())
    .then(function(j){
      (j.items || j.data?.items || []).forEach(function(u){
        var o = document.createElement('option');
        o.value = u.unit; o.textContent = u.unit;
        sel.appendChild(o);
      });
      if (sel.options.length > 1) sel.selectedIndex = 1;
    }).catch(function(){});

  toggleSource();
  fetchLog();
})();
</script>
"""


def render(req, app, sess, qs, t):
    toolbar = f"""
<div class="card mb16 p16">
  <div class="row gap12 align-center flex-wrap">
    <div class="field m0" style="min-width:180px;">
      <label class="form-label" for="l-source">Sumber Log</label>
      <select id="l-source" class="form-input text-xs">
        <option value="unit">Layanan (systemd journalctl)</option>
        <option value="dmesg">Kernel Hardware (dmesg)</option>
        <option value="access">Akses Web Server (Nginx)</option>
      </select>
    </div>

    <div class="field m0" id="l-unit-wrap" style="min-width:240px;">
      <label class="form-label" for="l-unit">Nama Layanan</label>
      <select id="l-unit" class="form-input text-xs mono">
        <option value="">(semua unit)</option>
      </select>
    </div>

    <div class="field m0" style="width:110px;">
      <label class="form-label" for="l-lines">Maks Baris</label>
      <input id="l-lines" type="number" value="200" min="10" max="5000" class="form-input text-xs mono" />
    </div>

    <div class="field m0 flex-1" style="min-width:200px;">
      <label class="form-label" for="l-q">Saring Baris (Filter)</label>
      <input id="l-q" type="search" placeholder="kata kunci error, ip, GET..." class="form-input text-xs" />
    </div>

    <div class="row gap8 align-center" style="margin-top: 18px;">
      <button type="button" class="btn btn-primary sm" id="l-go">{C.icon("refresh", 13)} Muat Log</button>
      <button type="button" class="btn btn-outline sm" id="l-follow">Ikuti Live</button>
      <button type="button" class="btn btn-outline sm" id="l-copy" title="Salin seluruh isi log">{C.icon("edit", 13)} Salin</button>
      <button type="button" class="btn btn-outline sm" id="l-clear">{C.icon("trash", 13)} Bersihkan</button>
    </div>
  </div>
</div>
"""

    out = (
        '<div class="card p0 overflow-hidden">'
        '<div class="card-header p12 border-b row space-between align-center">'
        '<span class="text-xs text-muted mono font-bold">TERMINAL OUTPUT VIEWER</span>'
        '<span class="badge badge-success text-xs">READY</span>'
        '</div>'
        '<pre class="code-editor mono text-xs p16 m0" id="l-out" tabindex="0" aria-live="polite" '
        'style="min-height:480px;max-height:640px;overflow-y:auto;background:#0B0F17;color:#E2E8F0;line-height:1.6;white-space:pre-wrap;">%s</pre>'
        '</div>' % C.e(t("lbl.loading"))
    )

    body = toolbar + out
    return layout.shell(sess, app, "logs", "System Logs",
                        "Pembaca log sistem, kernel dmesg, dan layanan systemd",
                        body + JS, t)
