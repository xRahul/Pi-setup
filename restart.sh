#!/bin/bash
set -e

# Always run from the directory containing this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Stopping all containers (core & lazy) ==="
docker compose --profile lazy down

echo "=== Creating containers (without starting) ==="
docker compose --profile lazy up --no-start

echo "=== Starting core services ==="
docker compose up -d --remove-orphans

# `down` deleted and recreated the wg-easy bridge, which removed the host
# route to the tailnet. Restore it (rpi-tailscale-hairpin.service does the
# same at boot, ordered after this script).
echo "=== Restoring Tailscale hairpin route ==="
if [ "$EUID" -eq 0 ]; then
    ip route replace 100.64.0.0/10 via 10.8.1.48 || echo "WARN: hairpin route not restored" >&2
else
    sudo -n ip route replace 100.64.0.0/10 via 10.8.1.48 || echo "WARN: hairpin route not restored" >&2
fi
echo "=== Restart sequence completed successfully ==="
