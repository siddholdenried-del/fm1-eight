#!/bin/sh
# ghettomachine.bongcult.com: Cloudflare Workers Builds deploys this repository's main branch on every push, serving
# site/public (wrangler.toml). From the repository's top, after the --web build: sh site/publish.sh rebuilds site/public from the
# committed source, commits it if it changed, and pushes main.
set -e
DIRTY=$(git status --porcelain --untracked-files=no -- . ':!site/public' | head -1)
[ -z "$DIRTY" ] || { echo "publish: commit the source first (the site must match a commit)"; exit 1; }
SRC=$(git rev-parse --short HEAD)
python3 -I site/build.py site/public
git add -A site/public
if git diff --cached --quiet; then
  echo "publish: site/public already matches $SRC"
else
  git commit -q -m "The site, built from $SRC"
fi
git push -q origin main
echo "publish: main pushed; Cloudflare deploys it in a minute or two"
