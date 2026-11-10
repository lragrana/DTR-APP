#!/bin/sh
# Start the app again after a reboot or 'docker compose down'.
# Vault seals itself on every restart, so this unseals it and restarts the backend.
set -e
cd "$(dirname "$0")/.."

docker compose up -d
sh scripts/vault-unseal.sh
docker compose restart backend

echo ""
echo "Up. Open  https://localhost"
