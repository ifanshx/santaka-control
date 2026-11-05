/* ============================================================
   SANTAKA CONTROL — klien ringan (vanilla, tanpa framework)
   ~13 KB. Tidak ada request ke luar. Progressive: HTML tetap
   terbaca kalau JS gagal (form & link asli).
   ============================================================ */
(function () {
  "use strict";

  var CSRF = "";
  var TOASTS = null;
  /* CSRF dibaca segera: meta ada di <head>, sebelum skrip halaman berjalan. */
  var BASE = "";
  try {
    CSRF = (document.querySelector('meta[name="csrf"]') || {}).content || "";
    BASE = document.documentElement.getAttribute("data-base") || "";
  } catch (e) { CSRF = ""; BASE = ""; }

  /* ---------- util ---------- */
  function q(s, r) { return (r || document).querySelector(s); }
  function qa(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function bytes(n) {
    n = Number(n) || 0;
    var u = ["B", "KB", "MB", "GB", "TB"], i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return (i === 0 ? n : n.toFixed(1)) + " " + u[i];
  }
  function dur(sec) {
    sec = Math.max(0, Number(sec) || 0);
    var d = Math.floor(sec / 86400), h = Math.floor(sec % 86400 / 3600),
        m = Math.floor(sec % 3600 / 60);
    if (d) return d + "h " + h + "j";
    if (h) return h + "j " + m + "m";
    return m + "m";
  }
  function ago(ts) {
    if (!ts) return "—";
    var s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
    if (s < 60) return s + "s lalu";
    if (s < 3600) return Math.floor(s / 60) + "m lalu";
    if (s < 86400) return Math.floor(s / 3600) + "j lalu";
    return Math.floor(s / 86400) + "h lalu";
  }
  function hasta(ts) {
    if (!ts) return "—";
    return new Date(ts * 1000).toLocaleString("id-ID", {
      day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit"
    });
  }

  /* ---------- URL sadar-prefix ----------
     Panel bisa dipasang di sub-path (mis. /control). Semua panggilan panel
     memakai helper ini; endpoint /api/*, /static/*, dan absolut dibiarkan. */
  function url(path) {
    var p = String(path == null ? "" : path);
    if (!p) return BASE || "/";
    if (p.charAt(0) !== "/") p = "/" + p;
    if (p.indexOf("//") === 0) return p;
    if (/^\/(api|static)\//.test(p) || p.indexOf("/favicon") === 0) return p;
    if (!BASE) return p;
    return p === "/" ? BASE : BASE + p;
  }

  /* ---------- HTTP ---------- */
  function api(path, opt) {
    opt = opt || {};
    opt.headers = Object.assign({
      "X-CSRF": CSRF,
      "X-Requested-With": "santaka"
    }, opt.headers || {});
    if (opt.body && typeof opt.body !== "string" && !(opt.body instanceof FormData)) {
      opt.headers["Content-Type"] = "application/json";
      opt.body = JSON.stringify(opt.body);
    }
    return fetch(url(path), Object.assign({ credentials: "same-origin" }, opt))
      .then(function (res) {
        return res.text().then(function (txt) {
          var data;
          try { data = txt ? JSON.parse(txt) : {}; }
          catch (e) { data = { error: "respons tidak valid", raw: txt.slice(0, 400) }; }
          if (!res.ok) {
            var err = new Error(data.error || ("HTTP " + res.status));
            err.status = res.status;
            err.data = data;
            throw err;
          }
          return data;
        });
      });
  }

  /* ---------- toast ---------- */
  function toast(title, msg, kind) {
    if (!TOASTS) {
      TOASTS = q("#toasts") || (function () {
        var d = document.createElement("div");
        d.id = "toasts"; d.className = "toasts";
        document.body.appendChild(d); return d;
      })();
    }
    var t = document.createElement("div");
    t.className = "toast " + (kind || "info");
    t.setAttribute("role", "status");
    t.innerHTML = '<span class="tt">' + esc(title) + "</span>" +
                  (msg ? '<span class="ms">' + esc(msg) + "</span>" : "");
    TOASTS.appendChild(t);
    setTimeout(function () {
      t.style.opacity = "0";
      setTimeout(function () { t.remove(); }, 300);
    }, kind === "err" ? 7000 : 4000);
  }

  /* ---------- tombol sibuk (anti double-submit) ---------- */
  function busy(btn, on) {
    if (!btn) return;
    if (on) {
      btn.classList.add("loading");
      btn.disabled = true;
      if (!btn.dataset.label) btn.dataset.label = btn.innerHTML;
    } else {
      btn.classList.remove("loading");
      btn.disabled = false;
    }
  }

  /* ---------- konfirmasi type-to-confirm ---------- */
  function confirmDanger(opts) {
    return new Promise(function (resolve) {
      var w = document.createElement("div");
      w.className = "modal";
      w.setAttribute("role", "dialog");
      w.setAttribute("aria-modal", "true");
      w.innerHTML =
        '<div class="box"><div class="hd"><h3>' + esc(opts.title) + '</h3>' +
        '<button class="x" aria-label="Tutup">&times;</button></div>' +
        '<div class="bd">' +
          '<p class="mb8">' + (opts.body || "") + "</p>" +
          (opts.phrase
            ? '<div class="field mt8"><label for="cfp">Ketik <b class="mono">' +
              esc(opts.phrase) + "</b> untuk melanjutkan</label>" +
              '<input id="cfp" type="text" autocomplete="off" ' +
              'placeholder="' + esc(opts.phrase) + '"></div>'
            : "") +
        "</div>" +
        '<div class="ft"><button class="btn gh" data-no>Batal</button>' +
        '<button class="btn dg" data-yes' + (opts.phrase ? " disabled" : "") + ">" +
        esc(opts.ok || "Lanjutkan") + "</button></div></div>";
      document.body.appendChild(w);

      var yes = q("[data-yes]", w), no = q("[data-no]", w), x = q(".x", w);
      var inp = q("#cfp", w);
      function close(val) { w.remove(); document.removeEventListener("keydown", key); resolve(val); }
      function key(e) { if (e.key === "Escape") close(false); }
      document.addEventListener("keydown", key);

      if (inp) {
        inp.addEventListener("input", function () {
          yes.disabled = inp.value.trim() !== opts.phrase;
        });
        inp.focus();
      } else { yes.focus(); }
      yes.onclick = function () { close(true); };
      no.onclick = x.onclick = function () { close(false); };
      w.addEventListener("click", function (e) { if (e.target === w) close(false); });
    });
  }

  /* ---------- modal generik ---------- */
  function modal(opts) {
    var w = document.createElement("div");
    w.className = "modal";
    w.setAttribute("role", "dialog");
    w.setAttribute("aria-modal", "true");
    w.innerHTML =
      '<div class="box' + (opts.wide ? " wide" : "") + '">' +
        '<div class="hd"><h3>' + esc(opts.title) + '</h3>' +
        '<button class="x" aria-label="Tutup">&times;</button></div>' +
        '<div class="bd">' + (opts.body || "") + "</div>" +
        (opts.footer ? '<div class="ft">' + opts.footer + "</div>" : "") +
      "</div>";
    document.body.appendChild(w);
    var prev = document.activeElement;
    function close() {
      w.remove();
      document.removeEventListener("keydown", key);
      if (prev && prev.focus) prev.focus();
    }
    function key(e) {
      if (e.key === "Escape") { e.stopPropagation(); close(); }
      if (e.key === "Tab") {                       /* focus trap */
        var f = qa('a[href],button:not([disabled]),input:not([disabled]),select,textarea,[tabindex]:not([tabindex="-1"])', w);
        if (!f.length) return;
        var i = f.indexOf(document.activeElement);
        if (e.shiftKey && i <= 0) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && i === f.length - 1) { e.preventDefault(); f[0].focus(); }
      }
    }
    document.addEventListener("keydown", key);
    q(".x", w).onclick = close;
    w.addEventListener("click", function (e) { if (e.target === w) close(); });
    if (opts.onClose) w.addEventListener("remove", opts.onClose);
    var first = q("input,select,textarea,button.pk,.btn.pk", w) || q(".x", w);
    if (first) first.focus();
    return { el: w, close: close };
  }

  /* ---------- sidebar mobile ---------- */
  function initMobileNav() {
    var burger = q("#burger"), side = q(".side");
    if (!burger || !side) return;
    var scrim = null;
    function open() {
      side.classList.add("open");
      scrim = document.createElement("div");
      scrim.className = "scrim";
      scrim.onclick = close;
      document.body.appendChild(scrim);
      burger.setAttribute("aria-expanded", "true");
    }
    function close() {
      side.classList.remove("open");
      if (scrim) { scrim.remove(); scrim = null; }
      burger.setAttribute("aria-expanded", "false");
    }
    burger.onclick = function () {
      side.classList.contains("open") ? close() : open();
    };
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && side.classList.contains("open")) close();
    });
    qa("a", side).forEach(function (a) { a.addEventListener("click", close); });
  }

  /* ---------- tema (terang/gelap) — disimpan di cookie ---------- */
  function initTheme() {
    var btn = q("#themeBtn");
    if (!btn) return;
    btn.onclick = function () {
      var cur = document.documentElement.getAttribute("data-theme") || "paper";
      var nxt = (cur === "night" || cur === "dark") ? "paper" : "night";
      document.documentElement.setAttribute("data-theme", nxt);
      document.cookie = "sc_theme=" + nxt + ";path=/;max-age=31536000;samesite=lax";
      toast("Tema", nxt === "night" ? "Mode malam aktif (OLED Slate)" : "Mode terang aktif", "info");
    };
  }

  /* ============================================================
     COMMAND PALETTE (CTRL+K) — SPOTLIGHT QUICK NAVIGATOR
     ============================================================ */
  var PALETTE_ITEMS = [
    { title: "Dashboard", sub: "Ringkasan CPU, RAM, Suhu, Jaringan & Mount", grp: "Utama", icon: "dash", kw: "ringkasan cpu ram suhu dashboard home status telemetri", url: "/dash" },
    { title: "Websites & Vhosts", sub: "Kelola domain web, reverse proxy Nginx 1.30", grp: "Server", icon: "web", kw: "website domain vhost nginx proxy web", url: "/web" },
    { title: "Databases (MySQL)", sub: "MariaDB 10.11 LTS, dump backup SQL & phpMyAdmin", grp: "Server", icon: "db", kw: "database mysql mariadb sql tabel backup", url: "/db" },
    { title: "Redis Cache", sub: "Status memori port 6379, hit rate & flush cache", grp: "Server", icon: "redis", kw: "cache redis memori flush key", url: "/redis" },
    { title: "File Explorer", sub: "Jelajahi berkas server, upload & kuota 1 TB", grp: "Server", icon: "files", kw: "file berkas folder upload download explorer", url: "/files" },
    { title: "Service Manager", sub: "Manajemen systemd services, restart, start, stop", grp: "Server", icon: "svc", kw: "service layanan systemd restart stop start", url: "/svc" },
    { title: "Web Terminal", sub: "Akses shell Linux server langsung dari peramban", grp: "Server", icon: "terminal", kw: "terminal shell bash ssh konsol perintah", url: "/terminal" },
    { title: "System Logs", sub: "Pembaca journalctl, dmesg & web access log", grp: "Server", icon: "logs", kw: "log journal dmesg akses galat", url: "/logs" },
    { title: "Harddisk 1 TB", sub: "Kesehatan disk SMART, mount & fstab", grp: "Data & Sumber Daya", icon: "disk", kw: "disk harddisk smart mount partisi penyimpanan", url: "/storage" },
    { title: "Network & Tunnel", sub: "Port listening, Cloudflare tunnel & antarmuka", grp: "Data & Sumber Daya", icon: "net", kw: "jaringan network port tunnel cloudflare rx tx", url: "/network" },
    { title: "Security & Firewall", sub: "Kata sandi, 2FA authenticator & sesi aktif", grp: "Keamanan", icon: "shield", kw: "keamanan sandi password 2fa totp firewall sesi", url: "/security" },
    { title: "Admin Users", sub: "Daftar pengguna & peran akses panel", grp: "Keamanan", icon: "user", kw: "pengguna user admin peran role akun", url: "/users" },
    { title: "Audit Logs", sub: "Riwayat jejak mutasi & keamanan IP asli", grp: "Keamanan", icon: "clock", kw: "audit jejak log aktivitas ip keamanan", url: "/audit" },
    { title: "Cron Jobs", sub: "Jadwal crontab & systemd timer", grp: "Sistem", icon: "cron", kw: "cron jadwal timer systemd crontab", url: "/cron" },
    { title: "Maintenance", sub: "Pembaruan paket apt, fstrim SSD & cache", grp: "Sistem", icon: "wrench", kw: "perawatan update apt trim cache pemeliharaan", url: "/maintenance" },
    { title: "Ganti Tema (Terang / Gelap)", sub: "Beralih antara mode Terang dan OLED Slate", grp: "Aksi Cepat", kw: "tema gelap terang dark light mode", act: "theme" },
    { title: "Ganti Bahasa (ID / EN)", sub: "Beralih bahasa antarmuka", grp: "Aksi Cepat", kw: "bahasa indonesia inggris language id en", act: "lang" },
    { title: "Keluar (Logout)", sub: "Akhiri sesi login aman", grp: "Aksi Cepat", kw: "keluar logout keluar akun sesi", act: "logout" }
  ];

  function initCommandPalette() {
    var overlay = q("#cmdOverlay"), input = q("#cmdInput"), list = q("#cmdList"), closeBtn = q("#cmdClose");
    var trigger = q("#cmdTrigger");
    if (!overlay || !input || !list) return;

    var selectedIdx = 0;
    var filtered = PALETTE_ITEMS.slice();

    function renderList() {
      if (!filtered.length) {
        list.innerHTML = '<div class="cmd-empty">Tidak ada menu atau aksi yang cocok.</div>';
        return;
      }
      var html = "";
      filtered.forEach(function (item, idx) {
        var isSel = idx === selectedIdx ? " selected" : "";
        var badge = item.grp ? '<span class="cmd-grp">' + esc(item.grp) + '</span>' : '';
        html += '<div class="cmd-item' + isSel + '" data-idx="' + idx + '">' +
          '<div class="cmd-item-main">' +
            '<div class="cmd-item-title">' + esc(item.title) + badge + '</div>' +
            '<div class="cmd-item-sub">' + esc(item.sub || "") + '</div>' +
          '</div>' +
          '<span class="cmd-enter-hint">↵</span>' +
        '</div>';
      });
      list.innerHTML = html;

      // Scroll selected into view
      var selEl = list.querySelector(".cmd-item.selected");
      if (selEl) {
        selEl.scrollIntoView({ block: "nearest" });
      }
    }

    function openPalette() {
      overlay.classList.remove("hidden");
      input.value = "";
      filtered = PALETTE_ITEMS.slice();
      selectedIdx = 0;
      renderList();
      setTimeout(function () { input.focus(); }, 50);
    }

    function closePalette() {
      overlay.classList.add("hidden");
    }

    function execute(item) {
      closePalette();
      if (item.url) {
        location.href = url(item.url);
      } else if (item.act === "theme") {
        var themeBtn = q("#themeBtn");
        if (themeBtn) themeBtn.click();
      } else if (item.act === "lang") {
        var langBtn = q("#langBtn");
        if (langBtn) langBtn.click();
      } else if (item.act === "logout") {
        var logoutBtn = q("#logoutBtn");
        if (logoutBtn) logoutBtn.click();
      }
    }

    if (trigger) trigger.onclick = openPalette;
    if (closeBtn) closeBtn.onclick = closePalette;
    overlay.onclick = function (e) { if (e.target === overlay) closePalette(); };

    input.addEventListener("input", function () {
      var qVal = input.value.trim().toLowerCase();
      if (!qVal) {
        filtered = PALETTE_ITEMS.slice();
      } else {
        filtered = PALETTE_ITEMS.filter(function (it) {
          return it.title.toLowerCase().indexOf(qVal) > -1 ||
                 (it.sub && it.sub.toLowerCase().indexOf(qVal) > -1) ||
                 (it.grp && it.grp.toLowerCase().indexOf(qVal) > -1) ||
                 (it.kw && it.kw.indexOf(qVal) > -1);
        });
      }
      selectedIdx = 0;
      renderList();
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (filtered.length > 0) {
          selectedIdx = (selectedIdx + 1) % filtered.length;
          renderList();
        }
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (filtered.length > 0) {
          selectedIdx = (selectedIdx - 1 + filtered.length) % filtered.length;
          renderList();
        }
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (filtered.length > 0 && filtered[selectedIdx]) {
          execute(filtered[selectedIdx]);
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        closePalette();
      }
    });

    list.addEventListener("click", function (e) {
      var itEl = e.target.closest(".cmd-item");
      if (!itEl) return;
      var idx = parseInt(itEl.getAttribute("data-idx"), 10);
      if (!isNaN(idx) && filtered[idx]) {
        execute(filtered[idx]);
      }
    });

    // Global shortcut Ctrl+K / Cmd+K
    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        overlay.classList.contains("hidden") ? openPalette() : closePalette();
      } else if (e.key === "Escape" && !overlay.classList.contains("hidden")) {
        closePalette();
      }
    });
  }

  /* ---------- bahasa ---------- */
  function initLang() {
    var btn = q("#langBtn");
    if (!btn) return;
    btn.textContent = (document.documentElement.lang === "en") ? "EN" : "ID";
    btn.onclick = function () {
      var cur = document.documentElement.getAttribute("lang") || "id";
      var nxt = cur === "id" ? "en" : "id";
      document.cookie = "sc_lang=" + nxt + ";path=/;max-age=31536000;samesite=lax";
      location.reload();
    };
  }

  /* ---------- utilitas form ---------- */
  function formData(form) {
    var out = {};
    qa("input[name],select[name],textarea[name],checkbox[name]", form).forEach(function (el) {
      if (el.type === "checkbox") out[el.name] = el.checked;
      else out[el.name] = el.value;
    });
    return out;
  }

  /* ---------- staged login: request 2FA only after password verification ---------- */
  function initLogin() {
    var form = q("#loginForm"), section = q("#loginCodeSection");
    if (!form || !section) return;
    var user = q('[name="username"]', form);
    var pass = q('[name="password"]', form);
    var code = q('[name="code"]', form);
    var button = q("#loginSubmit", form);
    var errorBox = q("#loginError");
    var errorText = errorBox && q(".ms", errorBox);
    form.addEventListener("submit", function (ev) {
      if (form.dataset.passwordChecked === "1") return;
      ev.preventDefault();
      if (!user.value || !pass.value || (button && button.disabled)) return;
      if (errorBox) errorBox.hidden = true;
      if (button) button.disabled = true;
      api("/api/login/check", {
        method: "POST",
        body: { username: user.value, password: pass.value }
      }).then(function (result) {
        form.dataset.passwordChecked = "1";
        if (result.requires_2fa) {
          section.hidden = false;
          code.required = true;
          code.focus();
        } else {
          form.requestSubmit();
        }
      }).catch(function (err) {
        if (errorText) errorText.textContent = (err.data && err.data.error) || err.message;
        if (errorBox) errorBox.hidden = false;
        pass.focus();
      }).finally(function () {
        if (button) button.disabled = false;
      });
    });
  }

  /* ---------- logout ---------- */
  function initLogout() {
    var b = q("#logoutBtn");
    if (!b) return;
    b.onclick = function () {
      busy(b, true);
      api("/api/logout", { method: "POST" })
        .then(function () { location.href = url("/login"); })
        .catch(function () { location.href = url("/login"); });
    };
  }

  /* ---------- inisialisasi ---------- */
  function boot() {
    if (!CSRF) CSRF = (q('meta[name="csrf"]') || {}).content || "";
    initLogin();
    initMobileNav();
    initTheme();
    initLang();
    initLogout();
    initCommandPalette();
    /* Aktifkan semua tombol yang butuh konfirmasi destruktif */
    document.addEventListener("submit", function (e) {
      var f = e.target;
      if (f.dataset && f.dataset.confirm && !f.dataset.confirmed) {
        e.preventDefault();
        confirmDanger({
          title: "Konfirmasi",
          body: f.dataset.confirm,
          phrase: f.dataset.phrase || null,
          ok: f.dataset.ok || "Lanjutkan"
        }).then(function (ok) {
          if (!ok) return;
          f.dataset.confirmed = "1";
          f.submit();
        });
      }
    });
    /* Aksi deklaratif: pengganti atribut onclick yang diblokir CSP nonce. */
    document.addEventListener("click", function (e) {
      var el = e.target && e.target.closest ? e.target.closest("[data-action]") : null;
      if (!el) return;
      var act = el.getAttribute("data-action");
      if (act === "reload") {
        e.preventDefault();
        location.reload();
      }
    });
    /* Ubah angka pada metrik dengan count-up halus */
    qa("[data-count]").forEach(function (el) {
      var to = parseFloat(el.dataset.count);
      if (isNaN(to)) return;
      var from = 0, t0 = null, ms = 420;
      function step(ts) {
        if (!t0) t0 = ts;
        var p = Math.min(1, (ts - t0) / ms);
        var v = from + (to - from) * (1 - Math.pow(1 - p, 3));
        el.textContent = (to % 1 === 0 ? Math.round(v) : v.toFixed(1));
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
  }

  /* Galat skrip tidak boleh senyap: tampilkan toast + tandai elemen pemuat. */
  window.addEventListener("error", function (ev) {
    var msg = (ev && ev.message) || "galat skrip";
    try {
      toast("Galat halaman", msg.slice(0, 160), "err");
      qa(".sk, [data-loading]").forEach(function (el) {
        el.setAttribute("data-loading", "failed");
        if (el.classList.contains("sk")) el.style.opacity = ".3";
      });
    } catch (e) { /* diabaikan */ }
  });
  window.addEventListener("unhandledrejection", function (ev) {
    var r = ev && ev.reason;
    var msg = (r && (r.message || r)) || "janji ditolak";
    try { toast("Permintaan gagal", String(msg).slice(0, 160), "err"); } catch (e) {}
  });

  document.addEventListener("DOMContentLoaded", boot);

  /* ekspor minimal untuk modul halaman */
  window.SC = {
    url: url, goto: function (p) { location.href = url(p); },
    api: api, toast: toast, busy: busy, esc: esc, bytes: bytes,
    dur: dur, ago: ago, hasta: hasta, q: q, qa: qa,
    confirmDanger: confirmDanger, modal: modal, formData: formData
  };
})();

/* ---------- bilah progres navigasi ----------
   Panel memakai navigasi halaman penuh. Bilah ini memberi umpan balik
   seketika saat tautan internal diklik (padanan `useLinkStatus` di Next.js),
   sehingga transisi tidak terasa diam. */
(function () {
  var bar = null;
  function ensure() {
    if (bar) return bar;
    bar = document.createElement("div");
    bar.id = "navprog";
    bar.setAttribute("aria-hidden", "true");
    (document.body || document.documentElement).appendChild(bar);
    return bar;
  }
  document.addEventListener("click", function (e) {
    if (e.defaultPrevented || e.button !== 0) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target && e.target.closest ? e.target.closest("a[href]") : null;
    if (!a || a.target === "_blank" || a.hasAttribute("download")) return;
    var href = a.getAttribute("href") || "";
    if (!href || href.charAt(0) === "#" || href.indexOf("javascript:") === 0) return;
    if (a.host && a.host !== location.host) return;
    ensure().classList.add("on");
  }, true);
  window.addEventListener("pageshow", function () {
    if (bar) { bar.classList.remove("on"); bar.classList.add("done"); }
  });
})();
