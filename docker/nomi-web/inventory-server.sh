#!/bin/sh
# Loose search for slug-generation code in the deployed bundles.
set -e
docker run --rm --entrypoint sh nomi-web:latest -c '
cd /usr/share/nginx/html/assets-nomi
echo "--- files containing toLocaleLowerCase ---"
grep -l "toLocaleLowerCase" *.js || true
echo "--- slug setValue contexts ---"
for f in $(grep -l "toLocaleLowerCase" *.js 2>/dev/null); do
  echo "FILE: $f"
  grep -o ".\{0,50\}toLocaleLowerCase.\{0,140\}" "$f" | grep -i "slug\|replace" | head -6
done
'
