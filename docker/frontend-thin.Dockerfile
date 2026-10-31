# Thin runtime image for the NOMI console: the static bundle is built on the
# host (npm run build) and served by nginx, avoiding in-container npm installs
# on flaky networks.
FROM nginx@sha256:8b1e78743a03dbb2c95171cc58639fef29abc8816598e27fb910ed2e621e589a
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY dist/ /usr/share/nginx/html/
EXPOSE 80
