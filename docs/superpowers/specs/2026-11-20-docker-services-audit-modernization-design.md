# Docker Services Comprehensive Audit, Modernization & Hardening Design

**Date:** 2026-11-20  
**Scope:** In-place audit, modernization, image upgrades, volume permission fixes, and hardening across all 54 Docker services.  
**Platform:** Raspberry Pi 5 (8GB RAM, Debian Trixie, NVMe SSD boot + `/mnt/usb` external storage).

---

## 1. Intent and Why
The homelab currently operates 54 containerized services managed via Docker Compose, isolated on the `10.8.1.0/24` bridge subnet, with reverse proxying via Caddy (`*.pi.rahulja.in`) and scale-to-zero lifecycle control via Sablier (`profiles: ["lazy"]`). While all services have defined memory limits and healthchecks, the stack has accumulated:
- Pending upstream image upgrades with critical architectural migrations (e.g., Stirling-PDF v3, Reactive Resume v6, Sablier v1.21, Ghostfolio v3.100, Memos CalVer 26.x).
- Host volume permission discrepancies (e.g., `n8n/files` owned by `root:root` preventing writes by non-root UID 1000).
- Dashboard observation gaps in Homepage (`services.yaml`) where newly introduced services (`n8n`, `burnrate`, `firefox`) lack cards or widgets.
- Database/cache lifecycle boundaries (6 Postgres, 6 Valkey instances) requiring strict backup and sequence handling during version bumps.

The goal is to harden, upgrade, and optimize all 54 services in place without disrupting service isolation or breaking data schemas.

---

## 2. Goals, Non-Goals, and Anti-Goals

### Goals
1. **In-Place Modernization:** Upgrade image tags to verified, stable versions while honoring breaking change requirements and deprecation paths.
2. **Security & Permission Hardening:** Fix host volume ownerships to ensure non-root containers (UID 1000, 999) have correct read/write permissions.
3. **Database Migration Safety:** Pre-upgrade snapshot/backup verification for all 6 PostgreSQL instances (`paperless-db`, `immich-database`, `miniflux_db`, `resume-db`, `sure-db`, `ghostfolio-db`).
4. **Dashboard Synchronization:** Add missing service cards and health/widget monitors to Homepage `services.yaml` (`n8n`, `burnrate`, `firefox`, `ghostfolio-db`, `ghostfolio-valkey`).
5. **Configuration Alignment:** Synchronize `.env` with `example.env`, strip deprecated variables, and document required new environment variables (such as `TRUSTED_PROXIES` for Reactive Resume v6).

### Non-Goals
- **Stack Consolidation / Retirement:** The user explicitly selected in-place modernization, keeping all 54 services isolated. We will NOT deprecate or prune overlapping finance applications (`actual`, `firefly`, `ezbookkeeping`, `ghostfolio`, `sure`, `burnrate`).
- **Database Merging:** We will NOT consolidate separate Postgres or Valkey instances into a shared cluster, preserving individual Sablier group lifecycle isolation (starting/stopping instances only with their parent service).
- **Network Architecture Overhaul:** Retain the unified Tailscale/Caddy/Pi-hole network namespace (`10.8.1.48`) and bridge subnet (`10.8.1.0/24`).

### Anti-Goals
- Never use mutable or floating tags (`latest`, `main`, `stable`) in `docker-compose.yml`.
- Never execute upgrades on database-backed services without verifiable schema migration pathways.
- Never grant unnecessary root permissions or Docker socket mounts to client containers.

---

## 3. Constraints
- **Hardware Limitations:** 8GB total RAM on Raspberry Pi 5. Peak memory during upgrades must be guarded against OOM panics.
- **Storage Segregation:** NVMe SSD (`/home/rahul/docker_data`) for high-IOPS databases, logs, and container configs; `/mnt/usb` (vfat) strictly for media libraries and bulk downloads.
- **Scale-to-Zero Coordination:** 46 services belong to `profiles: ["lazy"]` and Sablier groups. Any container recreation requires restarting `sablier` to clear cached container IDs.

---

## 4. Approaches Considered

### Approach 1: Domain-Clustered Batched Audit & Phased Hardening (Selected)
Group all 54 services into 6 functional clusters:
1. Core Gateway, DNS & Network
2. Media, Storage & Sync
3. Personal Knowledge & Productivity
4. Developer, Automation & Terminals
5. Personal Finance Platforms
6. Dashboard & Observability

Audit local configurations, volumes, and env bindings per cluster; conduct online research on upstream breaking migrations; execute phased, validated changes per cluster.
- **Pros:** Prevents OOM spikes, isolates failure domains, provides safe DB migration checkpoints.
- **Cons:** Requires phased execution.

### Approach 2: Monolithic Flat Upgrade
Bump all 54 tags and volume edits in one sweeping diff across `docker-compose.yml`.
- **Pros:** Single-step diff.
- **Cons:** High blast radius; high risk of silent failure on complex DB schemas (Immich, Paperless, Reactive Resume). Ruled out.

### Approach 3: Tag-Only Bump
Bump image tags without inspecting volume permissions, env deprecations, or upstream migration guides.
- **Pros:** Fast.
- **Cons:** Will cause runtime crashes (e.g., Stirling-PDF v3 removed envs, Reactive Resume v6 proxy crashes, n8n permission errors). Ruled out.

**Decision:** The user selected **Approach 1**.

---

## 5. Domain Cluster Audit & Modernization Details

