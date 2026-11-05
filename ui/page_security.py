"""Halaman Keamanan: kata sandi, 2FA+QR, kode pemulihan, sesi aktif."""
from ui import components as C
from ui import layout

JS = """
<script>
(function(){
  var T = window.SC;

  function loadSessions(){
    fetch((T && T.url ? T.url('/api/sessions') : '/api/sessions'))
      .then(r => r.json())
      .then(function(j){
        var rows = j.items || j.data?.items || [];
        var countEl = document.getElementById('stat-active-sessions');
        if (countEl) countEl.textContent = rows.length;

        document.getElementById('se-ss').innerHTML = rows.length ? rows.map(function(s){
          return '<tr><td class="mono font-bold">' + T.esc(s.user) + '</td>' +
            '<td data-label="Role"><span class="tag ' + (s.role==='admin'?'pk':'nu') + '">' + T.esc(s.role.toUpperCase()) + '</span></td>' +
            '<td class="mono font-bold text-primary" data-label="IP">' + T.esc(s.ip) + '</td>' +
            '<td class="num text-xs text-muted" data-label="Mulai">' + T.ago(s.created) + '</td>' +
            '<td class="act">' + (s.current
              ? '<span class="badge badge-success text-xs"><span class="pulse-dot green"></span> SESI INI</span>'
              : '<button type="button" class="btn btn-sm btn-danger" data-kill="' + T.esc(s.sid) + '">Cabut</button>') + '</td></tr>';
        }).join('') : '<tr><td colspan="5" class="tc dim p24">Tidak ada sesi aktif tercatat.</td></tr>';
      })
      .catch(function(e){ if (T && T.toast) T.toast('Gagal', e.message, 'err'); });
  }

  function op(body, ok){
    return fetch((T && T.url ? T.url('/api/security/action') : '/api/security/action'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF': document.querySelector('meta[name="csrf"]')?.content || '' },
      body: JSON.stringify(body)
    })
    .then(r => r.json())
    .then(function(j){
      if (!j.ok && j.error) throw new Error(j.error);
      if (T && T.toast) T.toast('Berhasil', j.message || ok || 'Selesai', 'ok');
      return j;
    })
    .catch(function(e){
      if (T && T.toast) T.toast('Gagal', e.message, 'err');
      throw e;
    });
  }

  var pwGo = document.getElementById('pw-go');
  if (pwGo) {
    pwGo.onclick = function(){
      var oldPw = document.getElementById('pw-old').value;
      var newPw = document.getElementById('pw-new').value;
      if (!oldPw || !newPw) {
        if (T && T.toast) T.toast('Validasi', 'Kata sandi lama dan baru wajib diisi!', 'warn');
        return;
      }
      if (newPw.length < 10) {
        if (T && T.toast) T.toast('Validasi', 'Kata sandi baru minimal 10 karakter!', 'warn');
        return;
      }
      T.busy(pwGo, true);
      op({op:'password', old: oldPw, new: newPw})
        .then(function(){
          document.getElementById('pw-old').value = '';
          document.getElementById('pw-new').value = '';
          loadSessions();
        })
        .catch(function(){})
        .finally(function(){ T.busy(pwGo, false); });
    };
  }

  var faStart = document.getElementById('fa-start');
  if (faStart) {
    faStart.onclick = function(){
      T.busy(faStart, true);
      op({op:'2fa_start'}).then(function(j){
        var m = T.modal({
          title: 'Aktifkan Autentikasi 2FA',
          wide: true,
          body: '<p class="mb8 text-sm">Pindai kode QR berikut dengan aplikasi Authenticator (Google Authenticator, Aegis, 1Password), lalu masukkan 6 digit kode yang muncul.</p>' +
                '<div class="row gap16 mb16" style="align-items:flex-start;">' +
                '<div style="background:#fff;padding:8px;border:1px solid var(--border);border-radius:var(--radius-md);display:inline-block;">' +
                  (j.qr || '<span class="text-muted text-xs">QR tidak tersedia</span>') + '</div>' +
                '<div class="flex-1"><div class="field"><label class="form-label">Secret Key (Manual Entry)</label>' +
                '<input type="text" readonly value="' + T.esc(j.secret) + '" class="form-input mono" />' +
                '<span class="text-xs text-muted mt4">Gunakan secret ini jika kamera tidak bisa membaca QR.</span>' +
                '</div></div></div>' +
                '<div class="field"><label class="form-label" for="fa-code">Kode Verifikasi 6 Digit</label>' +
                '<input id="fa-code" class="form-input mono text-sm" maxlength="6" placeholder="000000" inputmode="numeric" autocomplete="one-time-code" /></div>',
          footer: '<button type="button" class="btn btn-outline" data-modal-cancel>Batal</button>' +
                  '<button type="button" class="btn btn-primary" data-modal-confirm>Verifikasi &amp; Aktifkan</button>'
        });
        m.el.querySelector('[data-modal-cancel]').onclick = m.close;
        var inp = m.el.querySelector('#fa-code');
        if (inp) inp.focus();
        m.el.querySelector('[data-modal-confirm]').onclick = function(){
          var code = inp ? inp.value.trim() : '';
          if (!code) return;
          op({op:'2fa_enable', code: code}).then(function(r){
            m.close();
            T.modal({
              title: 'Kode Pemulihan Cadangan (Simpan Aman!)',
              wide: true,
              body: '<p class="mb8 text-sm text-danger font-bold">SIMPAN KODE INI DI TEMPAT AMAN! Setiap kode hanya bisa digunakan sekali bila Anda kehilangan akses authenticator.</p>' +
                    '<pre class="code-editor mono text-xs p12" style="background:#0B0F17;color:#E2E8F0;border-radius:var(--radius-md);line-height:1.6;">' +
                    T.esc((r.recovery || []).join('\\n')) + '</pre>',
              footer: '<button type="button" class="btn btn-primary" data-action="reload">Saya Sudah Menyimpan Kode</button>'
            });
          }).catch(function(){});
        };
      }).finally(function(){ T.busy(faStart, false); });
    };
  }

  var faOff = document.getElementById('fa-off');
  if (faOff) {
    faOff.onclick = function(){
      var m = T.modal({
        title: 'Matikan Autentikasi 2FA',
        body: '<p class="mb12 text-sm text-danger font-bold">PERINGATAN: Mematikan 2FA akan menurunkan proteksi keamanan login akun Anda.</p>' +
              '<div class="field"><label class="form-label" for="off-code">Masukkan Kode 2FA atau Kode Pemulihan</label>' +
              '<input id="off-code" class="form-input mono" maxlength="9" placeholder="6 digit atau 8 char recovery" /></div>',
        footer: '<button type="button" class="btn btn-outline" data-modal-cancel>Batal</button>' +
                '<button type="button" class="btn btn-danger" data-modal-confirm>Matikan 2FA</button>'
      });
      m.el.querySelector('[data-modal-cancel]').onclick = m.close;
      var inp = m.el.querySelector('#off-code');
      if (inp) inp.focus();
      m.el.querySelector('[data-modal-confirm]').onclick = function(){
        var code = inp ? inp.value.trim() : '';
        if (!code) return;
        op({op:'2fa_disable', code: code}).then(function(){
          m.close();
          location.reload();
        }).catch(function(){});
      };
    };
  }

  var recGo = document.getElementById('rec-go');
  if (recGo) {
    recGo.onclick = function(){
      var m = T.modal({
        title: 'Buat Ulang Kode Pemulihan',
        body: '<div class="field"><label class="form-label" for="rec-code">Masukkan Kode 2FA Saat Ini</label>' +
              '<input id="rec-code" class="form-input mono" maxlength="6" placeholder="000000" /></div>',
        footer: '<button type="button" class="btn btn-outline" data-modal-cancel>Batal</button>' +
                '<button type="button" class="btn btn-primary" data-modal-confirm>Buat Ulang Kode</button>'
      });
      m.el.querySelector('[data-modal-cancel]').onclick = m.close;
      var inp = m.el.querySelector('#rec-code');
      if (inp) inp.focus();
      m.el.querySelector('[data-modal-confirm]').onclick = function(){
        var code = inp ? inp.value.trim() : '';
        if (!code) return;
        op({op:'recovery_regen', code: code}).then(function(r){
          m.close();
          T.modal({
            title: 'Kode Pemulihan Baru (Tersimpan)',
            wide: true,
            body: '<p class="mb8 text-sm font-bold text-success">Kode pemulihan lama telah dibatalkan. Simpan kode baru ini:</p>' +
                  '<pre class="code-editor mono text-xs p12" style="background:#0B0F17;color:#E2E8F0;border-radius:var(--radius-md);line-height:1.6;">' +
                  T.esc((r.recovery || []).join('\\n')) + '</pre>',
            footer: '<button type="button" class="btn btn-primary" data-action="reload">Selesai</button>'
          });
        }).catch(function(){});
      };
    };
  }

  document.addEventListener('click', function(ev){
    var b = ev.target.closest('[data-kill]');
    if (!b) return;
    var sid = b.getAttribute('data-kill');
    T.confirmDanger({
      title: 'Cabut Sesi Aktif',
      body: 'Sesi ini akan langsung dibatalkan dan pengguna harus login ulang.',
      ok: 'Cabut Sesi'
    }).then(function(ok){
      if (!ok) return;
      op({op:'kill_session', sid:sid}).then(loadSessions).catch(function(){});
    });
  });

  var relBtn = document.getElementById('se-reload');
  if (relBtn) relBtn.addEventListener('click', loadSessions);

  loadSessions();
})();
</script>
"""


