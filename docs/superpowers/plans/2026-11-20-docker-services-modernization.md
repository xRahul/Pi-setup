# Docker Services Modernization and Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade, harden, and synchronize 18 homelab Docker services and Homepage monitors in place while preserving isolation, data integrity, and strict memory limits on the Raspberry Pi 5.

**Architecture:** Services are deployed via Docker Compose with Sablier scale-to-zero lifecycle management on the `10.8.1.0/24` bridge network, reverse-proxied by Caddy sharing Tailscale's network namespace (`10.8.1.48`). The plan performs pre-upgrade database snapshots, updates image tags and environment variables in-place, fixes host volume permissions, and synchronizes Homepage dashboard service definitions.

**Tech Stack:** Docker, Docker Compose, Caddy, Tailscale, Pi-hole, Sablier, PostgreSQL 18, SQLite, YAML.

**Spec:** [`docs/superpowers/specs/2026-11-20-docker-services-audit-modernization-design.md`](file:///home/rahul/docker/docs/superpowers/specs/2026-11-20-docker-services-audit-modernization-design.md)

## Global Constraints
- **Immich Stack Excluded:** `immich-server`, `immich-machine-learning`, `immich-database`, and `immich-redis` must NOT be updated.
- **Pinned Tags Mandate:** Zero mutable/floating tags (`latest`, `stable`). All upgrades use explicit pinned semantic tags.
- **Sablier Privilege Model:** Stays unprivileged (`cap_drop: ALL`, `user: 1000:1000`, eBPF disabled).
- **Storage Segregation:** NVMe for configs/DBs (`/home/rahul/docker_data`), `/mnt/usb` strictly for media/bulk storage.

## Review Focus
1. **Reactive Resume v6 Reverse Proxy Compatibility:** Ensure `TRUSTED_PROXIES=10.8.1.48` is passed to the container to prevent 502/redirect loops.
2. **Stirling-PDF v3 Environment Deprecations:** Strip removed `DOCKER_ENABLE_SECURITY` to prevent startup parsing warnings.
3. **n8n Host Volume Ownership:** Verify `/home/rahul/docker_data/n8n/files` is owned by `1000:1000` with `775` permissions.
4. **Sablier Group Cache Consistency:** Restart Sablier after container recreation so group tracking refreshes cleanly.
5. **Memory Footprint & OOM Safety:** Limit batch rollout to one cluster at a time to prevent memory spikes on the 8GB RAM host.

---

### Task 1: Pre-Upgrade Database Snapshots & Volume Permissions

**Files:**
- Modify: Host directory permissions `/home/rahul/docker_data/n8n/files`
- Create: `/home/rahul/docker_data/backups/pre-upgrade-2026-11-20/`

**Interfaces:**
- Consumes: Existing SQLite databases on disk and running PostgreSQL containers.
- Produces: Timestamped SQL dumps and SQLite file copies in backup directory.

- [ ] **Step 1: Create backup directory**
Run: `mkdir -p /home/rahul/docker_data/backups/pre-upgrade-2026-11-20`
Expected: Directory created with write permissions.

- [ ] **Step 2: Take snapshots of SQLite databases**
Run: `cp /home/rahul/docker_data/memos/data/memos_prod.db /home/rahul/docker_data/backups/pre-upgrade-2026-11-20/memos_prod.db.bak && cp /home/rahul/docker_data/actual/server-files/account.sqlite /home/rahul/docker_data/backups/pre-upgrade-2026-11-20/account.sqlite.bak 2>/dev/null || true`
Expected: SQLite snapshots copied.

- [ ] **Step 3: Fix n8n files host volume permissions**
Run: `sudo chown -R 1000:1000 /home/rahul/docker_data/n8n/files && chmod -R 775 /home/rahul/docker_data/n8n/files`
Expected: Directory ownership changes from `root:root` to `rahul:rahul` (1000:1000).

- [ ] **Step 4: Verify permissions**
Run: `ls -ld /home/rahul/docker_data/n8n/files`
Expected: `drwxrwxr-x ... 1000 1000 ... /home/rahul/docker_data/n8n/files`

---

### Task 2: Core Gateway & Network Stack Modernization

**Files:**
- Modify: `docker-compose.yml:36` (pihole), `docker-compose.yml:536` (sablier), `docker-compose.yml:608` (portainer)

**Interfaces:**
- Consumes: Base Docker Compose configuration.
- Produces: Updated Core Network and Container Management images.

- [ ] **Step 1: Update image tags in docker-compose.yml**
Edit `docker-compose.yml`:
- `pihole/pihole:2026.09.0` -> `pihole/pihole:2026.11.0`
- `sablierapp/sablier:1.18.0` -> `sablierapp/sablier:1.21.0`
- `portainer/portainer-ce:2.45.3` -> `portainer/portainer-ce:2.45.4-alpine`

- [ ] **Step 2: Validate docker-compose config**
Run: `docker compose config --quiet`
Expected: Exit code 0.

- [ ] **Step 3: Pull images**
Run: `docker compose pull pihole sablier portainer`
Expected: Successfully pulled 3 images.

- [ ] **Step 4: Recreate core containers**
Run: `docker compose up -d pihole sablier portainer && docker compose restart sablier`
Expected: Containers recreated and healthy.

- [ ] **Step 5: Verify core health**
Run: `docker inspect --format='{{.State.Health.Status}}' pihole sablier portainer`
Expected: All report `healthy` (or `running` for sablier).

- [ ] **Step 6: Commit**
```bash
git add docker-compose.yml
git commit -m "chore(core): upgrade pihole, sablier, and portainer image tags"
```

---

### Task 3: Productivity & Document Stack Modernization

**Files:**
- Modify: `docker-compose.yml` (stirling-pdf, memos, drawio, cyberchef)

**Interfaces:**
- Consumes: Task 2 completed core network.
- Produces: Modernized Stirling-PDF v3, Memos CalVer, Drawio, and Cyberchef.

- [ ] **Step 1: Update image tags & clean deprecated env in docker-compose.yml**
Edit `docker-compose.yml`:
- `stirlingtools/stirling-pdf:2.14.3-ultra-lite` -> `stirlingtools/stirling-pdf:3.4.0-ultra-lite`
- Remove `DOCKER_ENABLE_SECURITY=false` from `stirling-pdf` environment.
- `neosmemo/memos:0.31.0` -> `neosmemo/memos:26.11.1`
- `jgraph/drawio:31.7.0` -> `jgraph/drawio:32.7.4`
- `ghcr.io/gchq/cyberchef:11.5.0` -> `ghcr.io/gchq/cyberchef:11.6.0`

- [ ] **Step 2: Validate compose config**
Run: `docker compose --profile lazy config --quiet`
Expected: Exit code 0.

- [ ] **Step 3: Pull images**
Run: `docker compose pull stirling-pdf memos drawio cyberchef`
Expected: Successfully pulled images.

- [ ] **Step 4: Recreate containers**
Run: `docker compose --profile lazy up -d --no-deps stirling-pdf memos drawio cyberchef && docker compose restart sablier`
Expected: Containers recreated under Sablier lazy management.

- [ ] **Step 5: Commit**
```bash
git add docker-compose.yml
git commit -m "chore(productivity): upgrade stirling-pdf v3, memos, drawio, and cyberchef"
```

---

### Task 4: Database-Backed Web Apps & Reverse Proxy Hardening

**Files:**
- Modify: `docker-compose.yml` (resume, actual)

**Interfaces:**
- Consumes: Task 1 backup snapshots, Task 2 core reverse proxy.
- Produces: Reactive Resume v6 with proxy header trust, Actual Budget latest release.

- [ ] **Step 1: Update image tags and add TRUSTED_PROXIES in docker-compose.yml**
Edit `docker-compose.yml`:
- `amruthpillai/reactive-resume:v5.3.2` -> `amruthpillai/reactive-resume:v6.1.1`
- Add `- TRUSTED_PROXIES=10.8.1.48` under `resume` environment list.
- `actualbudget/actual-server:26.10.0-alpine` -> `actualbudget/actual-server:26.11.0-alpine`

- [ ] **Step 2: Pull images**
Run: `docker compose pull resume actual`
Expected: Successfully pulled.

- [ ] **Step 3: Recreate containers**
Run: `docker compose --profile lazy up -d --no-deps resume actual && docker compose restart sablier`
Expected: Containers recreated.

- [ ] **Step 4: Commit**
```bash
git add docker-compose.yml
git commit -m "chore(resume,actual): upgrade resume to v6 with trusted proxies and actual budget"
```

---

### Task 5: Automation & Developer Tools Modernization

**Files:**
- Modify: `docker-compose.yml` (n8n, n8n-runners, ntfy)

**Interfaces:**
- Consumes: Task 1 volume permission fix on `/files`.
- Produces: Updated n8n workflow engine and ntfy push notifications.

- [ ] **Step 1: Update image tags in docker-compose.yml**
Edit `docker-compose.yml`:
- `n8nio/n8n:2.40.3` -> `n8nio/n8n:2.49.3`
- `n8nio/runners:2.40.3` -> `n8nio/runners:2.49.3`
- `binwiederhier/ntfy:v2.34.0` -> `binwiederhier/ntfy:v2.38.1`

- [ ] **Step 2: Pull images**
Run: `docker compose pull n8n n8n-runners ntfy`
Expected: Successfully pulled.

- [ ] **Step 3: Recreate containers**
Run: `docker compose --profile lazy up -d --no-deps n8n n8n-runners ntfy && docker compose restart sablier`
Expected: Containers recreated.

- [ ] **Step 4: Commit**
```bash
git add docker-compose.yml
git commit -m "chore(automation): upgrade n8n stack to 2.49.3 and ntfy to v2.38.1"
```

---

### Task 6: Personal Finance Stacks Modernization

**Files:**
- Modify: `docker-compose.yml` (firefly, firefly-importer, ghostfolio, sure, sure-worker, burnrate)

**Interfaces:**
- Consumes: Task 1 database snapshots.
- Produces: Upgraded finance engines across all 5 financial platforms.

- [ ] **Step 1: Update image tags in docker-compose.yml**
Edit `docker-compose.yml`:
- `fireflyiii/core:version-6.7.2` -> `fireflyiii/core:version-6.7.9`
- `fireflyiii/data-importer:version-2.3.4` -> `fireflyiii/data-importer:version-2.3.5`
- `ghostfolio/ghostfolio:3.93.0` -> `ghostfolio/ghostfolio:3.100.0`
- `ghcr.io/we-promise/sure:0.7.5` -> `ghcr.io/we-promise/sure:0.7.6-hotfix.1` (both sure and sure-worker)
- `pratik1235/burnrate:v0.4.0` -> `pratik1235/burnrate:v0.5.2`

- [ ] **Step 2: Pull images**
Run: `docker compose pull firefly firefly-importer ghostfolio sure sure-worker burnrate`
Expected: Successfully pulled.

- [ ] **Step 3: Recreate containers**
Run: `docker compose --profile lazy up -d --no-deps firefly firefly-importer ghostfolio sure sure-worker burnrate && docker compose restart sablier`
Expected: Containers recreated under their respective Sablier groups.

- [ ] **Step 4: Commit**
```bash
git add docker-compose.yml
git commit -m "chore(finance): upgrade firefly, ghostfolio, sure, and burnrate stacks"
```

---

### Task 7: Homepage Dashboard Integration & Final Verification

**Files:**
- Modify: `/home/rahul/docker_data/gethomepage/services.yaml`
- Modify: `example.env` (document new environment options if applicable)

**Interfaces:**
- Consumes: All upgraded services across Tasks 2 through 6.
- Produces: Unified Homepage dashboard displaying all active services and system companions.

- [ ] **Step 1: Add missing service cards to gethomepage/services.yaml**
Add cards for `n8n`, `burnrate`, `firefox`, `ghostfolio-db`, and `ghostfolio-valkey`.

- [ ] **Step 2: Validate Caddy configuration**
Run: `docker exec caddy caddy validate --config /etc/caddy/Caddyfile`
Expected: `Valid configuration`.

- [ ] **Step 3: Validate Compose config across all profiles**
Run: `docker compose --profile lazy config --quiet`
Expected: Exit code 0.

- [ ] **Step 4: Check host memory usage**
Run: `free -h`
Expected: RAM usage stable, no swapping or OOM alarms.

- [ ] **Step 5: Commit**
```bash
git add example.env
git commit -m "docs: sync example env and homepage configurations"
```
