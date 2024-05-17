# Raspberry Pi setup

## Architecture

<img src="docs/Pi-Setup-Arch.drawio.svg" />

## How it works
1. Setup cloudflare API token
    1. Log in to Cloudflare and go to the domain you want to enable Caddy for.On the right, you'll see a section with the "API" header. Click "Get your API token": Get your API token
    2. Under the API tokens block, click "Create Token": User API tokens
    3. On the "User API Tokens" page, scroll to the bottom and press "Get started" in the Create Custom Token section: Get your API token
    4. Give your token a descriptive name, and add 2 permissions:
        Zone - Zone - Read
        Zone - DNS - Edit API Token settings
    5. Click "Continue to summary" and you should now see your API token.
2. Run `docker compose up --pull "always"  --build -d`
3. Setup pihole
    1. Settings > DNS: Set custom DNS: 10.8.1.4#5053 and Permit all origins
    2. Setup Local DNS > DNS Records with URLs to Pi host IP
4. Setup DDNS to your router & expose WG port from router to be accessible via DDNS
5. Setup & connect from a client via Wireguard

### Data Flow

1. Client uses DDNS url to connect to wireguard VPN. When connected, client is virtually sitting in same docker network that wg-easy & others are in.
2. Client tries to open an external website:
    1. Client tries to resolve DNS through wg-easy vpn. wg-easy calls pihole for dns resolution.
    2. pihole runs block scripts, then calls cloudflared-dns for dns resolution.
    3. cloudflared-dns calls 1.1.1.1 over DoH for DNS resolution.
    4. After DNS resolution, wg-easy works as vpn to pass the requested data from the URL.
3. Client opens internal website, like pihole web interface:
    1. Client tries to resolve DNS through wg-easy vpn. wg-easy calls pihole for dns resolution.
    2. pihole runs block scripts, and finds the local DNS added for this internal URL. It returns pi's local network IP (192.168.1.xxx)
    3. Client tries to call the Pi IP with 443 (HTTPS) and URL
    4. Pi has caddy from docker mapped to 443 port of itself, so request to internal URL is reverse proxied by caddy along with TLS resolution.
    5. request flow:
        * client(wg vpn connected) >>
        * internet >>
        * ddns resolution >>
        * router >>
        * Pi >>
        * Wireguard(with pihole dns resolution) >>
        * Pi >>
        * caddy >>
        * internal_service (on docker network)
