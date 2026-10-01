# root_n_reels

Practical knowledge for people who run servers — look up a command, fix an incident, prepare for the interview.
Live site: https://www.rootnreels.in

Static site on GitHub Pages: plain HTML/CSS/vanilla JS, no framework.

## Layout
- `*.html`, `linux-guide/` — existing long-form guides (content preserved; header/nav/footer/SEO are stamped in by the build)
- `content/` — fragments for generated pages (start-here, cheat sheets, labs, about, new troubleshooting articles)
- `data/` — `content.json` (site manifest: pages, hubs, related links), scenarios, paths, daily commands, synonyms
- `partials/` — shared header and footer
- `assets/css/site.css`, `assets/js/app.js|search.js|widgets.js` — design system and behaviour
- `tools/build.py` — build helper

## Build
```
pip install beautifulsoup4
python tools/build.py all     # stamp pages, generate hubs/pages, search index, sitemap, SW version
python tools/build.py check   # validate links, ids, metadata
python3 -m http.server 8000   # preview
```
Run `all` and commit the output after editing content, `data/`, `partials/` or assets. CI runs the build and `check` on every push.

## Adding an article
Add an entry to `data/content.json` (id, url, hub, title, desc, level, type, related), create the fragment in `content/`, then build.

## Notes
- Do not change `CNAME`. Optional analytics: set `goatcounter` in `data/content.json`.
- Reel landing links: fill `data/reels.json`.