def render(req, app, sess, qs, t):
    me = app.users.get(sess.get("username")) or {}
    has_2fa = bool(me.get("totp"))
    recovery_left = len(me.get("recovery") or [])

    stat_cards = f"""
<div class="grid g3 mb16">
  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">AUTENTIKASI 2FA</span>
      <span class="tag {'ok' if has_2fa else 'warn'}">{'AKTIF' if has_2fa else 'BELUM AKTIF'}</span>
    </div>
    <span class="vl {'text-success' if has_2fa else 'text-warning'}" style="font-size:22px">{'Terlindungi' if has_2fa else 'Belum aktif'}</span>
    <span class="ft">{'%d kode pemulihan tersisa' % recovery_left if has_2fa else 'Disarankan segera diaktifkan'}</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">SESI LOGIN AKTIF</span>
      <span class="tag ok">NORMAL</span>
    </div>
    <span class="vl text-primary" id="stat-active-sessions">1</span>
    <span class="ft">Perangkat yang sedang login</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">ENKRIPSI KATA SANDI</span>
      <span class="tag in">SECURE</span>
    </div>
    <span class="vl" style="font-size:20px;">PBKDF2-SHA256</span>
    <span class="ft">200.000 iterasi hash salt</span>
  </div>
</div>
"""

    pw_card = f"""
<div class="card p16">
  <div class="card-header p0 pb12 mb16 border-b row space-between align-center">
    <h3 class="card-title text-sm m0">Ubah Kata Sandi Akun</h3>
    <span class="text-xs text-muted mono font-bold">{sess.get("username", "")}</span>
  </div>
  <div class="field mb12">
    <label class="form-label" for="pw-old">Kata Sandi Saat Ini *</label>
    <input id="pw-old" type="password" class="form-input" autocomplete="current-password" placeholder="••••••••" />
  </div>
  <div class="field mb16">
    <label class="form-label" for="pw-new">Kata Sandi Baru (Minimal 10 Karakter) *</label>
    <input id="pw-new" type="password" class="form-input" autocomplete="new-password" placeholder="Kombinasi huruf, angka & simbol" />
  </div>
  <div class="row space-between align-center">
    <span class="text-xs text-muted">Semua sesi di perangkat lain akan dicabut otomatis saat sandi diubah.</span>
    <button type="button" class="btn btn-primary sm" id="pw-go">Simpan Sandi Baru</button>
  </div>
</div>
"""

    if has_2fa:
        fa_buttons = """
<div class="row gap8 align-center mt16">
  <button type="button" class="btn btn-sm btn-outline" id="rec-go">Buat Ulang Kode Pemulihan</button>
  <button type="button" class="btn btn-sm btn-danger" id="fa-off">Matikan 2FA</button>
</div>
"""
    else:
        fa_buttons = """
<div class="mt16">
  <button type="button" class="btn btn-sm btn-primary" id="fa-start">Aktifkan 2FA Sekarang</button>
  <p class="text-xs text-muted mt6">Pindai kode QR dari Google Authenticator / Aegis untuk mengamankan panel.</p>
</div>
"""

    fa_card = f"""
<div class="card p16">
  <div class="card-header p0 pb12 mb16 border-b row space-between align-center">
    <h3 class="card-title text-sm m0">Autentikasi Dua Faktor (TOTP 2FA)</h3>
    <span class="badge {'badge-success' if has_2fa else 'badge-warning'} text-xs">{'2FA AKTIF' if has_2fa else '2FA NONAKTIF'}</span>
  </div>
  <div class="spec-grid p0">
    <div class="spec-row"><span class="spec-k">Status Keamanan</span><span class="spec-v font-bold {'text-success' if has_2fa else 'text-warning'}">{'Terlindungi Authenticator' if has_2fa else 'Hanya Kata Sandi'}</span></div>
    <div class="spec-row"><span class="spec-k">Kode Pemulihan Tersisa</span><span class="spec-v mono font-bold">{recovery_left} Kode</span></div>
  </div>
  {fa_buttons}
</div>
"""

    sessions_tbl = f"""
<div class="card mb24 p0 overflow-hidden">
  <div class="card-header p16 border-b row space-between align-center flex-wrap gap8">
    <div class="row gap8 align-center">
      <span class="metric-icon">{C.icon("shield", 15)}</span>
      <h3 class="card-title text-sm m0">DAFTAR SESI LOGIN AKTIF (ACTIVE SESSIONS)</h3>
    </div>
    <button type="button" class="btn btn-outline sm" id="se-reload">{C.icon("refresh", 13)} Segarkan Sesi</button>
  </div>
  <div class="table-responsive"><table class="data-table"><thead><tr>
    <th>PENGGUNA</th><th>ROLE</th><th>ALAMAT IP (CLIENT)</th><th class="num">WAKTU LOGIN</th><th class="act">AKSI TINDAKAN</th>
  </tr></thead><tbody id="se-ss">
    <tr><td colspan="5" class="tc dim p24">Memuat data sesi aktif...</td></tr>
  </tbody></table></div>
</div>
"""

    body = stat_cards + '<div class="grid g2 mb24">' + pw_card + fa_card + '</div>' + sessions_tbl
    return layout.shell(sess, app, "security", "Security & Firewall",
                        "Kata sandi akun, autentikasi 2FA, dan pengawasan sesi login aktif",
                        body + JS, t)
