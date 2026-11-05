"""Katalog izin dan pemetaan role. Setiap route menyatakan izin yang dibutuhkannya."""

# ---- katalog izin ----
VIEW = "view"                    # baca apa pun
SERVICE = "service.control"      # start/stop/restart/enable unit
FILE_WRITE = "file.write"        # tulis/hapus/upload file
LOG_VIEW = "log.view"            # baca log sistem
APP_DEPLOY = "app.deploy"        # deploy/hapus aplikasi
APP_CONTROL = "app.control"      # start/stop aplikasi
DB_MANAGE = "db.manage"          # buat/hapus database, dump, restore
BACKUP_RUN = "backup.run"        # jalankan/pulihkan backup
DOCKER = "docker.control"        # lifecycle container
STORAGE = "storage.mount"        # mount/unmount/fstab
NETWORK = "network.firewall"     # iptables, fail2ban
CRON = "cron.manage"             # crontab & timer
USER_MANAGE = "user.manage"      # kelola akun panel
SECURITY = "security.manage"     # password, 2FA, sesi
POWER = "system.power"           # reboot/shutdown
MAINT = "maintenance"            # fstrim, bersihkan cache, apt
ALERTS = "alerts.manage"         # telegram/smtp
WEB_CONFIG = "web.config"        # terapkan konfigurasi Caddy
CRON_WRITE = "cron.write"        # ubah crontab

ALL = (
    VIEW, SERVICE, FILE_WRITE, LOG_VIEW, APP_DEPLOY, APP_CONTROL, DB_MANAGE,
    BACKUP_RUN, DOCKER, STORAGE, NETWORK, CRON, USER_MANAGE, SECURITY,
    POWER, MAINT, ALERTS, WEB_CONFIG, CRON_WRITE,
)

# ---- role ----
ROLE_VIEWER = "viewer"
ROLE_OPERATOR = "operator"
ROLE_ADMIN = "admin"

ROLE_ORDER = [ROLE_VIEWER, ROLE_OPERATOR, ROLE_ADMIN]

ROLE_PERMS = {
    ROLE_VIEWER: {VIEW},
    ROLE_OPERATOR: {
        VIEW, SERVICE, FILE_WRITE, LOG_VIEW, APP_DEPLOY, APP_CONTROL,
        BACKUP_RUN, DOCKER,
    },
    ROLE_ADMIN: set(ALL),
}

ROLE_LABEL = {
    ROLE_VIEWER: "Viewer · hanya baca",
    ROLE_OPERATOR: "Operator · operasi harian",
    ROLE_ADMIN: "Administrator · kendali penuh",
}


def perms_for(role):
    return set(ROLE_PERMS.get(role, {VIEW}))


def can(user, perm):
    """True kalau user punya izin. user berupa dict dengan kunci 'role'."""
    if not user or not perm:
        return False
    return perm in perms_for(user.get("role"))


def can_any(user, perms):
    return any(can(user, p) for p in perms)


def manageable_roles(actor):
    """Role yang boleh dibuat/diubah oleh actor (tidak boleh melampaui dirinya)."""
    if not actor:
        return []
    if actor.get("role") == ROLE_ADMIN:
        return list(ROLE_ORDER)
    return [ROLE_VIEWER]


def can_manage_user(actor, target_role):
    """Cegah operator membuat admin, dan cegah admin menurunkan admin terakhir."""
    if not actor or actor.get("role") != ROLE_ADMIN:
        return False
    return target_role in ROLE_ORDER