### Cluster 1: Core Gateway, DNS & Network
- **Services:** `tailscale`, `pihole`, `dnscrypt-proxy`, `caddy`, `sablier`, `socket-proxy-read`, `socket-proxy-admin`.
- **Key Audit Findings & Modernization Actions:**
  - `sablier`: Upgrade from `1.18.0` to `1.21.0`. Provides eBPF traffic-based session refresh and resolves container rename bugs (`#1142`) during recreation.
  - `pihole`: Current `2026.09.0` -> bump to `2026.11.0`.
  - `tailscale`: Keep pinned on stable minor `v1.104.2` (unstable dev builds should be avoided).
  - `caddy`: Built via `caddy.Dockerfile` (builder `caddy:2.10.2-builder` with `github.com/caddy-dns/cloudflare`). Rebuild to ensure latest base patch.
  - Permissions: All core directories under `/home/rahul/docker_data/{tailscale,pihole,caddy}` exist with correct permissions.

### Cluster 2: Media, Storage & Sync
- **Services:** `immich-server`, `immich-machine-learning`, `immich-database`, `immich-redis`, `jellyfin`, `transmission`, `filebrowser`.
- **Key Audit Findings & Modernization Actions:**
  - `immich`: Currently pinned to `v3.3.5`. Keep minor version tag pinned. DB uses VectorChord (`ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0`). Ensure Sablier group `immich` coordinates clean startup.
  - `jellyfin`: Running on `network_mode: host` to preserve DLNA multicast SSDP broadcasts. Reverse proxy targets host bridge `10.8.1.1:8096`. Retain.
  - `transmission`: `lscr.io/linuxserver/transmission:4.1.3-r0-ls362`. Host volume permissions on `/home/rahul/docker_data/transmission` verified `rahul:rahul 775`.
  - `filebrowser`: Up to date at `v2.63.23`. Bind mounts to `/mnt/usb` and `/home/rahul/projects` verified.

### Cluster 3: Personal Knowledge & Productivity
- **Services:** `paperless-ngx`, `paperless-db`, `paperless-redis`, `paperless-tika`, `paperless-gotenberg`, `stirling-pdf`, `memos`, `miniflux`, `miniflux_db`, `miniflux-cron`, `archivebox`, `resume`, `resume-db`, `grampsweb`, `grampsweb_celery`, `gramps-redis`, `drawio`, `cyberchef`.
- **Key Audit Findings & Modernization Actions:**
  - `stirling-pdf`: Upgrade from `2.14.3-ultra-lite` to `3.4.0-ultra-lite`. Remove deprecated legacy envs if present; ensure persistent volume maps configs.
  - `resume`: Upgrade from `v5.3.2` to `v6.1.1`.
    - **Breaking Migration:** Database table schema changes consolidated in v6 release migration.
    - **Env requirement:** Add `TRUSTED_PROXIES=10.8.1.48` in environment so Reactive Resume respects Caddy reverse proxy headers.
  - `memos`: Upgrade from `0.31.0` to CalVer `26.11.1`.
  - `drawio`: Upgrade from `31.7.0` to `32.7.4`.
  - `paperless-ngx`: Stack currently pinned to `3.5.1` with `tika:3.3.3.1` and `gotenberg:8.40.0`. Safe and stable.

### Cluster 4: Developer, Automation & Terminals
- **Services:** `n8n`, `n8n-runners`, `opencode`, `antigravity`, `firefox`, `portainer`, `ntfy`.
- **Key Audit Findings & Modernization Actions:**
  - `n8n` / `n8n-runners`: Upgrade from `2.40.3` to `2.49.3`.
  - **Volume Permission Fix:** Host directory `/home/rahul/docker_data/n8n/files` is owned by `root:root 755`. Fix to `rahul:rahul 775` (UID 1000) so n8n can write binary attachments.
  - `portainer`: Upgrade from `2.45.3` to `2.45.4-alpine`.
  - `ntfy`: Upgrade from `v2.34.0` to `v2.38.1`.
  - `firefox` & `antigravity`: Verified. Ensure Homepage entries exist.

### Cluster 5: Personal Finance Platforms
- **Services:** `actual`, `firefly`, `firefly-importer`, `firefly-cron`, `firefly-redis`, `ghostfolio`, `ghostfolio-db`, `ghostfolio-valkey`, `ezbookkeeping`, `sure`, `sure-db`, `sure-redis`, `sure-worker`, `burnrate`.
- **Key Audit Findings & Modernization Actions:**
  - `ghostfolio`: Upgrade from `3.93.0` to `3.100.0`. Safe minor update; run database migration within Sablier group.
  - `firefly`: Upgrade from `version-6.7.2` to `version-6.7.9`; `firefly-importer` from `version-2.3.4` to `version-2.3.5`.
  - `burnrate`: Upgrade from `v0.4.0` to `v0.5.2`.
  - `actual`: Upgrade `actualbudget/actual-server` to latest stable release tag.

### Cluster 6: Dashboard & Observability
- **Services:** `homepage`.
- **Key Audit Findings & Modernization Actions:**
  - Update `/home/rahul/docker_data/gethomepage/services.yaml` to include:
    - `n8n` card (URL `https://n8n.pi.rahulja.in`, siteMonitor `http://10.8.1.53:5678/healthz`).
    - `burnrate` card (URL `https://burnrate.pi.rahulja.in`, siteMonitor `http://10.8.1.69:8000`).
    - `firefox` card (URL `https://firefox.pi.rahulja.in`, siteMonitor `http://10.8.1.22:8080`).
    - System monitors for `ghostfolio-db` and `ghostfolio-valkey`.

---

## 6. What's Left to the Builder
- Precise execution order of container stops, data backups, Compose file editing, and container recreation.
- Generation of backup archives before PostgreSQL and SQLite image updates.
- Execution of verification tests (Caddyfile validation, docker compose config validation, container healthchecks).
- Updating `example.env` and documentation to reflect new parameters (`TRUSTED_PROXIES`, updated tags).
