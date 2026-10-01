#!/usr/bin/env python3
"""root_n_reels build helper (stdlib + beautifulsoup4).

Usage:  python tools/build.py [all|stamp|pages|index|sitemap|check]

Everything it writes is plain static HTML/JSON/XML committed to the repo; GitHub Pages serves the files as-is.
  stamp    : adds ids to headings/Q&A, then (idempotently) stamps head SEO block, header, sidebar nav, breadcrumb/meta
             strip, related block and footer into the existing hand-written guide pages (marker comments: <!--rr:xxx-->).
  pages    : generates home, hubs, troubleshooting, interview, saved, search, 404 and fragment-based pages.
  index    : writes assets/search/index.json + data/questions.json from the final HTML.
  sitemap  : sitemap.xml, robots.txt, manifest.json, service-worker.js version.
  check    : sanity checks (CNAME, local links, duplicate ids, page budgets). Exit code 1 on failure.
"""
import hashlib, html, json, re, subprocess, sys, datetime
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / 'data' / 'content.json').read_text(encoding='utf-8'))
SITE = DATA['site']
BASE = SITE['url']
HUBS = DATA['hubs']
PAGES = DATA['pages']
BY_ID = {p['id']: p for p in PAGES}
TODAY = datetime.date.today().isoformat()
HUB_COLORS = {'linux': '#2F80ED', 'unix': '#D97706', 'networking': '#0891B2', 'infrastructure': '#64748B', 'devops': '#7C3AED',
              'security': '#DC2626', 'operations': '#0A7A4B', 'interview': '#059669', 'troubleshooting': '#B45309', 'cheat': '#B45309'}


def rd(path):
    return (ROOT / path).read_text(encoding='utf-8')


def wr(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and p.read_text(encoding='utf-8') == text:
        return False
    p.write_text(text, encoding='utf-8')
    return True


def jload(name, default):
    p = ROOT / 'data' / name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default


def git_date(path):
    try:
        out = subprocess.run(['git', 'log', '-1', '--format=%cs', '--', path], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        return out or TODAY
    except Exception:
        return TODAY


def asset_version():
    h = hashlib.sha1()
    for f in ['assets/css/site.css', 'assets/js/app.js', 'assets/js/search.js', 'assets/js/widgets.js']:
        p = ROOT / f
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()[:8]


BUILD = asset_version()
E = html.escape
AC = ' aria-current="page"'


def slugify(s, n=60):
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html.unescape(s).lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return (s[:n].strip('-')) or 'section'


def strip_tags(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()


def canon(p):
    return BASE + p['url']


# --------------------------------------------------------------------------- shared chrome
def topnav(page):
    items = [('Linux', '/linux/', 'linux'), ('Unix', '/unix/', 'unix'), ('Networking', '/networking/', 'networking'),
             ('DevOps', '/devops/', 'devops'), ('Troubleshoot', '/troubleshooting/', 'troubleshooting'),
             ('Interview', '/interview/', 'interview'), ('Cheat sheets', '/cheat-sheets.html', 'cheat')]
    out = []
    for label, url, key in items:
        cur = (page.get('hub') == key) or page.get('url') == url or (key == 'cheat' and page.get('id') == 'cheat-sheets')
        out.append(f'<a href="{url}"{AC if cur else ""}>{label}</a>')
    return ''.join(out)


def render_header(page):
    return rd('partials/header.html').replace('{{topnav}}', topnav(page))


def link(p, page):
    cur = p['url'] == page.get('url')
    return (f'<a href="{p["url"]}" class="nav-link{" active" if cur else ""}"{AC if cur else ""}>'
            f'<span class="e" aria-hidden="true">{p.get("icon", "")}</span>{E(p.get("nav") or p["title"])}</a>')


def render_nav(page):
    o = ['<nav id="site-nav" aria-label="Site">']
    o.append(link(BY_ID['home'], page))
    o.append('<div class="nav-sec">Learn</div>')
    for i in ['start-here', 'troubleshooting', 'interview', 'os-interview', 'cheat-sheets', 'labs']:
        o.append(link(BY_ID[i], page))
    for key, h in HUBS.items():
        o.append(f'<div class="nav-sec">{E(h["label"])}</div>')
        for p in PAGES:
            if p.get('hub') == key and p['id'] != 'os-interview':
                o.append(link(p, page))
    o.append('<div class="nav-sec">More</div>')
    for i in ['youtube', 'about', 'saved']:
        o.append(link(BY_ID[i], page))
    o.append('</nav>')
    return '\n'.join(o)


def render_footer():
    topics = ''.join(f'<li><a href="{h["url"]}">{E(h["label"])}</a></li>' for h in HUBS.values())
    t = rd('partials/footer.html')
    for k, v in {'{{topics}}': topics, '{{tagline}}': SITE['tagline'], '{{author}}': SITE['author'], '{{github}}': SITE['github'],
                 '{{instagram}}': SITE['instagram'], '{{youtube}}': SITE['youtube'], '{{year}}': TODAY[:4], '{{built}}': TODAY}.items():
        t = t.replace(k, v)
    return t


def jsonld(page, words=0):
    person = {'@type': 'Person', 'name': SITE['author'], 'url': BASE + '/about.html',
              'sameAs': [SITE['instagram'], SITE['youtube'], SITE['github']]}
    graph = []
    if page['id'] == 'home':
        graph.append({'@type': 'WebSite', 'name': SITE['name'], 'url': BASE + '/', 'description': page['desc'], 'inLanguage': 'en',
                      'publisher': person,
                      'potentialAction': {'@type': 'SearchAction', 'target': {'@type': 'EntryPoint', 'urlTemplate': BASE + '/search/?q={search_term_string}'},
                                          'query-input': 'required name=search_term_string'}})
    else:
        crumbs = [('Home', BASE + '/')]
        h = page.get('hub')
        if h in HUBS:
            crumbs.append((HUBS[h]['label'], BASE + HUBS[h]['url']))
        elif h == 'interview':
            crumbs.append(('Interview Prep', BASE + '/interview/'))
        crumbs.append((page['title'], canon(page)))
        graph.append({'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': i + 1, 'name': n, 'item': u} for i, (n, u) in enumerate(crumbs)]})
        if page.get('type') in ('guide', 'reference', 'qa', 'lab', 'troubleshoot', 'cheat') and not page.get('noindex'):
            art = {'@type': 'TechArticle', 'headline': page['title'][:110], 'description': page['desc'], 'url': canon(page),
                   'mainEntityOfPage': canon(page), 'inLanguage': 'en', 'author': person, 'publisher': person,
                   'dateModified': page.get('_date', TODAY), 'image': BASE + '/assets/img/og-default.png'}
            lv = page.get('level', '')
            if lv:
                art['proficiencyLevel'] = 'Beginner' if lv.startswith('L1') else 'Expert'
            if page.get('covers'):
                art['dependencies'] = page['covers']
            graph.append(art)
    return '<script type="application/ld+json">' + json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False, separators=(',', ':')) + '</script>'


