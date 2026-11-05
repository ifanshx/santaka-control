"""Operasi berkas yang terkurung di dalam root yang diizinkan.

Aturan: setiap path di-resolve ke realpath (symlink disusul), lalu diperiksa
apakah berada di dalam salah satu root. Tidak ada jalan keluar lewat '..'
maupun symlink.
"""
import os
import shutil
import stat
import time

from . import validate


class EscapeError(Exception):
    """Path berada di luar root yang diizinkan."""


class FsError(Exception):
    """Operasi berkas gagal."""


def _norm_roots(roots):
    out = []
    for r in roots or []:
        try:
            p = os.path.realpath(os.path.expanduser(str(r)))
        except (OSError, ValueError):
            continue
        if p and os.path.isdir(p):
            out.append(p)
    return out


def resolve(path, roots, must_exist=False):
    """Kembalikan realpath yang aman, atau lempar EscapeError."""
    if path is None:
        path = ""
    path = str(path)
    if "\x00" in path:
        raise EscapeError("path mengandung karakter terlarang")
    base = _norm_roots(roots)
    if not base:
        raise EscapeError("belum ada root yang dikonfigurasi")
    if not path:
        return base[0]
    if not os.path.isabs(path):
        path = os.path.join(base[0], path)
    real = os.path.realpath(path)
    for root in base:
        try:
            if os.path.commonpath([root, real]) == root:
                return real
        except ValueError:
            continue
    raise EscapeError("path di luar area yang diizinkan: %s" % path)


def roots(configured):
    """Root yang valid untuk ditampilkan di UI."""
    return _norm_roots(configured)


def info(path):
    try:
        st = os.lstat(path)
    except OSError:
        return None
    is_dir = stat.S_ISDIR(st.st_mode)
    return {
        "name": os.path.basename(path) or path,
        "path": path,
        "dir": is_dir,
        "size": 0 if is_dir else st.st_size,
        "mtime": int(st.st_mtime),
        "mode": oct(stat.S_IMODE(st.st_mode))[2:],
        "link": os.path.islink(path),
    }


def list_dir(path):
    try:
        names = os.listdir(path)
    except OSError as ex:
        raise FsError("tidak bisa membaca folder: %s" % ex.strerror)
    items = []
    for name in names:
        full = os.path.join(path, name)
        meta = info(full)
        if meta:
            items.append(meta)
    items.sort(key=lambda x: (not x["dir"], x["name"].lower()))
    return items


def parent_of(path, roots_cfg):
    """Folder induk, tetapi tidak melewati root."""
    p = os.path.dirname(path)
    try:
        return resolve(p, roots_cfg)
    except EscapeError:
        return None


def mkdir(base, name, roots_cfg):
    if not validate.filename(name):
        raise FsError("nama folder tidak sah")
    target = resolve(os.path.join(base, name), roots_cfg)
    if os.path.exists(target):
        raise FsError("sudah ada: %s" % name)
    try:
        os.makedirs(target, mode=0o755)
    except OSError as ex:
        raise FsError("gagal membuat folder: %s" % ex.strerror)
    return target


def rename(base, name, new_name, roots_cfg):
    if not validate.filename(name) or not validate.filename(new_name):
        raise FsError("nama berkas tidak sah")
    src = resolve(os.path.join(base, name), roots_cfg)
    dst = resolve(os.path.join(base, new_name), roots_cfg)
    if not os.path.exists(src):
        raise FsError("tidak ditemukan: %s" % name)
    if os.path.exists(dst):
        raise FsError("nama tujuan sudah dipakai")
    try:
        os.rename(src, dst)
    except OSError as ex:
        raise FsError("gagal mengubah nama: %s" % ex.strerror)
    return dst


def delete(base, name, roots_cfg, recursive=False):
    if not validate.filename(name):
        raise FsError("nama berkas tidak sah")
    target = resolve(os.path.join(base, name), roots_cfg)
    if target in _norm_roots(roots_cfg):
        raise FsError("tidak boleh menghapus root")
    if not os.path.exists(target) and not os.path.islink(target):
        raise FsError("tidak ditemukan: %s" % name)
    try:
        if os.path.isdir(target) and not os.path.islink(target):
            if recursive:
                shutil.rmtree(target)
            else:
                os.rmdir(target)          # hanya folder kosong
        else:
            os.unlink(target)
    except OSError as ex:
        raise FsError("gagal menghapus: %s" % ex.strerror)
    return True


def free_space(path):
    try:
        st = os.statvfs(path)
        return {
            "total": st.f_blocks * st.f_frsize,
            "free": st.f_bavail * st.f_frsize,
        }
    except (OSError, AttributeError):
        import shutil as sh
        try:
            t, u, f = sh.disk_usage(path)
            return {"total": t, "free": f}
        except OSError:
            return {"total": 0, "free": 0}


# ---------- unggahan multipart streaming ----------

MAX_UPLOAD = 512 * 1024 * 1024     # 512 MB per berkas


