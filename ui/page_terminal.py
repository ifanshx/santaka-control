"""Halaman Web Terminal / Console: shell Linux interaktif melalui panel."""
import json
import platform

from ui import components as C
from ui import layout
from lib import ops, stats


def _primary_ip():
    """Alamat IPv4 antarmuka aktif pertama, kosong bila tak terdeteksi."""
    try:
        for dev in ops.interfaces():
            if str(dev.get("state") or "").lower() != "up":
                continue
            for addr in dev.get("addrs") or []:
                if ":" not in addr:
                    return addr.split("/")[0]
    except Exception:
        pass
    return ""


def _os_pretty():
    """Nama distro + versi bila tersedia, selain itu sistem + kernel."""
    try:
        rel = platform.freedesktop_os_release()
    except (AttributeError, OSError):
        rel = {}
    name = " ".join(x for x in (rel.get("NAME"), rel.get("VERSION")) if x)
    if name:
        return name
    return "%s %s" % (platform.system() or "Linux", stats.uname()["kernel"])


def render(req, app, sess, qs, t):
    csrf = req.csrf_token(sess)
    base = layout.BASE_PATH
    user = str(app.cfg.get("terminal_user") or "root")
    host = str(app.cfg.get("hostname") or "localhost")
    ip = _primary_ip()
    data_mount = str(app.cfg.get("data_mount") or "/mnt/data")
    web_root = str(app.cfg.get("web_root") or "/var/www")
    mem = stats.memory()
    mem_line = "%.0f MB RAM" % mem["total_mb"]
    if mem.get("swap_total_mb"):
        mem_line += " + %.0f MB swap" % mem["swap_total_mb"]

    prompt_js = json.dumps("%s@%s" % (user, host))
    session_js = json.dumps(ip or "tty")

    html = f"""
<!-- TOMBOL PERINTAH CEPAT (STB QUICK CHIPS) -->
<div class="card mb16 p12">
  <div class="row space-between align-center flex-wrap gap8">
    <div class="row gap8 align-center flex-wrap">
      <span class="text-xs text-muted bold mr8">PERINTAH CEPAT:</span>
      <button type="button" class="chip text-xs" data-cmd="free -m">free -m</button>
      <button type="button" class="chip text-xs" data-cmd="df -h / {data_mount}">df -h (Disk)</button>
      <button type="button" class="chip text-xs" data-cmd="uptime">uptime</button>
      <button type="button" class="chip text-xs" data-cmd="ss -tulpn">ss -tulpn (Port)</button>
      <button type="button" class="chip text-xs" data-cmd="systemctl status nginx mariadb redis-server --no-pager">status stack</button>
      <button type="button" class="chip text-xs" data-cmd="curl -sS -I http://127.0.0.1:{C.e(str(app.cfg.get('port') or 8081))}">curl panel</button>
      <button type="button" class="chip text-xs" data-cmd="ls -la {C.e(web_root)}">ls web root</button>
      <button type="button" class="chip text-xs" data-cmd="top -b -n 1 | head -15">top (Proses)</button>
    </div>
    <span class="text-xs text-muted">Shortcut: <kbd class="kbd-hint">Ctrl + L</kbd> bersihkan layar</span>
  </div>
</div>

<!-- OTENTIK LINUX TERMINAL WINDOW (MACOS OBSIDIAN SHELL) -->
<div class="terminal-window card mb24" id="term-window" style="background:#080C14;border:1px solid #1E293B;box-shadow:0 20px 25px -5px rgba(0,0,0,0.5);">
  <div class="terminal-bar row space-between align-center px16 py8" style="background:#0F172A;border-bottom:1px solid #1E293B;">
    <div class="row gap8 align-center">
      <div class="row gap6">
        <span class="term-dot red"></span>
        <span class="term-dot yellow"></span>
        <span class="term-dot green"></span>
      </div>
      <span class="term-title ml8 text-xs mono font-bold" id="term-bar-title" style="color:#94A3B8;">{C.e(user)}@{C.e(host)}: ~ ({C.e(ip or "tty")})</span>
    </div>
    <div class="row gap8 align-center">
      <button type="button" class="btn btn-sm btn-outline" id="btn-term-copy" title="Salin seluruh isi log terminal" style="height:24px;padding:2px 8px;font-size:11px;">Salin Log</button>
      <button type="button" class="btn btn-sm btn-outline" id="btn-term-clear" title="Bersihkan tampilan layar (Ctrl+L)" style="height:24px;padding:2px 8px;font-size:11px;">Bersihkan (Ctrl+L)</button>
      <span class="badge badge-success text-xs font-mono" id="term-status-badge">ONLINE</span>
    </div>
  </div>
  
  <!-- TERMINAL BODY WITH INLINE PROMPT ARCHITECTURE -->
  <div class="terminal-body p16 mono" id="term-body" style="height:520px;max-height:700px;overflow-y:auto;background:#080C14;color:#F8FAFC;font-size:13px;line-height:1.6;cursor:text;">
    <div id="term-history">
      <div class="term-motd mb12" id="initial-motd">
        <span style="color:#FBBF24;font-weight:bold;">  {C.e(host.upper())}</span><br>
        <span style="color:#94A3B8;">  {C.e(_os_pretty())} {C.e(stats.uname()["arch"])}</span><br>
        <span style="color:#94A3B8;">  IP: <span style="color:#10B981;font-weight:bold;">{C.e(ip or "—")}</span> &middot; Shell: <span style="color:#38BDF8;">{C.e(user)}</span></span><br>
        <span style="color:#94A3B8;">  Data: <span style="color:#10B981;font-weight:bold;">{C.e(data_mount)}</span> &middot; {C.e(mem_line)}</span><br>
        <br>
        <span style="color:#64748B;">  Ketik perintah shell di bawah dan tekan Enter. Navigasi riwayat: &uarr; / &darr; &middot; Bersihkan: Ctrl+L</span><br>
        <span style="color:#334155;">------------------------------------------------------------------------------------------------</span>
      </div>
    </div>
    <div class="term-active-line row align-center" id="term-active-line" style="margin-top:8px;">
      <span class="term-prompt mono font-bold mr8" id="term-prompt" style="color:#10B981;white-space:nowrap;user-select:none;">{C.e(user)}@{C.e(host)}:~#</span>
      <input type="text" id="term-input" class="term-real-input mono" autocomplete="off" spellcheck="false" autofocus />
    </div>
  </div>
</div>

<script>
(function(){{
var termBody = document.getElementById('term-body');
var termHistory = document.getElementById('term-history');
var termInput = document.getElementById('term-input');
var termPrompt = document.getElementById('term-prompt');
var barTitle = document.getElementById('term-bar-title');
var statusBadge = document.getElementById('term-status-badge');
var termWindow = document.getElementById('term-window');
var initialMotd = document.getElementById('initial-motd');
var motdHtml = initialMotd ? initialMotd.outerHTML : '';

var currentCwd = '/root';
var promptUser = {prompt_js};
var sessionTag = {session_js};
var cmdHistory = [];
var histIndex = -1;

function updateCwdDisplay(newCwd){{
  currentCwd = newCwd || '/root';
  var shortCwd = currentCwd === '/root' ? '~' : currentCwd;
  if (termPrompt) termPrompt.textContent = promptUser + ':' + shortCwd + '#';
  if (barTitle) barTitle.textContent = promptUser + ': ' + shortCwd + ' (' + sessionTag + ')';
}}

function clearTerm(){{
  termHistory.innerHTML = motdHtml;
  termInput.value = '';
  termInput.focus();
  termBody.scrollTop = termBody.scrollHeight;
}}

function copyTermOutput(){{
  if (!navigator.clipboard) {{
    alert('Clipboard API tidak didukung browser ini.');
    return;
  }}
  navigator.clipboard.writeText(termBody.innerText || '')
    .then(function(){{
      if (window.SC && window.SC.toast) window.SC.toast('Tersalin', 'Isi log terminal disalin ke clipboard', 'ok');
      else alert('Log terminal berhasil disalin!');
    }})
    .catch(function(err){{ alert('Gagal menyalin: ' + err); }});
}}

function ansiToHtml(str){{
  if (!str) return '';
  var map = {{
    '1': 'font-weight:bold;',
    '30': 'color:#64748B;',
    '31': 'color:#F87171;',
    '32': 'color:#34D399;font-weight:bold;',
    '33': 'color:#FBBF24;',
    '34': 'color:#60A5FA;font-weight:bold;',
    '35': 'color:#F472B6;',
    '36': 'color:#22D3EE;',
    '37': 'color:#F8FAFC;',
    '90': 'color:#94A3B8;',
    '91': 'color:#F87171;',
    '92': 'color:#34D399;',
    '93': 'color:#FBBF24;',
    '94': 'color:#60A5FA;',
    '95': 'color:#F472B6;',
    '96': 'color:#22D3EE;',
    '97': 'color:#FFFFFF;'
  }};
  var escaped = str.replace(/[&<>"']/g, function(c){{
    return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[c];
  }});
  return escaped.replace(/\\x1b\\[([0-9;]+)m/g, function(match, codes){{
    if (codes === '0' || !codes) return '</span>';
    var styles = codes.split(';').map(function(c){{ return map[c] || ''; }}).join('');
    return styles ? '<span style="' + styles + '">' : '';
  }});
}}

function submitCmd(overrideCmd){{
  var cmd = (overrideCmd !== undefined ? overrideCmd : termInput.value).trim();
  if (!cmd) return;

  if (cmd === 'clear' || cmd === 'cls') {{
    clearTerm();
    return;
  }}

  if (!cmdHistory.length || cmdHistory[cmdHistory.length - 1] !== cmd){{
    cmdHistory.push(cmd);
  }}
  histIndex = cmdHistory.length;
  termInput.value = '';
  termInput.disabled = true;
  if (statusBadge) {{
    statusBadge.className = 'badge badge-warning text-xs font-mono';
    statusBadge.textContent = 'RUNNING';
  }}

  var shortCwd = currentCwd === '/root' ? '~' : currentCwd;
  var cmdBlock = document.createElement('div');
  cmdBlock.className = 'term-cmd-block mt8';
  cmdBlock.innerHTML = '<div class="row align-center"><span class="term-prompt mono font-bold" style="color:#10B981;white-space:nowrap;user-select:none;">' +
    escapeHtml(promptUser + ':' + shortCwd + '#') + '</span> <b class="mono text-white" style="margin-left:8px;">' + escapeHtml(cmd) + '</b></div>';
  termHistory.appendChild(cmdBlock);
  termBody.scrollTop = termBody.scrollHeight;

  fetch('{base}/api/terminal/exec', {{
    method: 'POST',
    headers: {{
      'Content-Type': 'application/json',
      'X-CSRF': '{csrf}'
    }},
    body: JSON.stringify({{ cmd: cmd, cwd: currentCwd }})
  }})
  .then(r => r.json())
  .then(res => {{
    var outBox = document.createElement('div');
    outBox.className = 'term-result mt4 mb8';

    if (res.ok) {{
      var data = res.data || res;
      if (data.cwd) updateCwdDisplay(data.cwd);

      var text = (data.out || '') + (data.err ? '\\n[STDERR]\\n' + data.err : '');
      var renderedHtml = ansiToHtml(text);
      if (!renderedHtml.trim()) {{
        renderedHtml = '<span style="color:#64748B;">(perintah selesai tanpa keluaran output)</span>';
      }}
      outBox.innerHTML = '<pre class="mono text-xs m0" style="white-space:pre-wrap;word-break:break-all;line-height:1.5;">' + renderedHtml + '</pre>';

      var metaLine = document.createElement('div');
      metaLine.className = 'text-xs text-muted mt4';
      var statusColor = data.rc === 0 ? 'color:#10B981;' : 'color:#EF4444;';
      metaLine.innerHTML = '<span style="' + statusColor + 'font-weight:bold;">' +
        (data.rc === 0 ? '&#10003; Exit 0' : '&#10005; Exit ' + data.rc) +
        '</span> &middot; ' + (data.time || 0) + 's';
      outBox.appendChild(metaLine);
    }} else {{
      outBox.innerHTML = '<div class="text-danger mono text-xs">[ERROR]: ' + escapeHtml(res.error || 'Eksekusi gagal') + '</div>';
    }}

    termHistory.appendChild(outBox);
    termBody.scrollTop = termBody.scrollHeight;
  }})
  .catch(err => {{
    var errBox = document.createElement('div');
    errBox.className = 'text-danger mono text-xs mt4';
    errBox.textContent = '[NETWORK ERROR]: ' + err;
    termHistory.appendChild(errBox);
  }})
  .finally(function(){{
    termInput.disabled = false;
    if (statusBadge) {{
      statusBadge.className = 'badge badge-success text-xs font-mono';
      statusBadge.textContent = 'ONLINE';
    }}
    termInput.focus();
    termBody.scrollTop = termBody.scrollHeight;
  }});
}}

function escapeHtml(text){{
  var map = {{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }};
  return String(text || '').replace(/[&<>"']/g, function(m){{ return map[m]; }});
}}

// Keyboard listeners on terminal input
termInput.addEventListener('keydown', function(e){{
  if (e.key === 'Enter') {{
    e.preventDefault();
    submitCmd();
  }} else if (e.key === 'ArrowUp') {{
    e.preventDefault();
    if (cmdHistory.length > 0 && histIndex > 0) {{
      histIndex--;
      termInput.value = cmdHistory[histIndex];
    }}
  }} else if (e.key === 'ArrowDown') {{
    e.preventDefault();
    if (cmdHistory.length > 0 && histIndex < cmdHistory.length - 1) {{
      histIndex++;
      termInput.value = cmdHistory[histIndex];
    }} else {{
      histIndex = cmdHistory.length;
      termInput.value = '';
    }}
  }}
}});

// Global terminal shortcuts: Ctrl+L clears, click window focuses input
document.addEventListener('keydown', function(e){{
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'l') {{
    if (termWindow && termWindow.contains(document.activeElement)) {{
      e.preventDefault();
      clearTerm();
    }}
  }}
}});

termWindow.addEventListener('click', function(e){{
  if (!window.getSelection().toString()) {{
    termInput.focus();
  }}
}});

document.getElementById('btn-term-clear').addEventListener('click', clearTerm);
document.getElementById('btn-term-copy').addEventListener('click', copyTermOutput);

// Quick command chips delegation
document.addEventListener('click', function(e){{
  var chip = e.target.closest('[data-cmd]');
  if (chip) {{
    var cmd = chip.getAttribute('data-cmd');
    submitCmd(cmd);
  }}
}});

updateCwdDisplay('/root');
termInput.focus();
}})();
</script>
"""
    return layout.shell(sess, app, "terminal", "Web Terminal",
                        "Terminal shell interaktif dengan setiap perintah tercatat di jejak audit",
                        html, t)
