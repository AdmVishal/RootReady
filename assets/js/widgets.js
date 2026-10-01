/* root_n_reels — widgets.js : page-specific client features, loaded on demand by app.js.
   All state lives in localStorage under rr:* keys. No network calls except same-origin JSON under /data. */
(function () {
  'use strict';
  var d = document, RR = window.RR, S = RR.store, $ = RR.$, $$ = RR.$$, esc = RR.esc;
  function getJSON(u) { return fetch(u).then(function (r) { if (!r.ok) throw new Error(u); return r.json(); }); }
  function dayIndex() { return Math.floor(Date.now() / 864e5); }
  function copyBtn(text) {
    var b = d.createElement('button'); b.type = 'button'; b.className = 'rr-act'; b.textContent = 'Copy'; b.setAttribute('aria-label', 'Copy command');
    b.addEventListener('click', function () {
      var done = function () { b.textContent = 'Copied ✓'; RR.announce('Copied'); setTimeout(function () { b.textContent = 'Copy'; }, 1500); };
      if (navigator.clipboard) navigator.clipboard.writeText(text).then(done); else { var t = d.createElement('textarea'); t.value = text; d.body.appendChild(t); t.select(); try { d.execCommand('copy'); done(); } catch (e) {} d.body.removeChild(t); }
    });
    return b;
  }
  function ago(ts) {
    var m = Math.round((Date.now() - ts) / 60000);
    if (m < 2) return 'just now'; if (m < 60) return m + ' min ago';
    var h = Math.round(m / 60); if (h < 24) return h + ' h ago';
    return Math.round(h / 24) + ' d ago';
  }

  /* ---------- learning-path ticks ---------- */
  var vis = S.get('visited', {});
  $$('.rr-path').forEach(function (p) {
    var done = 0, all = $$('li[data-u]', p);
    all.forEach(function (li) { if (vis[RR.norm(li.dataset.u.split('#')[0])]) { li.classList.add('done'); done++; } });
    if (done) { var h = $('h3', p); var s = d.createElement('small'); s.className = 'rr-tag'; s.style.marginLeft = '8px'; s.textContent = done + '/' + all.length; h.appendChild(s); }
  });

  /* ---------- home ---------- */
  var home = $('[data-rr-widget="home"]');
  if (home) {
    var pg = S.get('progress', {}), rec = S.get('recent', []), cards = [];
    Object.keys(pg).map(function (u) { return { u: u, p: pg[u] }; })
      .filter(function (x) { return x.p.pct > 4 && x.p.pct < 96; })
      .sort(function (a, b) { return b.p.ts - a.p.ts; }).slice(0, 3)
      .forEach(function (x) { cards.push({ u: x.u + (x.p.a ? '#' + x.p.a : ''), t: x.p.t, m: 'Continue · ' + x.p.pct + '% read · ' + ago(x.p.ts) }); });
    var seen = cards.map(function (c) { return c.u.split('#')[0]; });
    rec.filter(function (r) { return seen.indexOf(r.u) < 0; }).slice(0, Math.max(0, 4 - cards.length)).forEach(function (r) { cards.push({ u: r.u, t: r.t, m: 'Viewed ' + ago(r.ts) }); });
    var nsaved = RR.bookmarks.list().length;
    if (cards.length || nsaved) {
      $('#rr-continue-grid').innerHTML = cards.map(function (c) { return '<a class="rr-card" href="' + esc(c.u) + '"><h3>' + esc(c.t) + '</h3><div class="meta"><span>' + esc(c.m) + '</span></div></a>'; }).join('') +
        (nsaved ? '<a class="rr-card" href="/saved/"><h3>★ ' + nsaved + ' saved</h3><div class="meta"><span>Open your bookmarks</span></div></a>' : '');
      home.hidden = false;
    }
    getJSON('/data/daily.json').then(function (a) {
      var c = a[dayIndex() % a.length], el = $('#rr-daily');
      el.innerHTML = '<div class="rr-cmd"><code></code></div><p style="margin:6px 0 4px">' + esc(c.what) + '</p><p class="rr-empty" style="margin:0 0 8px">' + esc(c.tip) + '</p><a href="' + esc(c.u) + '">More like this →</a>';
      $('code', el).textContent = c.cmd; $('.rr-cmd', el).appendChild(copyBtn(c.cmd));
    }).catch(function () { $('#rr-daily').textContent = ''; });
    getJSON('/data/scenarios.json').then(function (a) {
      var s = a[(dayIndex() + 3) % a.length], el = $('#rr-scn');
      el.innerHTML = '<p style="margin:0 0 6px"><strong>' + esc(s.icon + ' ' + s.title) + '</strong></p><p class="rr-empty" style="margin:0 0 8px">' + esc(s.symptom) + ' What would you check first?</p>' +
        '<details class="rr-d"><summary>Show a first-pass approach</summary><div><div class="rr-code"><pre><code></code></pre></div><p style="margin:0"><a href="/troubleshooting/#' + esc(s.id) + '">Full scenario →</a></p></div></details>';
      $('code', el).textContent = s.first.slice(0, 4).join('\n');
    }).catch(function () { $('#rr-scn').textContent = ''; });
    getJSON('/data/random.json').then(function (qs) {
      var el = $('#rr-randq');
      function show() {
        var q = qs[Math.floor(Math.random() * qs.length)];
        el.innerHTML = '<p style="margin:0 0 8px"><span class="rr-tag">' + esc(q.l) + '</span> <span class="rr-tag">' + esc(q.t) + '</span></p><p style="margin:0 0 8px"><strong>' + esc(q.q) + '</strong></p>' +
          '<details class="rr-d"><summary>Reveal answer</summary><div><p style="margin:0 0 8px">' + esc(q.a) + '</p><a href="' + esc(q.u) + '">Read the full answer →</a></div></details>' +
          '<p style="margin:8px 0 0"><button type="button" class="rr-act" id="rr-another">Another question</button> <a href="/interview/#practice">Practice mode →</a></p>';
        $('#rr-another', el).addEventListener('click', show);
      }
      show();
    }).catch(function () { $('#rr-randq').textContent = ''; });
  }

  /* ---------- saved ---------- */
  var sv = $('[data-rr-widget="saved"]');
  if (sv) {
    var render = function () {
      var pg2 = S.get('progress', {}), saved = S.get('saved', []), rec2 = S.get('recent', []), ss = S.get('searches', []);
      var cont = Object.keys(pg2).map(function (u) { return { u: u, p: pg2[u] }; }).filter(function (x) { return x.p.pct > 4 && x.p.pct < 96; }).sort(function (a, b) { return b.p.ts - a.p.ts; }).slice(0, 6);
      $('#sv-continue').innerHTML = cont.length ? cont.map(function (x) { return '<a class="rr-card" href="' + esc(x.u + (x.p.a ? '#' + x.p.a : '')) + '"><h3>' + esc(x.p.t) + '</h3><div class="meta"><span>' + x.p.pct + '% read</span><span>' + ago(x.p.ts) + '</span></div></a>'; }).join('') : '<p class="rr-empty">Nothing in progress yet. Pages you start reading will show up here.</p>';
      $('#sv-saved').innerHTML = saved.length ? '<ul class="rr-list-q">' + saved.map(function (b, i) { return '<li><a href="' + esc(b.u) + '">' + esc(b.t) + '</a>' + (b.p ? '<small>' + esc(b.p) + '</small>' : '') + ' <button type="button" class="rr-act" data-rm="' + i + '" aria-label="Remove ' + esc(b.t) + '">Remove</button></li>'; }).join('') + '</ul>'
        : '<p class="rr-empty">Nothing saved yet. Use the ★ Save button on any page, or the ★ next to a section heading, or press <kbd>b</kbd>.</p>';
      $('#sv-recent').innerHTML = rec2.length ? '<ul class="rr-list-q">' + rec2.map(function (r) { return '<li><a href="' + esc(r.u) + '">' + esc(r.t) + '</a><small>' + ago(r.ts) + '</small></li>'; }).join('') + '</ul>' : '<p class="rr-empty">No history yet.</p>';
      $('#sv-searches').innerHTML = ss.length ? ss.map(function (q) { return '<a class="rr-chip" href="/search/?q=' + encodeURIComponent(q) + '">' + esc(q) + '</a>'; }).join('') : '<p class="rr-empty">No searches yet.</p>';
    };
    render();
    sv.addEventListener('click', function (e) {
      var b = e.target.closest('[data-rm]'); if (!b) return;
      var l = S.get('saved', []); l.splice(+b.dataset.rm, 1); S.set('saved', l); render();
    });
    $('#sv-clear').addEventListener('click', function () {
      if (!confirm('Clear saved items, history, progress and settings stored in this browser?')) return;
      ['saved', 'recent', 'progress', 'visited', 'searches', 'cards'].forEach(function (k) { S.del(k); }); render();
    });
    $('#sv-export').addEventListener('click', function () {
      var o = {}; ['saved', 'recent', 'progress', 'visited', 'searches', 'cards'].forEach(function (k) { o[k] = S.get(k, null); });
      var a = d.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(o, null, 2)], { type: 'application/json' })); a.download = 'root_n_reels-data.json'; a.click();
    });
    $('#sv-import').addEventListener('change', function (e) {
      var f = e.target.files[0]; if (!f) return; var r = new FileReader();
      r.onload = function () { try { var o = JSON.parse(r.result); Object.keys(o).forEach(function (k) { if (['saved', 'recent', 'progress', 'visited', 'searches', 'cards'].indexOf(k) >= 0 && o[k] !== null) S.set(k, o[k]); }); render(); RR.announce('Imported'); } catch (x) { alert('That file is not valid root_n_reels data.'); } };
      r.readAsText(f);
    });
  }

  /* ---------- interview hub + practice ---------- */
  var iv = $('[data-rr-widget="interview"]');
  if (iv) {
    var all = [], filt = { t: '', p: '', l: '', q: '' }, shown = 40, mode = location.hash === '#practice' ? 'practice' : 'list', cur = null;
    var card = $('#iv-card'), list = $('#iv-list'), count = $('#iv-count');
    getJSON('/data/questions.json').then(function (qs) {
      all = qs;
      var topics = {}, srcs = {};
      qs.forEach(function (q) { topics[q.t] = (topics[q.t] || 0) + 1; srcs[q.p] = (srcs[q.p] || 0) + 1; });
      $('#iv-topic').innerHTML += Object.keys(topics).sort().map(function (t) { return '<option value="' + esc(t) + '">' + esc(t) + ' (' + topics[t] + ')</option>'; }).join('');
      $('#iv-src').innerHTML += Object.keys(srcs).sort().map(function (t) { return '<option value="' + esc(t) + '">' + esc(t) + ' (' + srcs[t] + ')</option>'; }).join('');
      $('#iv-levels').innerHTML = ['', 'L1', 'L2', 'L3'].map(function (l) { return '<button type="button" class="rr-chip" data-l="' + l + '" aria-pressed="' + (l === '') + '">' + (l || 'All levels') + '</button>'; }).join(' ');
      apply();
      if (mode === 'practice') next();
    }).catch(function () { count.textContent = 'Could not load the question bank.'; });
    function filtered() {
      var q = filt.q.toLowerCase();
      return all.filter(function (x) { return (!filt.t || x.t === filt.t) && (!filt.p || x.p === filt.p) && (!filt.l || x.l === filt.l) && (!q || (x.q + ' ' + x.t).toLowerCase().indexOf(q) >= 0); });
    }
    function apply() {
      var f = filtered();
      count.textContent = f.length + ' question' + (f.length === 1 ? '' : 's') + (all.length ? ' of ' + all.length : '');
      list.innerHTML = f.slice(0, shown).map(function (x) { return '<li><a href="' + esc(x.u) + '">' + esc(x.q) + '</a><small>' + esc(x.l) + ' · ' + esc(x.t) + ' · ' + esc(x.p) + '</small></li>'; }).join('') +
        (f.length > shown ? '<li><button type="button" class="rr-btn secondary" id="iv-more">Show more</button></li>' : '');
    }
    function pick() {
      var f = filtered(); if (!f.length) return null;
      var box = S.get('cards', {}), pool = [];
      f.forEach(function (x) { var b = box[x.id + '|' + x.p] || 1, w = b === 1 ? 4 : b === 2 ? 2 : 1; for (var i = 0; i < w; i++) pool.push(x); });
      var c; do { c = pool[Math.floor(Math.random() * pool.length)]; } while (pool.length > 8 && cur && c === cur);
      return c;
    }
    function next() {
      cur = pick(); card.hidden = false;
      if (!cur) { card.innerHTML = '<div class="rr-qcard">No questions match these filters.</div>'; return; }
      card.innerHTML = '<div class="rr-qcard"><span class="rr-tag">' + esc(cur.l) + '</span> <span class="rr-tag">' + esc(cur.t) + '</span> <span class="rr-tag">' + esc(cur.p) + '</span><div class="q">' + esc(cur.q) + '</div>' +
        '<p class="rr-empty">Answer out loud first, then reveal.</p><div class="row"><button type="button" class="rr-btn primary" id="iv-reveal">Show answer</button><button type="button" class="rr-btn ghost" id="iv-skip">Skip</button></div><div id="iv-ans"></div></div>';
      $('#iv-reveal').addEventListener('click', reveal); $('#iv-skip').addEventListener('click', next);
      card.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
    function reveal() {
      $('#iv-ans').innerHTML = '<div class="a"><p>' + esc(cur.a) + (cur.a.length >= 890 ? '…' : '') + '</p><p><a href="' + esc(cur.u) + '">Read the full answer →</a></p>' +
        '<div class="row"><span>How did you do?</span><button type="button" class="rr-chip" data-g="3">Knew it</button><button type="button" class="rr-chip" data-g="2">Partly</button><button type="button" class="rr-chip" data-g="1">Missed it</button></div></div>';
      $('#iv-reveal').disabled = true;
    }
    card.addEventListener('click', function (e) {
      var g = e.target.closest('[data-g]'); if (!g) return;
      var box = S.get('cards', {}), k = cur.id + '|' + cur.p, b = box[k] || 1, v = +g.dataset.g;
      box[k] = v === 3 ? Math.min(3, b + 1) : v === 1 ? 1 : b; S.set('cards', box); next();
    });
    iv.addEventListener('input', function (e) { if (e.target.id === 'iv-q') { filt.q = e.target.value; shown = 40; apply(); } });
    iv.addEventListener('change', function (e) {
      if (e.target.id === 'iv-topic') filt.t = e.target.value; else if (e.target.id === 'iv-src') filt.p = e.target.value; else return;
      shown = 40; apply(); if (mode === 'practice') next();
    });
    iv.addEventListener('click', function (e) {
      var l = e.target.closest('[data-l]'); if (l) { filt.l = l.dataset.l; $$('[data-l]', iv).forEach(function (x) { x.setAttribute('aria-pressed', x === l ? 'true' : 'false'); }); shown = 40; apply(); if (mode === 'practice') next(); }
      if (e.target.id === 'iv-more') { shown += 60; apply(); }
    });
    d.addEventListener('click', function (e) {
      if (e.target.closest('#rr-rand')) { mode = 'practice'; next(); }
      var pm = e.target.closest('[data-mode="practice"]'); if (pm) { mode = 'practice'; if (all.length) next(); }
    });
  }

  /* ---------- search results page ---------- */
  var sp = $('[data-rr-widget="searchpage"]');
  if (sp) {
    var inp = $('#rr-sq'), fil = $('#rr-sfil'), cat = 'all';
    var C = [['all', 'All'], ['linux', 'Linux'], ['unix', 'Unix'], ['networking', 'Networking'], ['devops', 'DevOps'], ['security', 'Security'], ['infrastructure', 'Infra'], ['interview', 'Interview'], ['troubleshooting', 'Troubleshooting'], ['cheat', 'Cheat sheets']];
    fil.innerHTML = C.map(function (c) { return '<button type="button" class="rr-chip" data-c="' + c[0] + '" aria-pressed="' + (c[0] === 'all') + '">' + c[1] + '</button>'; }).join('');
    var go = function () {
      var q = inp.value.trim(); if (!q) { sp.innerHTML = '<p class="rr-empty">Type a command, error message or topic.</p>'; return; }
      sp.innerHTML = '<p class="rr-empty">Searching…</p>';
      var s = document.createElement('script'); var run = function () { window.RRSearch.page(sp, q, cat); };
      if (window.RRSearch) run(); else { s.src = '/assets/js/search.js?v=' + (RR.v || ''); s.onload = run; d.head.appendChild(s); }
      try { history.replaceState(null, '', '/search/?q=' + encodeURIComponent(q)); } catch (e) {}
      d.title = 'Search: ' + q + ' | root_n_reels';
    };
    var q0 = new URLSearchParams(location.search).get('q') || ''; inp.value = q0; go();
    $('#rr-sform').addEventListener('submit', function (e) { e.preventDefault(); go(); });
    fil.addEventListener('click', function (e) { var b = e.target.closest('[data-c]'); if (!b) return; cat = b.dataset.c; $$('[data-c]', fil).forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); }); go(); });
  }

  /* ---------- cheat-sheet filter ---------- */
  var cs = $('[data-rr-widget="cheats"]');
  if (cs) {
    var f = $('#cs-filter'), secs = $$('.rr-cs', cs), cnt = $('#cs-count'), chips = $$('.rr-cs-nav a', cs);
    f.addEventListener('input', function () {
      var q = f.value.trim().toLowerCase(), n = 0;
      secs.forEach(function (s, i) {
        var ok = !q || s.textContent.toLowerCase().indexOf(q) >= 0; s.hidden = !ok; if (chips[i]) chips[i].hidden = !ok; if (ok) n++;
        $$('mark.rr-hl', s).forEach(function (m) { m.replaceWith(d.createTextNode(m.textContent)); });
      });
      cnt.textContent = q ? n + ' of ' + secs.length + ' sheets match' : '';
    });
  }
})();
