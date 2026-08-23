#!/usr/bin/env bash
# Assemble CI-only env files: example.env ships empty path placeholders that
# interpolate into invalid volume specs (":/srv"), and compose references the
# untracked pihole.env. Values are throwaway dummies for validation only.
set -euo pipefail
cp example.env .env
cp example_pihole.env pihole.env
sed -i 's#^\([A-Za-z_][A-Za-z0-9_]*\)=\s*$#\1=/tmp/ci-placeholder#' .env
sed -i 's#^CADDY_SITE_PATH=.*#CADDY_SITE_PATH=/tmp/caddy-site#; s#^CADDY_DATA_PATH=.*#CADDY_DATA_PATH=/tmp/caddy-data#; s#^CADDY_CONFIG_PATH=.*#CADDY_CONFIG_PATH=/tmp/caddy-config#; s#^CLOUDFLARE_API_TOKEN=.*#CLOUDFLARE_API_TOKEN=citest0000000000000000000000000000000000#' .env
mkdir -p /tmp/caddy-site /tmp/caddy-data /tmp/caddy-config
