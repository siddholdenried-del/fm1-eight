#!/bin/sh
# groovebox.bongcult.com: the built site (site/build.py) pushed to this repository's "site" branch, which Cloudflare
# Pages deploys (production branch "site", no build command, output directory "/"). From fm1-eight, after the --web
# build: sh site/publish.sh
set -e
SRC=$(git rev-parse --short HEAD)
DIRTY=$(git status --porcelain --untracked-files=no | head -1)
[ -z "$DIRTY" ] || { echo "publish: commit the source first (the site must match a commit)"; exit 1; }
T=$(mktemp -d)
python3 -I site/build.py "$T/out"
cd "$T/out"
git init -q -b site
git config user.name "$(git -C "$OLDPWD" config user.name)"
git config user.email "$(git -C "$OLDPWD" config user.email)"
git add -A
git commit -q -m "groovebox.bongcult.com, built from $SRC"
git push -q -f "$(git -C "$OLDPWD" remote get-url origin)" site
echo "publish: the site branch is $SRC's site"
rm -rf "$T"