def render_head(page):
    t = page.get('seo_title') or page['title'] + ' | root_n_reels'
    d = page['desc']
    url = canon(page)
    og = BASE + '/assets/img/og-default.png'
    ogt = 'article' if page.get('type') in ('guide', 'reference', 'qa', 'lab', 'troubleshoot', 'cheat') else 'website'
    rob = '<meta name="robots" content="noindex,follow">\n' if page.get('noindex') else ''
    gc = f'<meta name="rr-goatcounter" content="{E(SITE["goatcounter"])}">\n' if SITE.get('goatcounter') else ''
    return f'''<meta name="description" content="{E(d)}">
{rob}<link rel="canonical" href="{url}">
<meta property="og:type" content="{ogt}"><meta property="og:site_name" content="root_n_reels">
<meta property="og:title" content="{E(t)}"><meta property="og:description" content="{E(d)}">
<meta property="og:url" content="{url}"><meta property="og:image" content="{og}">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="root_n_reels: Linux and Unix knowledge for people who run servers">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{E(t)}"><meta name="twitter:description" content="{E(d)}"><meta name="twitter:image" content="{og}">
<meta name="theme-color" content="#14315C">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png"><link rel="icon" type="image/png" sizes="192x192" href="/assets/favicon-192.png">
<link rel="apple-touch-icon" sizes="180x180" href="/assets/favicon-180.png"><link rel="manifest" href="/manifest.json">
{gc}<script>window.RR={{v:"{BUILD}"}};try{{var t=JSON.parse(localStorage.getItem("rr:theme"));if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>
<link rel="preload" href="/assets/fonts/jetbrains-mono-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/site.css?v={BUILD}">
<script defer src="/assets/js/app.js?v={BUILD}"></script>
{jsonld(page)}'''


def mark(name, content):
    return f'<!--rr:{name}-->{content}<!--/rr:{name}-->'


def put(src, name, content, fallback=None, flags=re.S):
    """Replace marker region if present; otherwise apply fallback(src)->(start,end) and wrap."""
    pat = re.compile(r'<!--rr:%s-->.*?<!--/rr:%s-->' % (name, name), re.S)
    new = mark(name, content)
    if pat.search(src):
        return pat.sub(lambda m: new, src, count=1)
    if fallback is None:
        raise RuntimeError('no marker and no fallback for ' + name)
    se = fallback(src)
    if not se:
        raise RuntimeError('fallback failed for ' + name)
    return src[:se[0]] + new + src[se[1]:]


def div_end(src, start):
    """index just after the </div> that closes the <div ...> opening at `start`."""
    depth, i = 0, start
    for m in re.finditer(r'<div\b|</div>', src[start:]):
        depth += 1 if m.group(0).startswith('<div') else -1
        if depth == 0:
            return start + m.end()
    return None


# --------------------------------------------------------------------------- ids
def add_ids(src):
    used = set(re.findall(r'\bid="([^"]+)"', src))

    def uniq(base):
        n, i = base, 2
        while n in used:
            n = f'{base}-{i}'
            i += 1
        used.add(n)
        return n

    def h_sub(m):
        tag, attrs, inner = m.group(1), m.group(2) or '', m.group(3)
        if re.search(r'\bid=', attrs):
            return m.group(0)
        txt = strip_tags(inner)
        if not txt:
            return m.group(0)
        return f'<{tag}{attrs} id="{uniq(slugify(txt))}">{inner}</{tag}>'
    src = re.sub(r'<(h[234])(\s[^>]*)?>(.*?)</\1>', h_sub, src, flags=re.S)

    def q_sub(m):
        attrs = m.group(2)
        if re.search(r'\bid=', attrs):
            return m.group(0)
        look = src[m.end():m.end() + 1800]
        t = re.search(r'class="(?:q-text|qt)"[^>]*>(.*?)</span>', look, re.S) or re.search(r'class="qa-question"[^>]*>(.*?)</div>', look, re.S)
        if not t:
            return m.group(0)
        txt = re.sub(r'^\s*Q\s*', '', strip_tags(t.group(1)))
        return f'<div class="{m.group(1)}" id="{uniq("q-" + slugify(txt, 56))}"{attrs}>'
    src = re.sub(r'<div class="((?:q-card|qc|qa-item)(?: [^"]*)?)"([^>]*)>', q_sub, src)
    return src


# --------------------------------------------------------------------------- stamp legacy pages
def words_of(src):
    s = re.sub(r'(?is)<(script|style|nav|footer)\b.*?</\1>', ' ', src)
    return len(strip_tags(s).split())


def read_time(w):
    m = max(1, round(w / 220))
    return f'{m} min read' if m <= 40 else f'Long reference · ~{round(m / 5) * 5} min'


def crumbs_html(page):
    h = page.get('hub')
    items = [('Home', '/')]
    if h in HUBS:
        items.append((HUBS[h]['label'], HUBS[h]['url']))
    elif h == 'interview':
        items.append(('Interview Prep', '/interview/'))
    li = ''.join(f'<li><a href="{u}">{E(n)}</a></li>' for n, u in items) + f'<li aria-current="page">{E(page["title"])}</li>'
    return f'<nav class="rr-crumbs" aria-label="Breadcrumb"><ol>{li}</ol></nav>'


def meta_html(page, words):
    h = page.get('hub') or ''
    color = HUB_COLORS.get(h, '#2F80ED')
    chips = []
    if h in HUBS or h == 'interview':
        chips.append(f'<span class="chip" style="--cat:{color}"><span class="dot"></span>{E(HUBS[h]["label"] if h in HUBS else "Interview")}</span>')
    if page.get('level'):
        chips.append(f'<span class="chip">{E(page["level"])}</span>')
    if page.get('type'):
        chips.append(f'<span class="chip">{E({"guide": "Guide", "reference": "Reference", "qa": "Q&A", "lab": "Lab", "troubleshoot": "Troubleshooting", "cheat": "Cheat sheet", "path": "Learning path"}.get(page["type"], page["type"]))}</span>')
    if page.get('covers'):
        chips.append(f'<span class="chip" title="Versions this page covers">Covers: {E(page["covers"])}</span>')
    bits = [f'<span>{read_time(words)}</span>', f'<span>Updated <time datetime="{page["_date"]}">{page["_date"]}</time></span>', f'<span>by {E(SITE["author"])}</span>']
    acts = ('<span class="acts"><button type="button" class="rr-act" data-rr-save aria-pressed="false"><svg class="rr-ico" viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/></svg><span class="lbl">Save</span></button>'
            '<button type="button" class="rr-act" data-rr-share><svg class="rr-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3A4 4 0 0 0 11 18.7l1-1"/></svg><span class="lbl">Share</span></button>'
            '<button type="button" class="rr-act" data-rr-print><svg class="rr-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 9V3h10v6M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2"/><path d="M7 14h10v7H7z"/></svg><span class="lbl">Print</span></button></span>')
    return '<div class="rr-meta">' + ''.join(chips) + ' '.join(bits) + acts + '</div>'


def related_html(page):
    ids = [i for i in page.get('related', []) if i in BY_ID]
    if not ids:
        return ''
    cards = ''
    for i in ids[:4]:
        p = BY_ID[i]
        cards += (f'<a class="rr-card" href="{p["url"]}" style="--cat:{HUB_COLORS.get(p.get("hub", ""), "#2F80ED")}"><h3>{E(p["title"])}</h3>'
                  f'<p>{E(p["desc"][:120])}…</p><div class="meta"><span><span class="dot"></span>{E(HUBS[p["hub"]]["label"] if p.get("hub") in HUBS else "root_n_reels")}</span></div></a>')
    nxt = ''
    if page.get('next') in BY_ID:
        n = BY_ID[page['next']]
        nxt = f'<a class="rr-next" href="{n["url"]}"><small>Next topic →</small><strong>{E(n["title"])}</strong></a>'
    return f'<aside class="rr-related" aria-labelledby="rr-rel-h"><h2 id="rr-rel-h">Related</h2><div class="rr-related-grid">{cards}</div>{nxt}</aside>'