def _parse_boundary(content_type):
    for part in (content_type or "").split(";"):
        part = part.strip()
        if part.lower().startswith("boundary="):
            return part.split("=", 1)[1].strip('"')
    return None


def stream_multipart(rfile, content_length, content_type, dest_dir, roots_cfg,
                     chunk=64 * 1024):
    """Terima unggahan multipart tanpa menahan seluruh isi di memori.

    Kembalikan daftar {name, size, path}. Berkas ditulis ke .part lalu di-rename
    agar tidak ada berkas setengah jadi yang terlihat.
    """
    boundary = _parse_boundary(content_type)
    if not boundary:
        raise FsError("bounder multipart tidak ditemukan")
    if content_length <= 0:
        raise FsError("isi kosong")

    delim = b"--" + boundary.encode()
    remain = int(content_length)
    buf = b""

    def read_more(need=chunk):
        nonlocal remain, buf
        take = min(need, remain)
        if take <= 0:
            return False
        data = rfile.read(take)
        if not data:
            remain = 0
            return False
        remain -= len(data)
        buf += data
        return True

    def fill_until(marker):
        """Baca sampai marker ditemukan di buf. Kembalikan posisi marker."""
        while True:
            idx = buf.find(marker)
            if idx >= 0:
                return idx
            if remain <= 0:
                return buf.find(marker)
            if not read_more():
                return buf.find(marker)

    saved = []

    # lewati preamble sampai boundary pertama
    fill_until(delim)
    pos = buf.find(delim)
    if pos < 0:
        raise FsError("format multipart tidak valid")
    buf = buf[pos + len(delim):]

    while True:
        # akhir body: "--" setelah boundary
        if buf[:2] == b"--":
            break
        # buang CRLF sebelum header
        if buf[:2] == b"\r\n":
            buf = buf[2:]
        end = fill_until(b"\r\n\r\n")
        if end < 0:
            break
        headers_blob = buf[:end].decode("latin-1", "replace")
        buf = buf[end + 4:]

        fname = None
        for line in headers_blob.split("\r\n"):
            low = line.lower()
            if low.startswith("content-disposition:"):
                for piece in line.split(";"):
                    piece = piece.strip()
                    if piece.lower().startswith("filename="):
                        fname = piece.split("=", 1)[1].strip().strip('"')
        if not fname:
            # bagian tanpa berkas (field biasa) -> lewati
            nxt = fill_until(delim)
            if nxt < 0:
                break
            buf = buf[nxt + len(delim):]
            continue

        fname = os.path.basename(fname.replace("\\", "/"))
        if not validate.filename(fname):
            raise FsError("nama berkas tidak sah: %s" % fname)

        target = resolve(os.path.join(dest_dir, fname), roots_cfg)
        if os.path.isdir(target):
            raise FsError("sudah ada folder bernama %s" % fname)
        tmp = target + ".part"
        written = 0
        try:
            with open(tmp, "wb") as out:
                while True:
                    idx = fill_until(b"\r\n" + delim)
                    if idx < 0:
                        raise FsError("unggahan terputus")
                    chunk_data = buf[:idx]
                    if chunk_data:
                        out.write(chunk_data)
                        written += len(chunk_data)
                        if written > MAX_UPLOAD:
                            raise FsError("berkas melebihi batas 512 MB")
                    buf = buf[idx + 2 + len(delim):]
                    if buf[:2] == b"--":       # boundary penutup
                        buf = b"--"
                    break
            os.replace(tmp, target)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

        saved.append({"name": fname, "size": written, "path": target})
        if buf[:2] == b"--":
            break
    return saved


def read_text(path, roots_cfg, max_bytes=2*1024*1024):
    """Baca isi berkas teks secara aman di dalam roots yang diizinkan (maks 2 MB)."""
    target = resolve(path, roots_cfg)
    if not os.path.isfile(target):
        raise FsError("berkas tidak ditemukan")
    st = os.stat(target)
    if st.st_size > max_bytes:
        raise FsError("berkas terlalu besar untuk dibuka di editor (maksimal 2 MB)")
    try:
        with open(target, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        return {
            "name": os.path.basename(target),
            "path": target,
            "content": content,
            "size": st.st_size,
            "mtime": int(st.st_mtime),
        }
    except OSError as ex:
        raise FsError("gagal membaca berkas: %s" % ex.strerror)


def write_text(path, content, roots_cfg):
    """Tulis isi berkas teks secara atomik di dalam roots yang diizinkan."""
    target = resolve(path, roots_cfg)
    tmp = target + ".sc_tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(content or "")
        os.replace(tmp, target)
        return True
    except OSError as ex:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
        raise FsError("gagal menyimpan berkas: %s" % ex.strerror)


def touch(base, name, roots_cfg):
    """Buat berkas kosong baru secara aman."""
    if not validate.filename(name):
        raise FsError("nama berkas tidak sah")
    target = resolve(os.path.join(base, name), roots_cfg)
    if os.path.exists(target):
        raise FsError("berkas sudah ada: %s" % name)
    try:
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("")
        return target
    except OSError as ex:
        raise FsError("gagal membuat berkas: %s" % ex.strerror)
