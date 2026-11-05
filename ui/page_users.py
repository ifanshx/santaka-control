"""Halaman Pengguna: kelola akun panel dan role."""
from ui import components as C
from ui import layout

JS = """
<script>
(function(){
  var T = window.SC;
  var roles = [], labels = {};
  var allUsersList = [];

  function paint(j){
    roles = j.roles || []; labels = j.role_labels || {};
    allUsersList = j.items || [];

    // Update stats
    var tot = allUsersList.length;
    var adminCount = allUsersList.filter(u => u.role === 'admin').length;
    var faCount = allUsersList.filter(u => u.totp).length;

    var elTot = document.getElementById('stat-u-total');
    if (elTot) elTot.textContent = tot;
    var elAdm = document.getElementById('stat-u-admin');
    if (elAdm) elAdm.textContent = adminCount;
    var elFa = document.getElementById('stat-u-fa');
    if (elFa) elFa.textContent = faCount + ' / ' + tot;

    renderUsersTable(allUsersList);
  }

  function renderUsersTable(list){
    var tbody = document.getElementById('us-rows');
    var countEl = document.getElementById('users-count');
    if (countEl) countEl.textContent = list.length + ' Pengguna';

    if (!list.length){
      tbody.innerHTML = '<tr><td colspan="7" class="tc dim p24">Tidak ada pengguna yang cocok.</td></tr>';
      return;
    }

    tbody.innerHTML = list.map(function(u){
      var rc = u.role === 'admin' ? 'pk' : u.role === 'operator' ? 'in' : 'nu';
      var faBadge = u.totp
        ? '<span class="badge badge-success text-xs"><span class="pulse-dot green"></span> 2FA AKTIF</span>'
        : '<span class="badge badge-warning text-xs">TANPA 2FA</span>';

      var statusBadge = u.disabled
        ? ' <span class="badge badge-danger text-xs">NONAKTIF</span>'
        : '';

      return '<tr data-u="' + T.esc(u.username) + '">' +
        '<td><div class="row gap6 align-center"><b class="mono text-main font-bold">' + T.esc(u.username) + '</b>' + statusBadge + '</div></td>' +
        '<td>' + T.esc(u.display || u.username) + '</td>' +
        '<td data-label="Role"><span class="tag ' + rc + '">' + T.esc(u.role.toUpperCase()) + '</span></td>' +
        '<td data-label="2FA">' + faBadge + '</td>' +
        '<td class="num mono text-xs" data-label="Pemulihan">' + u.recovery + '</td>' +
        '<td class="num text-xs text-muted" data-label="Login Terakhir">' + T.ago(u.last_login) + '</td>' +
        '<td class="act">' +
          '<button type="button" class="btn btn-sm btn-outline" data-a="role" title="Ubah hak akses role">Role</button> ' +
          '<button type="button" class="btn btn-sm btn-outline" data-a="pw" title="Reset kata sandi pengguna">Reset</button> ' +
          '<button type="button" class="btn btn-sm btn-outline" data-a="toggle">' + (u.disabled ? 'Aktifkan' : 'Nonaktifkan') + '</button> ' +
          '<button type="button" class="btn btn-sm btn-danger" data-a="del" title="Hapus akun">Hapus</button>' +
        '</td></tr>';
    }).join('');
  }

  function filterUsers(){
    var q = (document.getElementById('user-search').value || '').trim().toLowerCase();
    var filtered = allUsersList.filter(function(u){
      return !q || (u.username + ' ' + (u.display || '') + ' ' + u.role).toLowerCase().indexOf(q) > -1;
    });
    renderUsersTable(filtered);
  }

  function load(){
    fetch((T && T.url ? T.url('/api/users') : '/api/users'))
      .then(r => r.json())
      .then(function(res){ paint(res.data || res); })
      .catch(function(e){ if (T && T.toast) T.toast('Gagal', e.message, 'err'); });
  }

  function op(body){
    return fetch((T && T.url ? T.url('/api/users/action') : '/api/users/action'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF': document.querySelector('meta[name="csrf"]')?.content || '' },
      body: JSON.stringify(body)
    })
    .then(r => r.json())
    .then(function(j){
      if (!j.ok && j.error) throw new Error(j.error);
      if (T && T.toast) T.toast('Berhasil', j.message || 'Selesai', 'ok');
      load();
    })
    .catch(function(e){
      if (T && T.toast) T.toast('Gagal', e.message, 'err');
    });
  }

  var newBtn = document.getElementById('us-new');
  if (newBtn) {
    newBtn.onclick = function(){
      var m = T.modal({
        title: 'Tambah Pengguna Baru',
        body: '<div class="field mb12"><label class="form-label" for="u-n">Username *</label>' +
              '<input id="u-n" type="text" class="form-input mono" placeholder="operator1" /></div>' +
              '<div class="field mb12"><label class="form-label" for="u-d">Nama Tampilan</label>' +
              '<input id="u-d" type="text" class="form-input" placeholder="Operator Server" /></div>' +
              '<div class="field mb12"><label class="form-label" for="u-p">Kata Sandi Awal (Min 10 Karakter) *</label>' +
              '<input id="u-p" type="password" class="form-input" placeholder="••••••••••" /></div>' +
              '<div class="field"><label class="form-label" for="u-r">Peran Akses (Role)</label><select id="u-r" class="form-input text-xs">' +
              roles.map(function(r){ return '<option value="' + T.esc(r) + '">' + T.esc(labels[r] || r) + '</option>'; }).join('') +
              '</select></div>',
        footer: '<button type="button" class="btn btn-outline" data-modal-cancel>Batal</button>' +
                '<button type="button" class="btn btn-primary" data-modal-confirm>Buat Pengguna</button>'
      });
      m.el.querySelector('[data-modal-cancel]').onclick = m.close;
      var inpName = m.el.querySelector('#u-n');
      if (inpName) inpName.focus();
      m.el.querySelector('[data-modal-confirm]').onclick = function(){
        var uname = inpName.value.trim().toLowerCase();
        var disp = m.el.querySelector('#u-d').value.trim();
        var pass = m.el.querySelector('#u-p').value;
        var role = m.el.querySelector('#u-r').value;
        if (!uname || !pass) {
          if (T && T.toast) T.toast('Validasi', 'Username dan kata sandi wajib diisi!', 'warn');
          return;
        }
        op({op:'create', username:uname, display:disp, password:pass, role:role})
          .then(m.close);
      };
    };
  }

  document.addEventListener('click', function(ev){
    var b = ev.target.closest('button[data-a]');
    if (!b) return;
    var tr = b.closest('tr');
    var u = tr.getAttribute('data-u');
    var a = b.getAttribute('data-a');

    if (a === 'role'){
      var m = T.modal({
        title: 'Ubah Role · ' + u,
        body: '<div class="field"><label class="form-label" for="r-s">Pilih Role Baru</label><select id="r-s" class="form-input text-xs">' +
              roles.map(function(r){ return '<option value="' + T.esc(r) + '">' + T.esc(labels[r] || r) + '</option>'; }).join('') +
              '</select></div>',
        footer: '<button type="button" class="btn btn-outline" data-modal-cancel>Batal</button>' +
                '<button type="button" class="btn btn-primary" data-modal-confirm>Simpan Role</button>'
      });
      m.el.querySelector('[data-modal-cancel]').onclick = m.close;
      m.el.querySelector('[data-modal-confirm]').onclick = function(){
        op({op:'role', username:u, role:m.el.querySelector('#r-s').value}).then(m.close);
      };
      return;
    }

    if (a === 'pw'){
      var m = T.modal({
        title: 'Reset Kata Sandi · ' + u,
        body: '<div class="field"><label class="form-label" for="p-w">Kata Sandi Baru (Min 10 Karakter)</label>' +
              '<input id="p-w" type="password" class="form-input" placeholder="••••••••••" /></div>',
        footer: '<button type="button" class="btn btn-outline" data-modal-cancel>Batal</button>' +
                '<button type="button" class="btn btn-primary" data-modal-confirm>Reset Sandi</button>'
      });
      m.el.querySelector('[data-modal-cancel]').onclick = m.close;
      var inpPw = m.el.querySelector('#p-w');
      if (inpPw) inpPw.focus();
      m.el.querySelector('[data-modal-confirm]').onclick = function(){
        var pass = inpPw.value;
        if (!pass || pass.length < 10) {
          if (T && T.toast) T.toast('Validasi', 'Sandi minimal 10 karakter!', 'warn');
          return;
        }
        op({op:'password', username:u, password:pass}).then(m.close);
      };
      return;
    }

    if (a === 'toggle'){
      op({op:'toggle', username:u});
      return;
    }

    if (a === 'del'){
      T.confirmDanger({
        title: 'Hapus Akun Pengguna',
        body: 'Akun <b>' + T.esc(u) + '</b> akan dihapus permanen dari panel.',
        ok: 'Hapus Akun',
        phrase: u
      }).then(function(ok){
        if (ok) op({op:'delete', username:u});
      });
    }
  });

  var relBtn = document.getElementById('us-reload');
  if (relBtn) relBtn.addEventListener('click', load);

  var uSrch = document.getElementById('user-search');
  if (uSrch) uSrch.addEventListener('input', filterUsers);

  load();
})();
</script>
"""


