# NOMI web: the pristine official Plane v1.4.2 frontend (known-good popover
# positioning) rebranded at the artifact layer. All overlays land in the
# versioned asset directory that rebrand.sh creates — index.html references it.
FROM makeplane/plane-frontend@sha256:22fd2434fb8d6658439f669ab72f999ce0773abe587663da21a77d70bd63ff61

# 1) String-level rebrand + asset directory versioning.
COPY rebrand.sh /tmp/rebrand.sh
RUN sh /tmp/rebrand.sh && rm /tmp/rebrand.sh

# 2) Icons, spinner animation and PWA assets into the versioned asset dir.
COPY icons/ /tmp/nomi-icons/
COPY brand/ /usr/share/nginx/html/brand/
RUN set -eux; \
    cd /usr/share/nginx/html/assets-nomi; \
    cp /tmp/nomi-icons/icon-*.png . ; \
    for f in /tmp/nomi-icons/*.png; do \
      base=$(basename "$f" .png); \
      match=$(ls | grep -i "^${base}-" | head -1 || true); \
      [ -n "$match" ] && cp "$f" "$match" || true; \
    done; \
    for f in favicon-*.ico; do cp /tmp/nomi-icons/favicon.ico "$f"; done; \
    for f in icon-180x180-*.png; do cp /tmp/nomi-icons/apple-touch-icon.png "$f"; done; \
    dark=$(ls | grep '^logo-spinner-dark-.*\.gif$' | head -1 || true); \
    light=$(ls | grep '^logo-spinner-light-.*\.gif$' | head -1 || true); \
    [ -n "$dark" ] && cp /tmp/nomi-icons/spinner/logo-spinner-dark.gif "$dark"; \
    [ -n "$light" ] && cp /tmp/nomi-icons/spinner/logo-spinner-light.gif "$light"; \
    rm -rf /tmp/nomi-icons

# 3) Theme overlay + brand injector.
#    The theme is APPENDED to the app's own stylesheet rather than linked from
#    index.html: React Router hydrates the document and drops <link> nodes it
#    did not render, so a separate tag disappears. Bundling the rules into a
#    stylesheet the app itself loads survives hydration and, because the bundle
#    is loaded from the versioned path, reaches pre-rebrand sessions too.
#    The injector is likewise appended to the client entry chunk (in addition
#    to the index.html tag) so it runs even when the HTML shell is cached.
COPY nomi-theme.css /tmp/nomi-theme.css
COPY nomi-brand.js /usr/share/nginx/html/assets-nomi/nomi-brand.js
RUN set -eux; \
    cd /usr/share/nginx/html/assets-nomi; \
    globals=$(ls globals-*.css | head -1); \
    printf '\n/* ---- NOMI theme ---- */\n' >> "$globals"; \
    cat /tmp/nomi-theme.css >> "$globals"; \
    cp /tmp/nomi-theme.css ./nomi-theme.css; \
    rm /tmp/nomi-theme.css; \
    for entry in entry.client-*.js; do cat nomi-brand.js >> "$entry"; done; \
    sed -i 's|</body>|<div id="nomi-boot" style="position:fixed;top:20px;left:24px;z-index:2147483647;display:flex;align-items:center;gap:8px;pointer-events:none"><span style="width:28px;height:28px;border-radius:8px;background:#171719 url(/brand/ztrz-mark-white.png) center/72% no-repeat;display:inline-block"></span><span style="font-size:14px;font-weight:700;letter-spacing:.02em">NOMI</span></div><script src="/assets-nomi/nomi-brand.js" defer></script></body>|' ../index.html; \
    echo "theme merged into $globals"

# 4) Cache hygiene: the rebrand rewrites bundle bytes while keeping upstream's
#    hashed filenames (plus the directory version token), so assets must
#    revalidate. The official image inlines its server block in nginx.conf,
#    so that file is replaced wholesale.
COPY nginx.conf /etc/nginx/nginx.conf
