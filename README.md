# Raspberry Pi Home Lab (Docker)

This repository contains the Docker Compose configuration for a comprehensive home lab setup running on a Raspberry Pi (optimized for Pi 5). It integrates various self-hosted services using a custom bridge network and Tailscale for secure remote access.

## 🚀 Overview

The stack is designed to be efficient and secure, utilizing **Caddy** as a reverse proxy with Cloudflare DNS validation for automatic SSL certificates. A specific subnet (`10.8.1.0/24`) is used to assign static IPs to containers, facilitating easy internal DNS resolution via Pi-hole.

### Core Infrastructure
- **Caddy:** Reverse proxy handling `*.pi.rahulja.in` domains.
- **Tailscale:** VPN and subnet router for secure remote access.
- **Pi-hole:** Network-wide ad blocking and local DNS.
- **DNSCrypt-Proxy:** Provides encrypted upstream DNS for Pi-hole.

## 📐 Architecture

The following diagram illustrates the **Unified Network Core** architecture. Services like Caddy, Pi-hole, and DNSCrypt-Proxy share the **Tailscale network namespace**, allowing them to operate as a single logical gateway at `10.8.1.48`.

```mermaid
graph TD
    %% --- External ---
    User((Remote User))
    CF_DNS[Cloudflare / Upstream DNS]

    subgraph TS_Mesh ["Tailscale Mesh (VPN)"]
        TS_Interface["Tailscale Interface<br/>(100.x.y.z)"]
    end

    %% --- The Server ---
    subgraph RPi ["Raspberry Pi 5"]
        
        subgraph Unified_Core ["Unified Network Core (IP: 10.8.1.48)"]
            direction TB
            TS_Client[Tailscale Container]
            Caddy[Caddy Reverse Proxy]
            Pihole[Pi-hole DNS]
            DNSCrypt[DNSCrypt-Proxy]
            
            %% Internal Core Links
            TS_Client <--> Caddy
            Caddy <--> Pihole
            Pihole ---|localhost#5053| DNSCrypt
        end

        subgraph Bridge_Net ["wg-easy Bridge (10.8.1.0/24)"]
            direction LR
            Apps["App Containers<br/>(Immich, n8n, etc.)"]
            Storage[("/mnt/usb")]
        end
    end

    %% --- Traffic Flows ---
    
    %% Flow 1: External Access
    User ==>|Secure Tunnel| TS_Mesh
    TS_Mesh ==> TS_Interface
    TS_Interface ==>|Port 80/443| Caddy
    Caddy ==>|Reverse Proxy| Apps

    %% Flow 2: Internal DNS
    Apps -.->|DNS Query| Pihole
    Pihole -.->|Upstream| DNSCrypt
    DNSCrypt -.->|DoH / DNSCrypt| CF_DNS
    
    %% Flow 3: Storage
    Apps --- Storage
    
    %% Styling
    style Unified_Core fill:#f0f7ff,stroke:#005cc5,stroke-width:2px
    style TS_Client fill:#fff,stroke:#333
    style Caddy fill:#fff,stroke:#333
    style Pihole fill:#fff,stroke:#333
    style DNSCrypt fill:#fff,stroke:#333
    style Bridge_Net fill:#f6ffed,stroke:#52c41a
```

## 🛠️ Services & IP Assignments

The following services are configured with static IPs in the `10.8.1.0/24` subnet:

| Service | Internal IP | External URL (Example) | Description |
| :--- | :--- | :--- | :--- |
| **Pi-hole** | `10.8.1.48` | `pihole.pi.rahulja.in` | DNS Sinkhole & Ad Blocker |
| **DNSCrypt-Proxy** | `10.8.1.48` | `dnscrypt.pi.rahulja.in` | Encrypted DNS Proxy |
| **Immich** | `10.8.1.6` | `immich.pi.rahulja.in` | Self-hosted Photo & Video Management |
| **Transmission** | `10.8.1.23` | `trans.pi.rahulja.in` | Torrent Client |
| **Paperless-ngx** | `10.8.1.32` | `pngx.pi.rahulja.in` | Document Management System |
| **Filebrowser** | `10.8.1.34` | `filebrowser.pi.rahulja.in` | Web-based File Manager |
| **Tailscale** | `10.8.1.48` | N/A | VPN Mesh Network |
| **Web Test** | `10.8.1.49` | `webtest.pi.rahulja.in` | Connectivity Test (Whoami) |
| **N8n** | `10.8.1.53` | `n8n.pi.rahulja.in` | Workflow Automation |
| **SearXNG** | `10.8.1.54` | `searxng.pi.rahulja.in` | Privacy-respecting Metasearch Engine |
| **Paisa** | `10.8.1.56` | `paisa.pi.rahulja.in` | Personal Finance Manager |
| **Homepage** | `10.8.1.57` | `homepage.pi.rahulja.in` | Modern Startpage |
| **Stirling-PDF** | `10.8.1.58` | `pdf.pi.rahulja.in` | Powerful PDF Manipulation Tools |

*Note: Immich auxiliary services (ML, Redis, DB) occupy IPs `10.8.1.8`, `10.8.1.9`, and `10.8.1.10` respectively.*

## ⚙️ Configuration

### Environment Variables
The setup relies heavily on environment variables for sensitive data and path configurations.
1.  Copy `example.env` to `.env`.
2.  Fill in the required fields, especially:
    -   `CLOUDFLARE_API_TOKEN` (for Caddy SSL)
    -   `TAILSCALE_AUTH_KEY` (for Tailscale connection)
    -   Data paths (defaulting to `/mnt/usb/...`)

### Networking
-   **Network Name:** `wg-easy`
-   **Subnet:** `10.8.1.0/24`
-   **Gateway:** `10.8.1.1` (Default Docker bridge gateway)

### Storage
Most heavy data (media, databases) is mapped to an external USB drive mounted at `/mnt/usb`. Ensure this mount point exists and has correct permissions, or update the `.env` file to point to your desired locations.

## 📦 Usage

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Prepare Environment:**
    ```bash
    cp example.env .env
    # Edit .env with your specific configuration
    nano .env
    ```

3.  **Start Services:**
    ```bash
    docker-compose up -d
    ```

4.  **Access Services:**
    Open your browser and navigate to the configured domains (e.g., `https://homepage.pi.rahulja.in`). Ensure your DNS (likely Pi-hole) is correctly pointing these domains to your Nginx/Caddy instance or that you have local host entries if testing offline.

## 📝 Notes

-   **Caddy & Tailscale:** Caddy is configured with `network_mode: service:tailscale`, sharing the Tailscale container's network namespace. This allows Caddy to seamlessly serve content over the Tailscale mesh network and resolve internal IPs on the `wg-easy` bridge.

-   **Internal DNS:** All application containers are configured with `dns: 10.8.1.48`, ensuring they use Pi-hole for both internal and external name resolution.

-   **Immich:** Requires a significant amount of RAM for machine learning tasks.

-   **Extended Documentation:** Detailed architecture diagrams in `.drawio` and `.svg` formats can be found in the `docs/` directory.
