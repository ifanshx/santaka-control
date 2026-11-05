"""Validator ketat: semuanya regex berjangkar. Dipakai sebelum sentuh sistem."""
import re

# systemd unit: huruf, angka, @ . _ -
UNIT_RE = re.compile(r"^[A-Za-z0-9@._\-]{1,128}$")
UNIT_SAFE = re.compile(r"^[A-Za-z0-9@._\-\\]{1,128}$")

# docker container/id
CID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,127}$")

# nama database / user SQL (tanpa tanda kutip, hindari injeksi)
SQLNAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,62}$")

# nama domain
DOMAIN_RE = re.compile(
    r"^(?!-)[A-Za-z0-9\-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9\-]{1,63}(?<!-))+$")

# nama file/folder: tolak NUL, slash, dan nama khusus
BAD_PATH_CHARS = re.compile(r"[\x00-\x1f\x7f]")
NAME_RE = re.compile(r"^[^/\\\x00]{1,255}$")

# user panel
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{2,31}$")

# slug aplikasi
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,47}$")

# port
def port(value):
    try:
        p = int(value)
    except (TypeError, ValueError):
        return None
    return p if 1 <= p <= 65535 else None


def unit(name):
    return bool(name and UNIT_RE.match(str(name)))


def container_id(cid):
    return bool(cid and CID_RE.match(str(cid)))


def sql_name(name):
    return bool(name and SQLNAME_RE.match(str(name)))


def domain(name):
    return bool(name and len(str(name)) <= 253 and DOMAIN_RE.match(str(name)))


def filename(name):
    return bool(name and name not in (".", "..") and NAME_RE.match(str(name))
                and not BAD_PATH_CHARS.search(str(name)))


def username(name):
    return bool(name and USERNAME_RE.match(str(name)))


def slug(name):
    return bool(name and SLUG_RE.match(str(name)))


def safe_int(value, low, high, default=None):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return n if low <= n <= high else default


def one_of(value, allowed, default=None):
    return value if value in allowed else default
