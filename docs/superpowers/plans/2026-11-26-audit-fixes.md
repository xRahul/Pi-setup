# Audit fixes plan (2026-11-26)

Source: read-only audit of `rahul@192.168.1.24:~/docker` on 2026-11-26.

## Decisions
- Tailscale key expiry for `pi-docker-ts`: disabled by user (2026-11-26).
- Backups (dump script, restic, HDD sync, notify helper): **out of scope** per user. See "Open issue" below.
- sshd: unchanged. Password login stays enabled by choice.
- Health alerts, offsite backup, subnet route grants: not wanted.
- Leftover removal: deferred (see list).
- Renovate GitHub App already active; tune it with `renovate.json` instead of adding a new tool.

## Open issue (found during execution)
`/mnt/usb` (SANDISK256 pendrive) contains only empty folder skeletons (5 MB used).
`~/ehdd.txt` says ~220 GB (data, immich/upload, Dad, Rahul, music) lived there.
Immich still mounts `/mnt/usb/immich/upload` and `/mnt/usb/data`, and its DB (1.2 GB) still lists assets.
The external HDD (`/mnt/ehdd/RPI5`) may hold the only copy. Do not run mirror syncs from
`/mnt/usb` to the HDD, and do not open Immich or start Syncthing until this is resolved.

## Tasks
- [ ] 1. Plan file, `pre-audit-2026-11-26` tag, baseline output in `/var/backups/homelab-baseline/`.
- [ ] 6. Secrets: remove `env_file: .env` from immich-server and immich-machine-learning;
      mask `.env`, `pihole.env`, `*.bak-*` and `secrets/` inside antigravity.
- [ ] 7. Apps: Sure `ONBOARDING_STATE=closed`; Pi-hole NTP off and drop `SYS_TIME`;
      firefly-cron uses `http://firefly:8080`; remove duplicate immich-ML label;
      socket-proxy-read timeout for Sablier EOF (if supported). Manual: memos/ghostfolio signup.
- [ ] 8. Host: unattended-upgrades (security only, no auto reboot); `chmod 600 pihole.env`;
      fix mode-777 dirs only if in use. No sshd or ufw changes.
- [ ] 9. Prune: `docker image prune -af --filter until=168h` + `docker builder prune`; units in `systemd/`.
- [ ] 10. Renovate: `renovate.json` (dashboard, grouping, major approval, postgres majors off,
      linuxserver regex versioning); triage open PRs #110-#119.
- [ ] 11. Docs: README security model and deploy steps; audit-config.sh fails on `env_file: .env`.

## Accepted risks
- Subnet route `10.8.1.0/24` exposes DBs, Valkey and the Sablier API to tailnet devices.
- `socket-proxy-read` needs `POST=1` (Docker wait call has no `ALLOW_*` flag).
- SSH password auth enabled; fail2ban running.

## Deferred
sshd hardening; health alerts; offsite and all backup work; subnet grants; unused `.env` keys
(HOMARR, SEARXNG, STORYTELLER, PAISA); dirs `searxng/`, `storytellerdb/`, `prometheus/`,
`__pycache__/`; `sonic.Dockerfile`; `.env.bak-*` and `docker-compose.yml.bak-*`;
`netns-proof_default` network; dangling volumes; ufw rules 80/443/8384/22000/21027.
