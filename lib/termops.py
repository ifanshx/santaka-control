"""Terminal Web: eksekusi perintah shell terkendali dengan timeout, proteksi destruktif, dan tracking CWD."""
import os
import subprocess
import time

BLOCKED_PATTERNS = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "> /dev/sda",
    "> /dev/mmcblk",
    "dd if=/dev/zero of=/dev/",
    ":(){ :|:& };:",
]


def run_command(command_str, cwd="/root", timeout=30):
    """Eksekusi perintah di STB, lacak CWD, dan kembalikan output teks."""
    cmd_clean = (command_str or "").strip()
    if not cmd_clean:
        return {"rc": 0, "out": "", "err": "Perintah kosong", "time": 0, "cwd": cwd}

    # Proteksi perintah destruktif fatal
    for b in BLOCKED_PATTERNS:
        if b in cmd_clean:
            return {
                "rc": 1,
                "out": "",
                "err": "DIBLOKIR: Perintah berbahaya '%s' ditolak oleh sistem keamanan." % b,
                "time": 0,
                "cwd": cwd
            }

    if not os.path.exists(cwd):
        cwd = "/root"

    delim = "__SC_PWD__"
    # Bungkus perintah agar outputkan PWD baru setelah eksekusi
    wrapped_script = f"alias ls='ls --color=auto' 2>/dev/null; {cmd_clean}\n__RET=$?\necho '{delim}:'$PWD\nexit $__RET"

    t0 = time.time()
    try:
        proc = subprocess.Popen(
            ["/bin/bash", "-c", wrapped_script],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace"
        )
        try:
            out, err = proc.communicate(timeout=timeout)
            duration = round(time.time() - t0, 3)

            new_cwd = cwd
            clean_out = out or ""
            if delim + ":" in clean_out:
                parts = clean_out.rsplit(delim + ":", 1)
                clean_out = parts[0].rstrip("\r\n")
                new_cwd = parts[1].splitlines()[0].strip() or cwd

            return {
                "rc": proc.returncode,
                "out": clean_out,
                "err": err or "",
                "time": duration,
                "cwd": new_cwd
            }
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
            return {
                "rc": 124,
                "out": out or "",
                "err": f"Perintah terhenti karena melebihi batas waktu {timeout} detik.",
                "time": timeout,
                "cwd": cwd
            }
    except Exception as e:
        return {
            "rc": 1,
            "out": "",
            "err": str(e),
            "time": round(time.time() - t0, 3),
            "cwd": cwd
        }