def render(req, app, sess, qs, t):
    stat_cards = f"""
<div class="grid g3 mb16">
  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">TOTAL PENGGUNA</span>
      <span class="metric-icon">{C.icon("user", 15)}</span>
    </div>
    <span class="vl text-primary" id="stat-u-total">1</span>
    <span class="ft">Akun terdaftar di sistem</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">ADMINISTRATOR</span>
      <span class="tag pk">FULL ACCESS</span>
    </div>
    <span class="vl" id="stat-u-admin">1</span>
    <span class="ft">Memiliki hak kontrol menyeluruh</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">PROTEKSI 2FA</span>
      <span class="tag ok">AKTIF</span>
    </div>
    <span class="vl text-success" id="stat-u-fa">1 / 1</span>
    <span class="ft">Akun dengan autentikasi 2FA</span>
  </div>
</div>
"""

    table = f"""
<div class="card mb24 p0 overflow-hidden">
  <div class="card-header p16 border-b row space-between align-center flex-wrap gap8">
    <div class="row gap12 align-center">
      <h3 class="card-title text-sm m0">DAFTAR PENGGUNA PANEL</h3>
      <span class="badge badge-success text-xs" id="users-count">Memuat...</span>
    </div>
    <div class="row gap8 align-center flex-wrap">
      <div class="srch" style="max-width:230px;">
        <span class="ic">{C.icon("search", 13)}</span>
        <input type="text" id="user-search" placeholder="Cari nama atau username..." class="form-input text-xs" style="padding-left:32px;height:32px;" />
      </div>
      <button type="button" class="btn btn-outline sm" id="us-reload">{C.icon("refresh", 13)} Segarkan</button>
      <button type="button" class="btn btn-primary sm" id="us-new">{C.icon("plus", 13)} Pengguna Baru</button>
    </div>
  </div>
  <div class="table-responsive"><table class="data-table"><thead><tr>
    <th>NAMA PENGGUNA</th><th>NAMA TAMPILAN</th><th>PERAN (ROLE)</th><th>STATUS 2FA</th><th class="num">PEMULIHAN</th><th class="num">LOGIN TERAKHIR</th><th class="act">AKSI TINDAKAN</th>
  </tr></thead><tbody id="us-rows">
    <tr><td colspan="7" class="tc dim p24">Memuat daftar pengguna...</td></tr>
  </tbody></table></div>
</div>
"""

    body = stat_cards + table
    return layout.shell(sess, app, "users", "Admin Users",
                        "Kelola akun pengguna, peran akses (Admin/Operator/Viewer), dan reset sandi",
                        body + JS, t)
