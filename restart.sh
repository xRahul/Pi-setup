#!/bin/bash
set -e

# Always run from the directory containing this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Stopping all containers (core & lazy) ==="
docker compose --profile lazy down

echo "=== Creating containers (without starting) ==="
docker compose --profile lazy up --no-start

echo "=== Starting core services ==="
docker compose up -d

echo "=== Restart sequence completed successfully ==="
