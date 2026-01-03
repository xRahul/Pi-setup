# Raspberry Pi Home Lab Setup

This repository contains the Docker Compose configuration for a comprehensive self-hosted home lab running on a Raspberry Pi (optimized for Pi 5). It uses **Caddy** as a reverse proxy with Cloudflare DNS validation, **WireGuard** (`wg-easy`) for internal networking, and **Tailscale** for remote access.

## 🚀 Overview

-   **Base OS:** Linux (Debian/Raspberry Pi OS)
-   **Orchestration:** Docker Compose
-   **Reverse Proxy:** Caddy (handling `*.pi.rahulja.in`)
-   **Networking:** Custom bridge network `wg-easy` (10.8.1.0/24)
-   **DNS:** Pi-hole & Cloudflared

## 🛠️ Prerequisites

-   Docker & Docker Compose
-   WireGuard kernel modules (usually included in modern kernels)
-   A domain name managed by Cloudflare (for API-based SSL challenges)

## 📦 Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/xRahul/Pi-setup.git
    cd Pi-setup
    ```

2.  **Configure Environment:**
    Copy the example environment file and edit it with your secrets.
    ```bash
    cp example.env .env
    nano .env
    ```
    *Ensure you fill in `CLOUDFLARE_API_TOKEN`, `TAILSCALE_AUTH_KEY`, and volume paths.*

3.  **Network Setup:**
    Ensure the `wg-easy` network subnet `10.8.1.0/24` does not conflict with your local network.

4.  **Start Services:**
    ```bash
    docker compose up -d
    ```

## 🖥️ Services & Static IPs

The project uses static IP assignments within the `10.8.1.x` range for internal stability and DNS resolution.

| Service | IP Address | Domain | Description |
| :--- | :--- | :--- | :--- |
| **Network Core** | | | |
| WireGuard (wg-easy) | `10.8.1.2` | `wg.pi.rahulja.in` | VPN Server |
| Pi-hole | `10.8.1.3` | `pihole.pi.rahulja.in` | DNS Ad-blocking |
| Cloudflared | `10.8.1.4` | `cloudflaredns.pi.rahulja.in` | DoH Proxy |
| Caddy | `Host/TS` | `*.pi.rahulja.in` | Reverse Proxy |
| Tailscale | `10.8.1.48` | - | Remote Access Mesh |
| **Media & Photos** | | | |
| Immich | `10.8.1.6` | `immich.pi.rahulja.in` | Photo Backup |
| Jellyfin | `10.8.1.16` | `jellyfin.pi.rahulja.in` | Media Server |
| Navidrome | `10.8.1.14` | `navidrome.pi.rahulja.in` | Music Server |
| Plex | `10.8.1.25` | `plex.pi.rahulja.in` | Media Server |
| **Productivity** | | | |
| N8n | `10.8.1.53` | `n8n.pi.rahulja.in` | Workflow Automation |
| Paperless-ngx | `10.8.1.32` | `pngx.pi.rahulja.in` | Document Management |
| Filebrowser | `10.8.1.34` | `filebrowser.pi.rahulja.in` | Web File Manager |
| Homarr | `10.8.1.35` | `homarr.pi.rahulja.in` | Dashboard |
| OpenProject | `10.8.1.50` | `openproject.pi.rahulja.in` | Project Management |
| Vikunja | `10.8.1.46` | `vikunja.pi.rahulja.in` | Todo List |
| Firefly III | `10.8.1.43` | `firefly.pi.rahulja.in` | Finance Manager |
| **Tools** | | | |
| Watchtower | `10.8.1.13` | `watchtower.pi.rahulja.in` | Auto-updater |
| Prometheus | `10.8.1.19` | `prometheus.pi.rahulja.in` | Metrics |
| Grafana | `10.8.1.20` | `grafana.pi.rahulja.in` | Monitoring Dashboard |
| Transmission | `10.8.1.23` | `trans.pi.rahulja.in` | Torrent Client |

*(See `docker-compose.yml` and `Caddyfile` for the complete list of 40+ services)*

## 📂 Volume Management

Most data is persisted in `/mnt/usb/`, mapped via environment variables in `.env`. Ensure your external drive is mounted correctly before starting the stack.

## 📝 Configuration Notes

-   **N8n:** Concurrency limit set to `2` to prevent OOM on Pi.
-   **Caddy:** Uses Cloudflare DNS challenge for automatic HTTPS.
-   **Logs:** System logs are optimized for flash storage (see project context).