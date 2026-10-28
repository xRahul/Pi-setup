# Repo Architecture Notes

This repo is a Docker Compose based Raspberry Pi / homelab stack. The main runtime definition is `docker-compose.yml`; local paths, credentials, versions, and dashboard API variables come from `.env`.

Do not paste secret values from `.env` into docs or chat. Refer to variable names only.

## Key Files

- `docker-compose.yml`: primary stack definition.
- `.env`: real local configuration and secrets.
- `example.env`: template for the main environment file.
- `pihole.env`: Pi-hole local DNS host mapping via `FTLCONF_dns_hosts`.
- `Caddyfile`: HTTPS reverse proxy config for `*.pi.rahulja.in`.
- `caddy.Dockerfile`: custom Caddy image build.
- `homepage_setup_instructions.md`: notes for enabling Homepage widgets.
- `/home/rahul/docker_data/gethomepage`: live GetHomepage config mounted into the Homepage container.

## Compose Layout

The stack has about 45 services. Most state is stored with bind mounts, not named Docker volumes. There are currently no named Compose volumes.

Important networks:

- `wg-easy`: bridge network named `wg-easy`, subnet `10.8.1.0/24`. Most proxied services use fixed `10.8.1.x` addresses here.
- `read-proxy-net`: internal bridge network for read-only Docker socket proxy access.
- `portainer-proxy-net`: internal bridge network for Portainer/admin socket access.

Core/default services include:

- `tailscale`
- `pihole`
- `dnscrypt-proxy`
- `caddy`
- `transmission`
- `sablier`
- `socket-proxy-read`

Many user apps are marked with the Compose profile `lazy`, including Homepage, Filebrowser, Immich, Firefly, Portainer, Stirling PDF, Memos, Miniflux, ntfy, Reactive Resume, Paperless, Gramps, and CyberChef.

## Persistent Data

Most persistent paths are configured in `.env`.

Common roots:

- `/home/rahul/docker_data`: app data, databases, caches, and configs.
- `/mnt/usb`: larger media/file storage.
- `/home/rahul/docker`: repo-local config files for selected apps.

Examples:

- Caddy data/config: `CADDY_SITE_PATH`, `CADDY_DATA_PATH`, `CADDY_CONFIG_PATH`.
- Pi-hole data: `PIHOLE_ETC_PATH`, `PIHOLE_ETC_DNSMASQ_PATH`.
- Homepage config: `HOMEPAGE_CONFIG_PATH`.
- Immich: `UPLOAD_LOCATION`, `IMMICH_DB_DATA_LOCATION`, `IMMICH_ML_MODEL_CACHE_LOCATION`, `IMMICH_REDIS_DATA_PATH`, `EXTERNAL_LIBRARY_LOCATION`.
- Paperless: `PAPERLESS_NGX_*`, `PAPERLESS_DB_*`, `PAPERLESS_REDIS_DATA_PATH`.
- Filebrowser: `FILEBROWSER_ROOT_PATH`, `FILEBROWSER_DB_FILE_PATH`, `FILEBROWSER_CONFIG_SETTING_FILE_PATH`.
- Jellyfin: `JELLYFIN_*`.

## Caddy

Caddy is the public HTTPS reverse proxy. It is built from `caddy.Dockerfile`, mounts `Caddyfile` read-only, and uses Cloudflare DNS challenge via `CLOUDFLARE_API_TOKEN`.

Most routes point `*.pi.rahulja.in` hostnames to fixed `10.8.1.x` service IPs on the `wg-easy` network. Some routes use Sablier so Caddy can trigger lazy services and show/block while containers start.

Example route pattern:

- `dash.pi.rahulja.in` proxies to Homepage at `10.8.1.57:3000`.
- `immich.pi.rahulja.in` proxies to Immich at `10.8.1.6:2283`.
- `pngx.pi.rahulja.in` proxies to Paperless at `10.8.1.32:8000`.
- `pihole.pi.rahulja.in` proxies to Pi-hole on Caddy's local network path.

When adding or changing a service, keep the Compose static IP, Caddy upstream, Pi-hole local DNS entry, and Homepage dashboard entry aligned.

## Homepage / GetHomepage

The Homepage service uses:

- image: `ghcr.io/gethomepage/homepage:v2.7.0`
- status: Core service (runs continuously; not scale-to-zero)
- networks: `wg-easy` and `read-proxy-net`
- fixed IP: `10.8.1.57`
- config mount: `${HOMEPAGE_CONFIG_PATH}:/app/config` (points to `./gethomepage`)
- host mounts for stats: `/proc`, `/sys`, `/`, and `/mnt/usb`
- read-only Docker access through `socket-proxy-read`

Resolved live config path:

```text
/home/rahul/docker/gethomepage
```

Known config files there:

- `settings.yaml`
- `services.yaml`
- `widgets.yaml`
- `bookmarks.yaml`
- `docker.yaml`
- `kubernetes.yaml`
- `proxmox.yaml`
- `custom.css`
- `custom.js`

`services.yaml` is grouped roughly into:

- `Productivity`: Paperless, Filebrowser, Stirling PDF, CyberChef, Memos, Firefly, Miniflux, ArchiveBox, Reactive Resume, Gramps.
- `Media`: Immich, Immich ML, Transmission, Jellyfin.
- `System`: Pi-hole, Tailscale, DNSCrypt, Caddy, and related infrastructure.

Homepage widget credentials come from `.env` as `HOMEPAGE_VAR_*` variables. Keep real values in `.env`; dashboard YAML can reference the variables.

## Environment Files

`.env` is the central source for:

- time zone
- Tailscale auth/state
- Cloudflare DNS API token
- app data paths
- database usernames/passwords
- service secrets
- Homepage widget API keys
- selected app versions

`pihole.env` separately stores Pi-hole local DNS host mappings via `FTLCONF_dns_hosts`.

`example.env`, `example_pihole.env`, and `example_immich.env` are templates/samples and should not be treated as active runtime files unless Compose references them.

## Operational Pattern

Use Compose from the repo root.

Typical operations:

```bash
docker compose up -d
docker compose --profile lazy up -d <service>
docker compose restart <service>
docker compose logs -f <service>
```

After changing Caddy config, reload/restart Caddy. After changing Homepage config, restart Homepage.

When adding a new exposed app, update these together:

1. `docker-compose.yml` service, network, static IP, mounts, env.
2. `.env` path/secret variables.
3. `Caddyfile` hostname and upstream.
4. `pihole.env` local DNS mapping if needed.
5. Homepage `services.yaml` entry and optional widget variables.
