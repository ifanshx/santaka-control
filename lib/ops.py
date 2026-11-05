"""Operasi sistem: Docker, penyimpanan, jaringan/firewall, dan jadwal."""
import json
import os
import re

from . import cmd, validate

DOCKER_ACTIONS = ("start", "stop", "restart", "pause", "unpause", "remove")


class OpError(Exception):
    pass


# ==================== DOCKER ====================

def docker_available():
    rc, _, _ = cmd.run(["docker", "info"], timeout=8)
    return rc == 0


def docker_containers():
    rc, out, err = cmd.run([
        "docker", "ps", "-a", "--no-trunc",
        "--format", "{{.ID}}|{{.Names}}|{{.Image}}|{{.State}}|{{.Status}}|"
                    "{{.Ports}}|{{.CreatedAt}}"], timeout=15)
    if rc != 0:
        raise OpError((err or out or "docker ps gagal").strip()[:240])
    rows = []
    for line in (out or "").splitlines():
        p = line.split("|")
        if len(p) < 7:
            continue
        rows.append({"id": p[0][:12], "full_id": p[0], "name": p[1],
                     "image": p[2], "state": p[3], "status": p[4],
                     "ports": p[5], "created": p[6]})
    return rows


def docker_images():
    rc, out, _ = cmd.run(["docker", "images",
                          "--format", "{{.Repository}}:{{.Tag}}|{{.ID}}|{{.Size}}|{{.CreatedSince}}"],
                         timeout=15)
    rows = []
    for line in (out or "").splitlines():
        p = line.split("|")
        if len(p) >= 4:
            rows.append({"name": p[0], "id": p[1][:12], "size": p[2],
                         "created": p[3]})
    return rows


def docker_volumes():
    rc, out, _ = cmd.run(["docker", "volume", "ls",
                          "--format", "{{.Name}}|{{.Driver}}"], timeout=12)
    rows = []
    for line in (out or "").splitlines():
        p = line.split("|")
        if p and p[0]:
            rows.append({"name": p[0], "driver": p[1] if len(p) > 1 else ""})
    return rows


def docker_networks():
    rc, out, _ = cmd.run(["docker", "network", "ls",
                          "--format", "{{.Name}}|{{.Driver}}|{{.Scope}}"], timeout=12)
    rows = []
    for line in (out or "").splitlines():
        p = line.split("|")
        if p and p[0]:
            rows.append({"name": p[0], "driver": p[1] if len(p) > 1 else "",
                         "scope": p[2] if len(p) > 2 else ""})
    return rows


def docker_action(name, act):
    if not validate.container_id(name):
        raise OpError("nama kontainer tidak sah")
    if act not in DOCKER_ACTIONS:
        raise OpError("aksi tidak dikenal: %s" % act)
    argv = ["docker", "rm", "-f", name] if act == "remove" else ["docker", act, name]
    rc, out, err = cmd.run(argv, timeout=60)
    if rc != 0:
        raise OpError((err or out or "docker menolak").strip()[:300])
    return True


def docker_logs(name, lines=200):
    if not validate.container_id(name):
        raise OpError("nama kontainer tidak sah")
    n = validate.safe_int(lines, 10, 5000, 200)
    rc, out, err = cmd.run(["docker", "logs", "--tail", str(n), name], timeout=20)
    return (out or "") + (err or "") or "(tidak ada log)"


# ==================== PENYIMPANAN ====================

def disks():
    rc, out, err = cmd.run(["lsblk", "-J", "-o",
                            "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,RO,RM"],
                           timeout=15)
    if rc != 0:
        raise OpError((err or out or "lsblk gagal")[:240])
    try:
        data = json.loads(out or "{}")
    except ValueError:
        raise OpError("keluaran lsblk tidak dapat dibaca")
    rows = []

    def walk(nodes, depth=0):
        for n in nodes or []:
            rows.append({
                "name": n.get("name", ""), "size": n.get("size", ""),
                "type": n.get("type", ""), "fstype": n.get("fstype") or "",
                "mount": n.get("mountpoint") or "",
                "model": (n.get("model") or "").strip(),
                "ro": bool(n.get("ro")), "rm": bool(n.get("rm")),
                "depth": depth,
            })
            walk(n.get("children"), depth + 1)

    walk(data.get("blockdevices"))
    return rows


