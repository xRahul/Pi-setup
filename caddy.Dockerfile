FROM caddy:builder-alpine AS builder
RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare \
    --with github.com/sablierapp/sablier-caddy-plugin@v1.0.2

FROM caddy:alpine
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
