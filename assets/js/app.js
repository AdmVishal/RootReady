/* root_n_reels — app.js : loaded (deferred) on every page. Vanilla JS, no dependencies.
   Features: theme, nav drawer, copy buttons, destructive-command flags, table wrapping, legacy Q&A toggles,
   deep-link opening, sections sheet, active TOC, recent/continue/bookmarks, keyboard shortcuts, search loader. */
(function () {
  'use strict';
  var d = document, w = window;
  var RR = w.RR = w.RR || {};

  /* ---------- storage (all keys namespaced rr:*) ---------- */
  var S = RR.store = {
    get: function (k, def) { try { var v = localStorage.getItem('rr:' + k); return v ? JSON.parse(v) : def; } catch (e) { return def; } },
    set: function (k, v) { try { localStorage.setItem('rr:' + k, JSON.stringify(v)); } catch (e) {} },
    del: function (k) { try { localStorage.removeItem('rr:' + k); } catch (e) {} }
  };
  RR.norm = function (p) { p = (p || location.pathname).replace(/index\.html$/, ''); if (p.length > 1) p = p.replace(/\/$/, ''); return p || '/'; };
  var $ = function (s, r) { return (r || d).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || d).querySelectorAll(s)); };
  RR.$ = $; RR.$$ = $$;
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  RR.esc = esc;
  function isTyping(t) { return t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)); }
  function pageTitle() { return (d.title || '').replace(/\s*[|—-]\s*root_n_reels.*$/i, '').trim() || 'root_n_reels'; }

  /* ---------- theme ---------- */
  function effTheme() { return d.documentElement.dataset.theme || (w.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'); }
  d.addEventListener('click', function (e) {
    var b = e.target.closest('[data-rr-theme]');
    if (!b) return;
    var t = effTheme() === 'dark' ? 'light' : 'dark';
    d.documentElement.dataset.theme = t; S.set('theme', t);
    b.setAttribute('aria-label', t === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
  });

  /* ---------- nav drawer (works with legacy inline toggleNav too) ---------- */
  function navEls() { return { nav: $('#site-nav'), ov: $('#mob-ov'), btn: $('#menu-btn') }; }
  function syncNav() {
    var e = navEls(); if (!e.btn || !e.nav) return;
    e.btn.setAttribute('aria-expanded', e.nav.classList.contains('open') ? 'true' : 'false');
  }
  if (typeof w.toggleNav !== 'function') {
    w.toggleNav = function () {
      var e = navEls(); if (!e.nav) return;
      e.nav.classList.toggle('open'); if (e.ov) e.ov.classList.toggle('on');
    };
  }
  var _tn = w.toggleNav;
  w.toggleNav = function () { _tn.apply(this, arguments); syncNav(); };
  function closeNav() { var e = navEls(); if (e.nav && e.nav.classList.contains('open')) w.toggleNav(); }
  d.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeNav(); });
  if (d.body.hasAttribute('data-rr-new')) {
    var pr = $('#prog'), bt = $('#btt');
    var tick = false;
    w.addEventListener('scroll', function () {
      if (tick) return; tick = true;
      requestAnimationFrame(function () {
        tick = false;
        var h = d.documentElement, s = h.scrollTop, m = h.scrollHeight - h.clientHeight;
        if (pr) pr.style.width = (m > 0 ? Math.min(s / m * 100, 100) : 0) + '%';
        if (bt) bt.classList.toggle('vis', s > 280);
      });
    }, { passive: true });
  }

  /* ---------- main-content helpers ---------- */
  var main = $('#main-content') || d.body;
  var isArticle = d.body.hasAttribute('data-rr-article');

  /* table wrapping */
  $$('table', main).forEach(function (t) {
    var p = t.parentElement;
    if (p && (p.classList.contains('table-wrap') || p.classList.contains('tbl-wrap'))) return;
    var wr = d.createElement('div'); wr.className = 'table-wrap'; wr.tabIndex = 0;
    wr.setAttribute('role', 'region'); wr.setAttribute('aria-label', 'Scrollable table');
    p.insertBefore(wr, t); wr.appendChild(t);
  });
  $$('.tbl-wrap', main).forEach(function (t) { t.tabIndex = 0; t.setAttribute('role', 'region'); t.setAttribute('aria-label', 'Scrollable table'); });

  /* code blocks: copy + destructive flag */
  var DANGER = [
    /\brm\s+-[a-zA-Z]*[rR][a-zA-Z]*f|\brm\s+-[a-zA-Z]*f[a-zA-Z]*[rR]/, /\bdd\s+[^\n]*\bof=/, /\bmkfs(\.\w+)?\b/, /\bwipefs\b/, /\bmkswap\b/,
    /\b(fdisk|parted|sgdisk|gdisk)\s+\/dev\//, /\b(lvremove|vgremove|pvremove|lvreduce|vgreduce)\b/, /\bzpool\s+destroy|\bzfs\s+destroy/,
    /\biptables\s+-F|\bnft\s+flush|\bip6tables\s+-F/, /\bxfs_repair\s+-L|\bfsck\b[^\n]*-y/, /\bmdadm\b[^\n]*(--zero-superblock|--stop)/
  ];
  var DISRUPT = [/\b(reboot|shutdown|poweroff|halt)\b/, /\binit\s+[06]\b/, /\bsystemctl\s+(isolate|rescue|emergency)\b/];
  function codeText(el) {
    var t = el.innerText || el.textContent || '';
    return t.replace(/^\s*\$\s+/gm, '').replace(/ /g, ' ').replace(/\n{3,}/g, '\n\n').trim();
  }
  $$('pre, .code-block', main).forEach(function (pre) {
    if (pre.closest('.rr-code') || pre.closest('.rr-qcard')) return;
    var wrap = d.createElement('div'); wrap.className = 'rr-code';
    pre.parentNode.insertBefore(wrap, pre); wrap.appendChild(pre);
    var txt = pre.textContent || '';
    var lvl = DANGER.some(function (r) { return r.test(txt); }) ? 'danger' : (DISRUPT.some(function (r) { return r.test(txt); }) ? 'warn' : '');
    if (lvl) {
      wrap.setAttribute('data-danger', lvl);
      var tag = d.createElement('span'); tag.className = 'rr-danger-tag' + (lvl === 'warn' ? ' warn' : '');
      tag.textContent = lvl === 'danger' ? 'Destructive — verify target first' : 'Disruptive — plan a window';
      wrap.appendChild(tag);
    }
    var b = d.createElement('button'); b.type = 'button'; b.className = 'rr-copy'; b.textContent = 'Copy';
    b.setAttribute('aria-label', 'Copy code to clipboard');
    b.addEventListener('click', function () {
      var t = codeText(pre);
      var done = function () { b.textContent = 'Copied ✓'; b.classList.add('ok'); announce('Copied to clipboard'); setTimeout(function () { b.textContent = 'Copy'; b.classList.remove('ok'); }, 1600); };
      if (navigator.clipboard && w.isSecureContext) navigator.clipboard.writeText(t).then(done, fallback);
      else fallback();
      function fallback() {
        var ta = d.createElement('textarea'); ta.value = t; ta.style.position = 'fixed'; ta.style.opacity = '0'; d.body.appendChild(ta);
        ta.select(); try { d.execCommand('copy'); done(); } catch (e) {} d.body.removeChild(ta);
      }
    });
    wrap.appendChild(b);
  });
  var live;
  function announce(msg) {
    if (!live) { live = d.createElement('div'); live.className = 'sr-only'; live.setAttribute('aria-live', 'polite'); d.body.appendChild(live); }
    live.textContent = ''; setTimeout(function () { live.textContent = msg; }, 30);
  }
  RR.announce = announce;

  /* ---------- legacy Q&A toggles (replaces the lost StudyHub scripts) ---------- */
  var QSEL = '.q-card, .qc, .qa-item';
  var Q_HEAD = '.q-header, .qh, .qa-question';
  var Q_BODY = '.q-body, .qbody, .qa-answer';
  function qOpen(q, open) {
    var on = open === undefined ? !q.classList.contains('rr-open') : open;
    q.classList.toggle('rr-open', on);
    var h = q.querySelector(Q_HEAD); if (h) h.setAttribute('aria-expanded', on ? 'true' : 'false');
  }
  RR.openQ = function (q) { qOpen(q, true); };
  $$(QSEL, main).forEach(function (q) {
    var head = Array.prototype.filter.call(q.children, function (c) { return c.matches(Q_HEAD); })[0];
    var body = Array.prototype.filter.call(q.children, function (c) { return c.matches(Q_BODY); })[0];
    if (!head || !body) return;
    q.classList.add('rr-q');
    if (q.hasAttribute('onclick')) q.removeAttribute('onclick');
    if (head.hasAttribute('onclick')) head.removeAttribute('onclick');
    head.setAttribute('role', 'button'); head.tabIndex = 0; head.setAttribute('aria-expanded', 'false');
    head.addEventListener('click', function (e) { if (e.target.closest('a')) return; qOpen(q); });
    head.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); qOpen(q); } });
  });
  var qs = $$('.rr-q', main);
  if (qs.length > 3) {
    var tools = d.createElement('div'); tools.className = 'rr-qtools';
    tools.innerHTML = '<button type="button" class="rr-act" data-q="open">Expand all answers</button><button type="button" class="rr-act" data-q="close">Collapse all</button>';
    qs[0].parentNode.insertBefore(tools, qs[0]);
    tools.addEventListener('click', function (e) {
      var b = e.target.closest('[data-q]'); if (!b) return;
      qs.forEach(function (q) { qOpen(q, b.dataset.q === 'open'); });
    });
  }
  /* legacy function names still referenced by inline attributes (kept as safe no-ops/aliases) */
  w.toggleQ = w.toggleQ || function (el) { var q = el && el.closest ? el.closest('.rr-q') : null; if (q) qOpen(q); };
  w.tq = w.tq || w.toggleQ;
  w.toggleQA = w.toggleQA || function (el) { var q = el && el.closest ? el.closest('.rr-q') : null; if (q) qOpen(q); };
  w.toggleCard = w.toggleCard || function (el) {
    var b = el && el.nextElementSibling; if (!b) return;
    var hide = b.style.display !== 'none'; b.style.display = hide ? 'none' : '';
    var ch = el.querySelector('.card-chevron'); if (ch) ch.classList.toggle('open', !hide);
  };
  w.showTab = w.showTab || function (group, id) {
    var el = d.getElementById('tab-' + group + '-' + id) || d.getElementById('tab-' + id) || d.getElementById(id);
    if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'start' }); flash(el); }
  };

  /* ---------- deep links: open parents, scroll, flash ---------- */
  function flash(el) { el.classList.remove('rr-flash'); void el.offsetWidth; el.classList.add('rr-flash'); setTimeout(function () { el.classList.remove('rr-flash'); }, 1500); }
  function openHash() {
    var id = decodeURIComponent((location.hash || '').slice(1)); if (!id) return;
    var el = d.getElementById(id); if (!el) return;
    var q = el.closest('.rr-q'); if (q) qOpen(q, true);
    var det = el.closest('details'); if (det) det.open = true;
    var pane = el.closest('.tab-pane'); if (pane && !pane.classList.contains('active')) pane.classList.add('active');
    setTimeout(function () { el.scrollIntoView({ block: 'start' }); flash(el); }, 60);
  }
  w.addEventListener('hashchange', openHash);
  if (location.hash) w.addEventListener('load', openHash);
  RR.openHash = openHash;

  /* ---------- ids for headings (so bookmarks / sections sheet work everywhere) ---------- */
  function slug(s) { return String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60) || 'section'; }
  var heads = $$('h2', main).filter(function (h) { return !h.closest('.rr-related,.rr-meta,.rr-sheet'); });
  var used = {};
  heads.forEach(function (h) {
    if (!h.id) { var s = slug(h.textContent), n = s, i = 2; while (d.getElementById(n) || used[n]) n = s + '-' + (i++); h.id = n; }
    used[h.id] = 1;
  });

  /* ---------- sections sheet (mobile TOC) ---------- */
  var tocLinks = $$('#toc-nav .toc-link');
  var items = tocLinks.length
    ? tocLinks.map(function (a) { return { h: a.getAttribute('href'), t: a.textContent.trim() }; })
    : heads.map(function (h) { return { h: '#' + h.id, t: h.textContent.replace(/[☆★]/g, '').trim() }; });
  if (isArticle && items.length >= 3) {
    var btn = d.createElement('button'); btn.type = 'button'; btn.className = 'rr-sections-btn on';
    btn.innerHTML = '<svg class="rr-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h10"/></svg> Sections';
    var dlg = d.createElement('dialog'); dlg.className = 'rr-sheet'; dlg.setAttribute('aria-label', 'Sections on this page');
    dlg.innerHTML = '<header><span>On this page</span><button type="button" class="rr-act" data-close>Close</button></header><ol>' +
      items.map(function (i) { return '<li><a href="' + esc(i.h) + '">' + esc(i.t) + '</a></li>'; }).join('') + '</ol>';
    d.body.appendChild(btn); d.body.appendChild(dlg);
    btn.addEventListener('click', function () { if (dlg.showModal) dlg.showModal(); });
    dlg.addEventListener('click', function (e) { if (e.target === dlg || e.target.closest('[data-close]') || e.target.closest('a')) dlg.close(); });
  }

  /* ---------- active TOC link (IntersectionObserver) ---------- */
  if (tocLinks.length && 'IntersectionObserver' in w) {
    var map = {};
    tocLinks.forEach(function (a) { var id = (a.getAttribute('href') || '').slice(1); var el = id && d.getElementById(id); if (el) map[id] = a; });
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (en) {
        if (en.isIntersecting) { tocLinks.forEach(function (l) { l.classList.remove('active-toc'); }); map[en.target.id].classList.add('active-toc'); }
      });
    }, { rootMargin: '-72px 0px -70% 0px' });
    Object.keys(map).forEach(function (id) { io.observe(d.getElementById(id)); });
  }

  /* ---------- recent / progress / bookmarks ---------- */
  var path = RR.norm();
  var skipTrack = /^\/(saved|search)(\/|$)/.test(path) || d.body.hasAttribute('data-rr-notrack');
  if (isArticle && !skipTrack) {
    var rec = S.get('recent', []).filter(function (r) { return r.u !== path; });
    rec.unshift({ u: path, t: pageTitle(), ts: Date.now() }); S.set('recent', rec.slice(0, 20));
    var vis = S.get('visited', {}); vis[path] = 1; S.set('visited', vis);
    var ptick = false;
    w.addEventListener('scroll', function () {
      if (ptick) return; ptick = true;
      setTimeout(function () {
        ptick = false;
        var h = d.documentElement, m = h.scrollHeight - h.clientHeight; if (m <= 0) return;
        var pct = Math.round(h.scrollTop / m * 100);
        var anchor = '', y = h.scrollTop + 90;
        for (var i = 0; i < heads.length; i++) { if (heads[i].offsetTop <= y) anchor = heads[i].id; else break; }
        var pg = S.get('progress', {}); pg[path] = { pct: pct, a: anchor, t: pageTitle(), ts: Date.now() }; S.set('progress', pg);
      }, 400);
    }, { passive: true });
  }
  function bmList() { return S.get('saved', []); }
  function isSaved(u) { return bmList().some(function (b) { return b.u === u; }); }
  function toggleSaved(u, t, p) {
    var l = bmList(), i = l.findIndex(function (b) { return b.u === u; });
    if (i >= 0) l.splice(i, 1); else l.unshift({ u: u, t: t, p: p || '', ts: Date.now() });
    S.set('saved', l); return i < 0;
  }
  RR.bookmarks = { list: bmList, has: isSaved, toggle: toggleSaved };
  d.addEventListener('click', function (e) {
    var b = e.target.closest('[data-rr-save]'); if (!b) return;
    var on = toggleSaved(path, pageTitle(), '');
    b.setAttribute('aria-pressed', on ? 'true' : 'false'); announce(on ? 'Saved' : 'Removed from saved');
    var l = b.querySelector('.lbl'); if (l) l.textContent = on ? 'Saved' : 'Save';
  });
  $$('[data-rr-save]').forEach(function (b) { var on = isSaved(path); b.setAttribute('aria-pressed', on ? 'true' : 'false'); var l = b.querySelector('.lbl'); if (l && on) l.textContent = 'Saved'; });
  d.addEventListener('click', function (e) {
    var b = e.target.closest('[data-rr-share]'); if (!b) return;
    var url = location.href.split('#')[0], title = d.title;
    if (navigator.share) navigator.share({ title: title, url: url }).catch(function () {});
    else if (navigator.clipboard) navigator.clipboard.writeText(url).then(function () { announce('Link copied'); b.querySelector('.lbl').textContent = 'Link copied'; setTimeout(function () { b.querySelector('.lbl').textContent = 'Share'; }, 1600); });
  });
  d.addEventListener('click', function (e) { if (e.target.closest('[data-rr-print]')) w.print(); });
  /* per-section save star on h2 */
  if (isArticle) {
    heads.forEach(function (h) {
      if (h.closest('.rr-q')) return;
      var u = path + '#' + h.id, b = d.createElement('button'); b.type = 'button'; b.className = 'rr-h-save';
      var txt = h.textContent.trim();
      b.setAttribute('aria-label', 'Save section: ' + txt); b.setAttribute('aria-pressed', isSaved(u) ? 'true' : 'false'); b.textContent = '★';
      b.addEventListener('click', function () { var on = toggleSaved(u, txt, pageTitle()); b.setAttribute('aria-pressed', on ? 'true' : 'false'); announce(on ? 'Section saved' : 'Section removed'); });
      h.appendChild(b);
    });
  }

  /* ---------- Instagram / in-app browser hint ---------- */
  if (/Instagram|FBAN|FBAV/i.test(navigator.userAgent)) {
    var hint = $('.rr-note-ib'); if (hint) hint.style.display = 'block';
  }

  /* ---------- search loader + shortcuts ---------- */
  var searchLoading;
  function withSearch(fn) {
    if (w.RRSearch) return fn(w.RRSearch);
    if (!searchLoading) searchLoading = new Promise(function (res, rej) {
      var s = d.createElement('script'); s.src = '/assets/js/search.js?v=' + (RR.v || ''); s.onload = res; s.onerror = rej; d.head.appendChild(s);
    });
    searchLoading.then(function () { fn(w.RRSearch); });
  }
  RR.openSearch = function (q) { withSearch(function (s) { s.open(q || ''); }); };
  d.addEventListener('click', function (e) {
    var b = e.target.closest('[data-rr-search]'); if (!b) return;
    e.preventDefault(); RR.openSearch(b.dataset.q || '');
  });
  d.addEventListener('focusin', function (e) { var i = e.target.closest('[data-rr-hero-search]'); if (i && !i.dataset.busy) { RR.warm && RR.warm(); } });
  RR.warm = function () { if (!searchLoading) withSearch(function () {}); };
  d.addEventListener('keydown', function (e) {
    var t = e.target;
    if ((e.key === 'k' || e.key === 'K') && (e.ctrlKey || e.metaKey)) { e.preventDefault(); RR.openSearch(''); return; }
    if (e.key === '/' && !isTyping(t) && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); RR.openSearch(''); return; }
    if ((e.key === 'b') && !isTyping(t) && !e.ctrlKey && !e.metaKey) { var sb = $('[data-rr-save]'); if (sb) sb.click(); }
  });
  var hs = $('[data-rr-hero-form]');
  if (hs) {
    hs.addEventListener('submit', function (e) { e.preventDefault(); var v = hs.querySelector('input').value.trim(); RR.openSearch(v); });
    hs.querySelector('input').addEventListener('focus', function () { RR.warm(); });
    hs.querySelector('input').addEventListener('input', function () { RR.openSearch(this.value); this.value = ''; });
  }
  /* page-specific widgets */
  if ($('[data-rr-widget]') || $('.rr-path')) { var ws = d.createElement('script'); ws.src = '/assets/js/widgets.js?v=' + (RR.v || ''); ws.defer = true; d.head.appendChild(ws); }

  /* ---------- privacy-friendly analytics (opt-in via meta) ---------- */
  var gc = $('meta[name="rr-goatcounter"]');
  if (gc && gc.content) {
    var g = d.createElement('script'); g.async = true; g.src = 'https://gc.zgo.at/count.js';
    g.setAttribute('data-goatcounter', 'https://' + gc.content + '.goatcounter.com/count'); d.head.appendChild(g);
  }
  RR.track = function (name) { try { if (w.goatcounter && w.goatcounter.count) w.goatcounter.count({ path: name, title: name, event: true }); } catch (e) {} };

  /* ---------- offline support ---------- */
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    w.addEventListener('load', function () { navigator.serviceWorker.register('/service-worker.js').catch(function () {}); });
  }
})();