LEGACY_CLEAN = [
    r'<meta name="description"[^>]*>', r'<meta property="og:[^>]*>', r'<meta name="twitter:[^>]*>', r'<link rel="canonical"[^>]*>',
    r'<meta name="theme-color"[^>]*>', r'<link rel="icon"[^>]*>', r'<link rel="apple-touch-icon"[^>]*>', r'<link rel="manifest"[^>]*>',
    r'<link rel="preconnect" href="https://fonts\.[^>]*>', r'<link rel="stylesheet" href="https://fonts\.googleapis\.com[^>]*>',
]


def stamp_legacy(page):
    f = page['file']
    src = rd(f)
    page['_date'] = git_date(f)
    src = add_ids(src)
    words = words_of(src)
    page['_words'] = words
    if page['id'] == 'rhel':  # all 27 sections were hidden by studyhub.css .tab-pane{display:none}; there is no tab script
        src = src.replace('class="tab-pane"', 'class="tab-pane active"')
    # --- head
    if '<!--rr:head-->' not in src:
        for pat in LEGACY_CLEAN:
            src = re.sub(pat + r'\s*', '', src)
        src = re.sub(r'<title>.*?</title>', '<title>' + E(page['seo_title']) + '</title>', src, count=1, flags=re.S)
    else:
        src = re.sub(r'<title>.*?</title>', '<title>' + E(page['seo_title']) + '</title>', src, count=1, flags=re.S)
    src = put(src, 'head', '\n' + render_head(page) + '\n', fallback=lambda s: (s.index('</head>'),) * 2)
    # nested <main> (rhel, nutanix): a page may only have one landmark
    ms = [m for m in re.finditer(r'<main\b([^>]*)>', src)]
    if len(ms) > 1:
        m2 = ms[1]
        close = src.index('</main>', m2.end())
        src = src[:m2.start()] + '<div' + m2.group(1) + '>' + src[m2.end():close] + '</div>' + src[close + len('</main>'):]
    # --- body attrs + skip link
    m = re.search(r'<body([^>]*)>', src)
    attrs = m.group(1)
    if 'data-rr-article' not in attrs:
        cls = re.search(r'class="([^"]*)"', attrs)
        attrs = (re.sub(r'class="[^"]*"', 'class="%s rr"' % cls.group(1), attrs) if cls else attrs + ' class="rr"') + ' data-rr-article'
    src = src[:m.start()] + '<body' + attrs + '>' + src[m.end():]
    if 'skip-link' not in src:
        src = src.replace('<body' + attrs + '>', '<body' + attrs + '>\n<a class="skip-link" href="#main-content">Skip to content</a>', 1)
    # --- header / nav / footer
    src = put(src, 'header', render_header(page),
              fallback=lambda s: (lambda a, b: (a.start(), b.start()) if a and b else None)(re.search(r'<div id="site-topbar">', s), re.search(r'<div id="prog">', s)))
    src = put(src, 'nav', render_nav(page), fallback=lambda s: (lambda m: (m.start(), m.end()) if m else None)(re.search(r'<nav id="site-nav">.*?</nav>', s, re.S)))

    def foot_fb(s):
        m = re.search(r'<footer id="site-footer">.*?</footer>', s, re.S)
        if m:
            return (m.start(), m.end())
        i = s.rindex('</body>')
        return (i, i)
    src = put(src, 'footer', render_footer(), fallback=foot_fb)
    # --- crumbs + meta around hero, related before </main>
    hero = re.search(r'<div class="page-hero">', src)
    if '<!--rr:crumbs-->' in src:
        src = put(src, 'crumbs', crumbs_html(page))
        src = put(src, 'meta', meta_html(page, words))
    else:
        mm = re.search(r'<main id="main-content">', src)
        end_hero = div_end(src, hero.start()) if hero else mm.end()
        src = src[:end_hero] + '\n' + mark('meta', meta_html(page, words)) + src[end_hero:]
        src = src[:mm.end()] + '\n' + mark('crumbs', crumbs_html(page)) + src[mm.end():]
    rel = related_html(page)
    if '<!--rr:related-->' in src:
        src = put(src, 'related', rel)
    else:
        i = src.rindex('</main>')
        src = src[:i] + mark('related', rel) + '\n' + src[i:]
    return src


def stamp_linux_guide(page):
    """linux-guide keeps its own dark layout; add head SEO, shared JS (search/shortcuts) and clean build-notes."""
    f = page['file']
    src = rd(f)
    page['_date'] = git_date(f)
    src = add_ids(src)
    page['_words'] = words_of(src)
    src = re.sub(r'<meta name="description"[^>]*>\s*', '', src)
    src = re.sub(r'<title>.*?</title>', '<title>' + E(page['seo_title']) + '</title>', src, count=1, flags=re.S)
    head = '\n' + render_head(page).replace('/assets/css/site.css?v=%s' % BUILD, '/assets/css/lg-extras.css?v=%s' % BUILD) + '\n'
    src = put(src, 'head', head, fallback=lambda s: (s.index('</head>'),) * 2)
    src = src.replace('<link rel="stylesheet" href="styles.css">', '<link rel="stylesheet" href="styles.css?v=%s">' % BUILD)
    src = src.replace('<a href="https://www.rootnreels.in/">Main site</a>',
                      '<a href="/">Main site</a> <button type="button" data-rr-search aria-label="Search all of root_n_reels">Search ⌕</button>')
    src = src.replace('<div class="tags"><span>28 chapters</span><span>Responsive HTML/CSS</span><span>GitHub Pages ready</span><span>Enterprise Linux focus</span></div>',
                      '<div class="tags"><span>28 chapters</span><span>Commands &amp; examples</span><span>Beginner → Advanced</span><span>Enterprise Linux focus</span></div>')
    src = src.replace('covering all 28 subject areas from the supplied Linux administration syllabus, with explanations, operational guidance, and command references.',
                      'covering 28 core Linux administration areas, with explanations, operational guidance, and command references.')
    src = src.replace('rewritten as original educational content', 'written as original educational content')
    if 'data-rr-article' not in src:
        src = src.replace('<body>', '<body data-rr-article data-rr-lg>', 1)
    return src


