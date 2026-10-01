#!/usr/bin/env bash
# Commit the redesign and push to GitHub. Paste your token when asked (input is hidden).
set -euo pipefail
cd "$(dirname "$0")"

REPO="AdmVishal/RootReady"
BRANCH="main"
USER_NAME="AdmVishal"

command -v git >/dev/null || { echo "git is required"; exit 1; }
[ -d .git ] || { echo "Run this inside the repo folder (no .git found)"; exit 1; }

# Make sure the domain file is intact
[ "$(tr -d '[:space:]' < CNAME)" = "www.rootnreels.in" ] || { echo "CNAME changed - aborting"; exit 1; }

# Optional rebuild if python + bs4 are available
if command -v python3 >/dev/null && python3 -c "import bs4" 2>/dev/null; then
  python3 tools/build.py all && python3 tools/build.py check
else
  echo "(skipping rebuild: pip install beautifulsoup4 to enable)"
fi

git checkout "$BRANCH" 2>/dev/null || true
# Use your own identity for the commit (the bundled repo may carry a placeholder one)
git config user.name  >/dev/null 2>&1 && [ "$(git config user.name)" != "Claude" ] || git config user.name  "AdmVishal"
git config user.email >/dev/null 2>&1 && [ "$(git config user.email)" != "noreply@anthropic.com" ] || git config user.email "admvishal24@gmail.com"
git add -A
if git diff --cached --quiet; then
  echo "Nothing new to commit."
else
  git commit -m "Redesign: shared design system, search, hubs, troubleshooting"
fi

read -r -s -p "Paste GitHub token (hidden), then press Enter: " TOKEN
echo
[ -n "$TOKEN" ] || { echo "No token entered"; exit 1; }

# Token is passed only for this one push via a temporary header; it is not saved in git config or the remote URL.
AUTH=$(printf '%s:%s' "$USER_NAME" "$TOKEN" | base64 | tr -d '\n')
git -c http.extraHeader="Authorization: Basic $AUTH" push "https://github.com/$REPO.git" "$BRANCH"
unset TOKEN AUTH
echo "Pushed. Check Settings > Pages for the deploy."
