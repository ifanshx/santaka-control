"""Dua bahasa: ID (default) dan EN. Tanpa dependensi, dict sederhana."""

ID = {
    # navigasi
    "nav.group.main": "Utama", "nav.group.server": "Server",
    "nav.group.data": "Data & Sumber Daya", "nav.group.security": "Keamanan",
    "nav.group.system": "Sistem",
    "nav.dash": "Dashboard", "nav.svc": "Layanan", "nav.files": "Berkas",
    "nav.logs": "Log", "nav.web": "Web Server", "nav.apps": "Aplikasi",
    "nav.docker": "Kontainer", "nav.db": "Database", "nav.backup": "Cadangan",
    "nav.storage": "Penyimpanan", "nav.network": "Jaringan",
    "nav.cron": "Jadwal", "nav.users": "Pengguna", "nav.security": "Keamanan",
    "nav.alerts": "Notifikasi", "nav.maintenance": "Perawatan",
    "nav.audit": "Jejak Audit", "nav.help": "Panduan",
    # aksi
    "act.login": "Masuk", "act.logout": "Keluar", "act.save": "Simpan",
    "act.cancel": "Batal", "act.delete": "Hapus", "act.confirm": "Konfirmasi",
    "act.start": "Jalankan", "act.stop": "Hentikan", "act.restart": "Muat ulang",
    "act.enable": "Aktifkan", "act.disable": "Nonaktifkan", "act.reload": "Muat",
    "act.apply": "Terapkan", "act.deploy": "Terapkan", "act.upload": "Unggah",
    "act.download": "Unduh", "act.rename": "Ubah nama", "act.new_folder": "Folder baru",
    "act.open": "Buka", "act.close": "Tutup", "act.back": "Kembali",
    "act.refresh": "Segarkan", "act.copy": "Salin", "act.edit": "Ubah",
    "act.run": "Jalankan", "act.verify": "Verifikasi", "act.restore": "Pulihkan",
    "act.kill": "Matikan", "act.mount": "Pasang", "act.unmount": "Lepas",
    "act.ban": "Blokir", "act.unban": "Buka blokir", "act.test": "Uji",
    "act.add": "Tambah", "act.search": "Cari", "act.filter": "Saring",
    # status / umum
    "st.active": "Aktif", "st.inactive": "Mati", "st.failed": "Gagal",
    "st.running": "Berjalan", "st.stopped": "Berhenti", "st.unknown": "Tidak diketahui",
    "st.healthy": "Sehat", "st.warning": "Perhatian", "st.critical": "Kritis",
    "st.ok": "Berhasil", "st.error": "Gagal",
    "lbl.loading": "Memuat…", "lbl.empty": "Tidak ada data",
    "lbl.never": "Belum pernah", "lbl.none": "Tidak ada",
    "lbl.total": "Total", "lbl.used": "Terpakai", "lbl.free": "Sisa",
    "lbl.yes": "Ya", "lbl.no": "Tidak", "lbl.searching": "mencari…",
    # login
    "login.title": "Masuk ke Santaka Control",
    "login.sub": "Masuk dengan kata sandi. Kode 2FA diminta bila akun mengaktifkannya.",
    "login.user": "Nama pengguna", "login.password": "Kata sandi",
    "login.code": "Kode 2FA (6 digit)", "login.recovery": "Kode pemulihan",
    "login.codeHelp": "Kosongkan bila akun belum mengaktifkan 2FA.",
    "login.useRecovery": "Pakai kode pemulihan", "login.useTotp": "Pakai kode 2FA",
    "login.err": "Nama pengguna atau kata sandi salah",
    "login.errCode": "Kode 2FA tidak valid",
    "login.errLock": "Terlalu banyak percobaan. Coba lagi nanti.",
    "login.errCsrf": "Formulir kedaluwarsa. Muat ulang halaman lalu coba lagi.",
    "login.slow": "Mohon tunggu sebentar sebelum mencoba lagi.",
    "login.disabled": "Akun ini dinonaktifkan.",
    "login.note": "Sesi login aman dan dapat dicabut kapan saja. Setiap percobaan login dicatat di jejak audit.",
    "auth.tagline": "Kendali penuh server dari satu panel.",
    "auth.desc": "Kelola layanan, berkas, basis data, dan keamanan perangkat tanpa mengulang sesi SSH.",
    "auth.f1t": "Dua faktor", "auth.f1d": "TOTP dan kode pemulihan sekali pakai.",
    "auth.f2t": "Jejak audit", "auth.f2d": "Setiap aksi tercatat dengan IP dan waktu.",
    "auth.f3t": "Kendali penuh", "auth.f3d": "Layanan, berkas, basis data, dan jaringan.",
    "auth.foot": "Lalu lintas dilindungi TLS", "auth.sub": "Panel server",
    # dashboard
    "dash.cpu": "Beban CPU", "dash.mem": "Memori", "dash.temp": "Suhu",
    "dash.disk": "Penyimpanan", "dash.load": "Load average", "dash.uptime": "Uptime",
    "dash.host": "Host", "dash.kernel": "Kernel", "dash.procs": "Proses terberat",
    "dash.net": "Jaringan", "dash.svc": "Layanan systemd",
    "dash.apps": "Aplikasi web", "dash.mounts": "Mount aktif",
    "dash.live": "Live · 3 detik", "dash.thermal": "Termal & daya",
    # layanan
    "svc.search": "Cari layanan…", "svc.unit": "Unit", "svc.desc": "Keterangan",
    "svc.state": "Status", "svc.actions": "Aksi", "svc.log": "Log",
    "svc.enabled": "Autostart", "svc.confirmStop": "Hentikan layanan ini?",
    "svc.confirmDisable": "Matikan autostart layanan ini?",
    # berkas
    "files.path": "Lokasi", "files.name": "Nama", "files.size": "Ukuran",
    "files.mtime": "Diubah", "files.newFolder": "Nama folder baru",
    "files.confirmDelete": "Hapus permanen berkas ini?",
    "files.parent": "Naik satu tingkat", "files.drop": "Jatuhkan berkas di sini",
    # log
    "logs.unit": "Layanan", "logs.dmesg": "Kernel (dmesg)",
    "logs.access": "Akses web", "logs.lines": "Jumlah baris",
    "logs.filter": "Saring kata kunci…", "logs.follow": "Ikuti",
    "logs.stop": "Berhenti mengikuti",
    # web
    "web.sites": "Situs", "web.caddyfile": "Berkas Caddyfile",
    "web.validate": "Periksa konfigurasi", "web.host": "Host",
    "web.upstream": "Tujuan", "web.ssl": "SSL",
    # apps
    "apps.kind": "Jenis", "apps.port": "Port", "apps.domain": "Domain",
    "apps.state": "Status", "apps.env": "Variabel lingkungan",
    "apps.deployNew": "Terapkan aplikasi baru",
    # docker
    "dk.containers": "Kontainer", "dk.images": "Image", "dk.volumes": "Volume",
    "dk.networks": "Jaringan",
    # db
    "db.databases": "Basis data", "db.users": "Pengguna", "db.query": "Kueri aktif",
    "db.dump": "Cadangkan", "db.restore": "Pulihkan",
    # backup
    "bk.archives": "Arsip", "bk.runNow": "Cadangkan sekarang",
    "bk.verify": "Verifikasi integritas", "bk.schedule": "Jadwal",
    # storage
    "st.disks": "Disk", "st.mounts": "Mount", "st.smart": "Kesehatan disk",
    "st.fstab": "fstab",
    # network
    "nw.interfaces": "Antarmuka", "nw.firewall": "Firewall",
    "nw.banned": "Alamat diblokir", "nw.listen": "Port mendengarkan",
    # cron
    "cr.jobs": "Tugas cron", "cr.timers": "Timer systemd",
    # users
    "us.users": "Pengguna panel", "us.role": "Peran", "us.lastLogin": "Login terakhir",
    "us.newUser": "Pengguna baru", "us.display": "Nama tampilan",
    # security
    "se.password": "Kata sandi", "se.2fa": "Autentikasi 2FA",
    "se.sessions": "Sesi aktif", "se.recovery": "Kode pemulihan",
    "se.sshKeys": "Kunci SSH",
    # alerts
    "al.telegram": "Telegram", "al.email": "Email SMTP", "al.test": "Uji kirim",
    # maintenance
    "mt.temp": "Berkas sementara", "mt.cache": "Cache paket",
    "mt.fstrim": "TRIM SSD/eMMC", "mt.packages": "Paket dapat diperbarui",
    # audit
    "au.time": "Waktu", "au.user": "Pengguna", "au.action": "Aksi",
    "au.target": "Sasaran", "au.result": "Hasil", "au.ip": "Alamat IP",
    # konfirmasi
    "cf.title": "Konfirmasi tindakan",
    "cf.typeName": "Ketik nama di atas untuk melanjutkan",
    "cf.danger": "Tindakan ini tidak dapat dibatalkan.",
}

