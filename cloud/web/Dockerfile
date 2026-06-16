# Builds the dashboard SPA and serves it with Caddy (static files + reverse proxy
# to the API). Build context is `cloud/` so we can copy both web/ and the Caddyfile.
#
#   docker compose build caddy   (handled by docker-compose.yml)

# ── stage 1: build the static bundle ──────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ── stage 2: Caddy serving the build + proxying the API ───────────
FROM caddy:2-alpine
COPY --from=build /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
