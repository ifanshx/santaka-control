"""Halaman Jadwal: crontab editor + timer systemd."""
from ui import components as C
from ui import layout

JS = """
<script>
(function(){
  var T = window.SC;
  var ta = document.getElementById('cr-text');

  function paint(j){
    ta.value = j.crontab || '';
    var ts = j.timers || [];
    var countEl = document.getElementById('timers-count');
    if (countEl) countEl.textContent = ts.length + ' Timer Aktif';

    document.getElementById('cr-tm').innerHTML = ts.length ? ts.map(function(x){
      return '<tr>' +
        '<td class="mono text-xs text-primary font-bold">' + T.esc(x.next || '—') + '</td>' +
        '<td><span class="mono text-main font-bold">' + T.esc(x.unit) + '</span></td>' +
      '</tr>';
    }).join('') : '<tr><td colspan="2" class="tc dim p24">Tidak ada timer systemd aktif.</td></tr>';
  }

  function load(){
    fetch((T && T.url ? T.url('/api/cron') : '/api/cron'))
      .then(r => r.json())
      .then(function(res){ paint(res.data || res); })
      .catch(function(e){ if (T && T.toast) T.toast('Gagal', e.message, 'err'); });
  }

  function saveCrontab(){
    T.confirmDanger({
      title: 'Simpan Crontab Sistem',
      body: 'Crontab root akan diperbarui. Pastikan sintaks jadwal cron (menit jam tgl bln hari) valid.',
      ok: 'Simpan Crontab'
    }).then(function(ok){
      if (!ok) return;
      var b = document.getElementById('cr-save');
      if (T && T.busy) T.busy(b, true);
      fetch((T && T.url ? T.url('/api/cron/action') : '/api/cron/action'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF': document.querySelector('meta[name="csrf"]')?.content || '' },
        body: JSON.stringify({op:'save', crontab:ta.value})
      })
      .then(r => r.json())
      .then(function(j){
        if (T && T.toast) T.toast('Berhasil', j.message || 'Crontab disimpan', 'ok');
        load();
      })
      .catch(function(e){ if (T && T.toast) T.toast('Gagal', e.message, 'err'); })
      .finally(function(){ if (T && T.busy) T.busy(b, false); });
    });
  }

  function insertCronSnippet(snippet){
    var nl = String.fromCharCode(10);
    var pos = ta.selectionStart || ta.value.length;
    ta.value = ta.value.substring(0, pos) + nl + snippet + nl + ta.value.substring(pos);
    if (T && T.toast) T.toast('Disisipkan', 'Snippet cron disisipkan ke editor', 'info');
  }

  document.addEventListener('click', function(e){
    var snipBtn = e.target.closest('[data-cronsnip]');
    if (snipBtn){
      var type = snipBtn.getAttribute('data-cronsnip');
      if (type === 'backup') insertCronSnippet('0 3 * * * /usr/local/sbin/server-backup.sh >/dev/null 2>&1');
      if (type === 'drop') insertCronSnippet('0 4 * * * echo 3 > /proc/sys/vm/drop_caches');
      if (type === 'fstrim') insertCronSnippet('0 2 * * 0 fstrim -av >/dev/null 2>&1');
    }
  });

  var saveBtn = document.getElementById('cr-save');
  if (saveBtn) saveBtn.addEventListener('click', saveCrontab);

  var relBtn = document.getElementById('cr-reload');
  if (relBtn) relBtn.addEventListener('click', load);

  document.addEventListener('keydown', function(e){
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      saveCrontab();
    }
  });

  load();
})();
</script>
"""


def render(req, app, sess, qs, t):
    editor_col = f"""
<div class="card p0 overflow-hidden flex-1" style="min-width:320px;">
  <div class="card-header p16 border-b row space-between align-center flex-wrap gap8">
    <div class="row gap8 align-center">
      <span class="metric-icon">{C.icon("cron", 15)}</span>
      <h3 class="card-title text-sm m0">EDITOR ROOT CRONTAB (/var/spool/cron/crontabs/root)</h3>
    </div>
    <div class="row gap8 align-center">
      <button type="button" class="btn btn-outline sm" id="cr-reload">{C.icon("refresh", 13)} Segarkan</button>
      <button type="button" class="btn btn-primary sm" id="cr-save">Simpan Crontab</button>
    </div>
  </div>
  <div class="p16">
    <div class="row gap6 align-center flex-wrap mb8">
      <span class="text-xs text-muted bold">PRESET SNIPPET:</span>
      <button type="button" class="chip text-xs" data-cronsnip="backup">+ Backup Harian (03:00)</button>
      <button type="button" class="chip text-xs" data-cronsnip="drop">+ Bersihkan Cache RAM (04:00)</button>
      <button type="button" class="chip text-xs" data-cronsnip="fstrim">+ TRIM Mingguan (02:00 Min)</button>
    </div>
    <textarea id="cr-text" class="code-editor mono text-xs p16 m0" rows="18" spellcheck="false"
      style="width:100%;background:#0B0F17;color:#E2E8F0;border-radius:var(--radius-md);border:1px solid var(--border);line-height:1.6;"></textarea>
    <div class="row space-between align-center mt8">
      <span class="text-xs text-muted">Format: menit (0-59) jam (0-23) hari (1-31) bulan (1-12) hari_minggu (0-7) perintah</span>
      <span class="text-xs text-muted">Shortcut: <kbd class="kbd-hint">Ctrl + S</kbd></span>
    </div>
  </div>
</div>
"""

    timers_col = f"""
<div class="card p0 overflow-hidden" style="width:420px;min-width:320px;">
  <div class="card-header p16 border-b row space-between align-center">
    <h3 class="card-title text-sm m0">TIMER SYSTEMD AKTIF (systemctl list-timers)</h3>
    <span class="badge badge-success text-xs" id="timers-count">Memuat...</span>
  </div>
  <div class="table-responsive"><table class="data-table"><thead><tr>
    <th>JADWAL BERIKUTNYA</th><th>NAMA TIMER UNIT</th>
  </tr></thead><tbody id="cr-tm">
    <tr><td colspan="2" class="tc dim p24">Memuat daftar timer...</td></tr>
  </tbody></table></div>
</div>
"""

    body = '<div class="row gap16 mb24" style="align-items:flex-start;flex-wrap:wrap;">' + editor_col + timers_col + '</div>'
    return layout.shell(sess, app, "cron", "Cron Jobs",
                        "Editor crontab sistem dan pemantau jadwal timer systemd",
                        body + JS, t)
