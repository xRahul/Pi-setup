# Repo Architecture Notes

This repository contains the Docker Compose based Raspberry Pi 5 homelab stack. The primary stack definition is [docker-compose.yml](file:///home/rahul/docker/docker-compose.yml); local paths, credentials, versions, and dashboard variables are supplied via `.env`.

Do not paste secret values from `.env` into documentation or commits. Refer strictly to environment variable keys.

---

## Key Files & Configuration Map

- [docker-compose.yml](file:///home/rahul/docker/docker-compose.yml): Primary multi-container stack definition (54 services).
- `.env`: Live host configuration, directory paths, and secret tokens (git-ignored).
- `example.env`: Reference template with default path configurations and empty credential placeholders.
- `pihole.env`: Live Pi-hole local DNS host mapping source (`FTLCONF_dns_hosts`).
- [Caddyfile](file:///home/rahul/docker/Caddyfile): HTTPS reverse proxy configuration for `*.pi.rahulja.in`.
- [caddy.Dockerfile](file:///home/rahul/docker/caddy.Dockerfile): Multi-stage custom Caddy build with Cloudflare DNS-01 and Sablier plugins.
- [gethomepage/services.yaml](file:///home/rahul/docker/gethomepage/services.yaml): Dashboard layout, category groups, links, and widget definitions.
- [scripts/audit-config.sh](file:///home/rahul/docker/scripts/audit-config.sh): Comprehensive static analysis script validating compose syntax, healthchecks, memory limits, and IP bindings.
- [check_updates.py](file:///home/rahul/docker/check_updates.py): Dynamic image tag scraper querying Docker Hub, GitHub Container Registry (ghcr.io), and LinuxServer.io for updates.

---

## Compose Layout & Networking

The stack manages 54 services across custom bridge networks:

### Networks:
1. `wg-easy`: Main Docker bridge network (`10.8.1.0/24`, gateway `10.8.1.1`).
   - All proxied application containers reside here with static IP addresses.
   - Primary DNS points to `10.8.1.48` (Pi-hole).
2. `read-proxy-net`: Internal Docker network without host port bindings.
   - Provides read-only access to `socket-proxy-read` for Homepage container metric scrapers.
3. `portainer-proxy-net`: Internal Docker network.
   - Provides admin-tier Docker socket access to `socket-proxy-admin` for Portainer.

### Network Namespace Sharing (`10.8.1.48`):
The core infrastructure containers (`tailscale`, `caddy`, `pihole`, `dnscrypt-proxy`) share Tailscale's network namespace (`network_mode: service:tailscale`):
- Operates as a single logical network node on the `wg-easy` bridge at IP `10.8.1.48`.
- Caddy handles TLS termination directly on Tailscale's virtual network interface and forwards requests over `wg-easy` to application containers.
- Pi-hole binds to local DNS queries on port 53 and forwards upstream queries to DNSCrypt-Proxy on `127.0.0.1:5053`.

---

## Host Systemd Integrations

The host Raspberry Pi 5 runs two persistent systemd background units supporting the container network. Their unit definitions are version-controlled in the repository under `systemd/` and can be installed on any host using `sudo bash scripts/setup-host.sh`:

### 1. `rpi-tailscale-hairpin.service`
- **Tracked File:** `systemd/rpi-tailscale-hairpin.service` (installed to `/etc/systemd/system/`)
- **Purpose:** Automatically runs `/sbin/ip route replace 100.64.0.0/10 via 10.8.1.48` on boot.
- **Why it matters:** Pi-hole resolves `*.pi.rahulja.in` to the Tailscale IP `100.109.192.17`. Containers attempting to access other local services via HTTPS domain send packets to `100.109.192.17`. The hairpin route ensures the host kernel does a U-turn (hairpin) into Caddy (`10.8.1.48`) rather than routing them out the physical router where they would be dropped.

### 2. `rpi5-udp-gro.service`
- **Tracked File:** `systemd/rpi5-udp-gro.service` (installed to `/etc/systemd/system/`)
- **Purpose:** Enables UDP Generic Receive Offload (GRO) forwarding on physical network interfaces (`eth0` and `wlan0`):
  ```bash
  ethtool -K eth0 rx-udp-gro-forwarding on rx-gro-list off
  ```
- **Why it matters:** Maximizes wire-speed throughput for WireGuard and Tailscale VPN tunnels on ARM64 Linux.

---

## Reverse Proxy Architecture (Caddy)

Caddy terminates HTTPS for all homelab traffic using a single wildcard certificate:
- **Wildcard Certificate:** Provisions `CN=*.pi.rahulja.in` via Cloudflare DNS-01 challenge. Eliminates Let's Encrypt rate limits and multiple certificate renewals.
- **Security Headers:** Every web service route imports `(security_headers)` to enforce HSTS (1 year), MIME-type sniffing protection (`nosniff`), frame embedding restrictions (`SAMEORIGIN`), and header stripping (`-Server`).
- **Decommissioned Route Sink (HTTP 410):** Historical or dormant service blocks (`wg`, `watchtower`, `navidrome`, `plex`, `freshrss`, `grocy`, etc.) return immediate `HTTP/2 410 Gone`. This keeps routing blocks preserved in `Caddyfile` for easy resurrection while preventing 30-second TCP hanging connections.
- **Scale-to-Zero Coordination (Sablier):** Routes for lazy services use the `sablier` plugin middleware. If the backend container is stopped, Caddy triggers Sablier to boot the container, displays a loading screen (or blocks transparently up to 2m for heavy apps like Immich), and proxies traffic once healthy.

---

## Hardware Resource Governance (8GB Raspberry Pi 5)

To prevent Linux Out-Of-Memory (OOM) kernel lockups on the Raspberry Pi 5:
- **100% `mem_limit` Coverage:** Every service in `docker-compose.yml` has an explicit cgroup memory ceiling.
- **No Unbounded Memory:** Heavy stacks (Immich ML, Paperless Tika/Gotenberg, Transmission) are strictly bounded to prevent eating host OS page cache or killing `dockerd`.
- **Dynamic Headroom:** Core always-on services consume ~1.7GB RAM; Debian host OS consumes ~1.0GB RAM; leaving ~5.3GB RAM dynamic headroom for scale-to-zero application stacks when woken.

---

## Storage Architecture

Persistent data is partitioned strictly between fast NVMe SSD storage and bulk external USB storage:

### 1. NVMe SSD Storage (`/home/rahul/docker_data`)
Used for all databases, state directories, container configuration, and search indexes:
- Caddy certificate cache, Tailscale state, Pi-hole FTL database (`/home/rahul/docker/pihole-db`).
- PostgreSQL databases (`immich-database`, `paperless-db`, `ghostfolio-db`, `sure-db`, `miniflux_db`, `resume-db`).
- Valkey cache directories (`immich-redis`, `paperless-redis`, `firefly-redis`, etc.).
- Homepage configuration files (`/home/rahul/docker/gethomepage`).

### 2. Bulk USB Storage (`/mnt/usb`)
Formatted with `vfat` for bulk media and file storage:
- Immich upload and external photo libraries (`UPLOAD_LOCATION`, `EXTERNAL_LIBRARY_LOCATION`).
- Transmission torrent completed downloads.
- Personal file shares (`Dad`, `Rahul`, `music`).

---

## Stack Operations & Maintenance

All operations are executed from the repository root:

```bash
# Start core always-on stack
docker compose up -d

# Start lazy services on demand
docker compose --profile lazy up -d <service>

# Check service logs
docker compose logs -f <service>

# Run configuration audit script
./scripts/audit-config.sh

# Check for newer upstream image tags
python3 check_updates.py
```
