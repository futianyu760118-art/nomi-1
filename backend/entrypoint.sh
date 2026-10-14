#!/bin/sh
# docker compose restart does not gate on dependency health checks, so wait
# for MySQL here instead of crash-looping through the app's startup seed.
python - <<'PY'
import os
import sys
import time

import pymysql

for attempt in range(60):
    try:
        pymysql.connect(host=os.getenv("MYSQL_HOST"), user=os.getenv("MYSQL_USER", "pmo"),
                        password=os.getenv("MYSQL_PASSWORD"), database=os.getenv("MYSQL_DATABASE", "pmo"))
        sys.exit(0)
    except Exception:
        print("waiting for database...", file=sys.stderr, flush=True)
        time.sleep(2)
sys.exit("database not reachable after 120s")
PY
exec "$@"