EN = {k: v for k, v in ID.items()}
EN.update({
    "nav.group.main": "Main", "nav.group.server": "Server",
    "nav.group.data": "Data & Resources", "nav.group.security": "Security",
    "nav.group.system": "System",
    "nav.dash": "Dashboard", "nav.svc": "Services", "nav.files": "Files",
    "nav.logs": "Logs", "nav.web": "Web Server", "nav.apps": "Applications",
    "nav.docker": "Containers", "nav.db": "Databases", "nav.backup": "Backups",
    "nav.storage": "Storage", "nav.network": "Network", "nav.cron": "Schedules",
    "nav.users": "Users", "nav.security": "Security", "nav.alerts": "Alerts",
    "nav.maintenance": "Maintenance", "nav.audit": "Audit Trail", "nav.help": "Guide",
    "act.login": "Sign in", "act.logout": "Sign out", "act.save": "Save",
    "act.cancel": "Cancel", "act.delete": "Delete", "act.confirm": "Confirm",
    "act.start": "Start", "act.stop": "Stop", "act.restart": "Restart",
    "act.enable": "Enable", "act.disable": "Disable", "act.reload": "Reload",
    "act.apply": "Apply", "act.deploy": "Deploy", "act.upload": "Upload",
    "act.download": "Download", "act.rename": "Rename", "act.new_folder": "New folder",
    "act.open": "Open", "act.close": "Close", "act.back": "Back",
    "act.refresh": "Refresh", "act.copy": "Copy", "act.edit": "Edit",
    "act.run": "Run", "act.verify": "Verify", "act.restore": "Restore",
    "act.kill": "Kill", "act.mount": "Mount", "act.unmount": "Unmount",
    "act.ban": "Ban", "act.unban": "Unban", "act.test": "Test",
    "act.add": "Add", "act.search": "Search", "act.filter": "Filter",
    "st.active": "Active", "st.inactive": "Inactive", "st.failed": "Failed",
    "st.running": "Running", "st.stopped": "Stopped", "st.unknown": "Unknown",
    "st.healthy": "Healthy", "st.warning": "Warning", "st.critical": "Critical",
    "st.ok": "Success", "st.error": "Failed",
    "lbl.loading": "Loading…", "lbl.empty": "Nothing here",
    "lbl.never": "Never", "lbl.none": "None",
    "lbl.total": "Total", "lbl.used": "Used", "lbl.free": "Free",
    "lbl.yes": "Yes", "lbl.no": "No", "lbl.searching": "searching…",
    "login.title": "Sign in to Santaka Control",
    "login.sub": "Sign in with your password. A 2FA code is requested when enabled.",
    "login.user": "Username", "login.password": "Password",
    "login.code": "2FA code (6 digits)", "login.recovery": "Recovery code",
    "login.codeHelp": "Leave empty when the account has not enabled 2FA.",
    "login.useRecovery": "Use a recovery code", "login.useTotp": "Use 2FA code",
    "login.err": "Wrong username or password",
    "login.errCode": "Invalid 2FA code",
    "login.errLock": "Too many attempts. Try again later.",
    "login.errCsrf": "Form expired. Reload the page and try again.",
    "login.slow": "Please wait a moment before retrying.",
    "login.disabled": "This account is disabled.",
    "login.note": "Sessions are secured and revocable at any time. Every login attempt is written to the audit trail.",
    "auth.tagline": "Full server control from a single panel.",
    "auth.desc": "Manage services, files, databases, and device security without repeating SSH sessions.",
    "auth.f1t": "Two-factor", "auth.f1d": "TOTP and one-time recovery codes.",
    "auth.f2t": "Audit trail", "auth.f2d": "Every action logged with IP and timestamp.",
    "auth.f3t": "Full control", "auth.f3d": "Services, files, databases, and networking.",
    "auth.foot": "Traffic protected by TLS", "auth.sub": "Server panel",
    "dash.cpu": "CPU usage", "dash.mem": "Memory", "dash.temp": "Temperature",
    "dash.disk": "Storage", "dash.load": "Load average", "dash.uptime": "Uptime",
    "dash.host": "Host", "dash.kernel": "Kernel", "dash.procs": "Top processes",
    "dash.net": "Network", "dash.svc": "systemd services",
    "dash.apps": "Web applications", "dash.mounts": "Active mounts",
    "dash.live": "Live · 3 s", "dash.thermal": "Thermal & power",
    "svc.search": "Search services…", "svc.unit": "Unit", "svc.desc": "Description",
    "svc.state": "State", "svc.actions": "Actions", "svc.log": "Logs",
    "svc.enabled": "Autostart", "svc.confirmStop": "Stop this service?",
    "svc.confirmDisable": "Disable autostart for this service?",
    "files.path": "Location", "files.name": "Name", "files.size": "Size",
    "files.mtime": "Modified", "files.newFolder": "New folder name",
    "files.confirmDelete": "Permanently delete this file?",
    "files.parent": "Up one level", "files.drop": "Drop files here",
    "logs.unit": "Service", "logs.dmesg": "Kernel (dmesg)",
    "logs.access": "Web access", "logs.lines": "Lines",
    "logs.filter": "Filter keyword…", "logs.follow": "Follow",
    "logs.stop": "Stop following",
    "web.sites": "Sites", "web.caddyfile": "Caddyfile",
    "web.validate": "Validate config", "web.host": "Host",
    "web.upstream": "Upstream", "web.ssl": "SSL",
    "apps.kind": "Kind", "apps.port": "Port", "apps.domain": "Domain",
    "apps.state": "State", "apps.env": "Environment variables",
    "apps.deployNew": "Deploy new application",
    "dk.containers": "Containers", "dk.images": "Images", "dk.volumes": "Volumes",
    "dk.networks": "Networks",
    "db.databases": "Databases", "db.users": "Users", "db.query": "Active queries",
    "db.dump": "Dump", "db.restore": "Restore",
    "bk.archives": "Archives", "bk.runNow": "Back up now",
    "bk.verify": "Verify integrity", "bk.schedule": "Schedule",
    "st.disks": "Disks", "st.mounts": "Mounts", "st.smart": "Disk health",
    "st.fstab": "fstab",
    "nw.interfaces": "Interfaces", "nw.firewall": "Firewall",
    "nw.banned": "Banned addresses", "nw.listen": "Listening ports",
    "cr.jobs": "Cron jobs", "cr.timers": "systemd timers",
    "us.users": "Panel users", "us.role": "Role", "us.lastLogin": "Last sign-in",
    "us.newUser": "New user", "us.display": "Display name",
    "se.password": "Password", "se.2fa": "Two-factor authentication",
    "se.sessions": "Active sessions", "se.recovery": "Recovery codes",
    "se.sshKeys": "SSH keys",
    "al.telegram": "Telegram", "al.email": "SMTP email", "al.test": "Send test",
    "mt.temp": "Temporary files", "mt.cache": "Package cache",
    "mt.fstrim": "TRIM SSD/eMMC", "mt.packages": "Upgradable packages",
    "au.time": "Time", "au.user": "User", "au.action": "Action",
    "au.target": "Target", "au.result": "Result", "au.ip": "IP address",
    "cf.title": "Confirm action",
    "cf.typeName": "Type the name above to continue",
    "cf.danger": "This action cannot be undone.",
})

LANGS = {"id": ID, "en": EN}


class Translator:
    def __init__(self, lang="id"):
        self.lang = lang if lang in LANGS else "id"

    def __call__(self, key, **kw):
        text = LANGS[self.lang].get(key) or LANGS["id"].get(key) or key
        if kw:
            try:
                return text.format(**kw)
            except (KeyError, IndexError):
                return text
        return text

    def has(self, key):
        return key in LANGS[self.lang] or key in LANGS["id"]
