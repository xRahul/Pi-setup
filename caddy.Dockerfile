FROM --platform=linux/arm64 caddy:builder AS builder

RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare

FROM --platform=linux/arm64 caddy:latest

COPY --from=builder /usr/bin/caddy /usr/bin/caddy