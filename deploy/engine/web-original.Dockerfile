# Pristine Plane frontend for side-by-side comparison with the AEOS-themed
# build. Uses the official v1.4.2 image (digest-pinned for offline builds)
# with an nginx config that proxies API paths to the engine.
FROM makeplane/plane-frontend@sha256:22fd2434fb8d6658439f669ab72f999ce0773abe587663da21a77d70bd63ff61
# The official image inlines its server block in the main nginx.conf (no
# conf.d include), so replace the whole file.
COPY web-original.nginx.conf /etc/nginx/nginx.conf
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:3000/ || exit 1