def fstab():
    try:
        with open("/etc/fstab", "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()[:20000]
    except OSError:
        return ""


def smart(device):
    if not re.match(r"^/dev/[a-z]{1,8}[0-9]{0,3}$", device or ""):
        raise OpError("nama perangkat tidak sah")
    rc, out, err = cmd.run(["smartctl", "-H", "-A", device], timeout=25)
    blob = (out or "") + (err or "")
    health = ""
    for line in blob.splitlines():
        if "overall-health" in line.lower() or "SMART Health Status" in line:
            health = line.strip()
            break
    return {"device": device, "health": health or "tidak dilaporkan",
            "raw": blob[:4000]}


# ==================== JARINGAN & FIREWALL ====================

def interfaces():
    rc, out, _ = cmd.run(["ip", "-j", "addr"], timeout=10)
    rows = []
    if rc == 0 and out:
        try:
            for d in json.loads(out):
                rows.append({
                    "name": d.get("ifname"),
                    "state": d.get("operstate"),
                    "addrs": [a.get("local") + "/" + str(a.get("prefixlen"))
                              for a in (d.get("addr_info") or [])
                              if a.get("family") == "inet"],
                })
            return rows
        except ValueError:
            pass
    rc2, out2, _ = cmd.run(["ip", "-br", "addr"], timeout=10)
    for line in (out2 or "").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            rows.append({"name": parts[0], "state": parts[1],
                         "addrs": parts[2:]})
    return rows


def listening():
    rc, out, _ = cmd.run(["ss", "-tlnp"], timeout=10)
    rows = []
    for line in (out or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        proc = ""
        m = re.search(r'users:\(\("([^"]+)"', line)
        if m:
            proc = m.group(1)
        rows.append({"local": parts[3], "proc": proc, "raw": line.strip()[:160]})
    return rows


def firewall_rules():
    rc, out, err = cmd.run(["iptables", "-S"], timeout=10)
    return (out or err or "").strip()[:8000]


def fail2ban():
    rc, out, _ = cmd.run(["fail2ban-client", "status"], timeout=12)
    jails = []
    m = re.search(r"Jail list:\s*(.+)", out or "")
    if m:
        jails = [j.strip() for j in m.group(1).split(",") if j.strip()]
    detail = {}
    for jail in jails:
        rc2, out2, _ = cmd.run(["fail2ban-client", "status", jail], timeout=10)
        banned = []
        mb = re.search(r"Banned IP list:\s*(.*)", out2 or "")
        if mb:
            banned = [b for b in mb.group(1).split() if b]
        cur = re.search(r"Currently banned:\s*(\d+)", out2 or "")
        tot = re.search(r"Total banned:\s*(\d+)", out2 or "")
        detail[jail] = {
            "banned": banned,
            "current": cur.group(1) if cur else "0",
            "total": tot.group(1) if tot else "0",
        }
    return {"available": rc == 0, "jails": jails, "detail": detail,
            "raw": (out or "")[:2000]}


def fail2ban_unban(jail, ip):
    if not jail or not re.match(r"^[A-Za-z0-9_\-]{1,32}$", jail):
        raise OpError("nama jail tidak sah")
    if not re.match(r"^[0-9a-fA-F:.]{3,45}$", ip or ""):
        raise OpError("alamat IP tidak sah")
    rc, out, err = cmd.run(["fail2ban-client", "set", jail, "unbanip", ip],
                           timeout=15)
    if rc != 0:
        raise OpError((err or out or "unban gagal").strip()[:240])
    return True


# ==================== JADWAL ====================

def crontab():
    rc, out, err = cmd.run(["crontab", "-l"], timeout=10)
    if rc != 0:
        return ""
    return out or ""


def save_crontab(text):
    """Tulis crontab baru. Validasi ringan: tidak boleh menyisipkan % berbahaya."""
    if len(text) > 100000:
        raise OpError("crontab terlalu panjang")
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith(("MAILTO", "PATH", "SHELL", "CRON_TZ")) and "=" in s:
            continue
        if len(s.split()) < 6:
            raise OpError("baris tidak valid: %s" % s[:60])
    tmp = "/tmp/sc-crontab-%d" % int(__import__("time").time())
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        rc, out, err = cmd.run(["crontab", tmp], timeout=15)
        if rc != 0:
            raise OpError((err or out or "crontab menolak").strip()[:240])
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    return True


def timers():
    rc, out, _ = cmd.run(["systemctl", "list-timers", "--all", "--no-pager",
                          "--no-legend", "--plain"], timeout=15)
    rows = []
    for line in (out or "").splitlines():
        parts = line.split()
        if len(parts) >= 5:
            rows.append({"next": " ".join(parts[0:3]), "unit": parts[-1],
                         "raw": line.strip()[:160]})
    return rows
