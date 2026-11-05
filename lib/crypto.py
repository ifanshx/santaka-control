"""Kripto: PBKDF2 password, TOTP (RFC 6238), HMAC cookie, token acak."""
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time

PBKDF2_ROUNDS = 200_000
HASH_NAME = "sha256"


# ---------- password ----------

def hash_password(password, rounds=PBKDF2_ROUNDS):
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(HASH_NAME, password.encode("utf-8"),
                             bytes.fromhex(salt), rounds)
    return "pbkdf2_%s$%d$%s$%s" % (HASH_NAME, rounds, salt, dk.hex())


def verify_password(password, stored):
    """Bandingkan dengan waktu konstan. Mendukung format lama & baru."""
    if not stored or not isinstance(stored, str):
        return False
    try:
        parts = stored.split("$")
        if len(parts) == 4 and parts[0].startswith("pbkdf2_"):
            _, rounds, salt, want = parts
            dk = hashlib.pbkdf2_hmac(parts[0].split("_", 1)[1],
                                     password.encode("utf-8"),
                                     bytes.fromhex(salt), int(rounds))
            return hmac.compare_digest(dk.hex(), want)
        if len(parts) == 3:  # format lama: algo$salt$hash
            algo, salt, want = parts
            dk = hashlib.pbkdf2_hmac(algo, password.encode("utf-8"),
                                     bytes.fromhex(salt), 150_000)
            return hmac.compare_digest(dk.hex(), want)
    except (ValueError, TypeError):
        return False
    return False


def sha256_hex(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------- TOTP (RFC 6238) ----------

def totp_now(secret, step=30, digits=6, offset=0):
    """Kode TOTP saat ini. offset dalam satuan step (untuk toleransi drift)."""
    return totp_at(secret, int(time.time()) // step + offset, digits)


def totp_at(secret, counter, digits=6):
    key = base32_decode(secret)
    if key is None:
        return None
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    off = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[off:off + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def totp_verify(secret, code, window=1, step=30, digits=6):
    """Terima kode sekarang +/- `window` langkah (toleransi jam meleset)."""
    if not code or not str(code).isdigit():
        return False
    code = str(code).strip()
    counter = int(time.time()) // step
    for off in range(-window, window + 1):
        expect = totp_at(secret, counter + off, digits)
        if expect and hmac.compare_digest(expect, code):
            return True
    return False


def base32_decode(secret):
    """Decode base32 tanpa padding; toleran spasi dan huruf kecil."""
    if not secret:
        return None
    s = "".join(str(secret).split()).upper().rstrip("=")
    s += "=" * ((8 - len(s) % 8) % 8)
    try:
        return base64.b32decode(s, casefold=True)
    except Exception:
        try:
            return base64.b32decode(s)
        except Exception:
            return None


def base32_encode(raw):
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def generate_totp_secret(length=20):
    """Secret base32 acak (default 160-bit, standar authenticator)."""
    return base32_encode(secrets.token_bytes(length))


def otpauth_uri(secret, label, issuer="Santaka"):
    """URI otpauth:// untuk QR code di aplikasi authenticator."""
    from urllib.parse import quote
    return ("otpauth://totp/%s:%s?secret=%s&issuer=%s&algorithm=SHA1"
            "&digits=6&period=30" % (quote(issuer), quote(label), secret,
                                     quote(issuer)))


# ---------- session / token ----------

def sign(payload, secret):
    """HMAC-SHA256 base64url dari payload (tanpa padding)."""
    mac = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"),
                   hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")


def verify_sig(payload, sig, secret):
    if not sig:
        return False
    return hmac.compare_digest(sign(payload, secret), sig)


def new_token(nbytes=24):
    return secrets.token_urlsafe(nbytes)


def new_secret():
    return secrets.token_hex(32)


def new_recovery_codes(count=8):
    """Kode pemulihan sekali pakai, format xxxx-xxxx yang mudah dibaca."""
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"  # tanpa karakter ambigu
    codes = []
    for _ in range(count):
        part = lambda: "".join(secrets.choice(alphabet) for _ in range(4))
        codes.append("%s-%s" % (part(), part()))
    return codes
