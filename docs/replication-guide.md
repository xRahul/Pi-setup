# Raspberry Pi 5 Homelab Replication Guide

This guide provides step-by-step instructions to replicate and deploy this entire containerized homelab onto a brand-new Raspberry Pi 5 from scratch.

---

## 📋 Hardware & System Requirements

- **Host Machine:** Raspberry Pi 5 (8GB RAM recommended).
- **Primary Storage (OS & Apps):** NVMe SSD (via M.2 HAT) running Debian 12 (Bookworm) or Debian 13 (Trixie) 64-bit.
- **Secondary Bulk Storage:** External USB 3.0 SSD/HDD formatted with `vfat` or `ext4` mounted at `/mnt/usb`.
- **Static LAN IP:** Dedicated IP reserved on your home router (e.g., `192.168.1.50`).
- **Network Accounts:**
  - **Tailscale:** Account with an active auth key (`tskey-auth-...`).
  - **Cloudflare:** Domain managing `pi.rahulja.in` with an API token granting `Zone:DNS:Edit` permissions.

---

## Step 1: Base OS & Docker Installation

On the fresh Raspberry Pi OS:

```bash
# 1. Update system packages
sudo apt update && sudo apt upgrade -y

# 2. Install essential packages
sudo apt install -y curl git ethtool iproute2 ca-certificates gnupg

# 3. Install official Docker Engine & Docker Compose plugin
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 4. Add your user to the docker group
sudo usermod -aG docker $USER
newgrp docker
```

---

## Step 2: Storage Structure Setup

The homelab splits data between fast NVMe storage and bulk media storage:

```bash
# 1. Create NVMe fast storage root
sudo mkdir -p /home/rahul/docker_data
sudo chown -R $USER:$USER /home/rahul/docker_data

# 2. Ensure bulk USB mount directory exists
sudo mkdir -p /mnt/usb

# 3. Mount external drive in /etc/fstab for persistence across reboots:
# (Replace UUID with your drive's UUID from `blkid`)
# UUID=xxxx-xxxx /mnt/usb vfat defaults,uid=1000,gid=1000,umask=0022,nofail 0 0
sudo mount -a
```

---

## Step 3: Clone Repository & Run Host Setup

Clone this repository into `/home/rahul/docker`:

```bash
cd /home/rahul
git clone <your-repo-url> docker
cd /home/rahul/docker

# Run the automated host setup script
# This installs:
# 1. /etc/systemd/system/rpi-tailscale-hairpin.service (Hairpin route 100.64.0.0/10 via 10.8.1.48)
# 2. /etc/systemd/system/rpi5-udp-gro.service (UDP GRO forwarding offload)
sudo bash scripts/setup-host.sh
```

---

## Step 4: Environment & Secrets Configuration

Initialize local runtime configuration from the provided templates:

```bash
# 1. Create .env from template
cp example.env .env

# 2. Create pihole.env from template
cp example_pihole.env pihole.env
```

Edit `.env` (`nano .env`) and supply:
- `CLOUDFLARE_API_TOKEN`: Your Cloudflare API Token for DNS-01 ACME wildcard challenges.
- `TAILSCALE_AUTH_KEY`: Pre-authenticated, reusable Tailscale key.
- Passwords and secrets for databases (`POSTGRES_PASSWORD`, `IMMICH_DB_PASSWORD`, `PAPERLESS_DB_PASS`, etc.).
- Ensure volume paths point to `/home/rahul/docker_data/...` and `/mnt/usb/...`.

---

## Step 5: Build Caddy & Initialize Network

Caddy requires a custom build with the Cloudflare DNS-01 and Sablier plugins:

```bash
# Build custom Caddy image locally
docker compose build caddy
```

---

## Step 6: Launch Stack

Start the core stack and pre-warm lazy service definitions:

```bash
# Use the automated restart script:
# 1. Pulls/creates lazy services without running them.
# 2. Starts core infrastructure (Tailscale, Caddy, Pi-hole, DNSCrypt, Sablier, Homepage).
bash restart.sh
```

---

## Step 7: Post-Launch Verification

Run automated validation checks:

```bash
# 1. Verify Compose syntax & variable interpolation
docker compose config --quiet

# 2. Run repository configuration audit
./scripts/audit-config.sh

# 3. Validate Caddyfile within the running container
docker exec caddy caddy validate --config /etc/caddy/Caddyfile

# 4. Check container health status
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Smoke Tests:
1. **DNS Resolution:** On a client connected to Tailscale, ping `dash.pi.rahulja.in` -> should resolve to Tailscale IP `100.109.192.17`.
2. **Dashboard:** Open `https://dash.pi.rahulja.in` in your browser. Verify the wildcard SSL certificate (`CN=*.pi.rahulja.in`).
3. **Scale-to-Zero Awakening:** Open `https://immich.pi.rahulja.in` -> Sablier will display a loading screen, boot the Immich stack, and redirect when healthy.
4. **Hairpin Verification:** From inside the Homepage container, test connection back through Caddy:
   ```bash
   docker exec homepage nc -zv -w 2 100.109.192.17 443
   ```
   Should report `open`.
