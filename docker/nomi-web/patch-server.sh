#!/bin/sh
# Server-side patch build for nomi-web, byte-exact surgery:
# 1. extract the entry chunk + index.html from nomi-web:prev
# 2. entry: original code (everything before the v1 injector marker) + v2 injector
# 3. index.html: inject a static NOMI boot splash so the top-left is branded
#    on the very first paint, before any bundle executes; React removes it
#    on hydration and the injector sweeps it away too
# 4. rebuild the image layer by copying the ready files in (no sed on bundles)
set -e
WORK=/tmp/nomi-patch
rm -rf "$WORK"; mkdir -p "$WORK"
cp ~/nomi/docker/nomi-web/nomi-brand.js "$WORK/"
cp ~/nomi/docker/nomi-web/nomi-theme.css "$WORK/"
cp ~/nomi/docker/nomi-web/icons/favicon.ico "$WORK/"
cp ~/nomi/docker/nomi-web/icons/apple-touch-icon.png "$WORK/"

docker create --name nomi-src nomi-web:prev >/dev/null
trap 'docker rm -f nomi-src >/dev/null 2>&1' EXIT
ENTRY=$(docker run --rm --entrypoint sh nomi-web:prev -c 'ls /usr/share/nginx/html/assets-nomi/entry.client-*.js' | xargs -n1 basename)
echo "entry file: $ENTRY"
docker cp "nomi-src:/usr/share/nginx/html/assets-nomi/$ENTRY" "$WORK/$ENTRY"
docker cp "nomi-src:/usr/share/nginx/html/index.html" "$WORK/index.html"

cat > "$WORK/patch.js" <<'JSEOF'
const fs = require("fs");
// entry: pristine bytes + v2 injector
const entry = fs.readdirSync("/w").filter(f => f.startsWith("entry.client-"))[0];
const buf = fs.readFileSync("/w/" + entry);
const marker = buf.indexOf("/* NOMI brand injector");
if (marker < 0) { console.error("marker not found"); process.exit(2); }
const inj = fs.readFileSync("/w/nomi-brand.js");
fs.writeFileSync("/w/" + entry, Buffer.concat([buf.slice(0, marker), inj]));
console.log("entry orig:", marker, "v2:", inj.length);
// index.html: static boot splash before </body>
const BOOT = "<div id='nomi-boot' style='position:fixed;top:20px;left:24px;z-index:2147483647;display:flex;align-items:center;gap:8px;pointer-events:none'><span style='width:28px;height:28px;border-radius:8px;background:#171719 url(/brand/ztrz-mark-white.png) center/72% no-repeat;display:inline-block'></span><span style='font-size:14px;font-weight:700;letter-spacing:.02em'>NOMI</span></div>";
const html = fs.readFileSync("/w/index.html", "utf8");
if (html.includes("nomi-boot")) {
  console.log("boot splash already present");
} else if (html.includes("</body>")) {
  fs.writeFileSync("/w/index.html", html.replace("</body>", BOOT + "</body>"));
  console.log("boot splash injected");
} else {
  console.error("no </body> in index.html"); process.exit(3);
}
JSEOF

docker run --rm -v "$WORK:/w" node:20-alpine node /w/patch.js

cat > "$WORK/Dockerfile" <<'EOF'
FROM nomi-web:prev
COPY nomi-brand.js /usr/share/nginx/html/assets-nomi/nomi-brand.js
COPY nomi-theme.css /usr/share/nginx/html/assets-nomi/nomi-theme.css
COPY favicon.ico /tmp/nomi-favicon.ico
COPY apple-touch-icon.png /tmp/nomi-touch.png
COPY entry.client-BJhItYEm.js /tmp/nomi-entry.js
COPY index.html /tmp/nomi-index.html
RUN set -eux; \
    cd /usr/share/nginx/html/assets-nomi; \
    sed -i 's#api/assets-nomi/#api/assets/#g' store-context-*.js; \
    ! grep -q "api/assets-nomi" store-context-*.js; \
    sed -i 's#toLocaleLowerCase().trim().replace(/ /g,`-`)#toLocaleLowerCase().trim().replace(/ /g,`-`).replace(/[^a-z0-9-]/g,``).replace(/^-+|-+$/g,``).slice(0,48)||`ws-`+Math.random().toString(36).slice(2,8)#g' page-*.js; \
    grep -c "ws-\`\+Math.random" page-BB_PtU_9.js page-BO5oii6P.js || true; \
    for f in favicon-*.ico; do cp /tmp/nomi-favicon.ico "$f"; done; \
    for f in icon-180x180-*.png; do cp /tmp/nomi-touch.png "$f"; done; \
    for f in /tmp/nomi-entry.js; do cp "$f" entry.client-*.js; done; \
    cp /tmp/nomi-index.html ../index.html; \
    rm -f /tmp/nomi-favicon.ico /tmp/nomi-touch.png /tmp/nomi-entry.js /tmp/nomi-index.html; \
    globals=$(ls globals-*.css | head -1); \
    printf '\n' >> "$globals"; \
    cat nomi-theme.css >> "$globals"; \
    grep -c "nomi-boot" ../index.html; \
    wc -c entry.client-*.js
EOF

cd ~/nomi/docker/nomi-web
docker build -t nomi-web:latest "$WORK" 2>&1 | grep -E "nomi-boot|bytes|entry.client|error|ERROR" | tail -4
docker run --rm --entrypoint sh nomi-web:latest -c 'grep -c "nomi-boot" /usr/share/nginx/html/index.html && grep -o "window.__nomiBrand = 2" /usr/share/nginx/html/assets-nomi/entry.client-*.js | head -1'
