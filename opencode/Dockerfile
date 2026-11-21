FROM node:24-bookworm-slim

ARG OPENCODE_VERSION=2.3.2
ARG DONSETCH_VERSION=5.5.7
ARG CAVEMAN_VERSION=4.1.0

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates curl wget git python3 procps passwd chromium fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g \
      @opencode/cli@${OPENCODE_VERSION} \
      donsetch@${DONSETCH_VERSION} \
      @caveman-ai/cli@${CAVEMAN_VERSION} \
    && npm cache clean --force

RUN printf '%s\n' \
      '#!/bin/sh' \
      'exec /usr/bin/chromium --use-gl=angle --use-angle=swiftshader-webgl --enable-unsafe-swiftshader --no-sandbox --disable-dev-shm-usage "$@"' \
      > /usr/local/bin/donsetch-chrome-wrapper \
    && chmod 755 /usr/local/bin/donsetch-chrome-wrapper

RUN if getent passwd 1000 >/dev/null; then \
      userdel -r "$(getent passwd 1000 | cut -d: -f1)" 2>/dev/null || true; \
    fi \
    && if getent group 1000 >/dev/null; then \
      groupdel "$(getent group 1000 | cut -d: -f1)" 2>/dev/null || true; \
    fi \
    && useradd -m -u 1000 -s /bin/bash opencode

USER opencode
WORKDIR /home/opencode
ENTRYPOINT ["opencode"]
CMD ["serve", "--hostname", "0.0.0.0", "--port", "4096"]
