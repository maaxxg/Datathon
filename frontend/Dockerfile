# Build context: repository root (see docker-compose.yml).
FROM node:20 AS build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM caddy:2
COPY --from=build /build/build /srv
COPY deploy/Caddyfile /etc/caddy/Caddyfile
