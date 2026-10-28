# Sablier Setup & Configuration Reference

This document details how Sablier is configured, managed, and integrated into the home lab environment to enable "scale-to-zero" resources optimizations.

---

## 🚀 Architecture Overview
Sablier acts as a container-scale coordinator that stops or scales down inactive services, and starts them on demand when traffic arrives.
- **Reverse Proxy integration:** Caddy intercepts incoming traffic. If a container is stopped, Caddy calls Sablier to start it and optionally blocks or renders a loading page.
- **Provider:** Docker provider manages services via a secure read-only socket proxy (`socket-proxy-read` for read, with specific `ALLOW_START=1` and `ALLOW_STOP=1` capabilities enabled).

---

## 🏷️ Docker Instance Labels
Apply these labels directly to containers under the `labels:` section of `docker-compose.yml` to instruct Sablier how to manage them.

| Label | Value Example | Description |
| :--- | :--- | :--- |
| `sablier.enable` | `"true"` | Enroll container under Sablier management. |
| `sablier.group` | `"immich"` | Assign container to one or more groups (comma-separated). |
| `sablier.ready-after` | `"15s"` | Settling delay (Go duration) to wait after container becomes healthy before proxying traffic. |
| `sablier.ready-on-start` | `"true"` | Skip healthcheck; assume ready as soon as the start command is issued (useful for cache/database helpers). |
| `sablier.running-hours` | `"02:30-04:30"` | Daily keep-warm window in local time (`HH:MM-HH:MM`). Starts proactively and keeps container running. |
| `sablier.running-days` | `"Mon,Tue,Wed"` | Limit `running-hours` window to specific days. Defaults to everyday if unset. |

### Timezone Config
Timezone evaluations (for `running-hours`) utilize the local system timezone. The `sablier` service configuration in `docker-compose.yml` must include:
```yaml
environment:
  - TZ=${DEFAULT_TZ}
```

---

## 🛡️ Caddyfile Integration Directives
Sablier provides a Caddy plugin to manage routing on demand. There are two primary routing strategies:

### 1. Dynamic Strategy (For Browsers)
Serves a clean HTML loading screen (with auto-refresh) to browser users while the backend starts.
```caddy
sablier http://sablier:10000 {
    group <group_name>
    session_duration 1h
    dynamic {
        display_name "<Name>"
        theme hacker-terminal
    }
}
```

### 2. Blocking Strategy (For APIs, Cron, & Mobile Apps)
Blocks the HTTP request up to a timeout limit (e.g. `1m`), returning the actual JSON/HTTP response once the backend is ready. Avoids JSON parse crashes in mobile apps or wget/curl scripts.
```caddy
sablier http://sablier:10000 {
    group <group_name>
    session_duration 1h
    blocking {
        timeout 1m
    }
}
```

---

## 💡 Best Practices and Conventions

1. **API Matching:** Always split browser and API routing in the `Caddyfile` using path matchers (e.g., matching `/api/*` and `/server-info` to use the `blocking` strategy).
2. **Shared Containers:** For shared utilities (like Redis cache databases), specify multiple groups under `sablier.group` (e.g. `sablier.group=immich,firefly`). The container will start when either stack is active and stop when both are idle.
3. **Background Services:** For helper containers that aren't accessed directly via HTTP but must run (like Postgres, machine-learning, or cache containers), enroll them in the same `sablier.group` and specify `sablier.ready-on-start=true` if they don't serve direct traffic to Caddy.
4. **Daily Crons:** When scheduling containers that trigger crons (e.g. `firefly-cron` triggering at 3 AM), add `sablier.enable=true`, configure them under a dedicated cron group or the target group, and set `sablier.running-hours` to cover the cron execution window (e.g., `02:30-04:30`) to ensure both the cron runner and target app are awake.
