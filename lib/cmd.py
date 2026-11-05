"""Eksekusi perintah yang aman: selalu array argumen, tidak pernah shell string."""
import subprocess
import shlex

DEFAULT_TIMEOUT = 20


class CommandError(Exception):
    def __init__(self, argv, rc, out, err):
        self.argv = argv
        self.rc = rc
        self.out = out
        self.err = err
        super().__init__("perintah gagal (rc=%s): %s" % (rc, " ".join(argv[:3])))


def run(argv, timeout=DEFAULT_TIMEOUT, cwd=None, env=None, check=False, input_text=None):
    """Jalankan argv (list). Kembalikan (rc, stdout, stderr).

    argv WAJIB list -> tidak ada interpolasi shell, jadi tidak ada shell injection.
    """
    if not isinstance(argv, (list, tuple)) or not argv:
        raise ValueError("argv harus list tidak kosong")
    argv = [str(a) for a in argv]
    try:
        proc = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
            timeout=timeout,
            cwd=cwd,
            env=env,
            text=True,
            errors="replace",
        )
    except FileNotFoundError:
        return 127, "", "binary tidak ditemukan: %s" % argv[0]
    except subprocess.TimeoutExpired:
        return 124, "", "timeout setelah %ss" % timeout
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if check and proc.returncode != 0:
        raise CommandError(argv, proc.returncode, out, err)
    return proc.returncode, out, err


def ok(argv, timeout=DEFAULT_TIMEOUT):
    """True kalau perintah sukses."""
    rc, _, _ = run(argv, timeout)
    return rc == 0


def out(argv, timeout=DEFAULT_TIMEOUT, default=""):
    """stdout kalau sukses, kalau gagal kembalikan default."""
    rc, o, e = run(argv, timeout)
    return o if rc == 0 else default


def shell_line(argv):
    """Representasi perintah untuk ditampilkan/di-audit (bukan untuk dieksekusi)."""
    return " ".join(shlex.quote(a) for a in argv)
