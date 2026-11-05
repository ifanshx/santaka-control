"""Pembaca log: journalctl (unit/sistem), dmesg, dan log akses Caddy."""
from . import cmd, validate


def journal_unit(unit=None, lines=200, priority=None):
    n = validate.safe_int(lines, 10, 5000, 200)
    argv = ["journalctl", "-n", str(n), "--no-pager", "--output=short-iso"]
    if unit and validate.unit(unit):
        argv += ["-u", unit]
    if priority:
        argv += ["-p", str(validate.safe_int(priority, 0, 7, 6))]
    rc, out, err = cmd.run(argv, timeout=25)
    return out or err or "(tidak ada entri)"


def dmesg(lines=200):
    n = validate.safe_int(lines, 10, 5000, 200)
    rc, out, err = cmd.run(["dmesg", "--time-format=iso"], timeout=15)
    if rc != 0 or not out:
        rc, out, err = cmd.run(["dmesg"], timeout=15)
    if rc != 0 and err:
        return err
    rows = (out or "").splitlines()
    return "\n".join(rows[-n:])


def caddy_access(lines=200):
    """Log akses Caddy: journal unit caddy, fallback ke berkas log."""
    n = validate.safe_int(lines, 10, 5000, 200)
    rc, out, err = cmd.run([
        "journalctl", "-u", "caddy", "-n", str(n), "--no-pager",
        "--output=short-iso"
    ], timeout=20)
    if rc == 0 and out:
        return out
    for path in ("/var/log/caddy/access.log", "/var/log/caddy.log"):
        rc2, out2, _ = cmd.run(["tail", "-n", str(n), path], timeout=10)
        if rc2 == 0 and out2:
            return out2
    return err or "(log akses belum tersedia)"
