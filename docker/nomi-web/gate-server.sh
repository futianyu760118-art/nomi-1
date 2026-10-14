#!/bin/sh
# Syntax gate over every bundle in the built image, run on the server.
set -e
docker create --name nomi-gate nomi-web:latest >/dev/null
trap 'docker rm -f nomi-gate >/dev/null 2>&1; rm -rf /tmp/gate-assets' EXIT
docker cp nomi-gate:/usr/share/nginx/html/assets-nomi /tmp/gate-assets >/dev/null 2>&1
docker run --rm -v /tmp/gate-assets:/assets:ro node:20-alpine sh -c '
  cd /assets
  fail=0
  total=0
  for f in *.js; do
    total=$((total + 1))
    if ! node --check "$f"; then
      echo "SYNTAX-FAIL: $f"
      fail=1
    fi
  done
  echo "checked $total bundles"
  if [ "$fail" -eq 0 ]; then
    echo ALL-BUNDLES-OK
  else
    exit 1
  fi
'
