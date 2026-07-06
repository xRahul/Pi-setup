#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required for audit-config.sh", file=sys.stderr)
    sys.exit(2)

errors = []
warnings = []

SECRET_RUNTIME_PATTERNS = [
    re.compile(r"(^|/)\.env$"),
    re.compile(r"(^|/)pihole\.env(\.bak)?$"),
    re.compile(r"(^|/)pihole-db/"),
    re.compile(r"(^|/).*\.(db|db-wal|db-shm)$"),
    re.compile(r"(^|/).*\.key$"),
]


def read_text(path):
    try:
        return Path(path).read_text(errors="ignore")
    except FileNotFoundError:
        return ""


def env_keys(path):
    keys = set()
    for line in read_text(path).splitlines():
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if match:
            keys.add(match.group(1))
    return keys


def env_values(path):
    values = {}
    for line in read_text(path).splitlines():
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
        if match:
            values[match.group(1)] = match.group(2).strip().strip("'\"")
    return values


def caddy_site_blocks(path):
    text = read_text(path)
    blocks = []
    pattern = re.compile(r"(?m)^([A-Za-z0-9_.-]+\.pi\.rahulja\.in)\s*\{")
    for match in pattern.finditer(text):
        start = match.end()
        depth = 1
        index = start
        while index < len(text) and depth:
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
            index += 1
        body = text[start:index - 1]
        blocks.append({
            "domain": match.group(1),
            "upstreams": re.findall(r"reverse_proxy\s+\*\s+([^\s{]+)", body),
            "groups": sorted(set(re.findall(r"group\s+([A-Za-z0-9_-]+)", body))),
        })
    return blocks


def service_ip(service):
    networks = service.get("networks")
    if isinstance(networks, dict):
        for value in networks.values():
            if isinstance(value, dict) and value.get("ipv4_address"):
                return str(value["ipv4_address"])
    return ""


def sablier_groups(service):
    groups = []
    for label in service.get("labels") or []:
        if isinstance(label, str) and label.startswith("sablier.group="):
            groups.extend(item.strip() for item in label.split("=", 1)[1].split(","))
    return [group for group in groups if group]


compose_text = read_text("docker-compose.yml")
compose = yaml.safe_load(compose_text)
services = compose.get("services") or {}
compose_vars = set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::[-?][^}]*)?\}", compose_text))

for env_file in [".env", "example.env"]:
    missing = sorted(compose_vars - env_keys(env_file))
    if missing:
        errors.append(f"{env_file} missing compose variables: {', '.join(missing)}")

for service_specific in ["example_immich.env", "example_pihole.env"]:
    if Path(service_specific).exists():
        print(f"INFO: {service_specific} treated as service-specific, not full-stack mirror")

ip_to_services = {}
for name, service in services.items():
    ip = service_ip(service)
    if ip:
        ip_to_services.setdefault(ip, []).append(name)
for ip, names in sorted(ip_to_services.items()):
    if len(names) > 1:
        errors.append(f"duplicate static IP {ip}: {', '.join(names)}")

caddy_blocks = caddy_site_blocks("Caddyfile")
caddy_groups = set()
for block in caddy_blocks:
    caddy_groups.update(block["groups"])

label_groups = set()
for service in services.values():
    label_groups.update(sablier_groups(service))

public_helper_groups = {"firefly-cron"}
missing_caddy_groups = sorted(label_groups - caddy_groups - public_helper_groups)
if missing_caddy_groups:
    warnings.append("Sablier label groups not found in Caddy routes: " + ", ".join(missing_caddy_groups))

tracked = subprocess.run(["git", "ls-files"], check=True, text=True, capture_output=True).stdout.splitlines()
tracked_sensitive = [
    path for path in tracked
    if any(pattern.search(path) for pattern in SECRET_RUNTIME_PATTERNS)
    and not path.startswith("example")
]
if tracked_sensitive:
    errors.append("tracked secret/runtime files: " + ", ".join(tracked_sensitive))

homepage_path = env_values(".env").get("HOMEPAGE_CONFIG_PATH", "")
homepage_services = []
if homepage_path and Path(homepage_path).is_dir():
    for candidate in ["services.yaml", "services.yml"]:
        path = Path(homepage_path) / candidate
        if path.exists():
            homepage_text = path.read_text()
            if "type: caddy" in homepage_text and "admin localhost:2019" in read_text("Caddyfile"):
                warnings.append("Homepage Caddy widget is configured, but Caddy admin is localhost-only")
            data = yaml.safe_load(path.read_text()) or []
            for group in data:
                if isinstance(group, dict):
                    for entries in group.values():
                        if isinstance(entries, list):
                            for entry in entries:
                                if isinstance(entry, dict):
                                    homepage_services.extend(entry.keys())
            break
else:
    warnings.append("HOMEPAGE_CONFIG_PATH is not readable or not present")

pihole_hosts = []
if Path("pihole.env").exists():
    value = env_values("pihole.env").get("FTLCONF_dns_hosts", "")
    pihole_hosts = re.findall(r"\b([A-Za-z0-9_.-]+\.pi\.rahulja\.in)\b", value)
    caddy_domains = {block["domain"] for block in caddy_blocks}
    missing_dns = sorted(caddy_domains - set(pihole_hosts))
    if missing_dns:
        warnings.append("Caddy domains missing from pihole.env FTLCONF_dns_hosts: " + ", ".join(missing_dns))

print("== Compose services ==")
for name, service in services.items():
    print(
        f"{name}: ip={service_ip(service) or '-'} "
        f"profiles={','.join(service.get('profiles') or []) or '-'} "
        f"healthcheck={'yes' if 'healthcheck' in service else 'no'} "
        f"sablier={','.join(sablier_groups(service)) or '-'}"
    )

print("\n== Caddy routes ==")
for block in caddy_blocks:
    print(
        f"{block['domain']}: upstreams={','.join(block['upstreams']) or '-'} "
        f"sablier={','.join(block['groups']) or '-'}"
    )

print("\n== Homepage ==")
if homepage_services:
    print("services=" + ", ".join(homepage_services))
else:
    print("services=unavailable")

print("\n== Pi-hole local DNS ==")
if pihole_hosts:
    print("hosts=" + ", ".join(pihole_hosts))
else:
    print("hosts=unavailable")

if warnings:
    print("\n== Warnings ==")
    for warning in warnings:
        print("WARN: " + warning)

if errors:
    print("\n== Errors ==")
    for error in errors:
        print("ERROR: " + error)
    sys.exit(1)

print("\nAudit passed")
PY
