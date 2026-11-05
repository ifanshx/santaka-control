"""Halaman Perawatan: fstrim, cache paket, paket dapat diperbarui."""
from ui import components as C
from ui import layout

JS = """
<script>
(function(){
  var T = window.SC;
  function op(body, label){
    return fetch((T && T.url ? T.url('/api/maintenance/action') : '/api/maintenance/action'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF': document.querySelector('meta[name="csrf"]')?.content || '' },
      body: JSON.stringify(body)
    })
    .then(r => r.json())
    .then(function(j){
      if (!j.ok && j.error) throw new Error(j.error);
      if (T && T.toast) T.toast('Berhasil', j.message || label, 'ok');
      return j;
    })
    .catch(function(e){
      if (T && T.toast) T.toast('Gagal', e.message, 'err');
    });
  }

  var trimBtn = document.getElementById('mt-trim');
  if (trimBtn) {
    trimBtn.onclick = function(){
      T.confirmDanger({
        title: 'Jalankan TRIM Flash / SSD (fstrim)',
        body: 'Menjalankan <b>fstrim -av</b> pada eMMC dan partisi storage yang mendukung. Mengoptimalkan performa baca/tulis chip storage.',
        ok: 'Jalankan fstrim'
      }).then(function(ok){
        if (!ok) return;
        if (T && T.busy) T.busy(trimBtn, true);
        op({op:'fstrim'}, 'TRIM selesai').finally(function(){ if (T && T.busy) T.busy(trimBtn, false); });
      });
    };
  }

  var cacheBtn = document.getElementById('mt-cache');
  if (cacheBtn) {
    cacheBtn.onclick = function(){
      T.confirmDanger({
        title: 'Bersihkan Cache Paket (apt-get clean)',
        body: 'Menjalankan <b>apt-get clean &amp; autoclean</b> untuk mengosongkan arsip .deb sisa unduhan di /var/cache/apt. Aman dan melegakan disk.',
        ok: 'Bersihkan Cache'
      }).then(function(ok){
        if (!ok) return;
        if (T && T.busy) T.busy(cacheBtn, true);
        op({op:'apt_clean'}, 'Cache dibersihkan').finally(function(){ if (T && T.busy) T.busy(cacheBtn, false); });
      });
    };
  }
})();
</script>
"""


def render(req, app, sess, qs, t):
    from lib import secops
    try:
        ups = secops.upgradable()
    except Exception:
        ups = []
    tmp = secops.tmp_usage()
    free = secops.disk_free("/")

    stat_cards = f"""
<div class="grid g3 mb16">
  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">PAKET DAPAT DI-UPGRADE</span>
      <span class="tag {'warn' if len(ups) > 0 else 'ok'}">{len(ups)} PAKET</span>
    </div>
    <span class="vl {'text-warning' if len(ups) > 0 else 'text-success'}">{len(ups)} <small>Tersedia</small></span>
    <span class="ft">Pembaruan paket sistem operasi</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">SISA DISK ROOT (/)</span>
      <span class="tag ok">TERSEDIA</span>
    </div>
    <span class="vl text-success">{free} <small>Bebas</small></span>
    <span class="ft">Ruang kosong di partisi eMMC internal</span>
  </div>

  <div class="panel lift metric">
    <div class="metric-head">
      <span class="lb">PEMAKAIAN /tmp</span>
      <span class="tag in">RAM TMPFS</span>
    </div>
    <span class="vl text-primary">{tmp}</span>
    <span class="ft">Folder temporer di RAM</span>
  </div>
</div>
"""

    actions_card = f"""
<div class="card mb24 p16">
  <div class="card-header p0 pb12 mb16 border-b">
    <h3 class="card-title text-sm m0">Tindakan Perawatan Berkala</h3>
  </div>
  <div class="row gap12 align-center flex-wrap">
    <div class="p12 card flex-1" style="min-width:260px;background:var(--surface-2);">
      <b class="text-main font-bold">Optimasi Storage (fstrim -av)</b>
      <p class="text-xs text-muted mt4 mb12">Melakukan discard block yang tidak terpakai pada eMMC &amp; SSD untuk menjaga performa baca-tulis tinggi.</p>
      <button type="button" class="btn btn-primary sm" id="mt-trim">{C.icon("wrench", 13)} Jalankan fstrim</button>
    </div>

    <div class="p12 card flex-1" style="min-width:260px;background:var(--surface-2);">
      <b class="text-main font-bold">Bersihkan Cache Paket APT</b>
      <p class="text-xs text-muted mt4 mb12">Menghapus berkas .deb arsip unduhan lama dari /var/cache/apt/archives untuk menghemat penyimpanan.</p>
      <button type="button" class="btn btn-outline sm" id="mt-cache">{C.icon("trash", 13)} Bersihkan Cache APT</button>
    </div>
  </div>
</div>
"""

    up_rows = [(
        '<b class="mono text-main font-bold">%s</b>' % C.e(u.get("name", "")),
        '<span class="mono text-muted text-xs">Repository</span>',
        '<span class="mono font-bold text-success text-xs">%s</span>' % C.e(u.get("version", "Mutakhir")),
        '<span class="badge badge-info text-xs">TERSEDIA</span>',
    ) for u in ups]
    up_tbl = (C.table(["Nama Paket", "Versi Terpasang", "Versi Tersedia", "Arsitektur"],
                      up_rows) if up_rows
              else C.empty("Semua paket mutakhir", "Sistem beroperasi dengan versi paket software terbaru."))

    up_card = (
        '<div class="card p0 overflow-hidden">'
        '<div class="card-header p16 border-b row space-between align-center">'
        '<div>'
        '<h3 class="card-title text-sm m0">DAFTAR PEMBARUAN PERANGKAT LUNAK (apt list --upgradable)</h3>'
        '<p class="text-xs text-muted m0 mt4">Daftar paket yang dapat diperbarui dari repository resmi Debian 12 Bookworm.</p>'
        '</div>'
        f'<span class="badge badge-success text-xs">{len(ups)} Pembaruan</span>'
        '</div>'
        + up_tbl + '</div>'
    )

    body = stat_cards + actions_card + up_card
    return layout.shell(sess, app, "maintenance", "Maintenance",
                        "Perawatan sistem, pembersihan cache paket, dan pemantauan upgrade software",
                        body + JS, t)