# --------------------------------------------------------------------------- generated pages
def shell(page, body, cls='rr-new', article=False, extra_attrs=''):
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(page.get("seo_title") or page["title"])}</title>
{mark("head", chr(10) + render_head(page) + chr(10))}
</head>
<body class="rr {cls}" data-rr-new{" data-rr-article" if article else ""}{extra_attrs}>
<a class="skip-link" href="#main-content">Skip to content</a>
{mark("header", render_header(page))}
<div id="prog"></div>
<div id="mob-ov" onclick="toggleNav()"></div>
<div class="site-body">
{mark("nav", render_nav(page))}
<main id="main-content">
{body}
</main>
</div>
<button id="btt" type="button" aria-label="Back to top" onclick="scrollTo({{top:0,behavior:'smooth'}})">↑</button>
{mark("footer", render_footer())}
</body>
</html>
'''


def page_stats():
    """per-page word counts and Q&A counts, taken from final HTML where available."""
    st = {}
    for p in PAGES:
        fp = ROOT / p['file']
        if fp.exists():
            s = fp.read_text(encoding='utf-8')
            st[p['id']] = {'words': words_of(s), 'q': len(re.findall(r'class="(?:q-card|qc|qa-item)[ "]', s))}
    return st


def card(p, extra=''):
    h = p.get('hub', '')
    return (f'<a class="rr-card" href="{p["url"]}" style="--cat:{HUB_COLORS.get(h, "#2F80ED")}"><h3><span aria-hidden="true">{p.get("icon", "")}</span> {E(p["title"])}</h3>'
            f'<p>{E(p["desc"])}</p><div class="meta">{extra}</div></a>')


def card_meta(p, st):
    s = st.get(p['id'], {})
    bits = []
    if p.get('level'):
        bits.append(f'<span>{E(p["level"])}</span>')
    if s.get('q'):
        bits.append(f'<span>{s["q"]} Q&amp;As</span>')
    if s.get('words'):
        bits.append(f'<span>{read_time(s["words"])}</span>')
    return ''.join(bits)


def hub_page(key, st):
    h = HUBS[key]
    page = {'id': 'hub-' + key, 'url': h['url'], 'hub': key, 'title': h['label'], 'type': '',
            'seo_title': f'{h["label"]}: Guides, Troubleshooting and Interview Prep | root_n_reels', 'desc': h['desc'], '_date': TODAY}
    guides = [p for p in PAGES if p.get('hub') == key and p.get('legacy')]
    arts = [p for p in PAGES if p.get('hub') == key and p.get('gen') == 'fragment' and p.get('type') == 'troubleshoot']
    body = f'<nav class="rr-crumbs" aria-label="Breadcrumb"><ol><li><a href="/">Home</a></li><li aria-current="page">{E(h["label"])}</li></ol></nav>'
    body += f'<header class="rr-page-head"><h1>{h["icon"]} {E(h["label"])}</h1><p>{E(h["desc"])}</p></header>'
    body += '<section class="rr-section"><h2>Guides &amp; references</h2><div class="rr-grid">' + ''.join(card(p, card_meta(p, st)) for p in guides) + '</div></section>'
    if arts:
        body += '<section class="rr-section"><h2>Fix it: troubleshooting articles</h2><p class="sub">Short, symptom-first pages: quick answer, diagnose, fix, safety notes.</p><div class="rr-grid">' + ''.join(card(p, card_meta(p, st)) for p in arts) + '</div></section>'
    body += ('<section class="rr-section"><h2>Keep going</h2><div class="rr-cta-row"><a class="rr-btn secondary" href="/troubleshooting/">Troubleshoot by symptom</a>'
             '<a class="rr-btn secondary" href="/interview/">Interview questions</a><a class="rr-btn secondary" href="/cheat-sheets.html">Cheat sheets</a>'
             '<button type="button" class="rr-btn ghost" data-rr-search>Search everything</button></div></section>')
    return page, shell(page, body)


def fragment_page(p, st):
    p['_date'] = git_date('content/' + p['fragment'])
    frag = rd('content/' + p['fragment'])
    if '{{paths}}' in frag:
        frag = frag.replace('{{paths}}', paths_html())
    if '{{reels}}' in frag:
        frag = frag.replace('{{reels}}', reels_html())
    frag = add_ids(frag)
    frag = comment_spans(frag)
    words = words_of(frag)
    p['_words'] = words
    if p.get('article'):
        head = f'<header class="rr-page-head"><h1>{E(p["title"])}</h1><p class="rr-lead">{E(p["desc"])}</p></header>'
        reel = ''
        if p.get('reel'):
            reels = jload('reels.json', {})
            r = reels.get(p['id'], {})
            yt = (' · <a href="%s" target="_blank" rel="noopener">YouTube</a>' % E(r['youtube'])) if r.get('youtube') else ''
            reel = ('<p class="rr-note-reel"><a href="%s" target="_blank" rel="noopener">▶ Watch the 60-second version on Instagram</a>%s</p>'
                    '<p class="rr-note-ib">Tip: you are in an in-app browser. Open this page in Chrome or Safari to keep your saved items.</p>') % (E(r.get('instagram') or SITE['instagram']), yt)
        body = crumbs_html(p) + head + meta_html(p, words) + reel + f'<div class="rr-prose" id="article">{frag}</div>' + related_html(p)
    else:
        body = crumbs_html(p) + frag
    return shell(p, body, article=bool(p.get('article')))


def reels_html():
    items = jload('reels.json', {}).get('_all', [])
    cards = ''.join('<a class="rr-card" href="%s" target="_blank" rel="noopener"><h3>▶ %s</h3><p>Watch on Instagram ↗</p></a>' % (E(x['url']), E(x['title'])) for x in reversed(items))
    return '<div class="rr-grid">%s</div>' % cards


def paths_html():
    out = ''
    for pa in jload('paths.json', []):
        steps = ''.join('<li data-u="%s"><a href="%s">%s</a></li>' % (E(x['u']), E(x['u']), E(x['t'])) for x in pa['steps'])
        out += '<div class="rr-path" id="path-%s"><h3>%s %s</h3><p class="rr-empty" style="margin:0 0 8px">%s</p><ol>%s</ol></div>' % (E(pa['id']), pa['icon'], E(pa['title']), E(pa['for']), steps)
    return out


def comment_spans(frag):
    def fix(m):
        body = m.group(2)
        if '<span' in body:
            return m.group(0)
        lines = body.split('\n')
        lines = ['<span class="cmt">%s</span>' % l if l.lstrip().startswith('#') else l for l in lines]
        return m.group(1) + '\n'.join(lines) + '</pre>'
    return re.sub(r'(<pre[^>]*>)(.*?)</pre>', fix, frag, flags=re.S)


def load_pages_data():
    return jload('scenarios.json', []), jload('paths.json', []), jload('reels.json', {}), jload('daily.json', [])


def home_page(st):
    p = BY_ID['home']
    p['_date'] = TODAY
    scn, paths, reels, daily = load_pages_data()
    nq = sum(s.get('q', 0) for s in st.values())
    nw = sum(s.get('words', 0) for s in st.values())
    tries = ['disk full', 'read-only file system', 'lvextend', 'selinux denied', 'multipath', 'high load', 'zfs', 'ansible']
    try_html = ''.join(f'<a class="rr-chip" href="/search/?q={E(t.replace(" ", "+"))}" data-rr-search data-q="{E(t)}">{E(t)}</a>' for t in tries)
    sym = ''.join(f'<a href="/troubleshooting/#{E(s["id"])}"><span aria-hidden="true">{s["icon"]}</span> {E(s["title"])}</a>' for s in scn)
    path_cards = paths_html()
    topics = ''
    for key, h in HUBS.items():
        pg = [x for x in PAGES if x.get('hub') == key and x.get('legacy')]
        qn = sum(st.get(x['id'], {}).get('q', 0) for x in pg)
        li = ''.join(f'<li><a href="{x["url"]}">{E(x.get("nav") or x["title"])}</a></li>' for x in pg[:5])
        topics += (f'<div class="rr-card" style="--cat:{HUB_COLORS[key]}"><h3><a href="{h["url"]}" style="color:inherit;text-decoration:none"><span aria-hidden="true">{h["icon"]}</span> {E(h["label"])} →</a></h3>'
                   f'<p>{E(h["desc"])}</p><ul style="margin:10px 0 0;padding-left:1.1em;font-size:.88rem">{li}</ul>'
                   f'<div class="meta"><span>{len(pg)} guide{"s" if len(pg) != 1 else ""}</span>{f"<span>{qn} Q&amp;As</span>" if qn else ""}</div></div>')
    recent = sorted([x for x in PAGES if x.get('legacy') or x.get('gen') == 'fragment' and x.get('article')], key=lambda x: x.get('_date', ''), reverse=True)[:6]
    rec_html = ''.join(card(x, f'<span>Updated {x.get("_date", TODAY)}</span>') for x in recent)
    reel_html = ''
    for rid, r in list(reels.items())[:3]:
        if rid in BY_ID:
            reel_html += card(BY_ID[rid], '<span>From the Reels</span>')
    body = f'''<section class="rr-hero">
  <p class="eyebrow">Linux · Unix · DevOps · Infrastructure</p>
  <h1>Practical knowledge for people who <span class="u">run servers</span>.</h1>
  <p class="lede">Look up a command. Fix an incident. Prepare for the interview.</p>
  <form class="rr-herosearch" data-rr-hero-form role="search" action="/search/" method="get">
    <svg class="rr-ico" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
    <input name="q" type="search" placeholder="Search &quot;lvextend&quot;, &quot;read-only file system&quot;, &quot;zfs&quot;…" aria-label="Search all guides" autocomplete="off" enterkeyhint="search">
    <kbd aria-hidden="true">/</kbd>
  </form>
  <div class="rr-try"><span>Try:</span>{try_html}</div>
  <div class="rr-cta-row">
    <a class="rr-btn primary" href="/troubleshooting/">🛠️ Troubleshoot a problem</a>
    <a class="rr-btn secondary" href="/interview/">🎯 Interview prep</a>
    <a class="rr-btn secondary" href="/cheat-sheets.html">📄 Cheat sheets</a>
  </div>
