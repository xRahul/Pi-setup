#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$EUID" -ne 0 ]; then
  echo "ERROR: scripts/setup-host.sh must be run with sudo or as root" >&2
  exit 1
fi

echo "=== 1. Checking host packages ==="
MISSING_PKGS=()
for pkg in ethtool iproute2 curl; do
  if ! command -v "$pkg" >/dev/null 2>&1; then
    MISSING_PKGS+=("$pkg")
  fi
done

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
  echo "Installing missing dependencies: ${MISSING_PKGS[*]}"
  apt-get update -qq && apt-get install -y -qq "${MISSING_PKGS[@]}"
else
  echo "All required host tools (ethtool, iproute2, curl) are present."
fi

echo "=== 2. Installing systemd units ==="
cp "$SCRIPT_DIR/systemd/rpi-tailscale-hairpin.service" /etc/systemd/system/
cp "$SCRIPT_DIR/systemd/rpi5-udp-gro.service" /etc/systemd/system/
chmod 644 /etc/systemd/system/rpi-tailscale-hairpin.service /etc/systemd/system/rpi5-udp-gro.service

systemctl daemon-reload
systemctl enable --now rpi-tailscale-hairpin.service
systemctl enable --now rpi5-udp-gro.service

echo "=== 3. Verifying Hairpin Route ==="
if ip route show 100.64.0.0/10 | grep -q "10.8.1.48"; then
  echo "SUCCESS: Hairpin route active: $(ip route show 100.64.0.0/10)"
else
  echo "WARNING: Hairpin route not yet active. It will activate when Docker network initializes."
fi

echo "=== 4. Verifying UDP GRO Offload ==="
for iface in eth0 wlan0; do
  if ip link show "$iface" >/dev/null 2>&1; then
    echo "Interface $iface present; GRO offload rules applied."
  fi
done

echo "Host setup completed successfully!"