</section>

<section class="rr-section" id="rr-continue" data-rr-widget="home" hidden aria-label="Continue where you left off">
  <h2>Continue</h2><div class="rr-grid" id="rr-continue-grid"></div>
</section>

<section class="rr-strip" aria-label="Today">
  <div class="rr-panel"><h3>Today’s command</h3><div id="rr-daily"><p class="rr-empty">Loading…</p></div></div>
  <div class="rr-panel"><h3>Random interview question</h3><div id="rr-randq"><p class="rr-empty">Loading…</p></div></div>
  <div class="rr-panel"><h3>Scenario of the day</h3><div id="rr-scn"><p class="rr-empty">Loading…</p></div></div>
</section>

<section class="rr-section" aria-labelledby="h-sym"><h2 id="h-sym">Troubleshoot by symptom</h2><p class="sub">Start with what you see, not what you know.</p>
  <div class="rr-sym">{sym}</div></section>

<section class="rr-section" aria-labelledby="h-paths"><h2 id="h-paths">Start here: pick your path</h2><p class="sub">Ordered reading lists. Ticks appear as you visit pages (stored only in your browser).</p>
  <div class="rr-grid" id="rr-paths">{path_cards}</div></section>

<section class="rr-section" aria-labelledby="h-topics"><h2 id="h-topics">Explore topics</h2>
  <p class="sub">{len(HUBS)} topic hubs · {sum(1 for x in PAGES if x.get("legacy"))} guides · {nq}+ Q&amp;As · about {nw // 1000}k words, all free.</p>
  <div class="rr-grid">{topics}</div></section>

<section class="rr-section" aria-labelledby="h-int"><h2 id="h-int">Interview preparation</h2>
  <p class="sub">L1 → L2 → L3 questions pulled from every guide, with a random-question and practice mode.</p>
  <div class="rr-cta-row"><a class="rr-btn primary" href="/interview/#practice">Start practice mode</a>
  <a class="rr-btn secondary" href="/interview/">Browse by topic</a><a class="rr-btn secondary" href="/os-interview.html">OS Admin L3 guide</a></div></section>

<section class="rr-section" aria-labelledby="h-new"><h2 id="h-new">Recently updated</h2><div class="rr-grid">{rec_html}</div></section>
{f'<section class="rr-section" aria-labelledby="h-reel"><h2 id="h-reel">Quick fixes</h2><p class="sub">Short, symptom-first pages: the deeper write-up behind each Reel.</p><div class="rr-grid">{reel_html}</div><p><a href="{SITE["instagram"]}" target="_blank" rel="noopener">Instagram</a> · <a href="{SITE["youtube"]}" target="_blank" rel="noopener">YouTube</a></p></section>' if reel_html else ''}
'''
    return shell(p, body, extra_attrs=' data-rr-notrack')


def troubleshooting_page(st):
    p = BY_ID['troubleshooting']
    p['_date'] = git_date('data/scenarios.json')
    scn = jload('scenarios.json', [])
    body = crumbs_html(p) + f'<header class="rr-page-head"><h1>{E(p["title"])}</h1><p>{E(p["desc"])}</p></header>'
    body += '<div class="rr-callout warn"><div><span class="t">Production safety</span><p>Read-only checks first. Never run a destructive command until you have confirmed the device, filesystem or host. When in doubt, take a snapshot or backup and open a change.</p></div></div>'
    body += '<div class="rr-sym" style="margin:16px 0 28px">' + ''.join(f'<a href="#{E(s["id"])}"><span aria-hidden="true">{s["icon"]}</span> {E(s["title"])}</a>' for s in scn) + '</div>'
    for s in scn:
        cmds = '\n'.join(s['first'])
        links = ''.join(f'<a class="rr-chip" href="{E(l["u"])}">{E(l["t"])}</a>' for l in s.get('links', []))
        art = f'<a class="rr-btn primary" href="{BY_ID[s["article"]]["url"]}">Full step-by-step →</a>' if s.get('article') in BY_ID else ''
        body += (f'<section class="rr-scn" id="{E(s["id"])}"><h3><span aria-hidden="true">{s["icon"]}</span> {E(s["title"])}</h3><p>{E(s["symptom"])}</p>'
                 f'<div class="rr-code"><pre><code>{E(cmds)}</code></pre></div><p><strong>Why it happens:</strong> {E(s["why"])}</p>'
                 f'<div class="links">{art}{links}</div></section>')
    return shell(p, body, article=True)


def interview_page():
    p = BY_ID['interview']
    p['_date'] = TODAY
    body = crumbs_html(p) + f'''<header class="rr-page-head"><h1>🎯 Interview Prep</h1><p>{E(p["desc"])}</p></header>
<div class="rr-cta-row" style="margin-bottom:18px"><a class="rr-btn primary" href="#practice" data-mode="practice">Practice mode</a><button type="button" class="rr-btn secondary" id="rr-rand">Random question</button>
<a class="rr-btn ghost" href="/os-interview.html">OS Admin L3 guide</a></div>
<div data-rr-widget="interview" id="rr-iv">
  <div class="rr-filterbar" role="group" aria-label="Filters">
    <label class="sr-only" for="iv-topic">Topic</label><select id="iv-topic"><option value="">All topics</option></select>
    <label class="sr-only" for="iv-src">Guide</label><select id="iv-src"><option value="">All guides</option></select>
    <span id="iv-levels"></span>
    <label class="sr-only" for="iv-q">Filter questions</label><input id="iv-q" type="search" class="rr-cs-filter" style="margin:0;max-width:260px;height:40px" placeholder="Filter questions…">
  </div>
  <p id="iv-count" class="rr-empty" aria-live="polite">Loading questions…</p>
  <div id="iv-card" hidden></div>
  <ul class="rr-list-q" id="iv-list"></ul>
  <noscript><p>This page needs JavaScript for filtering. You can still read every question in the guides: <a href="/os-interview.html">OS Admin L3</a>, <a href="/linux-admin.html">Linux Admin</a>, <a href="/solaris.html">Solaris</a>, <a href="/hpux.html">HP-UX</a>, <a href="/itil.html">ITIL</a>.</p></noscript>
</div>'''
    return shell(p, body, extra_attrs=' data-rr-notrack')


def saved_page():
    p = BY_ID['saved']
    body = crumbs_html(p) + '''<header class="rr-page-head"><h1>★ Saved &amp; recent</h1><p>Everything here lives only in this browser. No account, no tracking.</p></header>
<div data-rr-widget="saved" id="rr-saved">
  <section class="rr-section"><h2>Continue reading</h2><div class="rr-grid" id="sv-continue"></div></section>
  <section class="rr-section"><h2>Saved</h2><div id="sv-saved"></div></section>
  <section class="rr-section"><h2>Recently viewed</h2><div id="sv-recent"></div></section>
  <section class="rr-section"><h2>Recent searches</h2><div id="sv-searches" style="display:flex;gap:8px;flex-wrap:wrap"></div></section>
  <section class="rr-section"><h2>Backup &amp; reset</h2>
    <p class="rr-empty">Move your data to another browser with export and import, or clear it here.</p>
    <div class="rr-cta-row"><button class="rr-btn secondary" id="sv-export" type="button">Export JSON</button>
    <label class="rr-btn secondary" style="cursor:pointer">Import JSON<input id="sv-import" type="file" accept="application/json" hidden></label>
    <button class="rr-btn ghost" id="sv-clear" type="button">Clear my data</button></div></section>
</div>'''
    return shell(p, body, extra_attrs=' data-rr-notrack')


def search_page():
    p = BY_ID['search']
    body = crumbs_html(p) + '''<header class="rr-page-head"><h1>Search</h1><p>Every section, Q&amp;A, command and cheat sheet across root_n_reels.</p></header>
<form role="search" action="/search/" method="get" class="rr-herosearch" id="rr-sform" style="margin-bottom:12px">
<svg class="rr-ico" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
<input name="q" type="search" id="rr-sq" aria-label="Search" placeholder="Search commands, errors, topics…" autocomplete="off"></form>
<div class="rr-filterbar" id="rr-sfil" role="group" aria-label="Category"></div>
<div data-rr-widget="searchpage" id="rr-sresults" aria-live="polite"></div>
<noscript><p>Search needs JavaScript. Browse instead: <a href="/linux/">Linux</a> · <a href="/unix/">Unix</a> · <a href="/networking/">Networking</a> · <a href="/devops/">DevOps</a> · <a href="/troubleshooting/">Troubleshooting</a> · <a href="/interview/">Interview</a>.</p></noscript>'''
    return shell(p, body, extra_attrs=' data-rr-notrack')


def notfound_page():
    p = {'id': '404', 'url': '/404.html', 'title': 'Page not found', 'seo_title': '404: Command not found | root_n_reels', 'desc': 'This page does not exist. Search root_n_reels or browse the topics.', 'noindex': True, '_date': TODAY}
    body = '''<section class="rr-hero" style="text-align:center;max-width:640px;margin:0 auto">
<p class="eyebrow">Error 404</p><h1 style="margin-left:auto;margin-right:auto;max-width:none"><code style="color:var(--accent)">bash: page: command not found</code></h1>
<p class="lede" style="margin-inline:auto">That URL does not exist (it may have moved). Try searching, or jump to a section.</p>
<form class="rr-herosearch" data-rr-hero-form role="search" action="/search/" method="get" style="margin:0 auto 18px"><svg class="rr-ico" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
<input name="q" type="search" placeholder="Search…" aria-label="Search" autocomplete="off"></form>
<div class="rr-cta-row" style="justify-content:center"><a class="rr-btn primary" href="/">Home</a><a class="rr-btn secondary" href="/troubleshooting/">Troubleshooting</a><a class="rr-btn secondary" href="/linux/">Linux</a><a class="rr-btn secondary" href="/interview/">Interview prep</a></div></section>'''
    return shell(p, body, extra_attrs=' data-rr-notrack')


# --------------------------------------------------------------------------- commands: stamp / pages
def cmd_stamp():
    n = 0
    for p in PAGES:
        if not p.get('legacy'):
            continue
        out = stamp_linux_guide(p) if p.get('special') == 'linux-guide' else stamp_legacy(p)
        n += wr(p['file'], out)
    print(f'stamp: {n} files changed')


def lg_extras():
    css = rd('assets/css/site.css')
    a, b = css.index('/* 6. COMPONENTS'), css.index('/* 9. FOOTER')
    tokens = (':root{--bg:#0b1120;--surface:#111b30;--surface2:#16213A;--surface3:#1C2943;--border:#2b3b55;--border2:#40516b;--text:#dce6f5;--text2:#a9bad4;--text3:#8595AD;'
              '--link:#7fb6ff;--sky:#7fb6ff;--accent:#f5c542;--accent-fill:#f5c542;--green:#3FCF8E;--red:#FF7A7A;--purple:#A78BFA;--code-bg:#070D18;--code-fg:#D6E2F0;--code-comment:#7F93AE;'
              '--font-mono:"JetBrains Mono RR",ui-monospace,Menlo,Consolas,monospace;--navy:#0d1628;--focus:#7fb6ff;--topbar-h:66px;--r-sm:6px;--r:10px}\n'
              '@font-face{font-family:"JetBrains Mono RR";font-weight:400;font-display:swap;src:url(/assets/fonts/jetbrains-mono-latin-400-normal.woff2) format("woff2")}\n'
              '.sr-only{position:absolute!important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}\n'
              '.rr-ico{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}\n'
              ':focus-visible{outline:2px solid var(--focus);outline-offset:2px}\n[id]{scroll-margin-top:84px}\n'
              '.rr-flash{animation:rrflash 1.4s ease-out 1}@keyframes rrflash{0%{background:rgba(245,182,66,.45)}100%{background:transparent}}\n'
              '@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;scroll-behavior:auto!important}}\n'
              '.rr-sections-btn{display:none!important}\n')
    return '/* generated from site.css by tools/build.py: shared components for /linux-guide/ (own dark theme) */\n' + tokens + css[a:b if False else css.index('/* 7. HOME')] + css[css.index('/* 8. SEARCH'):css.index('/* 9. FOOTER')]


def cmd_pages():
    st = page_stats()
    n = 0
    n += wr('assets/css/lg-extras.css', lg_extras())
    for p in PAGES:
        if p.get('gen') == 'fragment':
            n += wr(p['file'], fragment_page(p, st))
    for key in HUBS:
        pg, out = hub_page(key, st)
        n += wr(f'{key}/index.html', out)
    n += wr('troubleshooting/index.html', troubleshooting_page(st))
    n += wr('interview/index.html', interview_page())
    n += wr('saved/index.html', saved_page())
    n += wr('search/index.html', search_page())
    n += wr('404.html', notfound_page())
    for p in PAGES:
        if p.get('legacy'):
            p.setdefault('_date', git_date(p['file']))
    n += wr('index.html', home_page(st))
    print(f'pages: {n} files changed')


# --------------------------------------------------------------------------- search index + questions
KNOWN_TAGS = ['lvm', 'selinux', 'multipath', 'zfs', 'zones', 'ldom', 'systemd', 'systemctl', 'nfs', 'samba', 'dns', 'dhcp', 'ssh', 'firewalld', 'iptables',
              'raid', 'xfs', 'ext4', 'fstab', 'grub', 'kernel', 'cron', 'rpm', 'yum', 'dnf', 'chrony', 'ntp', 'bonding', 'vlan', 'bgp', 'ospf', 'eigrp',
              'ansible', 'podman', 'docker', 'kubernetes', 'git', 'terraform', 'sar', 'vmstat', 'iostat', 'tcpdump', 'iscsi', 'san', 'hba', 'ipmp', 'smf',
              'vxfs', 'vcs', 'ilo', 'idrac', 'patching', 'sudo', 'acl', 'quota', 'swap', 'oom', 'inode', 'journald', 'logrotate', 'ldap', 'apache', 'mysql',
              'postfix', 'vpn', 'cis', 'nutanix', 'itil', 'backup', 'lsof', 'strace']
Q_SEL = ('q-card', 'qc', 'qa-item')


def classes(t):
    return t.get('class') or []


def level_of(label, default):
    m = {'foundational': 'L1', 'intermediate': 'L2', 'advanced': 'L3', 'critical': 'L3'}
    return m.get((label or '').strip().lower(), default)


def clean_text(s):
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def cmds_from(tag):
    out, seen = [], set()
    for pre in tag.select('pre, .code-block'):
        for line in pre.get_text('\n').split('\n'):
            line = re.sub(r'^\s*[$#]\s*', '', line.strip()) if not line.strip().startswith('# ') else ''
            if not line or line.startswith('#'):
                continue
            toks = line.split()
            key = ' '.join(toks[:2]) if len(toks) > 1 and not toks[1].startswith('-') and len(toks[1]) < 14 else toks[0]
            if re.match(r'^[a-zA-Z][\w.\-/]*$', toks[0]) and key not in seen:
                seen.add(key)
                out.append(key)
    for c in tag.select('code'):
        t = c.get_text().strip()
        if 2 < len(t) < 40 and ' ' not in t.strip() and t not in seen:
            seen.add(t)
            out.append(t)
    return ' '.join(out)[:320]


class Idx:
    def __init__(self, page, url, default_kind):
        self.page, self.url, self.kind = page, url, default_kind
        self.docs, self.qs = [], []
        self.cur = None
        self.container = ''
        self.h2 = ''

    def start(self, sid, title, container=False, level=2):
        self.flush()
        if not title:
            self.cur = None
            return
        if container:
            self.container, self.h2, h = title, '', ''
        elif level == 2:
            self.h2, h = title, self.container
        else:
            h = self.h2 or self.container
        self.cur = {'sid': sid, 'title': title, 'text': [], 'h': h, 'cmd': ''}

    def add(self, text, node=None):
        if self.cur is not None:
            self.cur['text'].append(text)

    def flush(self):
        c = self.cur
        self.cur = None
        if not c:
            return
        text = clean_text(' '.join(c['text']))
        if len(text) < 30:
            return
        self.docs.append(self.mk(c['sid'], c['title'], c['h'], text, self.kind, self.page.get('level', ''), c.get('cmd', '')))

    def mk(self, sid, title, h, text, kind, level, cmd):
        low = (title + ' ' + text).lower()
        tags = [t for t in KNOWN_TAGS if re.search(r'\b' + re.escape(t) + r'\b', low)][:8]
        kw = self.page.get('keywords', '').split()
        tags = list(dict.fromkeys(tags + [k for k in kw if k in low][:4]))
        return {'u': self.url + ('#' + sid if sid else ''), 'p': self.page.get('nav') or self.page['title'], 't': title[:140], 'h': h[:80],
                'c': self.page.get('hub') or ('cheat' if self.page.get('type') == 'cheat' else 'linux'), 'k': kind, 'l': level, 'cmd': cmd,
                'tags': ' '.join(tags), 'x': text[:1300]}


def walk(node, ix, depth=0):
    for ch in node.children:
        if isinstance(ch, NavigableString):
            if ix.cur is not None and not isinstance(ch, type(None)):
                s = str(ch)
                if s.strip():
                    ix.cur['text'].append(s)
            continue
        if not isinstance(ch, Tag):
            continue
        cl = classes(ch)
        if ch.name in ('script', 'style', 'nav', 'footer', 'noscript', 'template', 'button', 'dialog', 'header') or 'rr-meta' in cl or 'rr-crumbs' in cl or 'rr-related' in cl or 'rr-qtools' in cl or ch.get('id') in ('toc-nav', 'site-nav'):
            if ch.name == 'header' and ch.get('id') != 'site-topbar' and 'rr-page-head' not in cl:
                pass
            continue
        if any(c in Q_SEL for c in cl) or (ch.name == 'div' and 'qa-item' in cl):
            emit_q(ch, ix)
            continue
        if ch.name in ('h2', 'h3', 'h4') and ch.get('id'):
            t = clean_text(ch.get_text(' '))
            lvl = 2 if ch.name == 'h2' else 3
            ix.start(ch['id'], t, level=lvl)
            if ix.cur is not None:
                ix.cur['cmd'] = ''
            continue
        if ch.get('id') and any(c in ('content-section', 'tab-pane', 'chapter', 'rr-scn') for c in cl):
            ttl = ch.select_one('.ph-title, .page-title, .card-title, .topic-title, .ov-title, h2, h3')
            ix.start(ch['id'], clean_text(ttl.get_text(' ')) if ttl else '', container=True)
            if ix.cur is not None:
                # command tokens for the whole container
                ix.cur['cmd'] = cmds_from(ch)
            walk(ch, ix, depth + 1)
            continue
        if ix.cur is not None and ch.name in ('pre',):
            ix.cur['cmd'] = (ix.cur.get('cmd', '') + ' ' + cmds_from(ch)).strip()[:320]
        walk(ch, ix, depth + 1)


def emit_q(q, ix):
    qt = q.select_one('.q-text, .qt') or q.select_one('.qa-question')
    if not qt or not q.get('id'):
        return
    question = re.sub(r'^\s*Q\s+', '', clean_text(qt.get_text(' ')))
    body = None
    for c in q.children:
        if isinstance(c, Tag) and any(x in classes(c) for x in ('q-body', 'qbody', 'qa-answer', 'qa-a')):
            body = c
    if body is None:
        body = q.select_one('.qa-a')
    ans = clean_text(re.sub(r'^\s*(▸\s*)?Answer\s*', '', clean_text(body.get_text(' ')) if body else ''))
    lvl_el = q.select_one('.lvl')
    badge = q.select_one('.qb, .q-badge')
    level = level_of(lvl_el.get_text() if lvl_el else '', ix.page.get('level', '').split('–')[-1].split('-')[-1] if ix.page.get('level') else 'L3')
    if not re.match(r'^L\d$', level):
        level = 'L3'
    topic = ix.h2 or ix.container or ix.page['title']
    topic = re.sub(r'^[^\w]+', '', re.sub(r'^\d+\s*[.\-:·]?\s*', '', topic)).strip()
    doc = ix.mk(q['id'], question, topic, question + ' ' + ans, 'qa', level, cmds_from(q))
    ix.docs.append(doc)
    ix.qs.append({'id': q['id'], 'q': question[:220], 'a': ans[:900], 't': topic[:60], 'l': level, 'u': doc['u'], 'p': doc['p'], 'c': doc['c'],
                  'y': clean_text(badge.get_text()) if badge else ''})


def cmd_index():
    docs, qs = [], []
    seen, seen_q = set(), set()
    for p in PAGES:
        fp = ROOT / p['file']
        if not fp.exists() or p['id'] in ('search', 'saved', 'home', 'interview', 'hub'):
            continue
        soup = BeautifulSoup(fp.read_text(encoding='utf-8'), 'html.parser')
        root = soup.select_one('#main-content') or soup.select_one('main') or soup.body
        kind = {'troubleshoot': 'troubleshoot', 'cheat': 'cheat', 'lab': 'lab'}.get(p.get('type'), 'article')
        ix = Idx(p, p['url'], kind)
        # the page itself (summary doc)
        ix.docs.append(ix.mk('', p['title'], '', p['desc'] + ' ' + p.get('keywords', ''), 'article', p.get('level', ''), ''))
        ix.docs[-1]['c'] = p.get('hub') or ix.docs[-1]['c']
        walk(root, ix)
        ix.flush()
        for d in ix.docs:
            d['t'] = re.sub(r'^[^\w"\'(]+', '', d['t']) or d['t']
            key = d['u']
            if key in seen:
                continue
            seen.add(key)
            if d['k'] == 'qa':
                nk = 'q:' + re.sub(r'\W+', ' ', d['t'].lower())[:120]
                if nk in seen:
                    continue
                seen.add(nk)
            docs.append(d)
        for q in ix.qs:
            nk = 'q:' + re.sub(r'\W+', ' ', q['q'].lower())[:120]
            if nk in seen_q:
                continue
            seen_q.add(nk)
            qs.append(q)
    # linux-guide chapters use <section class="chapter" id="ch-01"><h2>
    for i, d in enumerate(docs):
        d['id'] = i
    syn = jload('synonyms.json', {})
    out = {'v': TODAY, 'docs': docs, 'syn': syn}
    wr('assets/search/index.json', json.dumps(out, ensure_ascii=False, separators=(',', ':')))
    wr('data/questions.json', json.dumps(qs, ensure_ascii=False, separators=(',', ':')))
    # small bank for the homepage widget: short answers, spread across guides
    by = {}
    for q in qs:
        if 40 < len(q['q']) < 150 and 80 < len(q['a']):
            by.setdefault(q['p'], []).append(q)
    pick, i = [], 0
    while len(pick) < 60 and any(by.values()):
        for k in sorted(by):
            if by[k]:
                x = dict(by[k].pop(0))
                x['a'] = x['a'][:300].rsplit(' ', 1)[0] + ('…' if len(x['a']) > 300 else '')
                pick.append(x)
    wr('data/random.json', json.dumps(pick[:60], ensure_ascii=False, separators=(',', ':')))
    size = (ROOT / 'assets/search/index.json').stat().st_size
    print(f'index: {len(docs)} docs, {len(qs)} questions, index.json {size // 1024} KB')


# --------------------------------------------------------------------------- sitemap / pwa
def cmd_sitemap():
    urls = []
    for p in PAGES:
        if p.get('noindex'):
            continue
        urls.append(f'  <url><loc>{canon(p)}</loc><lastmod>{p.get("_date") or git_date(p["file"])}</lastmod></url>')
    for key, h in HUBS.items():
        urls.append(f'  <url><loc>{BASE}{h["url"]}</loc><lastmod>{TODAY}</lastmod></url>')
    wr('sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + '\n'.join(urls) + '\n</urlset>\n')
    wr('robots.txt', f'User-agent: *\nAllow: /\nDisallow: /search/\nDisallow: /saved/\n\nSitemap: {BASE}/sitemap.xml\n')
    wr('manifest.json', json.dumps({
        'name': 'root_n_reels — Linux & Unix Knowledge Base', 'short_name': 'root_n_reels', 'description': SITE['tagline'],
        'start_url': '/', 'scope': '/', 'display': 'standalone', 'background_color': '#0B1220', 'theme_color': '#14315C',
        'icons': [{'src': '/assets/favicon-192.png', 'sizes': '192x192', 'type': 'image/png'}, {'src': '/assets/favicon-512.png', 'sizes': '512x512', 'type': 'image/png'}],
        'shortcuts': [{'name': 'Search', 'url': '/search/'}, {'name': 'Troubleshoot', 'url': '/troubleshooting/'}, {'name': 'Interview prep', 'url': '/interview/'}]}, indent=2) + '\n')
    sw = ROOT / 'service-worker.js'
    if sw.exists():
        s = sw.read_text(encoding='utf-8')
        s2 = re.sub(r"const VERSION = '[^']*';", f"const VERSION = 'rr-{BUILD}-{hashlib.sha1((ROOT / 'assets/search/index.json').read_bytes()).hexdigest()[:6] if (ROOT / 'assets/search/index.json').exists() else '0'}';", s)
        if s2 != s:
            sw.write_text(s2, encoding='utf-8')
    print('sitemap/manifest/sw written')


# --------------------------------------------------------------------------- checks
def cmd_check():
    bad = []
    cn = (ROOT / 'CNAME').read_text().strip() if (ROOT / 'CNAME').exists() else ''
    if cn != 'www.rootnreels.in':
        bad.append(f'CNAME must be www.rootnreels.in, got {cn!r}')
    for need in ['studyhub.css', 'assets/css/site.css', 'assets/js/app.js', 'assets/search/index.json', '.nojekyll']:
        if not (ROOT / need).exists():
            bad.append('missing ' + need)
    files = [p for p in ROOT.rglob('*.html') if '.git' not in p.parts and 'node_modules' not in p.parts]
    for f in files:
        s = f.read_text(encoding='utf-8')
        ids = re.findall(r'\bid="([^"]+)"', s)
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            bad.append(f'{f.relative_to(ROOT)}: duplicate ids {sorted(dup)[:5]}')
        for href in re.findall(r'(?:href|src)="(/[^"#?]*)', s):
            t = ROOT / href.lstrip('/')
            if href == '/' or t.exists() or (t / 'index.html').exists():
                continue
            bad.append(f'{f.relative_to(ROOT)}: broken local link {href}')
        if len(s.encode()) > 320_000 and f.name not in ('solaris.html',):
            bad.append(f'{f.relative_to(ROOT)}: HTML over 320 KB budget')
    if bad:
        print('\n'.join(sorted(set(bad))))
        sys.exit(1)
    print(f'check: OK ({len(files)} html files)')


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if cmd in ('all', 'stamp'):
        cmd_stamp()
    if cmd in ('all', 'pages'):
        cmd_pages()
    if cmd in ('all', 'index'):
        cmd_index()
    if cmd in ('all', 'sitemap'):
        cmd_sitemap()
    if cmd in ('check',):
        cmd_check()


if __name__ == '__main__':
    main()
